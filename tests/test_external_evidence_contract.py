"""Offline tests for conservative classification, not upstream execution."""
from pathlib import Path
import importlib.util
import xml.etree.ElementTree as ET

MOD_PATH = Path(__file__).resolve().parents[1] / "experiments" / "eventflow" / "collect_evidence.py"
spec = importlib.util.spec_from_file_location("eventflow_evidence", MOD_PATH)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


def _xml(path, outcomes, omit=()):
    root = ET.Element("testsuite")
    for case in gate.CASES:
        if case in omit:
            continue
        node = ET.SubElement(root, "testcase", name=case)
        if outcomes.get(case) == "FAIL":
            ET.SubElement(node, "failure", message="violated")
        if outcomes.get(case) == "ERROR":
            ET.SubElement(node, "error", message="infra")
        if outcomes.get(case) == "SKIP":
            ET.SubElement(node, "skipped")
    ET.ElementTree(root).write(path)


def test_all_pass_is_pass(tmp_path):
    p = tmp_path / "junit.xml"
    _xml(p, {})
    assert gate.evaluate(p, 0, gate.PIN)["status"] == "PASS"


def test_invariant_fail_is_fail_when_control_passes(tmp_path):
    p = tmp_path / "junit.xml"
    _xml(p, {gate.CASES[1]: "FAIL"})
    assert gate.evaluate(p, 1, gate.PIN)["status"] == "FAIL"


def test_control_failure_is_inconclusive(tmp_path):
    p = tmp_path / "junit.xml"
    _xml(p, {gate.CASES[0]: "FAIL", gate.CASES[1]: "FAIL"})
    assert gate.evaluate(p, 1, gate.PIN)["status"] == "INCONCLUSIVE"


def test_missing_case_is_inconclusive(tmp_path):
    p = tmp_path / "junit.xml"
    _xml(p, {}, omit=[gate.CASES[2]])
    assert gate.evaluate(p, 0, gate.PIN)["status"] == "INCONCLUSIVE"


def test_wrong_revision_and_missing_xml_inconclusive(tmp_path):
    p = tmp_path / "junit.xml"
    _xml(p, {})
    assert gate.evaluate(p, 0, "wrong")["status"] == "INCONCLUSIVE"
    assert gate.evaluate(tmp_path / "missing.xml", 0, gate.PIN)["status"] == "INCONCLUSIVE"


def test_skip_and_infra_failure_inconclusive(tmp_path):
    p = tmp_path / "junit.xml"
    _xml(p, {gate.CASES[2]: "SKIP"})
    assert gate.evaluate(p, 0, gate.PIN)["status"] == "INCONCLUSIVE"
    assert gate.evaluate(p, 2, gate.PIN)["status"] == "INCONCLUSIVE"
