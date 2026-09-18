import asyncio
import base64
import json
import time
import unittest
from unittest.mock import patch

import httpx
from fastapi import HTTPException

from app.services.esi_client import EsiClient, gather_esi
from app.services.esi_transport import Bucket, EsiTransport, close_esi_transport, get_esi_transport, identity


def token(character, expiry=1):
    claims = base64.urlsafe_b64encode(json.dumps({"azp": "eqm", "sub": f"CHARACTER:EVE:{character}", "exp": expiry}).encode()).decode().rstrip("=")
    return f"header.{claims}.signature"


class EsiTransportTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.transport = EsiTransport()
        await self.transport.client.aclose()

    async def asyncTearDown(self):
        await self.transport.close()
        await close_esi_transport()

    def mock(self, handler):
        self.transport.client = httpx.AsyncClient(base_url="https://esi.evetech.net/latest", transport=httpx.MockTransport(handler))

    async def request(self, path="/characters/1/skills/", bearer=None, method="GET"):
        return await self.transport.request(method, path, headers={"Authorization": f"Bearer {bearer or token(1)}"}, params={})

    async def test_shared_pool_keeps_concurrent_authorization_separate(self):
        seen, active, peak = [], 0, 0

        async def handler(request):
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            await asyncio.sleep(0.005)
            seen.append((request.url.path, request.headers.get("authorization")))
            active -= 1
            return httpx.Response(200, json={})

        self.mock(handler)
        with patch("app.services.esi_client.get_esi_transport", return_value=self.transport):
            await asyncio.gather(*(EsiClient(token(n)).get(f"/characters/{n}/skills/") for n in range(12)))
            await EsiClient().get("/status/")
        self.assertGreater(peak, 1)
        self.assertLessEqual(peak, 8)
        for path, authorization in seen[:-1]:
            self.assertEqual(authorization, "Bearer " + token(int(path.split("/")[3])))
        self.assertIsNone(seen[-1][1])
        self.assertNotIn("Authorization", self.transport.client.headers)

    async def test_server_cache_reused_but_never_crosses_character(self):
        calls = []
        def handler(request):
            calls.append(request)
            return httpx.Response(200, headers={"Cache-Control": "private, max-age=60", "Age": "2"}, json={"n": len(calls)})
        self.mock(handler)
        a = await self.request()
        b = await self.request()
        c = await self.request(bearer=token(2))
        self.assertEqual(a.json(), b.json())
        self.assertNotEqual(a.json(), c.json())
        self.assertEqual(len(calls), 2)
        await self.request(bearer=token(1, expiry=2))
        self.assertEqual(len(calls), 3)

    async def test_public_metadata_is_shared_between_characters(self):
        calls = []
        self.mock(lambda request: (calls.append(request), httpx.Response(200, headers={"Cache-Control": "max-age=60"}, json={}))[1])
        await self.request("/universe/categories/16/", bearer=token(1))
        await self.request("/universe/categories/16/", bearer=token(2))
        self.assertEqual(len(calls), 1)

    async def test_no_cache_and_expired_age_refetch(self):
        for headers in ({"Cache-Control": "no-store, max-age=60"}, {"Cache-Control": "max-age=2", "Age": "3"}, {"Cache-Control": "no-cache, max-age=60"}):
            calls = []
            self.mock(lambda request: (calls.append(request), httpx.Response(200, headers=headers, json={}))[1])
            await self.request()
            await self.request()
            self.assertEqual(len(calls), 2)
            await self.transport.client.aclose()

    async def test_cookies_are_not_sent_to_other_characters(self):
        seen = []
        def handler(request):
            seen.append(request.headers.get("cookie"))
            return httpx.Response(200, headers={"Set-Cookie": "secret=one; Path=/"}, json={})
        self.mock(handler)
        await self.request()
        await self.request(bearer=token(2))
        self.assertEqual(seen, [None, None])

    async def test_read_retries_429_after_server_delay(self):
        calls = []
        def handler(request):
            calls.append(request)
            return httpx.Response(429, headers={"Retry-After": "0"}, json={}) if len(calls) == 1 else httpx.Response(200, json={})
        self.mock(handler)
        start = time.monotonic()
        response = await self.request()
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(time.monotonic() - start, 0.1)
        self.assertEqual(len(calls), 2)

    async def test_writes_never_automatically_retried(self):
        calls = []
        self.mock(lambda request: (calls.append(request), httpx.Response(503, json={}))[1])
        self.assertEqual((await self.request(method="POST")).status_code, 503)
        self.assertEqual(len(calls), 1)

    async def test_retry_count_is_bounded(self):
        calls = []
        self.mock(lambda request: (calls.append(request), httpx.Response(503, headers={"Retry-After": "0"}, json={}))[1])
        self.assertEqual((await self.request()).status_code, 503)
        self.assertEqual(len(calls), 3)

    async def test_refreshes_share_identity_and_other_characters_do_not(self):
        self.assertEqual(identity(token(1)), identity(token(1, 123)))
        self.assertNotEqual(identity(token(1)), identity(token(2)))

    async def test_shared_group_headers_reserve_five_percent(self):
        now = time.monotonic()
        bucket = Bucket(remaining=7, limit=100, window=60, reset=now + 60)
        self.transport.groups.update({"one": "skills", "two": "skills"})
        self.transport.buckets[("skills", "pilot")] = bucket
        self.assertIs(await self.transport.admit("one", "pilot"), bucket)
        # Second in-flight request would cross the five-token reserve.
        with self.assertRaises(TimeoutError):
            await asyncio.wait_for(self.transport.admit("two", "pilot"), 0.02)
        self.assertEqual(bucket.inflight, 1)
        # Another character's bucket remains available.
        other = await self.transport.admit("two", "other")
        self.assertIsNot(other, bucket)

    async def test_global_error_budget_stops_other_routes(self):
        admitted = await self.transport.admit("one", "pilot")
        await self.transport.observe("one", "pilot", admitted, httpx.Response(200, headers={"X-ESI-Error-Limit-Remain": "5", "X-ESI-Error-Limit-Reset": "60"}))
        with self.assertRaises(TimeoutError):
            await asyncio.wait_for(self.transport.admit("two", "other"), 0.02)

    async def test_out_of_order_headers_cannot_increase_budget(self):
        self.transport.groups["route"] = "group"
        bucket = Bucket(remaining=20, limit=100, reset=time.monotonic() + 60, inflight=1)
        self.transport.buckets[("group", "pilot")] = bucket
        await self.transport.observe("route", "pilot", bucket, httpx.Response(200, headers={"X-Ratelimit-Group": "group", "X-Ratelimit-Limit": "100/1m", "X-Ratelimit-Remaining": "24"}))
        self.assertEqual(bucket.remaining, 20)

    async def test_cancelled_request_releases_reservation(self):
        async def handler(request):
            await asyncio.sleep(20)
        self.mock(handler)
        with self.assertRaises(TimeoutError):
            await asyncio.wait_for(self.request(), 0.02)
        self.assertTrue(all(bucket.inflight == 0 for bucket in self.transport.buckets.values()))

    async def test_lifecycle_reuses_then_closes_pool(self):
        pool = get_esi_transport()
        self.assertIs(get_esi_transport(), pool)
        await EsiClient(token(1)).close()  # facade must not close others' pool
        self.assertFalse(pool.client.is_closed)
        await close_esi_transport()
        self.assertTrue(pool.client.is_closed)

    async def test_parallel_fetch_failure_keeps_http_detail_and_joins_siblings(self):
        stopped = asyncio.Event()
        async def failing():
            await asyncio.sleep(0.01)
            raise HTTPException(403, "missing scope")
        async def sibling():
            try:
                await asyncio.sleep(20)
            finally:
                stopped.set()
        with self.assertRaises(HTTPException) as error:
            await gather_esi(failing(), sibling())
        self.assertEqual(error.exception.detail, "missing scope")
        self.assertTrue(stopped.is_set())

    async def test_expired_cache_entry_refetches(self):
        calls = []
        self.mock(lambda request: (calls.append(request), httpx.Response(200, headers={"Cache-Control": "max-age=60"}, json={}))[1])
        await self.request()
        key = next(iter(self.transport.cache))
        self.transport.cache[key] = (0, self.transport.cache[key][1])
        await self.request()
        self.assertEqual(len(calls), 2)

    async def test_420_blocks_all_local_characters_and_routes(self):
        admitted = await self.transport.admit("one", "pilot")
        await self.transport.observe("one", "pilot", admitted, httpx.Response(420, headers={"Retry-After": "60"}))
        with self.assertRaises(TimeoutError):
            await asyncio.wait_for(self.transport.admit("two", "other"), 0.02)


if __name__ == "__main__":
    unittest.main()
