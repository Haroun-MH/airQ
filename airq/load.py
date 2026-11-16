"""DuckDB persistence for normalized air-quality observations."""

from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb

from airq.transform import Observation

RAW_TABLE = "raw.openaq_measurements"

CREATE_RAW_TABLE = """
CREATE SCHEMA IF NOT EXISTS raw;
CREATE TABLE IF NOT EXISTS raw.openaq_measurements (
    observation_id VARCHAR PRIMARY KEY,
    location_id BIGINT NOT NULL,
    sensor_id BIGINT NOT NULL,
    location_name VARCHAR NOT NULL,
    locality VARCHAR,
    country_code VARCHAR,
    latitude DOUBLE,
    longitude DOUBLE,
    parameter VARCHAR NOT NULL,
    units VARCHAR NOT NULL,
    value DOUBLE NOT NULL,
    measured_at TIMESTAMPTZ NOT NULL,
    measured_at_local VARCHAR,
    source VARCHAR NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL
);
"""


class DuckDBLoadError(RuntimeError):
    """Raised when observations cannot be safely persisted."""


def connect(warehouse_path: Path, read_only: bool = False) -> duckdb.DuckDBPyConnection:
    """Open the AirQ warehouse, creating its parent directory when needed."""

    if not read_only:
        warehouse_path.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(warehouse_path), read_only=read_only)


def ensure_raw_table(connection: duckdb.DuckDBPyConnection) -> None:
    """Create the raw table if it does not exist."""

    connection.execute(CREATE_RAW_TABLE)


def upsert_observations(
    connection: duckdb.DuckDBPyConnection, observations: list[Observation]
) -> tuple[int, int]:
    """Insert observations and update existing business keys.

    Returns ``(inserted, updated)``. Re-running the same extraction does not create
    duplicate rows and does not change the table's row count.
    """

    if not observations:
        return (0, 0)

    ensure_raw_table(connection)
    existing_keys = {
        row[0]
        for row in connection.execute(
            "SELECT observation_id FROM raw.openaq_measurements"
        ).fetchall()
    }

    inserted = 0
    updated = 0
    connection.execute("BEGIN TRANSACTION")
    try:
        for observation in observations:
            row = _as_dict(observation)
            if row["observation_id"] in existing_keys:
                connection.execute(
                    """
                    UPDATE raw.openaq_measurements
                    SET location_id = ?,
                        sensor_id = ?,
                        location_name = ?,
                        locality = ?,
                        country_code = ?,
                        latitude = ?,
                        longitude = ?,
                        parameter = ?,
                        units = ?,
                        value = ?,
                        measured_at = ?,
                        measured_at_local = ?,
                        source = ?,
                        ingested_at = ?
                    WHERE observation_id = ?
                    """,
                    [
                        row["location_id"],
                        row["sensor_id"],
                        row["location_name"],
                        row["locality"],
                        row["country_code"],
                        row["latitude"],
                        row["longitude"],
                        row["parameter"],
                        row["units"],
                        row["value"],
                        row["measured_at"],
                        row["measured_at_local"],
                        row["source"],
                        row["ingested_at"],
                        row["observation_id"],
                    ],
                )
                updated += 1
            else:
                connection.execute(
                    """
                    INSERT INTO raw.openaq_measurements (
                        observation_id,
                        location_id,
                        sensor_id,
                        location_name,
                        locality,
                        country_code,
                        latitude,
                        longitude,
                        parameter,
                        units,
                        value,
                        measured_at,
                        measured_at_local,
                        source,
                        ingested_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        row["observation_id"],
                        row["location_id"],
                        row["sensor_id"],
                        row["location_name"],
                        row["locality"],
                        row["country_code"],
                        row["latitude"],
                        row["longitude"],
                        row["parameter"],
                        row["units"],
                        row["value"],
                        row["measured_at"],
                        row["measured_at_local"],
                        row["source"],
                        row["ingested_at"],
                    ],
                )
                existing_keys.add(row["observation_id"])
                inserted += 1
        connection.execute("COMMIT")
    except Exception:
        connection.execute("ROLLBACK")
        raise
    return (inserted, updated)


def count_observations(connection: duckdb.DuckDBPyConnection) -> int:
    """Return the number of rows in the raw observations table."""

    table_exists = connection.execute(
        """
        SELECT count(*)
        FROM duckdb_tables()
        WHERE schema_name = 'raw' AND table_name = 'openaq_measurements'
        """
    ).fetchone()[0]
    if not table_exists:
        return 0
    return connection.execute("SELECT count(*) FROM raw.openaq_measurements").fetchone()[0]


def _as_dict(observation: Observation) -> dict[str, Any]:
    row = asdict(observation)
    row["measured_at"] = observation.measured_at.astimezone(UTC)
    row["ingested_at"] = (observation.ingested_at or datetime.now(UTC)).astimezone(UTC)
    return row
