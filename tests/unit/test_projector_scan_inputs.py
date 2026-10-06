from __future__ import annotations

import pytest

from hubbardflow.domain.projector_plateau import ProjectorParameterKind
from hubbardflow.siesta_backend.projector_scan_inputs import (
    ProjectorScanInputError,
    validate_projector_only_fdf_change,
)

BASE_CUTOFF = """SystemLabel probe
NumberOfAtoms 1
DFTU.ProjectorGenerationMethod 2
DFTU.CutoffNorm 0.90
"""

BASE_EXPLICIT_RC = """SystemLabel probe
NumberOfAtoms 1
DFTU.ProjectorGenerationMethod 2
%block DFTU.Proj
Mn 1
3 2
2.5 0.05
0.0 0.0
%endblock DFTU.Proj
"""


def test_cutoff_norm_scan_changes_only_the_cutoff_line() -> None:
    candidate = BASE_CUTOFF.replace("DFTU.CutoffNorm 0.90", "DFTU.CutoffNorm 0.85")

    validate_projector_only_fdf_change(BASE_CUTOFF, candidate, ProjectorParameterKind.CUTOFF_NORM)


def test_non_projector_or_multiple_fdf_changes_are_rejected() -> None:
    candidate = BASE_CUTOFF.replace("NumberOfAtoms 1", "NumberOfAtoms 2").replace(
        "DFTU.CutoffNorm 0.90", "DFTU.CutoffNorm 0.85"
    )

    with pytest.raises(ProjectorScanInputError, match="exactly one projector line"):
        validate_projector_only_fdf_change(BASE_CUTOFF, candidate, ProjectorParameterKind.CUTOFF_NORM)


def test_cutoff_norm_sweep_rejects_explicit_projector_rc_records() -> None:
    baseline = BASE_EXPLICIT_RC.replace(
        "DFTU.ProjectorGenerationMethod 2\n", "DFTU.ProjectorGenerationMethod 2\nDFTU.CutoffNorm 0.90\n"
    )
    changed = baseline.replace("DFTU.CutoffNorm 0.90", "DFTU.CutoffNorm 0.91")

    with pytest.raises(ProjectorScanInputError, match="explicit rc"):
        validate_projector_only_fdf_change(baseline, changed, ProjectorParameterKind.CUTOFF_NORM)


def test_cutoff_norm_sweep_rejects_explicit_zero_rc_row() -> None:
    baseline = BASE_EXPLICIT_RC.replace(
        "DFTU.ProjectorGenerationMethod 2\n", "DFTU.ProjectorGenerationMethod 2\nDFTU.CutoffNorm 0.90\n"
    )
    assert "2.5 0.05\n0.0 0.0" in baseline
    candidate = baseline.replace("DFTU.CutoffNorm 0.90", "DFTU.CutoffNorm 0.91")

    with pytest.raises(ProjectorScanInputError, match="explicit rc"):
        validate_projector_only_fdf_change(baseline, candidate, ProjectorParameterKind.CUTOFF_NORM)


def test_explicit_rc_scan_changes_only_the_rc_record() -> None:
    candidate = BASE_EXPLICIT_RC.replace("0.0 0.0", "3.0 0.05")

    validate_projector_only_fdf_change(BASE_EXPLICIT_RC, candidate, ProjectorParameterKind.EXPLICIT_RC)


def test_explicit_rc_scan_rejects_cutoff_norm_change() -> None:
    candidate = BASE_CUTOFF.replace("DFTU.CutoffNorm 0.90", "DFTU.CutoffNorm 0.85")

    with pytest.raises(ProjectorScanInputError, match="explicit projector rc row"):
        validate_projector_only_fdf_change(BASE_CUTOFF, candidate, ProjectorParameterKind.EXPLICIT_RC)


def test_fdf_requires_method_two_exactly_once() -> None:
    invalid = BASE_CUTOFF.replace("DFTU.ProjectorGenerationMethod 2", "DFTU.ProjectorGenerationMethod 1")

    with pytest.raises(ProjectorScanInputError, match="Method 2"):
        validate_projector_only_fdf_change(invalid, invalid, ProjectorParameterKind.CUTOFF_NORM)
