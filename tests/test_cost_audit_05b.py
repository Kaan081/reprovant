"""Pure source-accounting tests; do not claim real-world developer hours."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


SOURCE = Path(__file__).resolve().parents[1] / "experiments/cost_audit_05b.py"
SPEC = importlib.util.spec_from_file_location("cost_audit_05b", SOURCE)
assert SPEC is not None and SPEC.loader is not None
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


def test_line_definition_empty_and_trailing_newline():
    assert m.count_source("") == {"physical": 0, "nonblank": 0, "nonblank_non_hash_comment": 0}
    assert m.count_source("a\n") == {"physical": 1, "nonblank": 1, "nonblank_non_hash_comment": 1}


def test_line_definition_windows_and_comments():
    assert m.count_source("# comment\r\nx = 1\r\n\r\n") == {
        "physical": 3, "nonblank": 2, "nonblank_non_hash_comment": 1,
    }


def test_module_docstrings_are_counted_in_noncomment_metric():
    assert m.count_source('"""Docstring"""\n# comment\n')['nonblank_non_hash_comment'] == 1


def test_manifest_no_duplicate_paths():
    paths = [x.path for x in m.MANIFEST]
    assert len(paths) == len(set(paths))


def test_manifest_keeps_shared_and_mixed_separate():
    names = {(x.app, x.category) for x in m.MANIFEST}
    assert ("eventflow", "prior_shared_probe") in names
    assert ("flask", "mixed_methods") in names
    assert ("global", "reusable_core") in names


def test_missing_file_is_incomplete_not_success(tmp_path):
    item = m.Entry("x", "pytest_method", "missing.py")
    report = m.audit(tmp_path, (item,))
    assert report['status'] == 'INCOMPLETE'
    assert report['missing_or_unreadable'] == ['missing.py']


def test_duplicate_manifest_fails(tmp_path):
    f = m.Entry("x", "pytest_method", "one.py")
    with pytest.raises(ValueError, match="Duplicate"):
        m.audit(tmp_path, (f, f))


def test_binary_file_fails_closed(tmp_path):
    (tmp_path / "bad.py").write_bytes(b"\xff\xfe")
    r = m.audit(tmp_path, (m.Entry("x", "mixed_methods", "bad.py"),))
    assert r["status"] == "INCOMPLETE"


def test_summary_totals_are_method_and_category_specific(tmp_path):
    (tmp_path / "a.py").write_text("# hi\na = 1\n", encoding="utf-8")
    (tmp_path / "b.py").write_text("\nif True:\n    pass\n", encoding="utf-8")
    items = (m.Entry("app", "shared_scenario", "a.py"),
             m.Entry("app", "pytest_method", "b.py"))
    result = m.audit(tmp_path, items)
    assert result["status"] == "SOURCE_INVENTORY_COMPLETE"
    assert result["groups"]["app"]["shared_scenario"]["physical"] == 2
    assert result["groups"]["app"]["pytest_method"]["physical"] == 3
    assert len(result["files"]) == 2
    assert all(len(x["sha256"]) == 64 for x in result["files"])


def test_path_outside_root_is_rejected(tmp_path):
    r = m.audit(tmp_path, (m.Entry("x", "shared_scenario", "../missing.txt"),))
    assert r["status"] == "INCOMPLETE"
