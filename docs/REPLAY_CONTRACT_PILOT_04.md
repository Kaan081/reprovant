# Reprovant replay contract pilot 04 — **experimental**

## What is real

`pipeline_acceptance.replay_contract` is a small, application-neutral Python API:

1. Caller attests that the adapter runs against a disposable sandbox.
2. Adapter observes a **known-good baseline** state and business-effect counts.
3. Runner performs **one repeat dispatch** through the adapter.
4. Adapter observes the result. The runner checks state preservation and bounded changes in each effect count.
5. Outputs `GREEN`, `RED`, or `INCONCLUSIVE`, including only non-sensitive counts and exception *types*.

**No dynamic module loading, remote database access, broker injection, or automatic bug discovery**. The adapter and environment are the caller's responsibility. This is not a test of ACK loss, worker crash, or externally atomic effects. `is_disposable()` is merely an assertion from the adapter, **not an independent safety guarantee**.

## Run local demonstration

In a checkout with Python >=3.10:

```powershell
python -m pip install -e '.[test]'
python examples/replay_contract_demo.py
python -m pytest -q tests/test_replay_contract.py
```

Expected local output: a guarded `GREEN` case and two known-broken `RED` controls (`duplicate_effect`, `state_regression`) against an isolated in-memory SQLite database. These are **synthetic controls**, not an external app result.

## Adapter contract — normal Python, no new dependency

```python
from pipeline_acceptance.replay_contract import ReplayContract, Snapshot, evaluate_replay

class MyDisposableAdapter:
    def is_disposable(self) -> bool:
        # The caller must verify this explicitly; never point at production.
        return sandbox_was_created_for_this_test

    def observe(self) -> Snapshot:
        return Snapshot(
            state=read_job_state(),
            effects={"confirmation_events": count_confirmations()},
        )

    def dispatch(self) -> None:
        resend_same_job_in_test_broker_and_wait_until_finished()

contract = ReplayContract(
    name="no-duplicate-confirmation-on-replay",
    expected_state="SHIPPED",
    baseline_effects={"confirmation_events": 1},
)
report = evaluate_replay(MyDisposableAdapter(), contract)
```

`read_job_state`, `count_confirmations`, and `resend_same_job_in_test_broker_and_wait_until_finished` above are **app-specific placeholders**. Implement and measure their cost. Failure to attain the baseline makes the result `INCONCLUSIVE` **without dispatching**. Missing/errored observations after dispatch never return GREEN. A business-effect count rising beyond its explicitly allowed growth is RED. Metrics must be numerical counts; raw customer data, credentials and URLs must not appear in snapshots.

## Decision gate — not an automatic product GO

- **Local:** confirm generic runner works and rejects known-broken controls.
- **External:** obtain owner permission and sandbox, freeze upstream SHA, assert an owner-approved business invariant, and compare against a conventional pytest test for the *same* failure.
- **Measure:** full setup / adapter / test / debug / review time, amount of bespoke code and whether the runner catches a problem pytest misses.
- **STOP:** if the adapter is mostly per-app or gives no material saving, leave Reprovant as an engineering case study / scoped QA service. A matching GREEN on an isolated demonstration **cannot** be sold as production acceptance.

**Scope decision:** this contract pilot does not claim to integrate with Prefect, Nautobot, or Eventflow until that integration is actually executed and verified.
