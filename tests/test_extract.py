"""Tests for OpenAQ HTTP extraction using a fake requests session."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import requests

from airq.extract import OpenAQClient, OpenAQError, discover_sensors

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
        self.calls: list[tuple[str, dict | None]] = []
        self.responses: dict[str, FakeResponse] = {}

    def get(self, url: str, params: dict | None = None, timeout: float = 0):
        self.calls.append((url, params))
        for suffix, response in self.responses.items():
            if url.endswith(suffix):
                return response
        raise AssertionError(f"Unexpected URL: {url}")


def make_client() -> tuple[OpenAQClient, FakeSession]:
    session = FakeSession()
    client = OpenAQClient("secret-key", session=session)
    return client, session


def test_discover_sensors_combines_location_and_sensor_metadata():
    client, session = make_client()
    location_payload = json.loads((FIXTURES / "openaq_location.json").read_text(encoding="utf-8"))
    sensor_payload = {"results": location_payload["results"][0]["sensors"]}
    session.responses["/locations/2178"] = FakeResponse(location_payload)
    session.responses["/locations/2178/sensors"] = FakeResponse(sensor_payload)

    sensors = discover_sensors(client, (2178,), "US")

    assert len(sensors) == 1
    assert sensors[0].sensor_id == 3920
    assert sensors[0].location_name == "Del Norte"
    assert sensors[0].parameter == "pm25"
    assert session.headers["X-API-Key"] == "secret-key"


def test_get_measurements_uses_bounded_time_window_and_pagination():
    client, session = make_client()
    session.responses["/sensors/3920/measurements"] = FakeResponse({"results": []})

    client.get_measurements(
        3920,
        datetime_from=datetime(2026, 11, 1, tzinfo=UTC),
        datetime_to=datetime(2026, 11, 16, tzinfo=UTC),
    )

    url, params = session.calls[0]
    assert url.endswith("/sensors/3920/measurements")
    assert params["datetime_from"] == "2026-11-01T00:00:00Z"
    assert params["datetime_to"] == "2026-11-16T00:00:00Z"
    assert params["page"] == 1


def test_http_error_is_not_silently_ignored():
    client, session = make_client()
    session.responses["/locations/2178"] = FakeResponse({"detail": "nope"}, status_code=401)

    try:
        client.list_locations((2178,), "US")
    except OpenAQError as error:
        assert "HTTP 401" in str(error)
    else:
        raise AssertionError("Expected OpenAQError")


def test_real_session_type_is_accepted():
    session = requests.Session()
    client = OpenAQClient("secret-key", session=session)
    assert client.session.headers["X-API-Key"] == "secret-key"
