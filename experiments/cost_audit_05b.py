"""05B: reproducible source-size inventory, NOT a labor/cost benchmark.

Usage:
  python experiments/cost_audit_05b.py --root . --output cost-audit-05b.json

Each file is counted once in a declared scope. In particular, shared infrastructure,
mixed Flask runners, comparators, unit tests and CI are NOT attributed exclusively
to either method. Physical lines are not person-hours or maintainability scores.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from typing import NamedTuple


class Entry(NamedTuple):
    app: str
    category: str
    path: str


# Explicit manifest: no ad-hoc glob, no retroactive deletion of expensive files.
# Docs and CI are visible in inventory but never presented as method-only code.
MANIFEST = (
    Entry("global", "reusable_core", "src/pipeline_acceptance/replay_contract.py"),
    Entry("eventflow", "prior_shared_probe", "experiments/eventflow_worker_probe/run_probe.py"),
    Entry("eventflow", "reprovant_method", "experiments/eventflow_replay_contract/run_contract.py"),
    Entry("eventflow", "pytest_method", "experiments/eventflow_pytest_baseline/test_live.py"),
    Entry("eventflow", "pytest_method", "experiments/eventflow_pytest_baseline/classify.py"),
    Entry("eventflow", "comparison", "experiments/eventflow_pytest_baseline/compare.py"),
    Entry("eventflow", "regression_tests", "tests/test_eventflow_replay_contract_04b.py"),
    Entry("eventflow", "regression_tests", "tests/test_eventflow_pytest_baseline_04c.py"),
    Entry("eventflow", "workflow", ".github/workflows/external-eventflow-replay-contract-04b.yml"),
    Entry("eventflow", "workflow", ".github/workflows/external-eventflow-pytest-parity-04c.yml"),
    Entry("eventflow", "documentation", "docs/EVENTFLOW_PYTEST_BASELINE_04C.md"),
    Entry("flask", "shared_scenario", "experiments/portability_05a/scenario.py"),
    Entry("flask", "mixed_methods", "experiments/portability_05a/execute.py"),
    Entry("flask", "mixed_methods", "experiments/portability_05a/verdict.py"),
    Entry("flask", "pytest_method", "experiments/portability_05a/test_live.py"),
    Entry("flask", "comparison", "experiments/portability_05a/compare.py"),
    Entry("flask", "regression_tests", "tests/test_portability_05a.py"),
    Entry("flask", "workflow", ".github/workflows/external-flask-job-portability-05a.yml"),
    Entry("flask", "documentation", "docs/PORTABILITY_FLASK_JOB_05A.md"),
)


def count_source(content: str) -> dict[str, int]:
    """Fixed line definition. A trailing newline is not an extra physical line."""
    lines = content.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    if lines[-1] == "":
        lines.pop()
    return {
        "physical": len(lines),
        "nonblank": sum(bool(line.strip()) for line in lines),
        "nonblank_non_hash_comment": sum(
            bool(line.strip()) and not line.lstrip().startswith("#") for line in lines
        ),
    }


def commit_sha(root: Path) -> str | None:
    try:
        p = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"],
                           capture_output=True, text=True, timeout=5, check=False)
        sha = p.stdout.strip()
        return sha if p.returncode == 0 and len(sha) == 40 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def audit(root: Path, manifest: tuple[Entry, ...] = MANIFEST) -> dict:
    """Fail closed if any declared file is absent or undecodable."""
    root = root.resolve()
    if len({item.path for item in manifest}) != len(manifest):
        raise ValueError("Duplicate manifest path")
    result = {
        "experiment": "reprovant-05b-source-cost-audit",
        "status": "INCOMPLETE",
        "scope": "physical source inventory; not developer time, product value or paid demand",
        "source_commit": commit_sha(root),
        "definition": "physical lines include blank/comment; nonblank_non_hash_comment excludes blank and full-line # comments only; docstrings remain included",
        "files": [],
        "missing_or_unreadable": [],
        "groups": {},
    }
    for entry in manifest:
        path = root / entry.path
        try:
            if not path.is_file() or not path.resolve().is_relative_to(root):
                raise OSError("File missing or outside repository")
            raw = path.read_bytes()
            lines = count_source(raw.decode("utf-8"))
        except (OSError, UnicodeDecodeError):
            result["missing_or_unreadable"].append(entry.path)
            continue
        result["files"].append({"app": entry.app, "category": entry.category,
                                "path": entry.path, "sha256": hashlib.sha256(raw).hexdigest(),
                                **lines})
        bucket = result["groups"].setdefault(entry.app, {}).setdefault(
            entry.category, {"files": 0, "physical": 0, "nonblank": 0,
                             "nonblank_non_hash_comment": 0})
        bucket["files"] += 1
        for metric in ("physical", "nonblank", "nonblank_non_hash_comment"):
            bucket[metric] += lines[metric]
    if not result["missing_or_unreadable"]:
        result["status"] = "SOURCE_INVENTORY_COMPLETE"
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = audit(args.root)
    serialized = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized, encoding="utf-8")
    else:
        print(serialized, end="")
    return 0 if result["status"] == "SOURCE_INVENTORY_COMPLETE" else 2


if __name__ == "__main__":
    raise SystemExit(main())
