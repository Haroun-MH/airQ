"""Transformation and quality rules for OpenAQ measurements."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from airq.extract import Sensor

ALLOWED_PARAMETERS = {"pm10", "pm25", "no2", "o3", "so2", "co", "nox"}
MAX_PLAUSIBLE_VALUE = 10_000.0


@dataclass(frozen=True)
class Observation:
    """One normalized, idempotent air-quality observation."""

    observation_id: str
    location_id: int
    sensor_id: int
    location_name: str
    locality: str | None
    country_code: str | None
    latitude: float | None
    longitude: float | None
    parameter: str
    units: str
    value: float
    measured_at: datetime
    measured_at_local: str | None
    source: str = "openaq"
    ingested_at: datetime | None = None


def normalize_measurements(
    sensor: Sensor, measurements: list[dict[str, Any]], ingested_at: datetime | None = None
) -> tuple[list[Observation], list[dict[str, Any]]]:
    """Normalize API measurements and separate valid rows from rejected rows."""

    clean: list[Observation] = []
    rejected: list[dict[str, Any]] = []
    loaded_at = (ingested_at or datetime.now(UTC)).astimezone(UTC)

    for raw in measurements:
        try:
            observation = _normalize_one(sensor, raw, loaded_at)
        except (TypeError, ValueError, KeyError) as error:
            rejected.append(
                {
                    "sensor_id": sensor.sensor_id,
                    "parameter": sensor.parameter,
                    "reason": "invalid_measurement",
                    "detail": str(error),
                    "raw": raw,
                }
            )
            continue
        clean.append(observation)

    # A repeated API row must not create a second observation.
    deduplicated: dict[str, Observation] = {}
    for observation in clean:
        deduplicated[observation.observation_id] = observation
    return list(deduplicated.values()), rejected


def _normalize_one(
    sensor: Sensor, raw: dict[str, Any], ingested_at: datetime
) -> Observation:
    value = _as_float(raw.get("value"))
    if value is None:
        raise ValueError("missing numeric value")
    if value < 0:
        raise ValueError("negative value")
    if value > MAX_PLAUSIBLE_VALUE:
        raise ValueError("value exceeds plausibility limit")

    period = raw.get("period") or {}
    datetime_from = period.get("datetimeFrom") or {}
    measured_at = _parse_datetime(datetime_from.get("utc"))
    measured_at_local = _optional_string(datetime_from.get("local"))

    parameter = str((raw.get("parameter") or {}).get("name") or sensor.parameter).strip().lower()
    if parameter not in ALLOWED_PARAMETERS:
        raise ValueError(f"unsupported parameter: {parameter}")

    observation_id = _observation_id(sensor.sensor_id, parameter, measured_at)
    return Observation(
        observation_id=observation_id,
        location_id=sensor.location_id,
        sensor_id=sensor.sensor_id,
        location_name=sensor.location_name,
        locality=sensor.locality,
        country_code=sensor.country_code,
        latitude=sensor.latitude,
        longitude=sensor.longitude,
        parameter=parameter,
        units=sensor.units,
        value=value,
        measured_at=measured_at,
        measured_at_local=measured_at_local,
        ingested_at=ingested_at,
    )


def _observation_id(sensor_id: int, parameter: str, measured_at: datetime) -> str:
    business_key = f"{sensor_id}|{parameter}|{measured_at.isoformat()}"
    return hashlib.sha256(business_key.encode("utf-8")).hexdigest()


def _parse_datetime(value: Any) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("missing UTC measurement timestamp")
    text = value.strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
