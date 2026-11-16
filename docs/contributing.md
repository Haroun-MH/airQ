# Contributing to AirQ

## Branch and pull-request flow

1. Never push directly to `main` (the initial repository bootstrap commit is the only
   exception; every later change goes through a pull request).
2. Create a focused branch: `feature/...`, `fix/...`, or `docs/...`.
3. Keep one logical change per pull request.
4. Run the local checks before requesting review.
5. Open a pull request against `main`.
6. A teammate must approve it and CI must be green.

Suggested local checks:

```bash
ruff check .
pytest
python scripts/build_fixture_warehouse.py
dbt build --project-dir dbt --profiles-dir dbt
datacontract test contracts/openaq.yaml --server local
```

## Team expectations

- Each team member should contribute to at least two project foundations.
- Git history must make the ownership of each change visible.
- Every contributor must be able to explain every committed line.
- AI assistance is allowed, but the team remains responsible for correctness and review.

## Branch protection expected on `main`

- Pull request required.
- At least one approving review.
- `CI / validate` status check required.
- Force pushes and deletion disallowed.
