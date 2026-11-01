# Benchmark 02A — independent pytest baseline before tool integration

**Status: PREPARED / NOT YET RUN AGAINST UPSTREAM.**

Upstream: https://github.com/timur-rimsky/api-airflow-postgres-etl-pipeline
Pinned revision: `28a65c42a9bdbcc6d2ed08038311ae22e9d66d11`.

This is an **educational open-source ETL project**, not a customer system or incident. No repository license was visible in the inspected root. The workflow checks out and executes upstream source without modifying or redistributing it. Stop if the repository terms disallow testing.

## Pre-registered acceptance claims (from upstream README)

1. **Positive control:** A fully runnable ETL iteration persists an audit record and final data.
2. **Replay idempotency:** Running the same input twice produces no additional final rows and marks unchanged rows unchanged.
3. **Dirty data:** Invalid records go to `rejected_users` and the audit counters reconcile.
4. **Atomicity negative control:** Inject a foreign-key failure *inside* the clean/rejected combined write; no partial clean or rejected rows may persist.

The source README already documents these properties and its **own test suite already checks sequential idempotency**. Repeating this claim is not novelty. Invariant #4 is an intentionally **seeded error**, not proof of a real bug. No actual bug is predicted; all four may PASS.

## Experimental design

This is **arm A only:** external ordinary `pytest` tests, `psycopg2`, disposable PostgreSQL 16, a fixed upstream SHA and JUnit artifact. There is **no use of** the `pipeline_acceptance` package; creating its own checks without the framework is allowed. Upstream API fetching is patched to a deterministic single record (the upstream's built-in demo data is still appended). All database writes and source modules other than the fake API call run unmodified.

`PPA_BENCHMARK_DISPOSABLE=YES`, `POSTGRES_DB=ppa_etl_bench02` and local PostgreSQL are required before fixtures issue a destructive `TRUNCATE`. **Never run the tests against an existing database.** The manual GitHub workflow provisions a fresh DB only for this test.

Run **Actions → External ETL pytest baseline (manual experiment) → Run workflow (main)**. Artifact: `external-etl-pytest-baseline-evidence`. Review `pytest.txt`, `junit.xml`, `provenance.txt`, `outcome.txt`.

## Evidence boundaries and later B arm

- Local tests of the syntax and fixture guard do **not** prove upstream behavior. Actual external PASS/FAIL exists only after CI execution.
- Missing pinned SHA, no JUnit, skipped tests, failed positive control, or infrastructure error = **INCONCLUSIVE**, even if a GitHub job is red. Do not infer a real contract violation merely from a red workflow.
- Time savings **cannot** be inferred from lines of code or one sequential run. Two independent, similarly scoped fresh-agent sessions are required; fixing arm A's problems and copying the answer to B would leak information and invalidate a speed comparison.
- Arm B must implement identical four pre-registered tests with the existing `pipeline_acceptance` tool; all special adapters, orchestration, CI and reporting code count toward its integration cost. Keep a fixed up-front decision criterion: at least 30% lower total engineering effort **or** detection of a meaningful problem missed by A, without higher false PASS rate. If B only wraps pytest or duplicates its test logic, report **NO DEMONSTRATED DIFFERENTIATION** rather than a product GO.
- No new feature development or buyer claims until the comparative evidence is available.
