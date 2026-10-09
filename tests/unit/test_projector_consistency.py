from __future__ import annotations

from pathlib import Path

import pytest

from hubbardflow.domain.symmetry_reduction import PerturbationSpec, ResponseMode
from hubbardflow.siesta_backend import symmetry_materializer
from hubbardflow.siesta_backend.projector_consistency import (
    ProjectorComparison,
    ProjectorComparisonStatus,
    ProjectorConsistencyError,
    ProjectorDifferenceReason,
    compare_projector_definitions,
)
from hubbardflow.siesta_backend.symmetry_materializer import ResponseMaterializationError

ROOT = Path(__file__).resolve().parents[2]
REFERENCE = ROOT / "tests" / "fixtures" / "cu3n_reference_siesta.fdf"


def _fdf(*, method: int = 2, cutoff_norm: float = 0.90, rc: float = 3.0, omega: float = 0.05) -> str:
    return f"""DFTU.ProjectorGenerationMethod {method}
DFTU.CutoffNorm {cutoff_norm}
%block DFTU.Proj
MnLR00 1
3 2
0.0 0.0 0.0
{rc} {omega}
%endblock DFTU.Proj
"""


def test_method_one_reference_and_method_two_response_are_rejected() -> None:
    method_one_reference = "DFTU.ProjectorGenerationMethod 1\n"
    result = compare_projector_definitions(method_one_reference, _fdf(method=2))

    assert result.status is ProjectorComparisonStatus.MISMATCH
    assert [item.reason for item in result.differences] == [ProjectorDifferenceReason.METHOD_MISMATCH]
    assert "reference=1" in result.describe()
    assert "response=2" in result.describe()


def test_identical_definitions_match_even_when_response_shift_values_differ() -> None:
    reference = _fdf().replace("0.0 0.0 0.0", "0.0 0.0 0.0 1.0")
    response = reference.replace("0.0 0.0 0.0 1.0", "-0.05 0.0 0.0 0.7")

    result = compare_projector_definitions(reference, response)

    assert result == ProjectorComparison(ProjectorComparisonStatus.MATCH, ())
    assert ProjectorComparison.from_mapping(result.to_mapping()) == result


def test_automatic_rc_compares_cutoff_norm_and_generated_radius_when_available() -> None:
    reference = _fdf(rc=0.0, cutoff_norm=0.90)
    response = _fdf(rc=0.0, cutoff_norm=0.95)
    cutoff_result = compare_projector_definitions(reference, response)
    assert ProjectorDifferenceReason.CUTOFF_NORM_MISMATCH in {
        item.reason for item in cutoff_result.differences
    }
    default_norm = _fdf(rc=0.0).replace("DFTU.CutoffNorm 0.9\n", "")
    assert compare_projector_definitions(default_norm, reference).compatible

    equal_generated_result = compare_projector_definitions(
        reference,
        reference,
        reference_generated_rc_bohr={"MnLR00/3/2": 2.44},
        response_generated_rc_bohr={"MnLR00/3/2": 2.44},
    )
    assert equal_generated_result.compatible

    generated_result = compare_projector_definitions(
        reference,
        reference,
        reference_generated_rc_bohr={"MnLR00/3/2": 2.44},
        response_generated_rc_bohr={"MnLR00/3/2": 2.45},
    )
    assert ProjectorDifferenceReason.GENERATED_RC_MISMATCH in {
        item.reason for item in generated_result.differences
    }


@pytest.mark.parametrize(
    ("reference", "response", "reason"),
    [
        (_fdf(), _fdf().replace("3 2", "4 2"), ProjectorDifferenceReason.RECORDS_MISMATCH),
        (_fdf(), _fdf().replace("3 2", "3 1"), ProjectorDifferenceReason.RECORDS_MISMATCH),
        (_fdf(rc=3.0), _fdf(rc=3.1), ProjectorDifferenceReason.RC_MISMATCH),
        (_fdf(omega=0.05), _fdf(omega=0.06), ProjectorDifferenceReason.OMEGA_MISMATCH),
        (_fdf(), _fdf().replace("MnLR00 1", "MnLR01 1"), ProjectorDifferenceReason.RECORDS_MISMATCH),
    ],
)
def test_explicit_projector_differences_are_rejected(
    reference: str, response: str, reason: ProjectorDifferenceReason
) -> None:
    result = compare_projector_definitions(reference, response)

    assert result.status is ProjectorComparisonStatus.MISMATCH
    assert reason in {item.reason for item in result.differences}


def test_malformed_projector_fails_closed() -> None:
    with pytest.raises(ProjectorConsistencyError, match="complete DFTU.Proj block"):
        compare_projector_definitions("DFTU.ProjectorGenerationMethod 2", _fdf())


def test_response_materialization_fails_closed_on_projector_difference(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def report_mismatch(reference: str, response: str):
        return compare_projector_definitions(_fdf(omega=0.05), _fdf(omega=0.06))

    monkeypatch.setattr(symmetry_materializer, "compare_projector_definitions", report_mismatch)
    spec = PerturbationSpec("screened_case", "orbit_001", 0, "CuLR03", ResponseMode.SCREENED, -0.05, "probe")

    with pytest.raises(ResponseMaterializationError, match="PROJECTOR_OMEGA_MISMATCH"):
        symmetry_materializer.materialize_response_fdf(REFERENCE, spec)
