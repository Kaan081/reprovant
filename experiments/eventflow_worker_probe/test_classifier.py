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
