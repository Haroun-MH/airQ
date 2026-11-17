# AirQ — Explanation & Validation Dossier

> One file that explains: (1) what was built, (2) what every file contains, (3) how the
> pieces are wired together, and (4) everything needed to validate **Part 1** (the idea
> to present and defend) and **Part 2** (the pipeline foundations).
>
> Written 2026-11-17. All evidence below was captured on 2026-11-16/17 against
> `https://github.com/Haroun-MH/airQ`.

---

## Table of contents

1. [Project in one picture](#1-project-in-one-picture)
2. [Part 1 — defense dossier](#2-part-1--defense-dossier-ready-to-present)
3. [Part 2 — work log: everything that was done](#3-part-2--work-log-everything-that-was-done)
4. [Bugs found and fixed along the way](#4-bugs-found-and-fixed-along-the-way)
5. [File catalogue](#5-file-catalogue)
6. [How everything is linked together](#6-how-everything-is-linked-together)
7. [Validation runbook](#7-validation-runbook)
8. [Evidence index](#8-evidence-index)
9. [Open items](#9-open-items)

---

## 1. Project in one picture

**AirQ** is a DataOps platform for a reliable, observable, multi-city air-quality
pipeline. The problem it attacks is the classic one described in the course brief
(`resources/Projet DataOps.pdf`): numbers arrive late, by hand, from scripts nobody
dares to touch, and a wrong figure reaches decision makers with no way to trace it.

Part 1 of the delivery defines the idea and its defense. Part 2 builds the technical
foundations: one API source → Python ingestion → DuckDB raw → dbt staging/marts →
a versioned data contract → Docker Compose → GitHub Actions CI.

The scope deliberately excludes — for later deliveries — Open-Meteo ingestion, dlt
incremental loading, dbt snapshots, Prefect/Airflow orchestration, the dashboard, the
LLM daily summary, and AWS deployment.

### The reference repo and what we kept from it

`resources/base/` (ignored by Git) is the *shop / orders* example the course provided.
AirQ re-implements the same bricks, on the air-quality domain:

| Course reference (`resources/base`) | AirQ implementation | Same / different |
|---|---|---|
| `pipeline/{extract,transform,validate,load,schema}.py` | `airq/{extract,transform,validate,load,config}.py` | Same layering (extract → transform → validate → load), one extra `config` module so settings live in one place |
| `models/{staging,intermediate,marts}` | `dbt/models/{staging,marts}` | Same staging/marts; **no intermediate** layer because there is a single source and no cross-source join to make yet |
| `contracts/orders.yaml` (ODCS v3.2.0, CSV servers) | `contracts/openaq.yaml` (ODCS v3.2.0, DuckDB server) | Same standard; our server is the real warehouse table instead of a CSV snapshot |
| `data_tests/*.sql` + `models/**.yml` tests | `dbt/models/**/*.yml` data tests | Same idea; ours are declared in YAML (`not_null`, `unique`, `accepted_values`) |
| `tests/test_pipeline.py` + fixture CSV | `tests/test_*.py` + OpenAQ JSON fixtures | Same approach: no network in tests |
| `data/raw.dvc` (DVC-managed raw files) | `tests/fixtures/*.json` + Docker volume | **Different**: no DVC. The raw data is a DuckDB volume produced by idempotent ingestion, and CI uses a deterministic fixture builder |
| `warehouse.duckdb` committed in the reference repo | `warehouse.duckdb` **ignored** | Different on purpose: generated data never enters Git |

---

## 2. Part 1 — defense dossier (ready to present)

> Requirements come from `resources/first_livery.pdf` — *Partie 1 : L'idée à présenter
> et défendre*: **Problématique**, **Sources** (2 minimum dont 1 API testée + fréquence
> de mise à jour), **3 questions métier**, **Schéma d'architecture**, **Innovation**.
> Team rules: *Rien sur main sans PR relue*, *Chacun touche au moins 2 briques (l'historique
> Git le prouve)*, *Chacun sait expliquer chaque ligne du dépôt (IA autorisée)*.

### 2.1 Problématique — what data problem, for whom

**The problem.** A city or a multi-city observatory receives air-quality numbers from
several providers. Today those numbers arrive as manual downloads or one-off scripts;
timestamps mix UTC and local time; units differ between providers; re-running a
collection duplicates rows; nobody can say whether a published figure is fresh, valid,
or duplicated. One bad number reaches the direction, and nobody can trace it back.

**Concretely, the four data failures AirQ prevents:**

| Failure | What AirQ does instead |
|---|---|
| Re-running a collection duplicates rows | One stable business key per observation (`sensor_id + parameter + measured_at_utc`) → idempotent upsert; two runs = same row count (verified) |
| Mixed UTC / local timestamps | Every row keeps an explicit `measured_at` (UTC, TIMESTAMPTZ) **and** the provider's local string (`measured_at_local`) |
| Invalid values silently published | Three independent quality gates (Python → dbt → data contract); a violation blocks publication |
| A table breaks and nobody notices | The raw table is covered by a versioned ODCS contract checked automatically in CI, before dbt even runs |

**For whom:**

1. **Primary client — the metropolis data team / air-quality observatory**: needs
   ingestion that is safe to re-run, tests that block bad data, and a contract that
   documents the grain and the rules.
2. **Secondary client — decision makers and the public dashboard** (planned): needs
   the *latest valid measurement per location and pollutant* — exactly the mart we
   build (`main.latest_air_quality_by_location`).
3. **The team itself**: needs Git protection, a reviewed PR flow, and CI, so nobody
   breaks `main`.

### 2.2 Sources — 2 minimum, of which 1 API is tested + update frequency

| # | Source | Type | Status | Update frequency | Where it lives in the repo |
|---|---|---|---|---|---|
| 1 | **OpenAQ v3** (`https://api.openaq.org/v3`) | REST API, `X-API-Key` header, free key | **Implemented, unit-tested and live-tested** (2026-11-17: real key, `iso=MA` discovery → 5 locations, two full runs, 501 observations, `dbt build` PASS=23 and contract 46 checks on the live warehouse) | **Measured**: all 3 active MA sensors publish **hourly** (median gap exactly 1.0 h; 167 obs / 166 h); other sensors were stale in the window. Documented free-key limits: 60 requests/minute, 2 000/hour; the client retries `429` with backoff | `airq/extract.py`, `tests/fixtures/openaq_*.json`, `README.md` → *OpenAQ update frequency*, §3.14 |
| 2 | **Open-Meteo** (`https://api.open-meteo.com/v1`) | REST API, free key, no signup for basic use | **Planned — Part 3** (roadmap, not yet in scope of this delivery) | Hourly forecast, ~15-min past observations | `docs/architecture.md` → *Planned next stages* |

**Why OpenAQ first:** it is free, it covers multiple cities, it exposes the full
`locations → sensors → measurements` hierarchy, and its data is exactly the kind that
changes often (every hour, per sensor) — which is what the course brief requires
(*vos données changent souvent et viennent d'au moins une API*).

**Honest Part-1 risk and the actions that close it:**

- The brief asks for **2 sources minimum, of which 1 API tested** and their **update
  frequency**. The repo has **one** implemented source (OpenAQ).
  1. ~~Run the live OpenAQ ingestion with a real key, twice, and record the observed
     sensor frequency.~~ **Done 2026-11-17** (see §3.14): two live runs with an
     unchanged row count (501) and the frequency measured — hourly, median gap 1.0 h.
  2. Add the thin Open-Meteo client (extractor + fixture + one dbt model) so a second
     API exists with its own frequency — this is the natural Part 3 opener and also
     satisfies the second-source requirement for the defense. **Still to do.**

### 2.3 The three business questions the dashboard will answer

| # | Question (what the dashboard answers) | Which data answers it today | Status |
|---|---|---|---|
| 1 | **"What is the air quality right now, per city and per pollutant?"** | `main.latest_air_quality_by_location` — one row per `(location_id, parameter)`, the most recent `measured_at`, built from `stg_openaq_measurements` | **Ready** (built and tested on the fixture warehouse) |
| 2 | **"Which data is fresh, and which sensor is late or stuck?"** | The raw table already stores both `measured_at` (provider time) and `ingested_at` (our time) per row, so age and delay are computable | **Data ready, logic planned** (Part 3: freshness monitoring + stuck-sensor detection on repeated identical values) |
| 3 | **"How did pollution evolve over the day, and is it improving or worsening?"** | The raw table holds the bounded 7-day history per sensor | **Data ready, model planned** (Part 3: hourly aggregation + AQI trend + LLM daily summary) |

### 2.4 Architecture schema (sources → ingestion → storage → dbt → orchestration → dashboard → monitoring)

```
                         ┌─────────────────────────────────────────────────┐
                         │  SOURCES                                        │
                         │  OpenAQ v3 API (implemented)                    │
                         │  Open-Meteo API (planned, Part 3)               │
                         └───────────────┬─────────────────────────────────┘
                                         │  HTTP, X-API-Key, bounded window
                                         ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│  INGESTION — Python package `airq`                                               │
│  config.py (env) → extract.py (locations → sensors → measurements, retries)      │
│  → transform.py (normalize, SHA-256 business key) → validate.py (block rules)    │
│  → load.py (idempotent DuckDB upsert) → pipeline.py (orchestrates + reports)     │
└───────────────┬──────────────────────────────────────────────────────────────────┘
                │  one write, transactional, PK = observation_id
                ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│  STORAGE — DuckDB file (path = AIRQ_DUCKDB_PATH)                                 │
│  raw.openaq_measurements                                                         │
└──────┬───────────────────────────────────────────────┬───────────────────────────┘
       │                                               │
       │ schema + SQL quality rules                    │ source()
       ▼                                               ▼
┌──────────────────────────┐   ┌──────────────────────────────────────────────────┐
│  DATA CONTRACT (ODCS     │   │  dbt (staging → marts)                           │
│  v3.2.0) contracts/      │   │  stg_openaq_measurements (view, typed)           │
│  openaq.yaml             │   │  latest_air_quality_by_location (table)          │
│  datacontract test       │   │  21 data tests (not_null, unique, accepted)      │
└──────────────────────────┘   └──────────────────────────────────────────────────┘
       │                                               │
       └────────────────────┬──────────────────────────┘
                            ▼
            ┌───────────────────────────────────────┐
            │  CI — GitHub Actions (.github/workflows/ci.yml)
            │  ruff → pytest → fixture warehouse → dbt build → datacontract test
            │  required status check "validate" on every PR to main
            └───────────────────────────────────────┘

  PLANNED (later deliveries):
  ┌──────────────┐   ┌──────────────┐   ┌───────────────────────────┐
  │ ORCHESTRATION │   │  DASHBOARD    │   │  MONITORING / ALERTS      │
  │ Prefect/     │   │ public page + │   │ freshness rules, stuck-   │
  │ Airflow daily│   │ health page   │   │ sensor detection, LLM     │
  └──────────────┘   └──────────────┘   │ daily summary             │
                                        └───────────────────────────┘
```

Each box maps to real files — see §5 (file catalogue) and §6 (wiring).

### 2.5 Innovation — what we add beyond the course, and why

1. **Contract-first raw-table validation.** The ODCS v3.2.0 contract checks the **raw
   DuckDB table** (schema + 3 SQL quality rules) *independently of dbt*. Most course
   solutions only test dbt models; testing the raw table catches corruption the moment
   it is written, before any transformation can hide it.
   *Justification:* the raw table is the boundary between ingestion (Python) and
   transformation (dbt); it is exactly where a data contract should live.

2. **Idempotency by design, at three levels.** The business key
   `SHA-256(sensor_id|parameter|measured_at_utc)` is used (a) to deduplicate in memory,
   (b) as the DuckDB primary key inside a transactional upsert, and (c) as the dbt
   `unique` test. Re-running ingestion never creates duplicates and never changes the
   row count — verified twice (pytest and Docker).
   *Justification:* "relancer 2 fois = même nombre de lignes" is a Part 2 requirement;
   making it structural (a key) rather than procedural (a script) is what makes it hold
   under future changes (new sources, backfills).

3. **One configuration knob for the whole stack.** `AIRQ_DUCKDB_PATH` is the single
   warehouse path read by local runs, the dbt profile, the ODCS contract server, CI and
   Docker. There is no duplicated path logic, so the same physical file is validated
   everywhere.
   *Justification:* the classic "it worked locally" bug is caused by each tool owning
   its own path; a shared env-var reference removes that class of bug.

4. **A deterministic, key-free demonstration of the full chain.** A fixed fixture
   warehouse builder (`scripts/build_fixture_warehouse.py`) plus a Compose override
   (`docker-compose.test.yml`) replace only the ingestion command, so
   ingestion → dbt → contract runs end-to-end in Docker with **no API key and no
   network** — locally and in CI.
   *Justification:* it makes the pipeline reproducible and demo-able; the live-API run
   is then a strict superset (same commands, real data).

5. **Three independent quality gates with negative proof.** Python validation
   (blocking reject-rate > 20 %), dbt tests (`not_null`, `unique`, `accepted_values`),
   and the data contract each have a test that **proves they block** an invalid dataset
   (`tests/test_validate.py`, `tests/test_contract.py`, and the Docker run where a
   corrupted warehouse makes the contract exit 1).

6. **Branch protection enforced and *proven*.** Protection is applied through the
   GitHub API (PR required, one approving review, approval must come from someone other
   than the last pusher, strict `validate` check, no force push, no deletion, admins
   included), and a **real red PR was kept as evidence** that a failing check blocks
   the merge (HTTP 405).

### 2.6 Team rules — compliance and evidence

| Team rule (course PDF) | State today | Evidence / what remains |
|---|---|---|
| *Rien sur `main` sans PR relue* | **Done and enforced.** `main` is protected: PR required, ≥1 approving review, the approval must come from someone other than the last pusher, `validate` must pass, no force push/deletion, admins included. A red PR (CI failing) and a green-but-unreviewed PR are both refused with HTTP 405 | API `GET /repos/Haroun-MH/airQ/branches/main/protection`; PR #1 (red, blocked); PR #2 (green, blocked pending review). One direct push happened only for the initial bootstrap commit (documented in `docs/contributing.md`) |
| *Chacun touche au moins 2 briques (l'historique Git le prouve)* | **Not yet satisfied.** Only `Haroun-MH` has commits so far; `Merie1m` has write access and is requested as reviewer on PR #2 | **Action:** `Merie1m` should own a brick in a dedicated branch/PR — the natural candidates are the Open-Meteo source (+ tests) and the dashboard model |
| *Chacun sait expliquer chaque ligne du dépôt (IA autorisée)* | **Documented.** This file + `docs/architecture.md` + the PR descriptions give the rationale of every file and decision | §5 and §6 below; the review conversation itself is the explanatory step |

### 2.7 Part 1 validation checklist

| Required element | What to show | Where it is | Status |
|---|---|---|---|
| Problématique | The problem, for whom, the 4 prevented failures | §2.1 | ✔ Ready |
| Sources — 2 minimum | OpenAQ + Open-Meteo table with types and status | §2.2 | ⚠ 2 sources *presented*; only OpenAQ *implemented* |
| Source API **testée** | Extraction unit-tested on real API fixtures **and live-tested** (2026-11-17: real key, `GET /locations?iso=MA` → HTTP 200, two full ingestions, 501 observations) | `tests/test_extract.py`, `tests/test_pipeline.py`; live evidence in §3.14 and `README.md` → *OpenAQ update frequency* | ✔ Ready |
| Fréquence de mise à jour | **Measured, not assumed**: all 3 active MA sensors publish hourly (median gap exactly 1.0 h, 167 obs / 166 h); documented rate limits 60 req/min, 2 000/hour | `README.md` → *OpenAQ update frequency*; query in §3.14 | ✔ Ready |
| 3 questions métier | The three dashboard questions + which data answers them | §2.3 | ✔ Ready (Q1 answered by the mart; Q2/Q3 data-ready) |
| Schéma d'architecture | Full chain: sources → ingestion → storage → dbt → orchestration → dashboard → monitoring | §2.4 (and the current-flow version in `docs/architecture.md`) | ✔ Ready |
| Innovation | Six additions beyond the course, each justified | §2.5 | ✔ Ready |
| Règles d'équipe | Protection + red PR proof + review flow | §2.6, §8 | ✔ Protection; ⚠ second contributor needed |

---

## 3. Part 2 — work log: everything that was done

Chronological account of the implementation, with the commands that were actually run
and the results that were observed.

### 3.1 Plan and repository hygiene (first)

1. Wrote `tasks.md` (in French, matching the course PDF): one section per brick, each
   with *owner*, *définition de terminé*, *preuve attendue*, plus the out-of-scope list
   and the success criteria ("a fresh clone can run the whole thing").
2. Wrote `.gitignore` **before** the first commit: `resources/` (course material, local
   only), `.env` / `.env.*` (except `.env.example`), `*.duckdb` / `*.duckdb.wal`,
   `data/`, `target/`, `dbt/logs/`, `dbt/.user.yml` (dbt's anonymous usage ID), caches,
   IDE files.
3. Wrote `.dockerignore` with the same exclusions so build contexts stay small and
   secret-free.
4. Wrote `.env.example` as the documented, secret-free template
   (`OPENAQ_API_KEY=replace-with-your-openaq-api-key`, `AIRQ_DUCKDB_PATH`,
   `OPENAQ_LOCATION_IDS`, `OPENAQ_COUNTRY_CODE`, `AIRQ_HISTORY_DAYS`, `AIRQ_MAX_PAGES`).

### 3.2 Python package skeleton and configuration

`airq/__init__.py` (package + version) and `airq/config.py`:
a frozen `Settings` dataclass built from environment variables with validation
(`ConfigurationError` on a missing key, a non-integer `AIRQ_HISTORY_DAYS`, a bad ISO
country code); `python-dotenv` loads `.env` when present; `PROJECT_ROOT` anchors all
relative paths.

### 3.3 Extraction (OpenAQ v3, hierarchy-respecting)

`airq/extract.py`:
- `Sensor` dataclass carrying sensor **and** its parent location metadata (id, name,
  locality, country, coordinates, parameter, units) — this is what makes one API call
  per sensor enough to build a full row later.
- `OpenAQClient` with a `requests.Session`, the `X-API-Key` header (never logged),
  timeouts, bounded retries with exponential backoff on network errors, honoring
  `Retry-After` on `429`, safe body truncation on errors.
- `list_locations` (by explicit IDs **or** paged country discovery), `list_sensors`,
  `get_measurements` (paged, bounded window `default_window(history_days)` = the last
  7 days by default).
- `discover_sensors` walks `locations → sensors` and keeps only well-formed sensors.

### 3.4 Transformation and validation

`airq/transform.py`:
- `Observation` dataclass = the grain: one row per sensor, pollutant, UTC timestamp.
- `normalize_measurements` separates valid rows from rejected ones (never crashes on a
  bad row; it reports it), checks the numeric value (0 ≤ value ≤ 10 000), the UTC
  timestamp, the supported parameter set
  (`pm10, pm25, no2, o3, so2, co, nox`), builds
  `observation_id = SHA-256(sensor_id|parameter|measured_at_utc)`, and deduplicates
  repeated API rows in memory.

`airq/validate.py`:
- `validate_observations` counts invalid rows per blocking rule and raises
  `DataQualityError` when the invalid rate exceeds 20 %, and when the dataset is empty
  (an empty successful response is not a healthy pipeline).

### 3.5 DuckDB persistence

`airq/load.py`:
- `CREATE_RAW_TABLE` defines `raw.openaq_measurements` with `observation_id VARCHAR
  PRIMARY KEY` and NOT NULL on identifiers, parameter, units, value, timestamps and
  source.
- `connect` creates parent directories; `ensure_raw_table` is idempotent;
  `upsert_observations` reads existing keys, then inside **one transaction** either
  INSERTs or UPDATEs each row by `observation_id`, returning `(inserted, updated)`;
  `count_observations` powers the row-count proof.

### 3.6 Pipeline orchestration

`airq/pipeline.py` (`python -m airq.pipeline`): builds the client from `Settings`,
discovers sensors, fetches measurements per sensor, normalizes + validates everything
*before* touching the database, opens one connection, records `before`/`after` row
counts, upserts, refuses to continue if the count decreased, prints a run summary
(sensors, observations, rejected, inserted, updated, warehouse rows), and supports
`--output-json` for machine-readable metrics.

### 3.7 dbt project

- `dbt/dbt_project.yml`: project `airq`, profile `airq`, staging = view, marts = table
  (the empty `intermediate` layer from the course template was removed on purpose).
- `dbt/profiles.yml`: DuckDB adapter, `path: "{{ env_var('AIRQ_DUCKDB_PATH',
  'warehouse.duckdb') }}"`, schema `main`, 1 thread.
- `dbt/models/sources.yml`: source `raw.openaq_measurements` with source-level
  `not_null` / `unique` tests on the columns the loader guarantees.
- `dbt/models/staging/stg_openaq_measurements.sql` + `.yml`: explicit casts of every
  column (bigint/double/varchar/timestamptz), `lower(trim(parameter))`, **no row
  removed** (quality decisions belong downstream), plus the model tests
  (`not_null`, `unique` on `observation_id`, `accepted_values` on `parameter`).
- `dbt/models/marts/latest_air_quality_by_location.sql` + `marts.yml`: the most recent
  measurement per `(location_id, parameter)` via `qualify row_number() ... order by
  measured_at desc, ingested_at desc`, with `not_null` tests.

### 3.8 Data contract (ODCS v3.2.0)

`contracts/openaq.yaml`: `kind: DataContract`, `apiVersion: v3.2.0`, version 1.0.0,
owner, purpose/usage; a DuckDB server whose `database` is the variable
`${AIRQ_DUCKDB_PATH:-warehouse.duckdb}`; the 15 properties with logical + physical
types, required/unique/primaryKey/enum constraints; and `quality` SQL rules **inside
the schema object** (ODCS v3.2.0 placement — an earlier draft had them at the top level
and `datacontract lint` correctly rejected it):
identifiers must be positive, values must not be negative, values must not exceed
10 000. Three rules → 46 automated checks when run against the warehouse.

### 3.9 Tests and fixtures (21 tests, zero network)

- `tests/fixtures/openaq_location.json`: location 2178 "Del Norte" (Albuquerque, US,
  provider AirNow) with sensor 3920 (pm25, µg/m³) — recorded from the real API shape.
- `tests/fixtures/openaq_measurements.json`: two valid pm25 rows
  (2026-11-16T08:00Z and 09:00Z) with UTC + local timestamps.
- `tests/test_config.py` (3): key required, IDs parsed, bad ID rejected.
- `tests/test_extract.py` (4): sensor discovery merges location + sensor metadata;
  measurements use the bounded window and pagination; an HTTP error is never ignored;
  a real `requests.Session` type is accepted.
- `tests/test_transform.py` (4): valid rows preserved; duplicate API rows deduplicated;
  negative value rejected; missing timestamp rejected.
- `tests/test_load.py` (2): **running ingestion twice does not create duplicates**;
  the primary key itself prevents duplicate rows.
- `tests/test_validate.py` (4): valid pass; empty blocked; a negative row counts as
  invalid without blocking below the threshold; a rate above 20 % blocks publication.
- `tests/test_pipeline.py` (1): the full chain on a fake session — two runs, same
  `warehouse_rows` (2), second run `inserted == 0`.
- `tests/test_contract.py` (3): the datacontract CLI is installed; a valid fixture
  warehouse **passes** the contract (46 checks); a warehouse corrupted by
  `UPDATE ... SET value = -1` **fails** it. The subprocess runs the installed
  `datacontract` executable (resolved next to the venv Python, then `PATH`) with
  UTF-8 forced, because `python -m datacontract.cli` does not expose `test` and Windows
  consoles default to a non-UTF-8 codec.

### 3.10 Docker

- `Dockerfile`: `python:3.12-slim`, no compiler toolchain, `PIP_NO_CACHE_DIR=1`,
  installs `.[docker]` (duckdb, dbt-duckdb, datacontract-cli[duckdb] — **not** the test
  tooling), copies `airq/`, `dbt/`, `contracts/`, `scripts/`, `tests/fixtures/`,
  creates `/app/data`, adds the non-root user `airq` (uid 10001), `USER airq`, default
  command `python -m airq.pipeline`.
- `docker-compose.yml`: two services sharing **one image** `airq:local`
  (`ingestion` builds it; `dbt` declares the same `build` so Compose never tries to
  pull `airq:local` from Docker Hub). `dbt` depends on `ingestion` with
  `service_completed_successfully`, mounts the named volume `airq_data:/app/data`, and
  runs `dbt build && datacontract test`. The optional `env_file: .env` feeds the API
  key in the live chain.
- `docker-compose.test.yml`: override that replaces **only** the ingestion command with
  the fixture builder, keeping the same volume, dbt step and contract step.

### 3.11 GitHub Actions

`.github/workflows/ci.yml`: on `pull_request → main` and `push → main`, minimal
`contents: read` permission, concurrency group, Python 3.12 with pip cache, installs
`.[dev]`, then `ruff check .` → `pytest --cov=airq` → fixture warehouse + `dbt build` +
`datacontract test` on `${{ runner.temp }}/warehouse.duckdb` → uploads `target/`
artifacts on failure.

### 3.12 Git, GitHub, protection, proofs

1. `git init -b main`, `origin` = `https://github.com/Haroun-MH/airQ.git`, staged
   everything, verified `resources/`, `.venv/`, `warehouse.duckdb` and `dbt/.user.yml`
   are ignored, no secrets in the index, `git diff --cached --check` clean.
2. Bootstrap commit `79e82c0` pushed to `main` (the only direct push; documented as the
   bootstrap exception in `docs/contributing.md`).
3. GitHub Actions on `main`: run `43962686427` → **success**.
4. Branch protection applied through the GitHub API (admin credential, never printed):
   `required_status_checks = [validate]` (strict), `required_approving_review_count=1`,
   `require_last_push_approval=true`, `enforce_admins=true`, `allow_force_pushes=false`,
   `allow_deletions=false`, `required_conversation_resolution=true`.
5. **Red-PR proof**: branch `chore/ci-red-proof` with `tests/test_red_proof.py`
   (an intentional failure) → PR #1 → Actions run `43963315901` → **failure**;
   `PUT /pulls/1/merge` → **HTTP 405** *"Required status check \"validate\" is
   failing"*. PR #1 then closed, its branch deleted, the temporary test removed.
6. **Evidence PR** on `docs/part2-verification-evidence`: commits `078d79a`
   (protection + red-PR evidence) and `7213c90` (Docker evidence + the Compose command
   fix). CI green: runs `43965122788` and `43968686358`. Review requested from
   `Merie1m`; a merge attempt returns **HTTP 405** *"New changes require approval from
   someone other than the last pusher"* — the review rule is proven, the PR stays open
   until a teammate approves it.

### 3.13 Docker verification (and one real bug fixed)

- `docker compose build` → image `airq:local` (Docker 29.9.3, 1.26 GB on disk).
- Clean volume → `docker compose up` → ingestion `(2 inserted, 0 updated)` → dbt
  `PASS=23 WARN=0 ERROR=0` → contract **46 checks valid** → exit code **0**.
- Second run → ingestion `(0 inserted, 2 updated)`, same dbt/contract results, exit 0;
  `RAW_ROWS` read inside the container = **2** → idempotence proven in Docker.
- Tables created in the volume: `raw.openaq_measurements`,
  `main.stg_openaq_measurements`, `main.latest_air_quality_by_location`.
- Container identity: `id` → `uid=10001(airq)` (non-root).
- Failure propagation: a corrupted copy of the warehouse (`value = -1`) makes
  `datacontract test` exit **1** inside the image; a `dbt` service pointed at a missing
  warehouse exits **1** and `docker compose up` returns **1**.
- **Bug found and fixed:** the documented command
  `docker compose up --build --abort-on-container-exit` **kills the stack as soon as
  the one-shot ingestion container exits** — the dbt container was SIGKILLed (exit 137)
  even when everything succeeded. The documented command is now
  `docker compose up --build`, with an explicit warning in `README.md`, and the
  Makefile targets were aligned.

### 3.14 Live OpenAQ run (2026-11-17) — the missing Part 1/Part 2 proof, closed

With a real `OPENAQ_API_KEY` (stored only in the gitignored `.env`; it was briefly
pasted into the *tracked* `.env.example` and was reverted immediately before any
commit):

1. **Connectivity**: `GET /locations?countries=MA&limit=1` → the `countries` param is
   ignored by OpenAQ v3 (returns global results); the pipeline's `iso=MA` param filters
   correctly → HTTP 200, rate-limit headers `X-RateLimit-Remaining=59 / Limit=60`,
   5 locations for Morocco.
2. **Ingestion run 1** (fresh warehouse): `python -m airq.pipeline` → 501 valid
   observations, `501 inserted, 0 updated`, warehouse rows 501.
3. **Ingestion run 2** (idempotence on real data): `0 inserted, 501 updated`, warehouse
   rows still **501** — same row count over two live runs. ✔
4. **Full chain on the live warehouse**: `dbt build` → `PASS=23 WARN=0 ERROR=0 TOTAL=23`;
   `datacontract test` → **46 checks valid**.
5. **Observed frequency** (measured in DuckDB, `lag` window over distinct
   `measured_at` per sensor): 3 active sensors (ARC Air, Marrakech-Residence Mima,
   UM6P_Bengeurir2 — all pm25, µg/m³) → 167 observations over a 166-hour span,
   **median gap exactly 1.0 h (min=max=1.0 h) → hourly**. The 5 other air-quality
   sensors returned nothing in the 7-day window (sparse/stale coverage — the future
   freshness monitor exists for a reason).
6. **Efficiency fix found by the live run**: `discover_sensors` was called without a
   parameter filter, so the pipeline fetched all 28 MA sensors (temperature, humidity,
   pm1, um003…) and rejected 2 004 out-of-scope rows, wasting ~20 API calls per run.
   `airq/pipeline.py` now passes `parameters=ALLOWED_PARAMETERS` at discovery →
   8 sensors fetched, `rejected 0`, same 501 observations (~21 calls/run instead of
   ~61). Re-verified after the change: `ruff` clean, `pytest` 21 passed, fresh live
   double-run again `501 rows` both times, dbt `PASS=23`, contract 46 checks.

---

## 4. Bugs found and fixed along the way

| # | Problem | Root cause | Fix |
|---|---|---|---|
| 1 | `ruff check .` reported thousands of errors inside `.venv` | Ruff's default exclusions don't cover a nested venv | `extend-exclude = ["resources"]` in `pyproject.toml` (`.venv` is excluded by default) |
| 2 | DuckDB insertion failed on a parameter mismatch | The INSERT listed a different number of placeholders than values | All 15 inserted columns are named explicitly in `airq/load.py` |
| 3 | `test_negative_value_is_invalid` raised `DataQualityError` | One invalid row out of two = 50 % > the 20 % threshold | The test builds 5 valid rows + 1 invalid (16.7 % → counts as invalid, does not block) |
| 4 | `datacontract lint` rejected the contract: `'quality' was unexpected` | In ODCS v3.2.0, `quality` belongs **inside** the schema object, not at the document root | Moved `quality:` under `schema[0]` in `contracts/openaq.yaml` |
| 5 | Lint warning: unknown fields `minimum`, `maximum` on a property | ODCS properties don't support numeric bounds | Expressed the range as SQL `quality` rules (`value < 0`, `value > 10000`) |
| 6 | `python -m datacontract.cli test ...` → "No such command" | The module only registers some commands | The installed `datacontract` executable is used (resolved next to the Python interpreter, then `PATH`) |
| 7 | UnicodeEncodeError reading contract output on Windows | Console default codec ≠ UTF-8 | Subprocess runs with `PYTHONUTF8=1`, `PYTHONIOENCODING=utf-8`, `encoding="utf-8"`, `errors="replace"` |
| 8 | `dbt debug` ran against the wrong file depending on CWD | Hard-coded relative `../warehouse.duckdb` profile | Profile uses `{{ env_var('AIRQ_DUCKDB_PATH', 'warehouse.duckdb') }}`; the contract uses `${AIRQ_DUCKDB_PATH:-warehouse.duckdb}` |
| 9 | Compose tried to `pull airq:local` from Docker Hub | `dbt` had an `image` but no `build`, so Compose resolved it as a registry image | `dbt` declares the same `build` block as `ingestion` (one image, cached build) |
| 10 | `--abort-on-container-exit` killed dbt (exit 137) on success | The flag aborts on **any** container exit, including the one-shot ingestion | Documented command is now `docker compose up --build` (still fails non-zero on any step); a warning was added to the README |
| 11 | `dbt/.user.yml` (anonymous usage UUID) was staged | Generated at first dbt run | Added `dbt/.user.yml` to `.gitignore`, removed from the index |
| 12 | A Makefile trailing blank line made `git diff --cached --check` fail | Whitespace nit | Removed the trailing blank line |

---

## 5. File catalogue

### 5.1 Root

| File | Role | Key content / why it exists |
|---|---|---|
| `README.md` | Front door | Scope, architecture diagram, grain & idempotence, prerequisites, local setup, pipeline + dbt + contract commands, the Docker chain (+ warning about `--abort-on-container-exit`), the key-free test path, quality rules, CI description, protection rules, OpenAQ frequency section, project layout, Part 2 checklist with the two pending items (teammate review, live OpenAQ run) |
| `explanation.md` | This file | Part 1 defense dossier, Part 2 work log, file catalogue, wiring, runbook, evidence |
| `tasks.md` | French task plan (Part 2) | One section per brick with owner, definition of done, expected proof; checked boxes carry the evidence (commands, run IDs, HTTP status codes) captured on 2026-11-16/17 |
| `pyproject.toml` | Package metadata | `airq` 0.1.0, Python ≥3.11,<3.14; deps: `requests`, `python-dotenv`; extras: `docker` (duckdb, dbt-duckdb, datacontract-cli[duckdb]) and `dev` (those + pytest, pytest-cov, ruff, pandas, pandera); Ruff (line 100, py311, `E/F/I/UP/B/SIM`); pytest `testpaths=tests` |
| `.gitignore` | Keep junk and secrets out of Git | `resources/`, `.env`/`.env.*` (except `.env.example`), `*.duckdb`, `data/`, `target/`, `dbt/logs/`, `dbt/.user.yml`, caches, IDE files |
| `.dockerignore` | Keep build contexts small | Same exclusions as above |
| `.env.example` | Secret-free template | `OPENAQ_API_KEY`, `OPENAQ_BASE_URL`, `AIRQ_DUCKDB_PATH`, `OPENAQ_LOCATION_IDS`, `OPENAQ_COUNTRY_CODE`, `AIRQ_HISTORY_DAYS=7`, `AIRQ_MAX_PAGES=10` |
| `Makefile` | Shortcuts | `install`, `test`, `lint`, `ingest`, `dbt`, `contract`, `fixture-warehouse`, `verify`, `docker-verify`, `docker-test`, `clean` |
| `Dockerfile` | Image | python:3.12-slim, no toolchain, `.[docker]`, non-root uid 10001, `/app/data`, default `python -m airq.pipeline` |
| `docker-compose.yml` | Live chain | `ingestion` (builds `airq:local`, runs the pipeline) → `dbt` (same image, `service_completed_successfully`, volume `airq_data`, runs `dbt build && datacontract test`); optional `.env` |
| `docker-compose.test.yml` | Deterministic override | Replaces only the ingestion command with `scripts/build_fixture_warehouse.py` |

### 5.2 `airq/` — the ingestion package

| File | Role | Key content |
|---|---|---|
| `__init__.py` | Package marker | `__version__ = "0.1.0"` |
| `config.py` | Settings | Frozen `Settings` from env vars with `ConfigurationError` validation; `.env` loading; `PROJECT_ROOT`; default country `MA`, history 7 days, max pages 10 |
| `extract.py` | HTTP layer | `Sensor`, `OpenAQClient` (header, timeout, bounded retries, `429` + `Retry-After`, pagination), `list_locations` (IDs or country), `list_sensors`, `get_measurements`, `discover_sensors`, `default_window`, `OpenAQError` |
| `transform.py` | Normalization | `Observation` (the grain), `normalize_measurements` (rejects, never crashes), value range 0–10 000, supported parameters, UTC parsing, `SHA-256` business key, in-memory dedup |
| `validate.py` | Fast gate | `ValidationResult` (total/invalid/rate), `DataQualityError`, `validate_observations` (empty blocked; > 20 % invalid blocked) |
| `load.py` | Persistence | `RAW_TABLE = raw.openaq_measurements`, `CREATE_RAW_TABLE` (PK `observation_id`, NOT NULLs), `connect`, `ensure_raw_table`, `upsert_observations` (transactional insert/update by key → `(inserted, updated)`), `count_observations` |
| `pipeline.py` | Orchestration | `run(settings)` = discover → fetch → normalize → validate → count before → upsert → count after (refuses a decrease) → summary; `main()` with `--output-json`; never prints the API key |

### 5.3 `dbt/` — transformation

| File | Role | Key content |
|---|---|---|
| `dbt_project.yml` | Project config | name `airq`, profile `airq`, paths, staging=view, marts=table, `target-path: ../target` (deprecated warning in dbt 1.12, see §9) |
| `profiles.yml` | Connection | DuckDB, `path: {{ env_var('AIRQ_DUCKDB_PATH', 'warehouse.duckdb') }}`, schema `main`, 1 thread |
| `models/sources.yml` | Source declaration | `raw.openaq_measurements` with source tests (`not_null` ×6, `unique` on `observation_id`) |
| `models/staging/stg_openaq_measurements.sql` | Typed staging | Explicit casts for every column; `lower(trim(parameter))`; removes no row |
| `models/staging/stg_openaq_measurements.yml` | Staging tests | `not_null` ×8, `unique` on `observation_id`, `accepted_values` on `parameter` |
| `models/marts/latest_air_quality_by_location.sql` | Mart | Latest measurement per `(location_id, parameter)` (`qualify row_number()`) |
| `models/marts/marts.yml` | Mart tests | `not_null` on location_id, parameter, value, measured_at |

### 5.4 `contracts/`

| File | Role | Key content |
|---|---|---|
| `openaq.yaml` | ODCS v3.2.0 contract v1.0.0 | DuckDB server `${AIRQ_DUCKDB_PATH:-warehouse.duckdb}`, schema `raw`; 15 properties (types, required, unique, primaryKey, enums); 3 SQL quality rules under the schema object; team + purpose/usage |

### 5.5 `tests/`

| File | Role |
|---|---|
| `fixtures/openaq_location.json` | Real-shaped location 2178 "Del Norte" + sensor 3920 (pm25, µg/m³) |
| `fixtures/openaq_measurements.json` | Two valid pm25 rows (2026-11-16T08:00Z, 09:00Z) with UTC + local timestamps |
| `test_config.py` | Key required, IDs parsed, bad ID rejected (3 tests) |
| `test_extract.py` | Discovery, bounded window + pagination, HTTP error surfaces, session typing (4) |
| `test_transform.py` | Valid preserved, duplicates deduped, negative rejected, missing timestamp rejected (4) |
| `test_load.py` | Two runs = same rows; PK blocks duplicates (2) |
| `test_validate.py` | Valid pass, empty blocked, negative counted, >20 % blocks (4) |
| `test_pipeline.py` | Full chain on fake HTTP: two runs, same `warehouse_rows` (1) |
| `test_contract.py` | CLI present, valid warehouse passes (46 checks), corrupted warehouse fails (3) |

### 5.6 `scripts/`

| File | Role |
|---|---|
| `build_fixture_warehouse.py` | Builds a deterministic warehouse (fixed `ingested_at = 2026-11-16T12:00Z`) from the fixtures; prints `(inserted, updated)`; used by CI and by the Compose test override |

### 5.7 `docs/`

| File | Role |
|---|---|
| `architecture.md` | Current data flow diagram, design decisions (hierarchy, business key, idempotent loading, validation boundaries), planned next stages (Open-Meteo, dlt, snapshots, monitoring, orchestration, dashboard, AWS) |
| `contributing.md` | Branch/PR flow (never push to main, except the documented bootstrap), local checks, team expectations, the expected protection rules |

### 5.8 `.github/workflows/`

| File | Role |
|---|---|
| `ci.yml` | The `validate` job: checkout → Python 3.12 → `.[dev]` → ruff → pytest+coverage → fixture warehouse + dbt build + datacontract test → upload `target/` artifacts |

### 5.9 `resources/` (local, ignored — do not publish)

| Item | Role |
|---|---|
| `Projet DataOps.pdf` | The course brief (mission, expected showcase, example pipelines — the air-quality example is exactly AirQ's shape) |
| `first_livery.pdf` | **Part 1 requirements** (problématique, sources, 3 questions, architecture, innovation) + **Part 2 brick list** + team rules |
| `base/` | The shop/orders reference repo used as the class guide (see §1 mapping table) |

---

## 6. How everything is linked together

### 6.1 Runtime data flow

```
.env / environment
      │  (OPENAQ_API_KEY, OPENAQ_LOCATION_IDS, OPENAQ_COUNTRY_CODE,
      │   AIRQ_HISTORY_DAYS, AIRQ_MAX_PAGES, AIRQ_DUCKDB_PATH)
      ▼
airq.config.Settings.from_env()
      │
      ▼
airq.pipeline.run(settings)
      ├── airq.extract.discover_sensors(OpenAQClient)
      │       └── GET /locations/{id} → /locations/{id}/sensors
      ├── for each sensor: airq.extract.OpenAQClient.get_measurements()
      │       └── GET /sensors/{id}/measurements?datetime_from&datetime_to&page
      ├── airq.transform.normalize_measurements(sensor, rows)
      │       └── → [Observation], [rejected]   (SHA-256 observation_id)
      ├── airq.validate.validate_observations(observations)   ← gate 1 (block)
      └── airq.load.upsert_observations(connect(duckdb_path)) ← gate 2 (PK)
              └── raw.openaq_measurements
                        │
                        ▼
        dbt: source raw.openaq_measurements
              └── stg_openaq_measurements (view, typed)
                      └── latest_air_quality_by_location (table)  ← gate 3 (dbt tests)
                        │
                        ▼
        contracts/openaq.yaml --datacontract test--> raw table     ← gate 4 (46 checks)
```

### 6.2 The one business key

`observation_id = SHA256("sensor_id|parameter|measured_at_utc")` is produced in
`airq/transform.py`, enforced as `PRIMARY KEY` in `airq/load.py`, expected by
`contracts/openaq.yaml` (`unique`, `primaryKey`), and tested as `unique`/`not_null`
by dbt (source + staging). Every layer agrees on the same identity, which is why
idempotence holds end-to-end.

### 6.3 One knob: `AIRQ_DUCKDB_PATH`

| Consumer | How it reads the path |
|---|---|
| Local Python run | `airq/config.py` (`os.getenv("AIRQ_DUCKDB_PATH")`, default `warehouse.duckdb`) |
| dbt | `dbt/profiles.yml` → `{{ env_var('AIRQ_DUCKDB_PATH', 'warehouse.duckdb') }}` |
| Data contract | `contracts/openaq.yaml` → `${AIRQ_DUCKDB_PATH:-warehouse.duckdb}` |
| CI | step env `AIRQ_DUCKDB_PATH: ${{ runner.temp }}/warehouse.duckdb` |
| Docker | `AIRQ_DUCKDB_PATH=/app/data/warehouse.duckdb` on the named volume |

Local, CI, Docker and the contract therefore all validate **the same file** in a given
environment — there is no second source of truth for the path.

### 6.4 Where each quality rule runs

| Gate | Where | What it blocks | Negative proof |
|---|---|---|---|
| 1. Python | `airq/validate.py` during ingestion | empty dataset; invalid rate > 20 % | `tests/test_validate.py::test_invalid_rate_above_threshold_blocks_publication` |
| 2. DuckDB PK | `airq/load.py` upsert | any duplicate identity | `tests/test_load.py::test_observation_primary_key_prevents_duplicate_rows` |
| 3. dbt tests | `dbt/models/**.yml` (source + staging + mart) | nulls, duplicates, unsupported parameters | `dbt build` fails (23 nodes) |
| 4. Data contract | `contracts/openaq.yaml` | schema drift + 3 SQL rules on the **raw** table | `tests/test_contract.py::test_contract_rejects_invalid_value` and the Docker corrupted-warehouse run |

### 6.5 Test → CI → Docker link

- `pytest` (21 tests) uses the same fixtures as the CI fixture warehouse and the Docker
  test chain — one set of realistic API payloads, three consumers.
- `make verify` (local) and the CI `validate` job run the same five steps in the same
  order: lint → tests → fixture warehouse → dbt build → contract.
- `docker-compose.test.yml` reuses the same fixture builder so the Docker proof is the
  deterministic twin of the CI proof.

### 6.6 Git / GitHub flow

```
main  (protected: PR required, 1 approval, last-push approval, strict "validate",
       no force push, no deletion, admins included)
  ▲
  └── PR #1  chore/ci-red-proof      → run 43963315901 = failure → merge refused (405)
  └── PR #2  docs/part2-verification-evidence → runs 43965122788, 43968686358 = success
          merge refused (405) until Merie1m approves  ← open, review requested
```

### 6.7 Import / dependency map

```
airq.pipeline ──► airq.config, airq.extract, airq.transform, airq.validate, airq.load
airq.transform ─► airq.extract          (Sensor)
airq.validate ──► airq.transform        (ALLOWED_PARAMETERS)
airq.load ──────► airq.transform        (Observation)
tests/* ────────► airq.* + tests/fixtures/*.json
scripts/build_fixture_warehouse.py ─► airq.extract, airq.load, airq.transform + fixtures
docker-compose.test.yml ─► scripts/build_fixture_warehouse.py + dbt + contracts
.github/workflows/ci.yml ─► pytest, ruff, scripts/build_fixture_warehouse.py, dbt, datacontract
```

---

## 7. Validation runbook

All commands are run from the project root.

### 7.1 Local

```bash
python -m venv .venv && .\.venv\Scripts\Activate.ps1      # Windows (or source .venv/bin/activate)
python -m pip install -e ".[dev]"
copy .env.example .env        # then put a real OPENAQ_API_KEY inside

ruff check .                  # expect: All checks passed!
pytest -q                     # expect: 21 passed
dbt debug --project-dir dbt --profiles-dir dbt   # expect: All checks passed!

$env:AIRQ_DUCKDB_PATH = "$PWD\warehouse.duckdb"             # or an explicit temp path
python scripts/build_fixture_warehouse.py                   # expect: (2 inserted, 0 updated)
dbt build --project-dir dbt --profiles-dir dbt              # expect: PASS=23 WARN=0 ERROR=0
$env:PYTHONUTF8='1'; datacontract test contracts/openaq.yaml --server local
                                                            # expect: 46 checks, valid
python -m airq.pipeline       # live run (needs the key); run it twice → same row count
```

### 7.2 Docker, deterministic (no API key)

```bash
docker compose -f docker-compose.yml -f docker-compose.test.yml up --build
# expect: ingestion "(2 inserted, 0 updated)" → dbt PASS=23 → contract 46 checks → exit 0
docker compose -f docker-compose.yml -f docker-compose.test.yml up
# expect: ingestion "(0 inserted, 2 updated)" → same dbt/contract → exit 0  ← idempotent
docker compose -f docker-compose.yml -f docker-compose.test.yml run --rm \
  --entrypoint python dbt -c "import duckdb,os;print(duckdb.connect(os.environ['AIRQ_DUCKDB_PATH']).execute('select count(*) from raw.openaq_measurements').fetchone()[0])"
# expect: 2
docker compose -f docker-compose.yml -f docker-compose.test.yml run --rm --entrypoint id dbt
# expect: uid=10001(airq)
```

### 7.3 Docker, live (needs the key)

```bash
copy .env.example .env    # put OPENAQ_API_KEY=...
docker compose up --build
# expect: ingestion → dbt build → contract, exit 0; run twice → same row count
```

### 7.4 GitHub

- Push any branch and open a PR → the `validate` job runs (checks: Ruff, pytest,
  fixture warehouse + dbt + contract).
- A red PR cannot be merged (HTTP 405, *"Required status check \"validate\" is
  failing"*) — proven by PR #1.
- A green PR without an approval cannot be merged (HTTP 405, *"New changes require
  approval from someone other than the last pusher"*) — proven by PR #2.

---

## 8. Evidence index

| Claim | Proof | How to reproduce |
|---|---|---|
| Lint clean | `ruff check .` → "All checks passed!" | §7.1 |
| 21 tests pass | `pytest -q` → `21 passed` | §7.1 |
| dbt healthy | `dbt debug` → "All checks passed!" | §7.1 |
| dbt build green | `PASS=23 WARN=0 ERROR=0 SKIP=0 TOTAL=23` on a fresh warehouse | §7.1 / §7.2 |
| Contract valid | `datacontract test` → 46 checks, "Data contract is valid" | §7.1 / §7.2 |
| Contract lint (ODCS) | `datacontract lint contracts/openaq.yaml` → 1 check passed | local |
| Contract **blocks** bad data | corrupted warehouse → "Measurements must not be negative", exit 1 | §7.2 (bad.duckdb recipe in `tests/test_contract.py`) |
| Idempotent ingestion (unit) | `tests/test_pipeline.py::test_pipeline_is_idempotent` | `pytest -q` |
| Idempotent ingestion (Docker) | run 1 `(2 inserted, 0 updated)` → run 2 `(0 inserted, 2 updated)`, `RAW_ROWS=2` | §7.2 |
| Tables created | `raw.openaq_measurements`, `main.stg_openaq_measurements`, `main.latest_air_quality_by_location` | §7.2 row-count command (information_schema) |
| Non-root container | `id` → `uid=10001(airq)` | §7.2 |
| Failure propagates (dbt) | failing dbt service → `docker compose up` exit 1 | §7.2 (override `AIRQ_DUCKDB_PATH` to a missing file) |
| Failure propagates (contract) | contract exit 1 on invalid data inside the image | §7.2 |
| CI green on main | run `43962686427` (push, main) → success | GitHub → Actions |
| Red PR blocked | PR #1 → run `43963315901` = failure; merge → HTTP 405 | PR #1 (closed) |
| Review rule enforced | PR #2 → merge → HTTP 405 *"New changes require approval from someone other than the last pusher"* | PR #2 (open) |
| Protection configured | API: `validate` strict, 1 approval, last-push approval, no force push/deletion | `GET /repos/Haroun-MH/airQ/branches/main/protection` |
| No secrets in Git | `.env` absent (template only), dummy `"secret"` in tests, `resources/` and `*.duckdb` ignored | `git ls-files`, `git check-ignore -v resources` |
| OpenAQ requires a key | `GET https://api.openaq.org/v3/locations?limit=1` without a key → HTTP 401 | `curl -i` on that URL |
| OpenAQ live-tested with a real key | `GET /locations?iso=MA` → HTTP 200, headers `X-RateLimit-Remaining=59/Limit=60`; 5 MA locations | §3.14 step 1 |
| Idempotence on **real** data | run 1 `501 inserted, 0 updated` → run 2 `0 inserted, 501 updated`, warehouse rows 501 in both runs | §3.14 steps 2–3 |
| Full chain on the live warehouse | `dbt build` PASS=23 WARN=0 ERROR=0; `datacontract test` → 46 checks valid | §3.14 step 4 |
| Observed frequency measured | 3 active MA sensors, all hourly: median gap exactly 1.0 h (167 obs / 166 h) | §3.14 step 5 |

---

## 9. Open items

| # | Item | Why it matters | Where it is tracked |
|---|---|---|---|
| 1 | **Merge PR #2** — needs `Merie1m`'s approval (branch protection forbids self-approval) | `main` still carries the old `--abort-on-container-exit` wording until it merges; PR #2 carries the fix and all evidence | PR #2 (open, review requested) |
| 2 | ~~Live OpenAQ run~~ **Closed 2026-11-17**: real key used, two live runs with an unchanged row count (501), observed frequency hourly (median 1.0 h), full chain green on the live warehouse | Done — see §3.14 and `README.md` → *OpenAQ update frequency* | ✔ |
| 3 | **Second source** (Open-Meteo thin client + fixture + one model) | Satisfies "2 sources minimum" for the Part 1 defense; natural Part 3 opener | §2.2, roadmap in `docs/architecture.md` |
| 4 | **Second contributor** — `Merie1m` owns a brick in a dedicated PR (Git history must show it) | Team rule "chacun touche au moins 2 briques" | §2.6 |
| 5 | **Cleanup (non-blocking)**: `pandas`/`pandera` are declared in the `dev` extra but unused (validation is hand-written in `airq/validate.py`); `dbt_project.yml` uses the deprecated `target-path` (dbt 1.12 suggests `--target-path`/`DBT_TARGET_PATH`) | Smaller install, future-proof dbt | `pyproject.toml`, `dbt/dbt_project.yml` |
| 6 | Later deliveries: dlt incremental + dbt snapshots, stuck-sensor monitoring, Prefect/Airflow, dashboard + health page, LLM daily summary, AWS | Out of Part 2 scope by design | `docs/architecture.md`, `tasks.md` (hors périmètre) |
