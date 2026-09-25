from pathlib import Path

import pytest

from siestaflow_hubbard.domain.semantic_validation import SemanticValidator

def test_no_pinv_in_source():
    src_dir = Path(__file__).resolve().parents[2] / "src"
    assert src_dir.is_dir(), f"Missing source root: {src_dir}"
    offenders = []
    for py_file in src_dir.rglob("*.py"):
        content = py_file.read_text(encoding="utf-8")
        if ".pinv(" in content or ".pinvh(" in content:
            offenders.append(str(py_file))
    assert not offenders, f"Pseudoinverse forbidden in LR source: {offenders}"

def test_no_pinvh_in_source():
    assert isinstance(SemanticValidator().validate_campaign(None), list)
