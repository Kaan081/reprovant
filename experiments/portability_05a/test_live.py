"""Plain pytest baseline: intentionally failing duplicate-attempt assertion."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from experiments.portability_05a.scenario import JobScenario, PIN


@pytest.fixture(scope="module")
def observations():
    scenario = JobScenario()
    scenario.prepare()
    before = scenario.observe()
    scenario.dispatch()
    after = scenario.observe()
    report = {"source_pin": PIN, "before": before,
              "after": after, "worker": scenario.attestation}
    output = os.getenv("PORTABILITY_05A_SNAPSHOT")
    if not output:
        raise RuntimeError("Snapshot output path required")
    Path(output).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def test_first_dispatch_succeeded(observations):
    assert observations["before"] == {"state": "success", "attempts": 1}


def test_replay_preserves_attempt_count(observations):
    if observations["after"]["attempts"] != 1:
        pytest.fail("INVARIANT_EXTRA_ATTEMPT", pytrace=False)
