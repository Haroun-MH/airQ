"""Central configuration for the AirQ pipeline.

Configuration is read from environment variables. A local `.env` file is loaded when
python-dotenv is installed, but secrets must never be committed to Git.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - only used in minimal installations
    def load_dotenv(*_args: object, **_kwargs: object) -> bool:
        return False


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")


class ConfigurationError(ValueError):
    """Raised when a required setting is absent or invalid."""


def _positive_int(name: str, default: int) -> int:
    raw_value = os.getenv(name, str(default))
    try:
        value = int(raw_value)
    except ValueError as error:
        raise ConfigurationError(f"{name} must be an integer, got {raw_value!r}") from error
    if value <= 0:
        raise ConfigurationError(f"{name} must be greater than zero")
    return value


@dataclass(frozen=True)
class Settings:
    """Runtime settings used by extraction, loading, and validation."""

    openaq_api_key: str
    openaq_base_url: str = "https://api.openaq.org/v3"
    duckdb_path: Path = PROJECT_ROOT / "warehouse.duckdb"
    location_ids: tuple[int, ...] = ()
    country_code: str = "MA"
    history_days: int = 7
    max_pages: int = 10
    request_timeout_seconds: float = 30.0
    request_retries: int = 3

    @classmethod
    def from_env(cls) -> Settings:
        api_key = os.getenv("OPENAQ_API_KEY", "").strip()
        if not api_key:
            raise ConfigurationError(
                "OPENAQ_API_KEY is required. Copy .env.example to .env and add your key."
            )

        raw_location_ids = os.getenv("OPENAQ_LOCATION_IDS", "").strip()
        location_ids: list[int] = []
        for raw_id in raw_location_ids.split(","):
            if not raw_id.strip():
                continue
            try:
                location_ids.append(int(raw_id.strip()))
            except ValueError as error:
                raise ConfigurationError(
                    f"OPENAQ_LOCATION_IDS must contain integers, got {raw_id!r}"
                ) from error

        base_url = os.getenv("OPENAQ_BASE_URL", "https://api.openaq.org/v3").rstrip("/")
        country_code = os.getenv("OPENAQ_COUNTRY_CODE", "MA").strip().upper()
        if len(country_code) != 2:
            raise ConfigurationError("OPENAQ_COUNTRY_CODE must be an ISO alpha-2 code")

        return cls(
            openaq_api_key=api_key,
            openaq_base_url=base_url,
            duckdb_path=Path(
                os.getenv("AIRQ_DUCKDB_PATH", str(PROJECT_ROOT / "warehouse.duckdb"))
            ).resolve(),
            location_ids=tuple(dict.fromkeys(location_ids)),
            country_code=country_code,
            history_days=_positive_int("AIRQ_HISTORY_DAYS", 7),
            max_pages=_positive_int("AIRQ_MAX_PAGES", 10),
        )
