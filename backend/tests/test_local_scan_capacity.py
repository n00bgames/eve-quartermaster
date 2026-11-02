"""Capacity boundaries with synthetic pilots and no upstream requests."""
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from app.api import local_scan
from app.api.dscan import DScanInput
from app.services import local_scan as service
from tests.test_local_scan import env


def pilot_names(count):
    return ["X" * 94 + f"{i:06d}" for i in range(count)]


@pytest.mark.parametrize("count", [2001, 4999, 9999])
def test_accepts_large_local_lists_and_deduplicates(count):
    names = pilot_names(count)
    text = "\r\n".join([*names, names[0].lower()])
    assert service.parse_local(text) == names
    assert local_scan.ScanInput(text=text).text == text
    assert DScanInput(text="dscan", local_text=text).local_text == text


def test_rejects_10000_unique_pilots_with_updated_error():
    with pytest.raises(ValueError, match="at most 9,999 unique pilots"):
        service.parse_local("\n".join(pilot_names(10000)))


@pytest.mark.parametrize("model,fields", [
    (local_scan.ScanInput, {}),
    (DScanInput, {"text": "dscan"}),
])
def test_retains_a_bounded_local_text_size(model, fields):
    field = "local_text" if fields else "text"
    with pytest.raises(ValidationError):
        model(**fields, **{field: "X" * 1200001})


def test_api_generates_and_reopens_9999_pilots_without_truncation(env):
    class LargeSource:
        def __init__(self):
            self.calls = []

        async def resolve(self, names):
            self.calls.append(("resolve", len(names)))
            return {"characters": [{"id": 100000 + int(n[-6:]), "name": n} for n in names]}

        async def affiliations(self, ids):
            self.calls.append(("affiliations", len(ids)))
            return [{"character_id": i, "corporation_id": 101} for i in ids]

        async def names(self, ids):
            self.calls.append(("names", len(ids)))
            return [{"id": 101, "name": "Example Corp", "category": "corporation"}]

        async def close(self):
            pass

    names = pilot_names(9999)
    text = "\r\n".join(names)
    assert len(text) > 600000
    assert env.client.get("/api/local-scans/context").json()["max_pilots"] == 9999
    source = LargeSource()
    with patch.object(local_scan, "source_factory", return_value=source) as factory:
        response = env.client.post("/api/local-scans", json={"text": text})
        assert response.status_code == 201, response.text
        report = response.json()
        assert report["input_count"] == report["character_count"] == 9999
        assert {p["name"] for p in report["pilots"]} == set(names)
        assert report["unresolved"] == [] and report["warnings"] == []
        saved = env.client.get("/api/local-scans/reports/" + report["token"])
        assert saved.status_code == 200
        assert saved.json()["pilots"] == report["pilots"]
        public = env.client.get("/api/local-scans/public/" + report["token"])
        assert public.status_code == 200
        assert public.json()["pilots"] == report["pilots"]
        assert max(size for _, size in source.calls) == 250
        assert sum(kind == "resolve" for kind, _ in source.calls) == 40
        assert sum(kind == "affiliations" for kind, _ in source.calls) == 40
        rejected = env.client.post("/api/local-scans", json={"text": text + "\nOne More Pilot"})
        assert rejected.status_code == 422
        assert rejected.json()["detail"] == "A local scan supports at most 9,999 unique pilots."
        assert factory.call_count == 1
