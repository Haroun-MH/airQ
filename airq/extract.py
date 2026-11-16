"""Extraction layer for OpenAQ v3.

The extractor follows the API hierarchy documented by OpenAQ:

1. discover locations;
2. discover the sensors belonging to each location;
3. fetch measurements for each sensor over a bounded time window.

No HTTP code is mixed with transformation or persistence logic.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import requests


class OpenAQError(RuntimeError):
    """Raised when OpenAQ cannot provide a valid response."""


@dataclass(frozen=True)
class Sensor:
    """A sensor discovered at an OpenAQ monitoring location."""

    sensor_id: int
    location_id: int
    location_name: str
    locality: str | None
    country_code: str | None
    latitude: float | None
    longitude: float | None
    parameter: str
    units: str


class OpenAQClient:
    """Small HTTP client for the OpenAQ v3 API."""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.openaq.org/v3",
        timeout: float = 30.0,
        retries: int = 3,
        session: requests.Session | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.retries = retries
        self.session = session or requests.Session()
        self.session.headers.update({"X-API-Key": api_key, "Accept": "application/json"})

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self.base_url}/{path.lstrip('/')}"
        for attempt in range(self.retries + 1):
            try:
                response = self.session.get(url, params=params, timeout=self.timeout)
            except requests.RequestException as error:
                if attempt >= self.retries:
                    raise OpenAQError(f"Request to {path} failed: {error}") from error
                time.sleep(2**attempt)
                continue

            if response.status_code == 429 and attempt < self.retries:
                retry_after = _retry_after_seconds(response)
                time.sleep(retry_after)
                continue
            if not response.ok:
                body = _safe_response_body(response)
                raise OpenAQError(
                    f"OpenAQ returned HTTP {response.status_code} for {path}: {body}"
                )

            try:
                payload = response.json()
            except ValueError as error:
                raise OpenAQError(f"OpenAQ returned invalid JSON for {path}") from error
            if not isinstance(payload, dict):
                raise OpenAQError(f"OpenAQ returned an unexpected payload for {path}")
            return payload

        raise OpenAQError(f"Request to {path} exhausted all retries")

    def list_locations(
        self,
        location_ids: tuple[int, ...] = (),
        country_code: str = "MA",
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Return locations, either by explicit IDs or by ISO country code."""

        locations: list[dict[str, Any]] = []
        if location_ids:
            for location_id in location_ids:
                payload = self._get(f"/locations/{location_id}")
                locations.extend(_results(payload))
            return locations

        page = 1
        while True:
            payload = self._get(
                "/locations",
                {
                    "iso": country_code,
                    "limit": limit,
                    "page": page,
                    "order_by": "id",
                    "sort_order": "asc",
                },
            )
            page_results = _results(payload)
            locations.extend(page_results)
            if len(page_results) < limit:
                break
            page += 1
        return locations

    def list_sensors(self, location_id: int) -> list[dict[str, Any]]:
        """Return sensor metadata for one location."""

        payload = self._get(f"/locations/{location_id}/sensors")
        return _results(payload)

    def get_measurements(
        self,
        sensor_id: int,
        datetime_from: datetime,
        datetime_to: datetime,
        limit: int = 1000,
        max_pages: int = 10,
    ) -> list[dict[str, Any]]:
        """Fetch raw measurements for one sensor, following pagination."""

        measurements: list[dict[str, Any]] = []
        for page in range(1, max_pages + 1):
            payload = self._get(
                f"/sensors/{sensor_id}/measurements",
                {
                    "datetime_from": _api_datetime(datetime_from),
                    "datetime_to": _api_datetime(datetime_to),
                    "limit": limit,
                    "page": page,
                },
            )
            page_results = _results(payload)
            measurements.extend(page_results)
            if len(page_results) < limit:
                break
        return measurements


def discover_sensors(
    client: OpenAQClient,
    location_ids: tuple[int, ...],
    country_code: str,
    parameters: set[str] | None = None,
) -> list[Sensor]:
    """Discover sensors and retain their parent location metadata."""

    locations = client.list_locations(location_ids, country_code)
    sensors: list[Sensor] = []
    for location in locations:
        location_id = _as_int(location.get("id"))
        if location_id is None:
            continue
        country = location.get("country") or {}
        coordinates = location.get("coordinates") or {}
        for sensor in client.list_sensors(location_id):
            sensor_id = _as_int(sensor.get("id"))
            parameter = sensor.get("parameter") or {}
            parameter_name = str(parameter.get("name") or "").strip().lower()
            if sensor_id is None or not parameter_name:
                continue
            if parameters and parameter_name not in parameters:
                continue
            sensors.append(
                Sensor(
                    sensor_id=sensor_id,
                    location_id=location_id,
                    location_name=str(location.get("name") or "").strip(),
                    locality=_optional_string(location.get("locality")),
                    country_code=_optional_string(country.get("code")),
                    latitude=_as_float(coordinates.get("latitude")),
                    longitude=_as_float(coordinates.get("longitude")),
                    parameter=parameter_name,
                    units=str(parameter.get("units") or "").strip(),
                )
            )
    return sensors


def default_window(history_days: int) -> tuple[datetime, datetime]:
    """Return a UTC extraction window ending now."""

    datetime_to = datetime.now(UTC)
    return datetime_to - timedelta(days=history_days), datetime_to


def _results(payload: dict[str, Any]) -> list[dict[str, Any]]:
    results = payload.get("results", [])
    if not isinstance(results, list):
        raise OpenAQError("OpenAQ response field 'results' must be a list")
    return [item for item in results if isinstance(item, dict)]


def _as_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


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


def _api_datetime(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _retry_after_seconds(response: requests.Response) -> float:
    raw_value = response.headers.get("Retry-After")
    try:
        return max(1.0, float(raw_value)) if raw_value else 2.0
    except ValueError:
        return 2.0


def _safe_response_body(response: requests.Response) -> str:
    try:
        return response.text[:300]
    except Exception:  # pragma: no cover - defensive only
        return "<unreadable response>"
