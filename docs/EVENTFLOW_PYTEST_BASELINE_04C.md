# 04C — Ordinary pytest versus Reprovant on one Eventflow regression

**State:** code prepared, NOT live-verified. Manual GitHub Actions must run on the merged commit before any result claim.

## Hypothesis

An experienced engineer using pytest can reproduce and verify this manually repeated Celery dispatch without a generic replay-contract engine. Reprovant may make the invariant result format more reusable, but **this is not yet shown to reduce integration time or work**.

## Design and controls

The manual `.github/workflows/external-eventflow-pytest-parity-04c.yml` runs **four independent jobs** in a 2×2 matrix (plain pytest / Reprovant, original / guarded).

- All jobs pin `juneja-varun/eventflow` at `c08455d626d5e1c316d932c4da0652086fb1b19e` and use the same exact test-only guarded `orders/tasks.py` replacement, PostgreSQL 16, Redis 7, Python 3.12, separate Celery worker (not eager), disposable environment assertions and task settings.
- Both methodologies reuse already-written *03A environmental helpers* for revision, worker ping, and Redis event collection. This is disclosed shared code, not a hidden Reprovant advantage.
- The plain pytest test is **not** based on `ReplayContract` and does not import `pipeline_acceptance.replay_contract` or `run_contract.py`.
- One module-scoped pytest fixture generates the two dispatches and checks positive control. Exactly two ordinary test cases assert terminal-state preservation and duplicate confirmation absence.
- An original upstream **expected RED** is two *specific failing invariants* in pytest (nonzero pytest exit expected), while guarded source must pass both tests. A missing fixture, unexpected failure, skip, wrong source, or insufficient worker attestation is `INCONCLUSIVE`, not success.
- Reprovant uses the unchanged 04B `run_contract.py` and engine, reexecuted in separate jobs; both JSON formats are independently compared by `compare.py` and each original/guarded result must agree on observed before/after values.

## How to run (only after merge)

```powershell
gh workflow run external-eventflow-pytest-parity-04c.yml --repo kaanbartubozkurt/reprovant --ref main
gh run list --repo kaanbartubozkurt/reprovant --workflow external-eventflow-pytest-parity-04c.yml --limit 3
# After identifying the NEW run ID:
gh run watch <run-id> --repo kaanbartubozkurt/reprovant --exit-status
```

Expected four verdicts: `VERIFIED_PYTEST_RED`, `VERIFIED_PYTEST_GREEN`, `VERIFIED_RED_CONTROL`, `VERIFIED_GUARDED_GREEN`; summary: `VERIFIED_PARITY`.

## What this experiment can and cannot measure

**Can verify:** repeatability of the specific regression detection and protection for two separately provisioned methods, plus explicit fail-closed behavior and evidence parity.

**Cannot conclude:** Reprovant is faster, has less implementation code, is easier to maintain, catches additional bug families, reduces the engineering hours of adapter authoring, or earns customers. Both methods reuse 03A helpers; absolute total code and non-reusable app-specific lines must be separately audited. Runtime comparisons across GitHub-hosted runners are noisy and this workflow does not benchmark developer productivity. No second independent external app was tested.

**Decision:** If ordinary pytest gives equally reliable evidence with lower integration and maintenance cost, do not scale Reprovant as a generic product from this result. Measure migration to one owner-authorized second app and engineering effort next. The 04B RED/GREEN is established separately; 04C must produce its own artifacts before we say it succeeded.
