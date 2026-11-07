"""Minimal app-neutral replay acceptance contract (experimental, v0).

An adapter performs actions in its *own disposable sandbox*. This module does not
connect to databases, execute dynamic import strings, or inject broker faults.
A GREEN result verifies only the specific replay observed, not production safety.
"""
from __future__ import annotations

import json
import os
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Protocol

SCHEMA = "reprovant.replay-contract.v0"


def _counts(value: Mapping[str, int], label: str) -> dict[str, int]:
    if not isinstance(value, Mapping) or not value:
        raise ValueError(f"{label} must be a nonempty metric map")
    copy = {}
    for key, count in value.items():
        if not isinstance(key, str) or not key.strip() or len(key) > 100:
            raise ValueError(f"{label} has an invalid metric name")
        if type(count) is not int or count < 0:
            raise ValueError(f"{label} counts must be nonnegative integers")
        copy[key] = count
    return copy


@dataclass(frozen=True)
class Snapshot:
    """Only non-sensitive state and business-effect counts; no identifiers or payloads."""
    state: str
    effects: Mapping[str, int]

    def __post_init__(self) -> None:
        if not isinstance(self.state, str) or not self.state.strip():
            raise ValueError("Snapshot state must be a nonempty string")
        object.__setattr__(self, "effects", _counts(self.effects, "snapshot.effects"))


@dataclass(frozen=True)
class ReplayContract:
    """Exact expected precondition, then repeat a dispatch and preserve invariants.

    baseline_effects is an *exact* known-good count per monitored business effect.
    max_growth controls permitted increases during replay (normally zero).
    """
    name: str
    expected_state: str
    baseline_effects: Mapping[str, int]
    max_growth: Mapping[str, int] | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("Contract name required")
        if not isinstance(self.expected_state, str) or not self.expected_state.strip():
            raise ValueError("Expected state required")
        baseline = _counts(self.baseline_effects, "baseline_effects")
        growth = {key: 0 for key in baseline}
        if self.max_growth is not None:
            if not isinstance(self.max_growth, Mapping):
                raise ValueError("max_growth must be a mapping")
            for key, limit in self.max_growth.items():
                if key not in baseline or type(limit) is not int or limit < 0:
                    raise ValueError("max_growth has unknown keys or invalid limits")
                growth[key] = limit
        object.__setattr__(self, "baseline_effects", baseline)
        object.__setattr__(self, "max_growth", growth)


class ReplayAdapter(Protocol):
    def is_disposable(self) -> bool: ...
    def observe(self) -> Snapshot: ...
    def dispatch(self) -> None: ...


def _public(snapshot: Snapshot, keys: list[str]) -> dict:
    return {"state": snapshot.state,
            "effects": {key: snapshot.effects[key] for key in keys}}


def evaluate_replay(adapter: ReplayAdapter, contract: ReplayContract) -> dict:
    """Run one repeat dispatch. Never claim GREEN with incomplete evidence.

    is_disposable is an explicit adapter *assertion*, not independently verified.
    Any dispatch/observer exception becomes INCONCLUSIVE, with type only reported.
    Dispatch completion is not proof that a broker delivered or a worker
    executed the task; that evidence is outside this v0 snapshot contract.
    Does not catch BaseException (e.g. KeyboardInterrupt/SystemExit).
    """
    started = time.perf_counter()
    keys = list(contract.baseline_effects)
    report: dict = {
        "schema_version": SCHEMA,
        "contract": contract.name,
        "status": "INCONCLUSIVE",
        "scope": "one replay in adapter-attested disposable environment; no verified worker execution, production or broker ACK-loss proof",
        "checks": {},
        "before": None,
        "after": None,
        "dispatch_completed": False,
        "worker_execution_verified": False,  # No worker receipt in the v0 contract.
    }
    phase = "safety_check"
    try:
        if adapter.is_disposable() is not True:
            report["reason"] = "disposable_environment_not_attested"
            return report

        phase = "observe_before"
        before = adapter.observe()
        if not isinstance(before, Snapshot) or any(k not in before.effects for k in keys):
            report["reason"] = "incomplete_pre_replay_observation"
            return report
        report["before"] = _public(before, keys)
        if (before.state != contract.expected_state or
                any(before.effects[k] != contract.baseline_effects[k] for k in keys)):
            report["reason"] = "baseline_precondition_not_met"
            return report

        phase = "dispatch"
        adapter.dispatch()
        report["dispatch_completed"] = True

        phase = "observe_after"
        after = adapter.observe()
        if not isinstance(after, Snapshot) or any(k not in after.effects for k in keys):
            report["reason"] = "incomplete_post_replay_observation"
            return report
        report["after"] = _public(after, keys)

        report["checks"]["state_preserved"] = after.state == before.state
        for key in keys:
            delta = after.effects[key] - before.effects[key]
            report["checks"][f"effect:{key}"] = 0 <= delta <= contract.max_growth[key]

        failed = [k for k, valid in report["checks"].items() if not valid]
        if failed:
            report["status"] = "RED"
            report["reason"] = "replay_invariant_violated"
            report["failed_checks"] = failed
        else:
            report["status"] = "GREEN"
            report["reason"] = "observed_replay_invariants_preserved"
        return report
    except Exception as exc:
        # Exception *messages* can embed DSNs or customer data, so never record them.
        report["reason"] = "adapter_error"
        report["error_phase"] = phase
        report["error_type"] = type(exc).__name__
        return report
    finally:
        report["duration_ms"] = round((time.perf_counter() - started) * 1000, 2)


def write_evidence(path: str | Path, report: dict) -> None:
    """Atomic local JSON write. File destination must be intentionally chosen by caller."""
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(prefix=".reprovant-", dir=str(dest.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            json.dump(report, file, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
            file.write("\n")
        os.replace(temp_path, dest)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
