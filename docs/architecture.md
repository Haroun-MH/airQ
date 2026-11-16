# AirQ architecture — Part 2

## Current data flow

```text
OpenAQ v3
  /locations and /locations/{id}/sensors
  /sensors/{id}/measurements
        |
        v
airq.extract.OpenAQClient
  - API-key header
  - timeout and bounded retry
  - pagination and bounded history window
        |
        v
airq.transform.normalize_measurements
  - typed observations
  - supported-pollutant checks
  - range/timestamp checks
  - stable business key
        |
        v
airq.validate.validate_observations
  - required fields and blocking reject-rate threshold
        |
        v
DuckDB raw.openaq_measurements
  - observation_id primary key
  - idempotent insert/update
        |
        +---------------------------+
        |                           |
        v                           v
dbt staging model             Data Contract v1
        |                  schema + SQL quality checks
        v
dbt marts
```

## Design decisions

### OpenAQ hierarchy

The OpenAQ v3 API does not expose a single endpoint containing all cities and all
measurements. The extractor follows the documented hierarchy: locations → sensors →
measurements. Explicit `OPENAQ_LOCATION_IDS` keep the first delivery bounded; country
discovery remains available through `OPENAQ_COUNTRY_CODE`.

### Stable observation key

The business key is:

```text
sensor_id + parameter + measured_at_utc
```

This is intentionally independent of the location display name, because a station can
be renamed without creating a new measurement. The SHA-256 representation is stable and
safe to use as a primary key.

### Idempotent loading

The loader reads existing business keys and performs an upsert inside a transaction.
Running the same extraction twice updates existing rows instead of adding rows. A
primary key on `observation_id` is the final database-level duplicate protection.

### Validation boundaries

- Python validation runs before loading and blocks invalid API payloads early.
- dbt tests validate the typed relational model.
- The data contract validates the raw table independently of dbt.

A failure at any layer stops the pipeline.

## Planned next stages

1. Open-Meteo weather context and location mapping.
2. dlt incremental ingestion with checkpoints.
3. dbt snapshots for sensor metadata changes.
4. Freshness and stuck-sensor monitoring.
5. Prefect/Airflow daily orchestration.
6. Public dashboard, data-health page, and validated LLM daily summary.
7. AWS deployment through GitHub Actions and S3-compatible storage.
