"""Actual separate-process termination; not a simulated Python exception."""
from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

from pipeline_acceptance.crash_harness import run_acceptance


def test_real_child_process_kill_and_replay(engine):
    if engine.dialect.name == "sqlite" and engine.url.database == ":memory:":
        pytest.skip("File-backed disposable DB required")
    report = run_acceptance(engine)
    assert report["pass"]
    assert [c["checkpoint"] for c in report["scenarios"]] == ["before_commit", "after_commit"]
    before, after = report["scenarios"]
    assert (before["effect_count_after_kill"], before["status_after_kill"]) == (0, "PENDING")
    assert (after["effect_count_after_kill"], after["status_after_kill"]) == (1, "SUCCEEDED")
    for case in report["scenarios"]:
        assert case["worker_terminated_by_parent"]
        assert case["worker_exit_code"] != 0
        assert case["effect_count_after_replay"] == 1
        assert case["status_after_replay"] == "SUCCEEDED"


def test_known_broken_legacy_negative_control_is_detected(engine):
    report = run_acceptance(engine, implementation="legacy")
    assert report["pass"] is False
    before, after = report["scenarios"]
    assert before["pass"] is True
    assert after["pass"] is False
    assert after["effect_count_after_kill"] == 1
    assert after["effect_count_after_replay"] == 2


def test_cli_real_process_crash_and_json_evidence(tmp_path):
    proof = tmp_path / "crash-proof.json"
    env = dict(os.environ)
    env.pop("PIPELINE_TEST_DSN", None)
    completed = subprocess.run(
        [sys.executable, "-m", "pipeline_acceptance.crash_harness", "--output", str(proof)],
        env=env, text=True, capture_output=True, timeout=35,
    )
    assert completed.returncode == 0, completed.stderr
    report = json.loads(proof.read_text(encoding="utf-8"))
    assert report["pass"] and report["backend"] == "sqlite"
    assert len(report["scenarios"]) == 2
    assert "postgresql+psycopg" not in proof.read_text(encoding="utf-8")


def test_worker_cannot_run_without_parent_marker():
    env = dict(os.environ)
    env.pop("PIPELINE_CRASH_CHILD", None)
    p = subprocess.run(
        [sys.executable, "-m", "pipeline_acceptance.crash_harness",
         "--child-stage", "before_commit", "--job-id", "x", "--logical-key", "y", "--payload", "z"],
        env=env, text=True, capture_output=True, timeout=5,
    )
    assert p.returncode != 0
    assert "Direct worker execution is disabled" in p.stderr


def test_crash_harness_postgres_requires_explicit_opt_in():
    env = dict(os.environ)
    env.pop("PIPELINE_TEST_DSN", None)
    p = subprocess.run(
        [sys.executable, "-m", "pipeline_acceptance.crash_harness", "--postgres"],
        env=env, text=True, capture_output=True, timeout=5,
    )
    assert p.returncode != 0
    assert "requires PIPELINE_TEST_DSN" in p.stderr
