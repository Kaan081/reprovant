# 05A — Portability to a second independent application (Flask/SQLAlchemy)

**State:** prepared; live verification NOT YET RUN. No product advantage established.

## External target and risk boundary

Public educational sample: `soymattheus/Study---API-for-asynchronous-processing`, pinned to commit
`509eda4df11d0a79b314494104a7e60aa176f693`. Unlike the previous Django
Eventflow experiment, this is Flask + Flask-SQLAlchemy + Celery + PostgreSQL + Redis.
The GitHub workflow clones the pinned source into its **disposable** runner; our repo
contains no copied sample source and does not modify the upstream checkout.
No user data or production credentials are permitted.

The example's `process_job` sets `status=RUNNING`, increments `attempts`, and later
sets `status=SUCCESS`, without a check that the job was already `SUCCESS`.
**Hypothesis** (not yet observed by this workflow): manual duplicate dispatch on
one completed job increments a persisted attempts counter from 1 to 2, while its
state stays `success`. The actual `perform_job` is a demo return value: attempts
is **not** evidence that money, email, or any real external side effect duplicated.
Manual dispatch is **not** broker redelivery, ACK loss, or worker crash.

## Design

The manual `.github/workflows/external-flask-job-portability-05a.yml` uses two
separate PostgreSQL 16 + Redis 7 + actual Celery worker jobs, one for ordinary
pytest and one for Reprovant. Both use one app-specific `JobScenario` for the
same environment setup, first positive control, second dispatch and observations.
This shared scaffold is disclosed and **must not be credited to Reprovant**.
Both enforce the same Git SHA, disposable DB/Redis endpoints, worker ping,
Celery non-eager, two distinct successful task IDs and exact before/after values.

- `pytest`: two ordinary tests; one passes positive-control, one intentionally
  fails with a named invariant marker. The classifier rejects errors, skipped
  tests, extra tests, wrong exit status, missing snapshot or unexpected failure.
- `reprovant`: unchanged `ReplayContract` core, `expected_state='success'` and
  `baseline_effects={'attempts':1}`, with **zero permitted growth**.
- `compare`: requires both expected RED statuses and matching state/counter
  snapshots; otherwise returns `INCONCLUSIVE` and fails CI.

Expected only **if actually observed**:
`VERIFIED_PYTEST_RED`, `VERIFIED_REPROVANT_RED`, and
`VERIFIED_SECOND_APP_PARITY`.

## What this does not demonstrate

This is an educational second app, not a production system or a client-sanctioned
integration. A success would demonstrate portable *core evaluation* in a second
framework, **not** independent adapter portability, elapsed engineering time,
ease of onboarding, generalized idempotency protection, a real side-effect bug,
or a superior value proposition against pytest. Do not infer buyer demand.

### Measure honestly

For an engineering-cost comparison, count all application-specific lines
(`scenario.py` plus setup/workflow), plain pytest/classifier lines, Reprovant
adapter/runner lines, shared reusable core lines separately. Track actual human
integration hours *prospectively* on the next app; historical time estimates
cannot be reconstructed accurately.

## Execution (after local PR review)

1. Run local tests and PR CI.
2. Trigger workflow from the PR branch, not from `main`.
3. Inspect both job artifacts and parity JSON; if any inconclusive, fix the
   minimal real cause in a separate commit before merging.
4. Only merge once source provenance and reports are verified. Keep all
   external code in isolated test infrastructure, never production.
