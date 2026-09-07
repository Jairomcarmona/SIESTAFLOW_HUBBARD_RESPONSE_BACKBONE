import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[2] / "tools"))
from scientific_dag_gate import complete, is_complete, load  # noqa: E402


def test_gates_require_artifacts_and_order(tmp_path):
    state = tmp_path / "results" / "scientific_dag_state.json"
    artifact = tmp_path / "artifact.json"
    artifact.write_text("{}")

    with pytest.raises(ValueError, match="parent gate"):
        complete(state, "REFERENCE", [artifact], None)

    complete(state, "PROJECTOR_AUDIT", [artifact], "locality accepted")
    assert is_complete(state, "PROJECTOR_AUDIT", [artifact])
    artifact.unlink()
    assert not is_complete(state, "PROJECTOR_AUDIT", [artifact])
    assert load(state)["gates"]["PROJECTOR_AUDIT"]["status"] == "VALIDATED"
