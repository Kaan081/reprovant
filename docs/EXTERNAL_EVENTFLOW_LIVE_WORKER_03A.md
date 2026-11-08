# External Eventflow 03A — actual Celery worker, manual duplicate dispatch

**Status: prepared; NOT executed on GitHub Actions.** A green workflow can only be reported after the user executes it. The local classifier unit tests are not a live database/worker result.

## Why
The previous Eventflow Django tests called the task function directly. The upstream conftest sets `CELERY_TASK_ALWAYS_EAGER = True`, so they do not demonstrate Redis broker → independent Celery worker execution. Upstream `orders/tasks.py` writes `CONFIRMED` and emits `order.confirmed` without checking `Order.status`; previous source-level tests exposed stale state and repeated events.

03A tests the *same concrete failure family* with a separately running actual Celery worker, PostgreSQL 16 and Redis 7, using the unmodified upstream commit `c08455d626d5e1c316d932c4da0652086fb1b19e` from https://github.com/juneja-varun/eventflow (MIT license).

## Sequence and positive control
1. Require a unique disposable GitHub-hosted PostgreSQL DB named `ppa_eventflow_worker_ci`, localhost and Redis DB 14; otherwise refuse to mutate DB.
2. Require a real worker to respond to a Celery broker ping, reject Celery eager mode.
3. Open Redis pubsub subscription before creating a dummy order.
4. Submit `process_new_order` via `apply_async`, collect the first `order.confirmed` event and verify `CONFIRMED`.
5. Advance the same order to `SHIPPED` with a separate SQL update.
6. **Manually enqueue a second task** for the same order ID, via real Redis broker and real worker. Observe final order status and count of `order.confirmed` publishes.

`OBSERVED_RED` only if: first task succeeded with exactly one confirmation event, second task succeeded, final order status **regressed** to `confirmed` AND two `order.confirmed` events were observed. This returns process exit 0 for a successful *failure reproduction*; do not read this as a successful business contract! `NOT_REPRODUCED` or any partial/setup failure returns exit 2 and a non-green workflow. `report.json` captures observed states and task IDs; `worker.log`, `outcome.txt`, and `provenance.txt` are uploaded even on failures.

**Important:** Two deliberate `.apply_async()` calls create *different* Celery task IDs. This is NOT automatic Redis redelivery, a process kill, a post-commit crash, or ACK loss. The upstream Celery task uses default acknowledgement settings; real ACK-loss behavior requires a separate explicitly designed experiment. A Redis pubsub message does not establish durable exactly-once notification delivery.

## Execution
Apply the sibling patch in the root of your `kaanbartubozkurt/reprovant` repo, check diff, commit to a feature branch and verify manual workflow visibility on `main`. Then run via:

```powershell
gh workflow run external-eventflow-live-worker-manual.yml --repo kaanbartubozkurt/reprovant --ref main
```

Download the resulting artifact using its run ID and inspect `report.json`, `outcome.txt`, and `worker.log`. If the job fails at worker readiness, Redis subscription, migration or dependency installation, report `INCONCLUSIVE`; do not claim an upstream regression without a passing positive control.

## Why this is not yet a product GO
This is a **pytest/SQL/Django/Celery baseline experiment** in a public *demo*, not a verified customer incident. The existing `pipeline_acceptance` v0.2.1 code is not used. It cannot prove a general adapter, differentiating fault-injection engine, developer time savings, or willingness to pay. Next technical gate is an owner-approved real worker crash / redelivery scenario with an equivalent plain-agent+pytest baseline, not an arbitrary increase in synthetic demo complexity.
