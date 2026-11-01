# Verification evidence — 2026-11-01, v0.2

## Local sandbox (assistant environment)

- Python: 3.13.5
- SQLAlchemy: 2.0.50
- pytest: 9.0.2
- Windows: User previously ran **8 passed, 1 skipped** on 0.1 using Python 3.13. This is USER-REPORTED, not independently re-executed by the assistant.
- Local version 0.2 command: `PYTHONPATH=src python -m pytest -q`
- Result: **26 passed, 1 skipped** in local Linux container (SQLite + security preflight). See latest command output rather than treating this document as a live test result.
- PostgreSQL runtime: **not available / not tested** in the assistant's container. Postgres-specific concurrency test **skipped**.
- Wheel build: `python -m pip wheel --no-deps --no-build-isolation . -w /mnt/data/pipeline_buildcheck` succeeded (v0.2). No hosted CI run verified.

## Experiment output

- `python -m pipeline_acceptance.demo --output ...` produces a synthetic SQLite evidence report.
- `docs/example-sqlite-evidence.json` contains synthetic example data, no connection credentials or user data. It is not a production incident report.
- Legacy red tests: run separately with `python -m pytest -q tests/legacy_red_cases.py`; the tests are intentionally expected to fail. They are NOT included in the default suite.

## Meaning

**Proven locally:** toy DB-level idempotency deduplication, monotonic successful state under sequential stale update, rejected invalid-data flag; rejected disallowed DSNs before network access; SQL parameter binding; no DSN in generated report; local wheel builds.

**Unproven:** PostgreSQL concurrency behavior, multi-process races, broker ACK semantics in a real queue, production isolation guarantees, external side-effect exactly-once semantics, user-provided validation logic, customer adoption, pricing, business ROI, superiority to pytest+SQLAlchemy.

Risk note: the SQLite demo is not evidence of PostgreSQL locking behavior. Do not use test databases shared with others.
