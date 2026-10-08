from pathlib import Path

from hubbardflow.execution.result_paths import (
    analysis_output_path,
    data_directory,
    find_analysis_path,
    find_state_gate_path,
    state_gate_output_path,
)


def test_new_analysis_and_state_gate_results_use_data_directory(tmp_path: Path) -> None:
    assert analysis_output_path(tmp_path, "siestaflow.lr_u_analysis.v3") == (
        tmp_path / "data" / "lr_u_analysis.v3.json"
    )
    assert analysis_output_path(tmp_path, "siestaflow.lr_u_analysis.v2") == (
        tmp_path / "data" / "lr_u_analysis.v2.json"
    )
    assert state_gate_output_path(tmp_path) == tmp_path / "data" / "i5_state_gate.json"


def test_legacy_analysis_and_state_gate_paths_remain_readable(tmp_path: Path) -> None:
    legacy_analysis = tmp_path / "lr_u_analysis.v3.json"
    legacy_state_gate = tmp_path / "i5_state_gate.json"
    legacy_analysis.write_text("{}", encoding="utf-8")
    legacy_state_gate.write_text("{}", encoding="utf-8")

    assert find_analysis_path(tmp_path) == legacy_analysis
    assert find_state_gate_path(tmp_path) == legacy_state_gate


def test_new_paths_take_precedence_over_legacy_archived_paths(tmp_path: Path) -> None:
    new_analysis = analysis_output_path(tmp_path, "siestaflow.lr_u_analysis.v3")
    new_state_gate = state_gate_output_path(tmp_path)
    legacy_analysis = tmp_path / "lr_u_analysis.v3.json"
    legacy_state_gate = tmp_path / "i5_state_gate.json"
    for path in (new_analysis, new_state_gate, legacy_analysis, legacy_state_gate):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}", encoding="utf-8")

    assert find_analysis_path(tmp_path) == new_analysis
    assert find_state_gate_path(tmp_path) == new_state_gate


def test_missing_result_json_paths_are_unassessed(tmp_path: Path) -> None:
    assert find_analysis_path(tmp_path) is None
    assert find_state_gate_path(tmp_path) is None
    assert data_directory(tmp_path) == tmp_path / "data"
