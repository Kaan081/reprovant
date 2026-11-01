"""Run GREEN and RED negative control against disposable SQLite (no Docker).

Run: python examples/replay_contract_demo.py
Requires: pip install -e .
"""
import json

from pipeline_acceptance.guarded import process_once
from pipeline_acceptance.legacy import process_with_bug, stale_running_update_with_bug
from pipeline_acceptance.replay_contract import ReplayContract, Snapshot, evaluate_replay
from pipeline_acceptance.storage import get_effect_count, get_status, isolated_engine, seed_job


def scenario(kind):
    with isolated_engine() as engine:
        job_id, key = "demo-job", "demo:effect"
        seed_job(engine, job_id)
        legacy = kind != "guarded"
        process = process_once if not legacy else process_with_bug
        process(engine, job_id, key, "result")

        class Adapter:
            def is_disposable(self):
                # This engine is owned by isolated_engine() above, not arbitrary DB credentials.
                return engine.dialect.name == "sqlite"

            def observe(self):
                return Snapshot(get_status(engine, job_id), {
                    "business_effects": get_effect_count(engine, key, legacy=legacy),
                })

            def dispatch(self):
                if kind == "state_regression":
                    stale_running_update_with_bug(engine, job_id)
                else:
                    process(engine, job_id, key, "result")

        contract = ReplayContract(kind, "SUCCEEDED", {"business_effects": 1})
        return evaluate_replay(Adapter(), contract)


if __name__ == "__main__":
    result = {name: scenario(name) for name in ("guarded", "duplicate_effect", "state_regression")}
    print(json.dumps(result, indent=2))
    assert [result[name]["status"] for name in result] == ["GREEN", "RED", "RED"]
