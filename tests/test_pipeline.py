"""Tests for the end-to-end pipeline orchestration using fake HTTP responses."""

from __future__ import annotations

import json
from pathlib import Path

from airq.config import Settings
from airq.pipeline import run

FIXTURES = Path(__file__).parent / "fixtures"


class FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200):
        self.payload = payload
        self.status_code = status_code
        self.ok = 200 <= status_code < 300
        self.text = json.dumps(payload)
        self.headers: dict[str, str] = {}

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self):
        self.headers: dict[str, str] = {}

    def get(self, url: str, params: dict | None = None, timeout: float = 0):
        if url.endswith("/locations/2178"):
            return FakeResponse(
                json.loads((FIXTURES / "openaq_location.json").read_text(encoding="utf-8"))
            )
        if url.endswith("/locations/2178/sensors"):
            location = json.loads(
                (FIXTURES / "openaq_location.json").read_text(encoding="utf-8")
            )
            return FakeResponse({"results": location["results"][0]["sensors"]})
        if url.endswith("/sensors/3920/measurements"):
            return FakeResponse(
                json.loads(
                    (FIXTURES / "openaq_measurements.json").read_text(encoding="utf-8")
                )
            )
        raise AssertionError(f"Unexpected URL: {url}")


def test_pipeline_is_idempotent(monkeypatch, tmp_path: Path):
    from airq import extract

    def fake_init(self, *args, **kwargs):
        self.api_key = kwargs.get("api_key", "")
        self.base_url = kwargs.get("base_url", "")
        self.timeout = 30.0
        self.retries = 3
        self.session = FakeSession()

    monkeypatch.setattr(extract.OpenAQClient, "__init__", fake_init)
    settings = Settings(
        openaq_api_key="secret",
        duckdb_path=tmp_path / "warehouse.duckdb",
        location_ids=(2178,),
        country_code="US",
    )

    first = run(settings)
    second = run(settings)

    assert first["warehouse_rows"] == 2
    assert second["warehouse_rows"] == 2
    assert second["inserted"] == 0
    assert second["updated"] == 2
