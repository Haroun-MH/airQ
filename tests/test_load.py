"""Tests for idempotent DuckDB persistence."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from airq.extract import Sensor
from airq.load import connect, count_observations, upsert_observations
from airq.transform import normalize_measurements

FIXTURES = Path(__file__).parent / "fixtures"


def make_observations():
    sensor = Sensor(
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
    payload = json.loads((FIXTURES / "openaq_measurements.json").read_text(encoding="utf-8"))
    observations, _ = normalize_measurements(
        sensor,
        payload["results"],
        ingested_at=datetime(2026, 11, 16, 12, tzinfo=UTC),
    )
    return observations


def test_running_ingestion_twice_does_not_create_duplicates(tmp_path: Path):
    observations = make_observations()
    warehouse = tmp_path / "warehouse.duckdb"
    connection = connect(warehouse)
    try:
        first_inserted, first_updated = upsert_observations(connection, observations)
        first_count = count_observations(connection)

        second_inserted, second_updated = upsert_observations(connection, observations)
        second_count = count_observations(connection)
    finally:
        connection.close()

    assert first_inserted == 2
    assert first_updated == 0
    assert second_inserted == 0
    assert second_updated == 2
    assert first_count == second_count == 2


def test_observation_primary_key_prevents_duplicate_rows(tmp_path: Path):
    warehouse = tmp_path / "warehouse.duckdb"
    connection = connect(warehouse)
    try:
        upsert_observations(connection, make_observations())
        rows = connection.execute(
            "SELECT count(*), count(DISTINCT observation_id) "
            "FROM raw.openaq_measurements"
        ).fetchone()
    finally:
        connection.close()

    assert rows == (2, 2)
