# Eventflow 03B — scoped RED -> GREEN candidate, NOT production repair

**Status:** Prepared only. The source-guard patch has NOT been exercised in hosted PostgreSQL/Redis/Celery yet. Do not claim a verified GREEN until `eventflow-guarded-green-03b-evidence/report.json` is read and independently reviewed.

## Existing independent RED
03A manual GitHub Actions run `41318068548` exercised two explicit Celery `.apply_async()` calls against pinned MIT-licensed `juneja-varun/eventflow` SHA `c08455d626d5e1c316d932c4da0652086fb1b19e`: independent actual worker, PostgreSQL16, Redis7, eager disabled. Initial order CONFIRMED and one event. After simulated legitimate SHIPPED transition, second explicit dispatch set it back to CONFIRMED and emitted a second `order.confirmed`. 03A `status=OBSERVED_RED`. This is **manual second dispatch**, not broker redelivery or worker crash.

## Smallest targeted repair attempt
Replace only the isolated upstream checkout's `orders/tasks.py` with `tasks_guarded.py`; leave the real upstream untouched and with pinned HEAD. Use `UPDATE ... WHERE status=PENDING` as an atomic compare-and-set and publish an event only when an actual transition occurred. The same 03A probe exercises a separate real Celery worker and the same observable PostgreSQL/Redis contract. The plain `run_probe.py` classifies the expected guarded behavior as `NOT_REPRODUCED` and exits 2; this new standalone 03B oracle **explicitly requires** that exact verdict, positive control, distinct task IDs, one event, `SHIPPED` after second dispatch, real worker, no eager mode, original pinned SHA, and a one-file change. The 03B classifier alone can emit `GUARDED_GREEN`.

## Important scope boundary
This guard *does not atomically couple* the PostgreSQL transition and Redis pub/sub publish. A worker death between SQL commit and event publish can still lose the event; concurrent failure cases and actual ACK-loss have not been covered. Redis pub/sub also does not guarantee durable delivery. This is not an exactly-once proof, production certification, customer fix, or product differentiation. Upstream authors have not reviewed this trial candidate.

## No false commercial claim
03A and this 03B use **normal Django ORM, pytest, Celery and PostgreSQL**; `pipeline_acceptance` package is NOT used. If RED -> GREEN is demonstrated, it validates the scoped engineering service/test case, not the commercial need for a standalone PPA package. No SaaS roadmap expansion until another genuinely independent application and a buyer/baseline gate.

## Execution after reviewed PR merge
1. Run `python -m pytest -q experiments/eventflow_guarded/test_classifier.py` (unit classifier only).
2. Trigger manual Actions workflow `external-eventflow-guarded-green-manual.yml` on main.
3. Download `eventflow-guarded-green-03b-evidence` artifact and inspect `report.json`, `probe.json`, `outcome.txt`, `changed_files.txt`, `worker.log`, `provenance.txt` and SHA files.
4. `GUARDED_GREEN` means only this manual duplicate dispatch path passed after the one-file candidate guard.
