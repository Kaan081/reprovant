"""Local contract tests for the evidence classifier only; no live stack claim."""
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("worker_probe", Path(__file__).with_name("run_probe.py"))
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


def control():
    return {
        "worker_seen": True,
        "eager_mode": False,
        "first_task_state": "SUCCESS",
        "first_status": "confirmed",
        "first_confirmed_events": 1,
        "second_task_state": "SUCCESS",
        "status_after_manual_reenqueue": "confirmed",
        "confirmed_events_total": 2,
    }


def test_observed_red():
    assert probe.classify(control())[0] == "OBSERVED_RED"


def test_positive_control_fail_closed():
    o = control()
    o["first_confirmed_events"] = 0
    assert probe.classify(o)[0] == "INCONCLUSIVE"


def test_worker_not_verified_fail_closed():
    o = control()
    o["worker_seen"] = False
    assert probe.classify(o)[0] == "INCONCLUSIVE"


def test_eager_simulation_fail_closed():
    o = control()
    o["eager_mode"] = True
    assert probe.classify(o)[0] == "INCONCLUSIVE"


def test_guarded_not_reported_as_red():
    o = control()
    o["status_after_manual_reenqueue"] = "shipped"
    o["confirmed_events_total"] = 1
    assert probe.classify(o)[0] == "NOT_REPRODUCED"


def test_partial_violation_is_inconclusive():
    o = control()
    o["confirmed_events_total"] = 1
    assert probe.classify(o)[0] == "INCONCLUSIVE"


def test_pinned_revision_reads_external_checkout_not_our_head(monkeypatch, tmp_path):
    """Regression: workflow runs the probe from our repo root, not upstream."""
    monkeypatch.chdir(tmp_path)
    seen = {}

    def fake_check_output(argv, *, text):
        seen["argv"] = argv
        assert text is True
        return probe.UPSTREAM_SHA + "\n"

    monkeypatch.setattr(probe.subprocess, "check_output", fake_check_output)
    assert probe.read_upstream_revision() == probe.UPSTREAM_SHA
    assert seen["argv"][0:2] == ["git", "-C"]
    assert Path(seen["argv"][2]) == Path(probe.__file__).resolve().parents[2] / "upstream-eventflow"
    assert seen["argv"][3:] == ["rev-parse", "HEAD"]
