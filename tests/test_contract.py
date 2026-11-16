"""Tests that prove the OpenAQ data contract blocks invalid data."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from airq.extract import Sensor
from airq.load import connect, upsert_observations
from airq.transform import normalize_measurements

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "contracts" / "openaq.yaml"
FIXTURE = ROOT / "tests" / "fixtures" / "openaq_measurements.json"


def _build_warehouse(path: Path) -> None:
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
    assert not rejected
    connection = connect(path)
    try:
        upsert_observations(connection, observations)
    finally:
        connection.close()


def _datacontract_executable() -> str:
    script_name = "datacontract.exe" if os.name == "nt" else "datacontract"
    beside_python = Path(sys.executable).with_name(script_name)
    if beside_python.is_file():
        return str(beside_python)

    executable = shutil.which("datacontract")
    assert executable is not None, "the datacontract executable must be installed"
    return executable


def _contract_environment(warehouse: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["AIRQ_DUCKDB_PATH"] = str(warehouse)
    env["DATACONTRACT_DUCKDB_DATABASE"] = str(warehouse)
    env["DATACONTRACT_DUCKDB_SCHEMA"] = "raw"
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    return env


def test_contract_accepts_valid_warehouse(tmp_path: Path):
    warehouse = tmp_path / "warehouse.duckdb"
    _build_warehouse(warehouse)
    env = _contract_environment(warehouse)

    result = subprocess.run(
        [_datacontract_executable(), "test", str(CONTRACT), "--server", "local"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_contract_rejects_invalid_value(tmp_path: Path):
    warehouse = tmp_path / "warehouse.duckdb"
    _build_warehouse(warehouse)
    connection = connect(warehouse)
    try:
        connection.execute(
            "UPDATE raw.openaq_measurements SET value = -1 WHERE observation_id = "
            "(SELECT min(observation_id) FROM raw.openaq_measurements)"
        )
    finally:
        connection.close()

    env = _contract_environment(warehouse)
    result = subprocess.run(
        [_datacontract_executable(), "test", str(CONTRACT), "--server", "local"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    assert result.returncode != 0
    assert "quality" in (result.stdout + result.stderr).lower() or "failed" in (
        result.stdout + result.stderr
    ).lower()


def test_datacontract_cli_is_installed():
    assert _datacontract_executable()
