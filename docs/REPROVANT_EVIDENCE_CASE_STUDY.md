# Reprovant — external evidence case study

**Status:** research / open engineering evidence, **NOT** a production-ready universal validator or a paid SaaS.

Reprovant is a working name for an evidence-first study of retry, idempotency, durable effects, and terminal-state acceptance in existing Python worker applications. The installed Python distribution and import interface remain `python-pipeline-acceptance` and `pipeline_acceptance` for now. Renaming the GitHub repository does **not** change the published package name.

## Verified evidence ledger (2026-11-01)

| Experiment | Target | What was actually observed | Boundary |
|---|---|---|---|
| **02A** independent pytest baseline | `timur-rimsky/api-airflow-postgres-etl-pipeline` at `28a65c42a9bdbcc6d2ed08038311ae22e9d66d11` | GitHub Actions run [41316392717](https://github.com/Kaan081/python-pipeline-acceptance/actions/runs/41316392717): 4/4 PASS on disposable PostgreSQL 16 with **ordinary pytest**, not the Reprovant package | Educational upstream, sequential replay and seeded FK rollback. No customer bug found, no comparative product advantage. |
| **03A** live-worker RED | `juneja-varun/eventflow` at `c08455d626d5e1c316d932c4da0652086fb1b19e` | Run [41318068548](https://github.com/Kaan081/python-pipeline-acceptance/actions/runs/41318068548): two separate Celery task IDs succeeded; manually re-enqueued order regressed from `shipped` to `confirmed`, and `order.confirmed` was published twice | Real Celery worker, Redis and PostgreSQL, **manual re-enqueue**; *not* broker redelivery after ACK loss or a worker crash. Upstream demo bug, not customer incident. |
| **03B** guarded GREEN | Same pinned Eventflow source with only `orders/tasks.py` changed inside a disposable test checkout | Run [41319161073](https://github.com/Kaan081/python-pipeline-acceptance/actions/runs/41319161073): both tasks executed, the order remained `shipped`, and only one `order.confirmed` event was seen; wrapper classified `GUARDED_GREEN` | Standard Django conditional state transition. No Redis/DB distributed transaction, no payment integration, no production acceptance. |

### What 03A → 03B demonstrates

A targeted failure can be reproduced in a separate Celery worker against a real PostgreSQL and Redis test environment, and a narrow application-specific repair can be checked under the same manual dispatch conditions. The two observed symptoms can stem from the same missing state guard; they are not evidence of two independent root causes.

The source and regression checks in this repo **do not automate discovery of arbitrary business invariants**. Application-specific tests were written by the experimenter. There is no measured advantage over an engineer using AI + pytest, Celery and ordinary Django/SQLAlchemy patterns.

## Explicitly NOT established

- Production incident or paid customer adoption.
- Automatic diagnosis, automatic repair, or independent customer-defined acceptance.
- Real worker loss, lost ACK, broker-triggered redelivery, or outbox guarantees.
- General compatibility with customer databases or deployment without source-specific adapters.
- Commercial willingness to pay, time saved, correctness advantage, or product-market fit.

## Research decision

**Product build: HOLD.** Keep this repository as a case study. Only continue reusable-tool development after (a) at least one real owner-approved case, (b) benchmark against baseline AI + pytest, and (c) evidence of material repeated effort savings or a bug missed by ordinary tools. An explicitly scoped test-and-repair service is a separate, unvalidated commercial hypothesis.

External repositories remain owned by their respective authors; no upstream code is distributed here. Follow each upstream license/terms before reproducing or distributing tests.
