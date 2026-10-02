"""Synthetic T0–T4 record checks; no prospective evidence is manufactured."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from hubbardflow.domain.scf_ladder_models import ScfLadderError
from hubbardflow.domain.scf_validation import (
    ValidationCase,
    ValidationMetrics,
    ValidationProtocol,
    ValidationReason,
    ValidationResult,
    ValidationStatus,
    validate_t0_t4,
)
from hubbardflow.domain.symmetry_reduction import ResponseMode
from tests.unit.test_scf_ladder import policy
from tests.unit.test_scf_ladder_inputs import source_text
from tools.fdebq_scf_ladder_campaign import LadderRunInput, build_ladder_runs

DIGEST = "1" * 64


def metrics(case: ValidationCase, *, holdout: bool = False) -> ValidationMetrics:
    return ValidationMetrics(case, 10, 10, 0, 0, True, True, holdout, True, DIGEST, ("2" * 64,))


def test_validation_pass_requires_all_cases_development_holdout_and_frozen_policy() -> None:
    p = ValidationProtocol("test-only-v1", 1.0, DIGEST, False)
    rows = tuple(metrics(c) for c in ValidationCase if c is not ValidationCase.T4) + (
        metrics(ValidationCase.T2, holdout=True),
    )
    result = validate_t0_t4(p, rows)
    assert result.status is ValidationStatus.PASSED
    assert ValidationResult.from_mapping(result.to_mapping()) == result
    assert result == validate_t0_t4(p, tuple(reversed(rows)))
    for changed, reason in (
        (rows[:-1], ValidationReason.HOLDOUT_NOT_ESTABLISHED),
        (tuple(r for r in rows if r.case is not ValidationCase.T3), ValidationReason.EVIDENCE_INCOMPLETE),
        (
            tuple(replace(r, covered_count=8) if r.case is ValidationCase.T0 else r for r in rows),
            ValidationReason.COVERAGE_TARGET_NOT_MET,
        ),
        (
            tuple(replace(r, false_pass_count=1) if r.case is ValidationCase.T3 else r for r in rows),
            ValidationReason.FALSE_PASS,
        ),
        (
            tuple(replace(r, scientific_protocol_sha256="3" * 64) for r in rows),
            ValidationReason.PROTOCOL_NOT_FROZEN,
        ),
        (tuple(replace(r, order_invariant=False) for r in rows), ValidationReason.ORDER_OR_GRID_DEPENDENT),
        (
            tuple(replace(r, reciprocity_violation_count=1) for r in rows),
            ValidationReason.RECIPROCITY_VIOLATION,
        ),
    ):
        failed = validate_t0_t4(p, changed)
        assert failed.status is ValidationStatus.REVIEW and reason in failed.reasons
    assert validate_t0_t4(replace(p, t4_required=True), rows).status is ValidationStatus.REVIEW


def test_invalid_metrics_nonfinite_policy_and_absent_evidence_fail_closed() -> None:
    for target in (float("nan"), float("inf"), True, 0.0, 1.1):
        with pytest.raises(ScfLadderError):
            ValidationProtocol("test", target, DIGEST, False)
    with pytest.raises(ScfLadderError):
        replace(metrics(ValidationCase.T0), covered_count=11)
    result = validate_t0_t4(
        ValidationProtocol("test", 0.9, DIGEST, False),
        (replace(metrics(ValidationCase.T0), evidence_sha256=()),),
    )
    assert result.status is ValidationStatus.REVIEW


def test_materialized_ladder_changes_only_tolerance_and_preserves_parent(tmp_path: Path) -> None:
    parent = tmp_path / "toy.DM"
    parent.write_bytes(b"same-parent-density-matrix")
    asset = tmp_path / "toy.psml"
    asset.write_bytes(b"same-pseudopotential")
    inputs = []
    for index, a in enumerate((-0.08, -0.01, 0.01, 0.08)):
        fdf = tmp_path / f"source{index}.fdf"
        fdf.write_text(source_text(a), encoding="utf-8")
        inputs.append(LadderRunInput("toy", ResponseMode.SCREENED, a, str(fdf), str(parent), (str(asset),)))
    receipts = build_ladder_runs(tuple(inputs), policy(), tmp_path / "generated")
    assert len(receipts) == 12
    assert len({r.parent_dm_sha256 for r in receipts}) == 1
    for r in receipts:
        directory = Path(r.directory)
        assert (directory / "toy.DM").read_bytes() == parent.read_bytes()
        assert (directory / "toy.psml").read_bytes() == asset.read_bytes()
        assert f"DM.Tolerance {r.dm_tolerance!r}" in (directory / "input.fdf").read_text(encoding="utf-8")
        assert "File.DM.Init" not in (directory / "input.fdf").read_text(encoding="utf-8")
    with pytest.raises(ScfLadderError):
        build_ladder_runs(inputs, policy(), tmp_path / "generated")
    with pytest.raises(ScfLadderError):
        build_ladder_runs(inputs[:2], policy(), tmp_path / "invalid")
    with pytest.raises(ValueError):
        replace(inputs[0], alpha_ev=0.0)


def test_materializer_rejects_missing_parent_assets_and_unsafe_restart(tmp_path: Path) -> None:
    fdf = tmp_path / "unsafe.fdf"
    fdf.write_text("File.DM.Init parent.DM\n", encoding="utf-8")
    inputs = tuple(
        LadderRunInput("j", ResponseMode.SCREENED, a, str(fdf), str(tmp_path / "parent.DM"), ())
        for a in (-0.08, -0.01, 0.01, 0.08)
    )
    with pytest.raises(ScfLadderError, match="File.DM.Init"):
        build_ladder_runs(inputs, policy(), tmp_path / "failed")
    assert not (tmp_path / "failed").exists()
