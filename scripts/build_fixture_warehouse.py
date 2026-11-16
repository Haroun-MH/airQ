"""Build a deterministic DuckDB warehouse for CI contract and dbt checks."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path

from airq.extract import Sensor
from airq.load import connect, upsert_observations
from airq.transform import normalize_measurements

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "openaq_measurements.json"


def main() -> None:
    warehouse_path = Path(
        os.getenv("AIRQ_DUCKDB_PATH", str(ROOT / "warehouse.duckdb"))
    ).resolve()
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
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
    observations, rejected = normalize_measurements(
        sensor,
        payload["results"],
        ingested_at=datetime(2026, 11, 16, 12, tzinfo=UTC),
    )
    if rejected:
        raise RuntimeError(f"Fixture contains rejected measurements: {rejected}")

    connection = connect(warehouse_path)
    try:
        inserted, updated = upsert_observations(connection, observations)
    finally:
        connection.close()
    print(f"Fixture warehouse: {warehouse_path} ({inserted} inserted, {updated} updated).")


if __name__ == "__main__":
    main()
