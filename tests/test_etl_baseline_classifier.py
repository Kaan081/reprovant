"""Local unit tests of the baseline evidence parser, NOT upstream execution."""
from pathlib import Path
import importlib.util
from xml.etree import ElementTree as ET

P = Path(__file__).resolve().parents[1] / "experiments" / "etl_baseline" / "classify_junit.py"
spec = importlib.util.spec_from_file_location("etl_classify", P)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def xml(path, errors=None, missing=()):
    root = ET.Element("testsuite")
    for name in mod.EXPECTED:
        if name in missing:
            continue
        tc = ET.SubElement(root, "testcase", name=name)
        if (errors or {}).get(name):
            ET.SubElement(tc, (errors or {})[name])
    ET.ElementTree(root).write(path)


def test_all_four_pass(tmp_path):
    f = tmp_path / "j.xml"
    xml(f)
    assert mod.classify(f, "0", mod.UPSTREAM_PIN)["status"] == "PASS"


def test_case_failed_when_control_ok(tmp_path):
    f = tmp_path / "j.xml"
    xml(f, {mod.EXPECTED[1]: "failure"})
    assert mod.classify(f, "1", mod.UPSTREAM_PIN)["status"] == "FAIL"


def test_control_failure_is_not_claimed(tmp_path):
    f = tmp_path / "j.xml"
    xml(f, {mod.EXPECTED[0]: "failure", mod.EXPECTED[1]: "failure"})
    assert mod.classify(f, "1", mod.UPSTREAM_PIN)["status"] == "INCONCLUSIVE"


def test_missing_or_skip_never_pass(tmp_path):
    f = tmp_path / "j.xml"
    xml(f, missing=[mod.EXPECTED[3]])
    assert mod.classify(f, "0", mod.UPSTREAM_PIN)["status"] == "INCONCLUSIVE"
    xml(f, {mod.EXPECTED[2]: "skipped"})
    assert mod.classify(f, "0", mod.UPSTREAM_PIN)["status"] == "INCONCLUSIVE"
    assert mod.classify(f, "0", "wrong")["status"] == "INCONCLUSIVE"
    assert mod.classify(tmp_path / "missing.xml", "0", mod.UPSTREAM_PIN)["status"] == "INCONCLUSIVE"
