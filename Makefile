.PHONY: install test lint ingest dbt contract fixture-warehouse verify docker-verify docker-test compose clean

install:
	python -m pip install ".[dev]"

test:
	pytest

lint:
	ruff check .

ingest:
	python -m airq.pipeline

dbt:
	dbt build --project-dir dbt --profiles-dir dbt

contract:
	datacontract test contracts/openaq.yaml --server local

fixture-warehouse:
	python scripts/build_fixture_warehouse.py

verify: lint test fixture-warehouse dbt contract

docker-verify:
	docker compose up --build --abort-on-container-exit

docker-test:
	docker compose -f docker-compose.yml -f docker-compose.test.yml up --build --abort-on-container-exit

compose: docker-verify

clean:
	rm -rf target dbt/logs logs .pytest_cache .ruff_cache
