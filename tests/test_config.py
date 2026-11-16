"""Tests for environment-based configuration."""

from __future__ import annotations

import pytest

from airq.config import ConfigurationError, Settings


def test_settings_require_api_key(monkeypatch):
    monkeypatch.delenv("OPENAQ_API_KEY", raising=False)
    with pytest.raises(ConfigurationError, match="OPENAQ_API_KEY"):
        Settings.from_env()


def test_settings_parse_location_ids(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAQ_API_KEY", "secret")
    monkeypatch.setenv("OPENAQ_LOCATION_IDS", "2178, 3917,2178")
    monkeypatch.setenv("AIRQ_DUCKDB_PATH", str(tmp_path / "warehouse.duckdb"))

    settings = Settings.from_env()

    assert settings.location_ids == (2178, 3917)
    assert settings.duckdb_path == tmp_path / "warehouse.duckdb"


def test_settings_reject_invalid_location_id(monkeypatch):
    monkeypatch.setenv("OPENAQ_API_KEY", "secret")
    monkeypatch.setenv("OPENAQ_LOCATION_IDS", "not-an-id")
    with pytest.raises(ConfigurationError, match="OPENAQ_LOCATION_IDS"):
        Settings.from_env()
