"""AirQ extraction pipeline command."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from airq.config import Settings
from airq.extract import OpenAQClient, default_window, discover_sensors
from airq.load import connect, count_observations, ensure_raw_table, upsert_observations
from airq.transform import ALLOWED_PARAMETERS, normalize_measurements
from airq.validate import DataQualityError, validate_observations


def run(settings: Settings) -> dict[str, int]:
    """Extract OpenAQ measurements and idempotently upsert them into DuckDB."""

    client = OpenAQClient(
        api_key=settings.openaq_api_key,
        base_url=settings.openaq_base_url,
        timeout=settings.request_timeout_seconds,
        retries=settings.request_retries,
    )
    datetime_from, datetime_to = default_window(settings.history_days)
    sensors = discover_sensors(
        client,
        location_ids=settings.location_ids,
        country_code=settings.country_code,
        parameters=ALLOWED_PARAMETERS,
    )
    if not sensors:
        raise DataQualityError(
            "No OpenAQ sensors matched the configured locations/country and supported pollutants"
        )

    observations = []
    rejected_count = 0
    for sensor in sensors:
        measurements = client.get_measurements(
            sensor.sensor_id,
            datetime_from=datetime_from,
            datetime_to=datetime_to,
            max_pages=settings.max_pages,
        )
        normalized, rejected = normalize_measurements(
            sensor, measurements, ingested_at=datetime.now(UTC)
        )
        observations.extend(normalized)
        rejected_count += len(rejected)

    validation = validate_observations(observations)
    connection = connect(settings.duckdb_path)
    try:
        ensure_raw_table(connection)
        before = count_observations(connection)
        inserted, updated = upsert_observations(connection, observations)
        after = count_observations(connection)
    finally:
        connection.close()

    if after < before:
        raise DataQualityError("The number of persisted rows decreased unexpectedly")

    print(
        f"Fetched {len(observations)} valid observations from {len(sensors)} sensors; "
        f"rejected {rejected_count} invalid rows."
    )
    print(f"Inserted {inserted}, updated {updated}; warehouse rows: {after}.")
    print(
        f"Validation: {validation.total_rows - validation.invalid_rows}/"
        f"{validation.total_rows} rows passed ({validation.invalid_rate:.1%} invalid)."
    )
    return {
        "sensors": len(sensors),
        "observations": len(observations),
        "rejected": rejected_count,
        "inserted": inserted,
        "updated": updated,
        "warehouse_rows": after,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ingest OpenAQ observations into DuckDB")
    parser.add_argument(
        "--output-json",
        type=Path,
        help="Optional path where run metrics are written as JSON",
    )
    args = parser.parse_args(argv)

    try:
        settings = Settings.from_env()
        metrics = run(settings)
    except (DataQualityError, RuntimeError, ValueError) as error:
        print(f"PIPELINE STOPPED: {error}", file=sys.stderr)
        return 1

    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
