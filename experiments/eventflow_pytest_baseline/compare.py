"""04C four-artifact comparator; refuses conclusions from missing/invalid arms.

Not a developer-time benchmark: no human effort, setup cost or maintenance data.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

PIN = "c08455d626d5e1c316d932c4da0652086fb1b19e"
EXPECTED = {
    ("upstream", "pytest"): "VERIFIED_PYTEST_RED",
    ("guarded", "pytest"): "VERIFIED_PYTEST_GREEN",
    ("upstream", "reprovant"): "VERIFIED_RED_CONTROL",
    ("guarded", "reprovant"): "VERIFIED_GUARDED_GREEN",
}


def compare(reports: dict[tuple[str, str], dict]) -> dict:
    summary = {"experiment": "eventflow-04c-comparison", "status": "INCONCLUSIVE",
               "reason": "missing_or_invalid_arm", "arms": {},
               "fairness": "same upstream SHA/scenario/services; separately provisioned job environments",
               "developer_time": "NOT_MEASURED", "adapter_portability": "NOT_MEASURED",
               "runtime_speed_advantage": "NOT_ESTABLISHED"}
    if set(reports) != set(EXPECTED):
        return summary
    for (mode, method), expected in EXPECTED.items():
        r = reports[(mode, method)]
        if r.get("status") != expected or r.get("source_pin") != PIN or r.get("mode") != mode:
            return summary
        if method == "pytest":
            before, after = r.get("before"), r.get("after")
            changed = r.get("changed_upstream_files")
        else:
            contract = r.get("contract_report") or {}
            before_raw, after_raw = contract.get("before") or {}, contract.get("after") or {}
            before = {"state": before_raw.get("state"), "order_confirmed": (before_raw.get("effects") or {}).get("order_confirmed")}
            after = {"state": after_raw.get("state"), "order_confirmed": (after_raw.get("effects") or {}).get("order_confirmed")}
            changed = r.get("changed_upstream_files")
        expected_before = {"state": "shipped", "order_confirmed": 1}
        expected_after = ({"state": "confirmed", "order_confirmed": 2} if mode == "upstream"
                          else {"state": "shipped", "order_confirmed": 1})
        expected_changed = ([] if mode == "upstream" else ["orders/tasks.py"])
        if before != expected_before or after != expected_after or changed != expected_changed:
            return summary
        summary["arms"][f"{method}/{mode}"] = {"status": expected, "before": before, "after": after}
    summary.update(status="VERIFIED_PARITY", reason="both_methods_detect_same_control_behaviors")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        reports = {}
        for mode, method in EXPECTED:
            name = f"eventflow-04c-{method}-{mode}"
            path = args.evidence_dir / name / "report.json"
            reports[(mode, method)] = json.loads(path.read_text(encoding="utf-8"))
        result = compare(reports)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        result = {"experiment": "eventflow-04c-comparison", "status": "INCONCLUSIVE",
                  "reason": "evidence_unavailable", "error_type": type(exc).__name__}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("EVENTFLOW 04C:", result["status"], result["reason"])
    return 0 if result["status"] == "VERIFIED_PARITY" else 2


if __name__ == "__main__":
    raise SystemExit(main())
