# External acceptance experiment 01 — Eventflow

Status: **PREPARED / NOT EXECUTED ON UPSTREAM**. Do not report an external PASS/FAIL until the manual GitHub Actions run and artifacts are inspected.

- Upstream: https://github.com/juneja-varun/eventflow
- Revision: `c08455d626d5e1c316d932c4da0652086fb1b19e` (pinned).
- License: upstream MIT, copyright Varun Juneja 2026. No upstream code included in this repository. Repository is checked out for testing only.
- Runtime: Django 5, Celery, PostgreSQL 16 test DB on GitHub-hosted disposable runner.
- Contract: normal pending order confirmation is a **positive control**, plus shipped-order status monotonicity and no repeated confirmation event on a confirmed-order replay.
- Source-reading hypothesis: upstream `orders/tasks.py` saves `confirmed` for any valid order without prior-status guard and publishes `order.confirmed` on every invocation. Upstream tests cover normal cases, not these re-delivery contracts. This is **not** a claim of real customer incident or confirmed business requirement.

## Execution

Manually dispatch `.github/workflows/external-eventflow-manual.yml` in GitHub Actions. Workflow checks out external upstream by exact SHA, runs acceptance against upstream imports on a disposable PostgreSQL DB without modifying upstream code, then uploads `junit.xml` and `report.json` even if contract FAILs.

`report.json` is `PASS` only if all expected cases are collected and pass, the positive control passes, upstream SHA matches, and pytest exits 0. It is `FAIL` only for an observed contract failure with a passing positive control. Any missing tests, errors, skips, SHA mismatch, test infrastructure failure or absent report is `INCONCLUSIVE`. A contract FAIL makes the **manual workflow red by design**; ordinary CI is unaffected.

## Expected outcomes and limits

Reading the pinned upstream code suggests both contract tests will FAIL; actual outcome is **not verified**. A FAIL means *our proposed acceptance contract is violated on the pinned demo*, not that a production incident occurred. Contract assumptions (e.g. shipped never moves back to confirmed, replay must not duplicate a notification) need owner validation before changing upstream behavior.

**No time-saving claim**: writing the same assertions directly with `pytest-django` is a baseline that may be just as fast or faster. This experiment tests whether we can capture real external behavior safely at all, not superiority to an AI agent or an ability to charge customers.

## Next evidence gate

1. Inspect real manual Actions run and evidence artifacts; diagnose INCONCLUSIVE before interpreting FAIL/PASS.
2. Obtain upstream owner acceptance of the invariants, or select a documented real incident in another project.
3. Compare total engineer time to writing ordinary `pytest-django` tests for exactly the same defect; include infrastructure and integration time.
4. Only then consider a reusable adapter; otherwise keep this as a case study, not a sellable product.
