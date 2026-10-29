"""Report processing must not freeze unrelated API requests or hide overload as 404."""
import asyncio
from threading import Event, Timer
from time import monotonic
from unittest.mock import patch

import httpx
import pytest

from app.api import health, industry_reports
from app.services import industry_reports as service
from tests.test_industry_inventory import stock, create
from tests.test_local_scan import env


def test_slow_report_build_keeps_health_responsive(stock):
    app = stock.env.app
    app.include_router(health.router, prefix='/api')
    started, release = Event(), Event()
    original = service.build

    def slow_build(*args):
        started.set()
        assert release.wait(3), 'report worker was not released'
        return original(*args)

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            before = monotonic()
            task = asyncio.create_task(client.post('/api/industry-reports', json={}))
            try:
                assert await asyncio.to_thread(started.wait, 2)
                response = await asyncio.wait_for(client.get('/api/health'), timeout=1)
                assert response.status_code == 200
                assert monotonic() - before < 1.5
                assert not task.done(), 'health must respond while report work remains blocked'
            finally:
                release.set()
                report = await task
            assert report.status_code == 201, report.text

    # A regression that runs build on the event loop must fail, not hang pytest.
    timer = Timer(2.5, release.set)
    timer.start()
    try:
        with patch.object(service, 'build', side_effect=slow_build):
            asyncio.run(exercise())
    finally:
        release.set()
        timer.cancel()


def test_overloaded_dynamic_report_returns_retryable_503(stock):
    report = create(stock, is_private=False, dynamic=True)
    slots = industry_reports._report_slots
    assert slots.acquire(blocking=False)
    assert slots.acquire(blocking=False)
    try:
        response = stock.env.client.get('/api/industry-reports/public/' + report['token'])
        assert response.status_code == 503
        assert response.headers['retry-after'] == '5'
        assert 'busy' in response.json()['detail']
        response = stock.env.client.post('/api/industry-reports', json={})
        assert response.status_code == 503
    finally:
        slots.release()
        slots.release()
    # A rejected generation must also release the per-user generation guard.
    assert stock.env.client.post('/api/industry-reports', json={}).status_code == 201
    assert stock.env.client.get('/api/industry-reports/public/' + report['token']).status_code == 200


def test_report_worker_exception_releases_capacity():
    def fail():
        raise ValueError('synthetic build failure')

    async def exercise():
        for _ in range(3):
            with pytest.raises(ValueError, match='synthetic build failure'):
                await industry_reports.report_work(fail)
        assert await industry_reports.report_work(lambda: 'recovered') == 'recovered'

    asyncio.run(exercise())
