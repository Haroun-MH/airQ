"""Tests for OpenAQ response normalization and idempotent business keys."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from airq.extract import Sensor
from airq.transform import normalize_measurements

FIXTURES = Path(__file__).parent / "fixtures"


def make_sensor() -> Sensor:
    return Sensor(
        sensor_id=3920,
        location_id=2178,
        location_name="Del Norte",
        locality="Albuquerque",
        country_code="US",
        latitude=35.1353,
        longitude=-106.584702,
        parameter="pm25",
        units="µg/m³",
    )


def read_measurements() -> list[dict]:
    return json.loads((FIXTURES / "openaq_measurements.json").read_text(encoding="utf-8"))[
        "results"
    ]


def test_normalize_measurements_preserves_valid_rows():
    observations, rejected = normalize_measurements(make_sensor(), read_measurements())

    assert len(observations) == 2
    assert rejected == []
    assert observations[0].value == 12.4
    assert observations[0].measured_at == datetime(2026, 11, 16, 8, tzinfo=UTC)
    assert observations[0].location_name == "Del Norte"


def test_duplicate_api_rows_are_deduplicated():
    measurements = read_measurements()
    observations, rejected = normalize_measurements(
        make_sensor(), measurements + [measurements[0]]
    )

    assert len(observations) == 2
    assert rejected == []
    assert len({observation.observation_id for observation in observations}) == 2


def test_negative_measurement_is_rejected():
    measurements = read_measurements()
    measurements[0]["value"] = -1

    observations, rejected = normalize_measurements(make_sensor(), measurements)

    assert len(observations) == 1
    assert rejected[0]["reason"] == "invalid_measurement"
    assert "negative value" in rejected[0]["detail"]


def test_missing_timestamp_is_rejected():
    measurements = read_measurements()
    measurements[0]["period"]["datetimeFrom"]["utc"] = None

    observations, rejected = normalize_measurements(make_sensor(), measurements)

    assert len(observations) == 1
    assert rejected[0]["reason"] == "invalid_measurement"
