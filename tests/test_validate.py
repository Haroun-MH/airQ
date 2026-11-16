"""Tests for fast validation rules."""

from __future__ import annotations

import pytest

from airq.transform import Observation
from airq.validate import DataQualityError, validate_observations


def make_observation(**changes) -> Observation:
    defaults = {
        "observation_id": "obs-1",
        "location_id": 1,
        "sensor_id": 2,
        "location_name": "Station",
        "locality": "City",
        "country_code": "MA",
        "latitude": 31.6,
        "longitude": -8.0,
        "parameter": "pm25",
        "units": "µg/m³",
        "value": 10.0,
        "measured_at": "2026-11-16T08:00:00+00:00",
        "measured_at_local": None,
    }
    defaults.update(changes)
    return Observation(**defaults)


def test_valid_observations_pass():
    result = validate_observations([make_observation()])
    assert result.total_rows == 1
    assert result.invalid_rows == 0


def test_empty_dataset_is_blocked():
    with pytest.raises(DataQualityError, match="no valid observations"):
        validate_observations([])


def test_negative_value_is_invalid():
    valid = [make_observation(observation_id=f"obs-{index}") for index in range(5)]
    invalid = make_observation(observation_id="obs-invalid", value=-1)
    result = validate_observations([*valid, invalid])
    assert result.invalid_rows == 1


def test_invalid_rate_above_threshold_blocks_publication():
    invalid = make_observation(observation_id="obs-2", value=-1)
    with pytest.raises(DataQualityError, match="exceeds"):
        validate_observations([invalid])
