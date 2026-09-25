import json
import re
from pathlib import Path

from tools.build_cu3n_symmetry_shadow_campaign import (
    ALPHA,
    SHADOWS,
    SOURCE,
    shadow_fdf,
    shadow_runs,
)


def _projector_shifts(fdf: str):
    block = fdf.split("%block DFTU.Proj", 1)[1].split("%endblock DFTU.Proj", 1)[0]
    return {
        match.group(1): float(match.group(2))
        for match in re.finditer(
            r"^\s*(CuLR\d+)\s+1\s*\n\s*3\s+2\s*\n\s*([+-]?\d+\.\d+)\s+0\.0000",
            block,
            re.MULTILINE,
        )
    }


def test_shadow_run_set_is_three_translation_orbits_times_four_responses():
    runs = shadow_runs()
    assert len(runs) == 12
    assert {run["target"] for run in runs} == {"CuLR03", "CuLR04", "CuLR05"}
    for orbit, representative, target, representative_index, target_index in SHADOWS:
        selected = [run for run in runs if run["orbit"] == orbit]
        assert len(selected) == 4
        assert {run["representative"] for run in selected} == {representative}
        assert {run["target_matrix_index"] for run in selected} == {target_index}
        assert {run["alpha_ev"] for run in selected} == {-ALPHA, ALPHA}


def test_fdf_mutation_changes_only_the_declared_target_shift():
    template = SOURCE / "runs/10_X_BARE_MINUS/siesta.fdf"
    original = _projector_shifts(template.read_text())
    assert original["CuLR00"] == -ALPHA
    for _, _, target, _, _ in SHADOWS:
        rendered = shadow_fdf(template, "SHADOW_TEST", target, ALPHA)
        shifts = _projector_shifts(rendered)
        assert len(shifts) == 24
        assert shifts[target] == ALPHA
        assert shifts["CuLR00"] == 0.0
        assert sum(value != 0.0 for value in shifts.values()) == 1
        assert "SystemLabel SHADOW_TEST" in rendered
