"""These unit tests validate only the independent evidence classifier."""
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("green_classifier", Path(__file__).with_name("classify_guarded.py"))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def good():
    return {
        "status": "NOT_REPRODUCED", "reason": "upstream_behaved_as_guarded",
        "observation": {
            "upstream_revision": mod.PIN, "worker_seen": True,
            "eager_mode": False, "worker_names": ["celery@host"],
            "first_task_state": "SUCCESS", "second_task_state": "SUCCESS",
            "first_status": "confirmed", "first_confirmed_events": 1,
            "status_after_manual_reenqueue": "shipped", "confirmed_events_total": 1,
            "task_acks_late": False, "first_task_id": "a", "second_task_id": "b",
            "event_log": [{"type": "order.confirmed", "order_id": 1}],
        },
    }


def status(data=None, code="2", changed=None):
    return mod.classify(data if data is not None else good(), code, ["orders/tasks.py"] if changed is None else changed)["status"]


def test_green_happy_path():
    assert status() == "GUARDED_GREEN"


def test_red_after_patch_is_real_failure():
    x=good();x["status"]="OBSERVED_RED";x["reason"]="shipped_regressed_and_duplicate_confirmed_event"
    assert status(x) == "FAIL"


def test_no_positive_control_does_not_pass():
    x=good();x["observation"]["first_confirmed_events"]=0
    assert status(x) == "INCONCLUSIVE"


def test_missing_worker_does_not_pass():
    x=good();x["observation"]["worker_seen"]=False
    assert status(x) == "INCONCLUSIVE"


def test_wrong_pin_does_not_pass():
    x=good();x["observation"]["upstream_revision"]="other"
    assert status(x) == "INCONCLUSIVE"


def test_wrong_patch_files_does_not_pass():
    assert status(changed=["orders/models.py"]) == "INCONCLUSIVE"


def test_wrong_probe_exit_does_not_pass():
    assert status(code="0") == "INCONCLUSIVE"


def test_missing_task_identity_does_not_pass():
    x=good();x["observation"]["second_task_id"]=x["observation"]["first_task_id"]
    assert status(x) == "INCONCLUSIVE"


def test_bad_event_log_does_not_pass():
    x=good();x["observation"]["event_log"]=[]
    assert status(x) == "INCONCLUSIVE"


def test_no_ack_loss_claim():
    x=good();x["observation"]["task_acks_late"]=True
    assert status(x) == "INCONCLUSIVE"
