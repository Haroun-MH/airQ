FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    AIRQ_DUCKDB_PATH=/app/data/warehouse.duckdb

WORKDIR /app

COPY pyproject.toml README.md ./
COPY airq ./airq
COPY dbt ./dbt
COPY contracts ./contracts
COPY scripts ./scripts
COPY tests/fixtures ./tests/fixtures

RUN python -m pip install --upgrade pip \
    && python -m pip install ".[docker]"

RUN mkdir -p /app/data && useradd --create-home --uid 10001 airq \
    && chown -R airq:airq /app

USER airq

CMD ["python", "-m", "airq.pipeline"]
