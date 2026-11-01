# Reprovant 05B — source-cost inventory and product gate

**Date:** 2026-11-01
**Source examined:** `Kaan081/reprovant`, `main` at `de26f1a5cede95f53dae0cc3a87d5196696aad6d`
**Status:** source-size audit completed; human labor costs and commercial advantage **NOT MEASURED**.

## Verified technical outcomes (separate from this source audit)

| Experiment | Real CI run | Artifact verdict | Scope |
| --- | --- | --- | --- |
| 04B Eventflow, Reprovant | [41331192111](https://github.com/Kaan081/reprovant/actions/runs/41331192111) | upstream RED, guarded GREEN | Real non-eager Celery/Redis/PostgreSQL; manual duplicate dispatch |
| 04C Eventflow, both methods | [41336778411](https://github.com/Kaan081/reprovant/actions/runs/41336778411) | `VERIFIED_PARITY` | Same original/guarded scenario; pytest equals Reprovant on observed invariants |
| 05A Flask, both methods | [41338574356](https://github.com/Kaan081/reprovant/actions/runs/41338574356) | `VERIFIED_SECOND_APP_PARITY` | Both detect `success/attempts=1` -> `success/attempts=2` |

The 05A result is not proof of a duplicate external effect. `perform_job()` is a demo operation. No natural broker redelivery, ACK-loss or customer production behavior was tested.

## Reproducible accounting method

Run from a checked-out repo root:

```bash
python experiments/cost_audit_05b.py --root . --output cost-audit-05b.json
```

This inventories an **explicit, fixed list** of source files, records each SHA-256, physical lines (including comments/blanks), nonblank lines, and nonblank lines excluding full-line `#` comments. A final newline does not create a new physical line. It fails closed (`INCOMPLETE`, exit 2) for missing/unreadable files. **Counts are not developer hours, code quality, maintainability, or annual cost.** It does not infer which approach is better from LOC.

The table below was checked against source files at the stated GitHub commit. The audit script itself is an additional research tool and **is excluded from the existing integration inventory**.

### Eventflow (Django + Celery)

| Source group | Physical lines | Meaning / attribution |
| --- | ---: | --- |
| Reprovant 04B `run_contract.py` | 218 | App-specific adapter + runner + fail-closed classifier; Reprovant-only |
| Ordinary pytest 04C `test_live.py` + `classify.py` | 243 (123 + 120) | App-specific test + evidence classifier; pytest-only |
| Earlier 03A `run_probe.py` | 190 | Pre-existing environmental/worker probe, reused in both; **not** Reprovant-only savings |
| Parity `compare.py` | 74 | Comparison infrastructure, not attributable to either product |
| Unit tests for 04B + 04C | 316 (144 + 172) | Regression and safety tests, not a method-only cost comparison |
| 04B + 04C workflow YAML | 338 (149 + 189) | Earlier standalone and later four-arm CI; not direct per-method cost |
| 04C design document | 37 | Documentation, not running adapter code |

**Naive direct method-source difference: 218 vs. 243 = 25 physical lines.** It is not evidence of reduced engineering effort: different source layouts, reused 03A code, Reprovant's previously built core, runner-specific setup, and differing evidence obligations are all relevant. No stopwatch or authoring-cost experiment was performed.

### Flask + SQLAlchemy + Celery (second application)

| Source group | Physical lines | Meaning / attribution |
| --- | ---: | --- |
| `scenario.py` | 108 | Application-specific environment, positive control and dispatch shared by both methods |
| `test_live.py` | 35 | Pytest-only acceptance tests and snapshot output |
| `execute.py` + `verdict.py` | 153 (62 + 91) | **Mixed** Reprovant adapter, method dispatch, both classifiers and shared reporting; cannot allocate all to Reprovant |
| `compare.py` | 29 | Comparison infrastructure |
| Unit tests | 132 | Verification maintenance |
| Workflow YAML | 161 | Real Redis/Postgres/Celery setup for both independent jobs |
| 05A documentation | 67 | Research documentation |
| **05A experiment total** | **685** | Research scaffold plus both methods; **not** product adapter size |

Reprovant's reusable v0 core `src/pipeline_acceptance/replay_contract.py` is **169 physical lines**. That is a pre-existing shared library cost, separate from both application integrations. Do not treat the 169 lines as zero when discussing total product maintenance, or charge all 169 afresh for every adoption.

### Important independence/attribution caveat

In 05A, the ordinary pytest **test file** does not call `ReplayContract`. However, `experiments/portability_05a/execute.py` imports the Reprovant core at module import time even when running the pytest results classifier. Thus the orchestrator is not strictly import-independent. A follow-up cleanup can split execution/verification imports without changing the already-observed business behavior; its regression risk must be tested. The shared `JobScenario` is external-app-specific, not a demonstrated reusable adapter.

## Findings and decision

**Demonstrated:** Reprovant's unchanged evaluator can evaluate a replay invariant on a Django sample and a Flask sample with live workers, while ordinary pytest independently detects the same observed violations.

**Not demonstrated:** fewer engineer-hours, lower ongoing CI expense, lower maintenance burden, automagic app integration, portability of application-specific adapters, more defects detected, customer willingness to pay, or production assurance.

**Decision: no generic feature expansion based on 05A.** Before another integration, set an explicit adoption gate: identify one real team/problem with owner permission and a costly recurring regression, then prospectively track (1) setup minutes, (2) app-specific lines and edit files, (3) CI reliability/re-runs, (4) quality of reviewer-usable evidence, (5) actual willingness to adopt/pay. The same person should implement matched plain-pytest and Reprovant tasks under equivalent constraints; report unfavourable outcomes. If the only benefit remains normalized JSON, market that as a narrow evidence/reporting component rather than an autonomous testing framework.

## Audit limitations

- Includes specifically enumerated experiment files, not every line ever written while developing the project.
- Shared/mixed file assignments are disclosed rather than silently apportioned. File line count is descriptive, not a causal time measurement.
- 04B and 04C have historical code reused from 03A. A line added at one stage cannot be represented as fresh labor at every later stage.
- Human effort, setup/cleanup time, review burden and future drift were not instrumented.
- No external client's repository was modified; the second application was a public educational example cloned into disposable CI.
