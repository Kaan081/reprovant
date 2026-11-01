"""Independently verify that both artifacts contain matching live results."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from experiments.portability_05a.verdict import parity, save


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--evidence-dir", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    try:
        first = json.loads((args.evidence_dir / "portability-05a-pytest" / "report.json").read_text(encoding="utf-8"))
        second = json.loads((args.evidence_dir / "portability-05a-reprovant" / "report.json").read_text(encoding="utf-8"))
        report = parity(first, second)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        report = {"status": "INCONCLUSIVE", "reason": "unavailable_evidence",
                  "error_type": type(exc).__name__}
    save(args.output, report)
    print("PORTABILITY 05A:", report["status"])
    return 0 if report["status"] == "VERIFIED_SECOND_APP_PARITY" else 2


if __name__ == "__main__":
    raise SystemExit(main())
