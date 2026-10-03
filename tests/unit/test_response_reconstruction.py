"""Scalar covariance, diagnostics and frozen retrospective regressions."""

from __future__ import annotations

import json
import runpy
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from hubbardflow.domain.response_reconstruction import (
    ObservableKind,
    ReconstructionClass,
    ReconstructionResult,
    ResidualReport,
    ResponseReconstructionError,
    SymmetrizationReport,
    reciprocity_residuals,
    reconstruct_matrix,
    stabilizer_residuals,
    symmetrization_report,
)
from hubbardflow.domain.symmetry_operation_models import IDENTITY, Operation, SymmetryAtom, SymmetryModel

ROOT = Path(__file__).resolve().parents[2]


def _op(permutation: tuple[int, ...]) -> Operation:
    model = SymmetryModel(
        "0" * 64,
        ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
        tuple(SymmetryAtom(i, (0.0, 0.0, 0.0), None, True) for i in range(len(permutation))),
        2,
        True,
        False,
        True,
        True,
    )
    return Operation(IDENTITY, (0.0, 0.0, 0.0), -1, permutation, permutation, model)


@given(st.lists(st.integers(-100, 100), min_size=4, max_size=4))
def test_cyclic_covariance_and_class_order(values: list[int]) -> None:
    ops = tuple(_op(tuple((i + j) % 4 for i in range(4))) for j in range(4))
    cls = ReconstructionClass((3, 1, 2, 0), 0, ((3, 3), (2, 2), (1, 1), (0, 0)))
    raw = reconstruct_matrix({0: values}, (cls,), ops, observable=ObservableKind.SPIN_SUMMED_TRACE)
    expected = tuple(tuple(float(values[(i - j) % 4]) for j in range(4)) for i in range(4))
    assert raw.raw_matrix == expected
    assert ReconstructionResult.from_mapping(raw.to_mapping()) == raw
    assert ReconstructionClass.from_mapping(cls.to_mapping()) == cls
    for op in ops:
        pi = op.correlated_permutation
        assert np.array_equal(np.asarray(raw.raw_matrix)[np.ix_(pi, pi)], raw.raw_matrix)


def test_wrong_column_map_detected() -> None:
    with pytest.raises(ResponseReconstructionError, match="map representative"):
        reconstruct_matrix(
            {0: (1.0, 2.0)},
            (ReconstructionClass((0, 1), 0, ((0, 0), (1, 0))),),
            (_op((0, 1)),),
            observable=ObservableKind.SPIN_SUMMED_TRACE,
        )


def test_stabilizer_and_symmetrization_keep_raw() -> None:
    raw = ((1.0, 4.0, 3.0), (2.0, 5.0, 6.0), (7.0, 8.0, 9.0))
    report = symmetrization_report(raw)
    assert report.raw_matrix == raw
    assert report.symmetrized_matrix == ((1.0, 3.0, 5.0), (3.0, 5.0, 7.0), (5.0, 7.0, 9.0))
    assert report.correction_frobenius_norm == pytest.approx(np.sqrt(12))
    assert reciprocity_residuals(raw).max_abs == 4
    check = stabilizer_residuals((1.0, 2.0, 4.0), 0, (_op((0, 2, 1)),))
    assert check.max_abs == 2
    assert ResidualReport.from_mapping(check.to_mapping()) == check
    assert SymmetrizationReport.from_mapping(report.to_mapping()) == report
    bad = check.to_mapping()
    bad["frobenius_norm"] = float("nan")
    with pytest.raises(ResponseReconstructionError):
        ResidualReport.from_mapping(bad)


def test_two_orbits_reconstruct_rows_and_columns() -> None:
    classes = (
        ReconstructionClass((0, 2), 0, ((0, 0), (2, 1))),
        ReconstructionClass((1, 3), 1, ((1, 0), (3, 1))),
    )
    ops = (_op((0, 1, 2, 3)), _op((2, 3, 0, 1)))
    raw = reconstruct_matrix(
        {0: (1.0, 2.0, 3.0, 4.0), 1: (5.0, 6.0, 7.0, 8.0)},
        classes,
        ops,
        observable=ObservableKind.SPIN_SUMMED_TRACE,
    )
    assert raw.raw_matrix == (
        (1.0, 5.0, 3.0, 7.0),
        (2.0, 6.0, 4.0, 8.0),
        (3.0, 7.0, 1.0, 5.0),
        (4.0, 8.0, 2.0, 6.0),
    )
    reversed_raw = reconstruct_matrix(
        {1: (5.0, 6.0, 7.0, 8.0), 0: (1.0, 2.0, 3.0, 4.0)},
        classes[::-1],
        ops,
        observable=ObservableKind.SPIN_SUMMED_TRACE,
    )
    assert raw == reversed_raw


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -float("inf"), True])
def test_nonfinite_rejection(bad: float) -> None:
    with pytest.raises(ResponseReconstructionError):
        reconstruct_matrix(
            {0: (bad,)},
            (ReconstructionClass((0,), 0, ((0, 0),)),),
            (_op((0,)),),
            observable=ObservableKind.SPIN_SUMMED_TRACE,
        )


def test_occupation_matrices_rejected() -> None:
    with pytest.raises(ResponseReconstructionError, match="occupation matrices"):
        reconstruct_matrix({}, (), (), observable=ObservableKind.OCCUPATION_MATRIX)


def test_partial_partition_and_invalid_record_rejected() -> None:
    with pytest.raises(ResponseReconstructionError, match="partition"):
        reconstruct_matrix(
            {0: (1.0, 2.0)},
            (ReconstructionClass((0, 2), 0, ((0, 0), (2, 1))),),
            (_op((0, 1)),),
            observable=ObservableKind.SPIN_SUMMED_TRACE,
        )
    with pytest.raises(ResponseReconstructionError):
        ReconstructionClass.from_mapping(
            {"members": [0], "representative": 0, "ops_rep_to_member": [[0, 0, 0]]}
        )


def test_retrospective_matches_reference_arithmetic() -> None:
    tool = runpy.run_path(str(ROOT / "tools/v1_retrospective.py"))
    report = tool["build_report"](ROOT)
    reference = runpy.run_path(str(ROOT / "docs/fdebq/reference/coverage_review_checks.py"))
    output = StringIO()
    with redirect_stdout(output):
        reference["coo"](ROOT)
        reference["mno"](ROOT)
    coo, _, mno, cu3n = report.campaigns
    for row in coo["comparisons"]:
        mode, a = row["mode"].lower(), row["alpha_ev"]
        line = (
            f"  {mode:8s} a={a:.2f}  chi00-chi11={row['chi00_minus_chi11']:+.2e}  "
            f"chi01-chi10={row['chi01_minus_chi10']:+.2e}  (|chi00|={row['abs_chi00']:.4f})"
        )
        assert line in output.getvalue()
    for row in mno["comparisons"]:
        mode, a, d = row["mode"], row["alpha_ev"], row["max_abs_difference_e_per_ev"]
        line = (
            f"  {mode:8s} a={a:.3f}  max|chi_B - P chi_A|={d:.1e} e/eV   x a = {d * a:.1e} e"
            f"   print-only bound 2*5e-6/a={row['legacy_script_comparison_bound_e_per_ev']:.1e}"
        )
        assert line in output.getvalue()
        assert row["within_print_bounds"]
        assert row["print_bounds_e_per_ev"] == [pytest.approx(1e-4 / a)] * 16
    assert cu3n["status"] == "INDEPENDENT_SHADOW_NOT_AVAILABLE"
    assert {c["missing_independent_shadow_columns"] for c in cu3n["campaigns"]} == {21, 78}
    assert not coo["comparisons"][-1]["within_print_bounds"]
    assert coo["matrices"][-1]["direct_reciprocity"]["max_abs"] > 0
    assert tool["markdown"](tool["build_report"](ROOT)) == tool["markdown"](report)
    payload: dict[str, Any] = report.to_mapping()
    assert "U_Cu_eV" not in json.dumps(payload)
    assert report == tool["V1Report"].from_mapping(payload)
