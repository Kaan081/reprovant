"""Execute one 05A verification method; unexpected outcomes fail closed."""
from __future__ import annotations

import argparse
from pathlib import Path

from pipeline_acceptance.replay_contract import ReplayContract, Snapshot, evaluate_replay
from experiments.portability_05a.scenario import JobScenario, PIN
from experiments.portability_05a.verdict import plain_pytest, reprovant, save


class ReprovantAdapter:
    """The *only* 05A module that bridges common app observations to the core."""
    def __init__(self, scenario: JobScenario):
        self.scenario = scenario

    def is_disposable(self):
        return self.scenario.is_disposable()

    def observe(self):
        state = self.scenario.observe()
        return Snapshot(state=state["state"], effects={"attempts": state["attempts"]})

    def dispatch(self):
        self.scenario.dispatch()


def run_reprovant() -> dict:
    scenario = JobScenario()
    scenario.prepare()
    contract = ReplayContract("job-no-extra-processing", "success", {"attempts": 1})
    evaluation = evaluate_replay(ReprovantAdapter(scenario), contract)
    return reprovant({"source_pin": PIN, "contract_report": evaluation,
                      "worker": scenario.attestation})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--method", required=True, choices=["pytest", "reprovant"])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--snapshot", type=Path)
    parser.add_argument("--junit", type=Path)
    parser.add_argument("--pytest-exit", type=int)
    args = parser.parse_args()
    try:
        if args.method == "reprovant":
            report = run_reprovant()
        else:
            import json
            report = plain_pytest(json.loads(args.snapshot.read_text(encoding="utf-8")),
                                  args.junit.read_text(encoding="utf-8"), args.pytest_exit)
    except Exception as exc:
        report = {"method": args.method, "status": "INCONCLUSIVE",
                  "reason": "experiment_exception", "error_type": type(exc).__name__}
    save(args.output, report)
    print("PORTABILITY 05A:", args.method, report["status"])
    expected = "VERIFIED_PYTEST_RED" if args.method == "pytest" else "VERIFIED_REPROVANT_RED"
    return 0 if report["status"] == expected else 2


if __name__ == "__main__":
    raise SystemExit(main())
