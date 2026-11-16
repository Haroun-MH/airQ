# AirQ

AirQ is a DataOps project for a reliable, observable, multi-city air-quality platform.
This repository currently implements **Part 2 of the first delivery**: the foundations of
an ingestion, storage, transformation, validation, Docker, and CI pipeline.

## Current scope

The first implementation uses one source—the **OpenAQ v3 API**—and stores normalized
measurements in **DuckDB**. **dbt** exposes typed staging and mart models. A versioned
**data contract** is checked automatically before the transformed data is considered
valid.

The following are intentionally deferred to later deliveries:

- Open-Meteo weather data;
- dlt incremental loading and dbt sensor snapshots;
- Prefect or Airflow scheduling;
- public dashboard and data-health page;
- daily LLM summary and AWS deployment.

## Architecture

```text
OpenAQ v3 API
      |
      v
airq.extract ----> airq.transform ----> airq.validate
      |                                      |
      +-------------> DuckDB raw ------------+
                              |
                              v
                       dbt staging
                              |
                              v
                       dbt marts
                              |
                              v
                    data contract check
```

The current dbt contract test targets the raw table. dbt tests additionally validate
the staging model and the latest-measurement mart.

## Data grain and idempotence

One observation represents:

```text
sensor_id + parameter + measured_at (UTC)
```

Its stable `observation_id` is a SHA-256 hash of that business key. The raw DuckDB table
uses this value as its primary key. Re-running ingestion updates matching observations
instead of appending duplicates, so two consecutive runs leave the row count unchanged.

## Prerequisites

- Python 3.11, 3.12, or 3.13;
- Docker Desktop with Docker Compose;
- a free OpenAQ API key from <https://explore.openaq.org/register>.

## Local setup

```bash
python -m venv .venv
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
# macOS/Linux
source .venv/bin/activate

python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
cp .env.example .env       # Windows: copy .env.example .env
```

Add your key to `.env`:

```dotenv
OPENAQ_API_KEY=your-real-key
```

`.env` is ignored by Git. Never commit an API key.

### Choosing locations

For a small and deterministic first run, set one or more OpenAQ location IDs:

```dotenv
OPENAQ_LOCATION_IDS=2178
```

If `OPENAQ_LOCATION_IDS` is empty, the pipeline discovers locations using
`OPENAQ_COUNTRY_CODE`. Explicit IDs are recommended for the first delivery because they
keep request volume and runtime predictable.

## Run the pipeline

```bash
python -m airq.pipeline
```

Then build the dbt models and verify the contract:

```bash
dbt build --project-dir dbt --profiles-dir dbt
datacontract test contracts/openaq.yaml --server local
```

Or run the complete local verification with:

```bash
make verify
```

On Windows without `make`, run the commands in `Makefile` individually.

## Run everything with Docker

Start Docker Desktop, create `.env`, and run:

```bash
docker compose up --build --abort-on-container-exit
```

Compose performs these steps:

1. `ingestion` extracts OpenAQ data and writes it to the `airq_data` volume;
2. `dbt` runs only after ingestion succeeds;
3. the data contract is tested after dbt succeeds.

The service exits non-zero if ingestion, a dbt test, or the contract fails.

To exercise the same Docker chain without an API key, use the deterministic Compose
override:

```bash
docker compose -f docker-compose.yml -f docker-compose.test.yml up --build --abort-on-container-exit
```

This replaces only the ingestion command with the fixture builder. The same volume,
dbt build, and contract check still run in Docker.

## Test without the live API

The unit and integration tests use deterministic fixtures. To build a fixture warehouse
and validate dbt plus the contract:

```bash
python scripts/build_fixture_warehouse.py
dbt build --project-dir dbt --profiles-dir dbt
datacontract test contracts/openaq.yaml --server local
```

Both dbt and the data contract read `AIRQ_DUCKDB_PATH`. The default is
`warehouse.duckdb` in the project directory; CI and Docker set an explicit absolute
path, so all three environments test the same DuckDB file.

## Quality rules

The ingestion refuses to publish when:

- the OpenAQ API key is missing;
- no supported sensor or valid observation is found;
- more than 20% of observations violate a blocking Python rule;
- required identifiers, timestamps, parameters, or ranges are invalid;
- a dbt `not_null`, `unique`, or `accepted_values` test fails;
- the data contract reports a schema or quality violation.

Rejected API rows are isolated during normalization and reported in the run summary.

## CI

`.github/workflows/ci.yml` runs for every pull request and every push to `main`. It:

1. installs the project and its development dependencies;
2. runs Ruff;
3. runs the Python test suite with coverage;
4. builds a deterministic DuckDB fixture warehouse;
5. runs `dbt build`;
6. runs the data-contract test.

A red job must block the pull request. Configure `main` with these branch-protection rules
in GitHub Settings → Branches → Branch protection rules:

- require a pull request before merging;
- require at least one approving review;
- require the `validate` status check to pass;
- disallow force pushes and branch deletion.

## OpenAQ update frequency

OpenAQ does not expose one universal cadence. Many sensors publish hourly, but other
providers have irregular or delayed reporting. The extractor therefore requests a bounded
seven-day window by default (`AIRQ_HISTORY_DAYS`) and records the actual `measured_at`
for every row. The frequency observed in the selected sensors must be documented after
the first live run.

OpenAQ's documented free-key rate limit is 60 requests per minute and 2,000 per hour.
The client retries `429` responses with a bounded backoff.

## Project layout

```text
airq/                  Python extraction, transformation, validation, and loading
contracts/             Versioned OpenAQ data contract
dbt/                   dbt project, models, sources, and tests
scripts/               Reproducible helper commands
tests/                 Unit/integration tests and API fixtures
.github/workflows/     GitHub Actions CI
airq_data/             Docker-managed DuckDB volume (not in Git)
```

## Part 2 checklist

- [x] Git repository structure, README, and secret exclusion
- [x] One OpenAQ API source with a bounded extractor
- [x] Idempotent DuckDB ingestion
- [x] dbt staging model with `not_null` and `unique` tests
- [x] Versioned, automatically verified data contract
- [x] Docker Compose for ingestion + dbt + contract
- [x] GitHub Actions workflow
- [x] Branch protection enabled on `main` (pull request required, one approving review,
      the `validate` status check required, force pushes and deletion disabled)
- [ ] Obtain one approving review from a teammate on an open pull request
- [ ] Run against the live OpenAQ API and record observed sensor frequency
- [ ] Demonstrate two live ingestion runs with an unchanged row count

## Attribution and licensing

OpenAQ data is provided by its contributing providers. Follow the attribution and terms
published by OpenAQ when publishing measurements or derived data.
