from __future__ import annotations

from dataclasses import replace

from hubbardflow.domain.projector_compatibility import (
    ProjectorArtifactDigest,
    ProjectorCompatibilityResult,
    ProjectorCompatibilityStatus,
    ProjectorDefinition,
    ProjectorIncompleteReason,
    ProjectorRecordDefinition,
    compare_projector_definitions,
)
from hubbardflow.domain.projector_compatibility_models import ProjectorCompatibilityReasonCode


def _record(*, rc_bohr: float = 0.0) -> ProjectorRecordDefinition:
    return ProjectorRecordDefinition("1", 3, 2, 0.0, 0.0, rc_bohr, 0.05, ())


def _definition(
    label: str = "MnLR00",
    *,
    method: int | None = 2,
    record: ProjectorRecordDefinition | None = None,
    cutoff_norm: float | None = 0.9,
    pao_basis_size: str | None = "dzp",
    energy_shift: float | None = 0.005 * 13.605693122994,
    split_norm: float | None = 0.15,
    basis_tokens: tuple[str, ...] | None = ("n=3 2", "3.5 3.5"),
    digests: tuple[ProjectorArtifactDigest, ...] = (),
) -> ProjectorDefinition:
    return ProjectorDefinition(
        label,
        method,
        _record() if record is None else record,
        cutoff_norm,
        pao_basis_size,
        energy_shift,
        split_norm,
        basis_tokens,
        digests,
    )


def _compare(
    lr: ProjectorDefinition,
    target: ProjectorDefinition,
) -> ProjectorCompatibilityResult:
    return compare_projector_definitions(lr, target, label_mapping=(lr.label, target.label))


def test_equal_projector_definitions_match_across_explicit_species_mapping() -> None:
    result = _compare(_definition("MnLR00"), _definition("Mn"))

    assert result.status is ProjectorCompatibilityStatus.MATCH
    assert result.application_permitted
    assert not result.differences


def test_cutoff_norm_difference_is_mismatch() -> None:
    result = _compare(_definition(cutoff_norm=0.90), _definition("Mn", cutoff_norm=0.95))

    assert result.status is ProjectorCompatibilityStatus.MISMATCH
    assert [(item.field, item.lr_value, item.dftu_value) for item in result.differences] == [
        ("DFTU.CutoffNorm", 0.9, 0.95)
    ]
    assert result.reason_code is ProjectorCompatibilityReasonCode.MANIFOLD_MISMATCH
    assert result.to_mapping()["reason_code"] == "DFTU_PROJECTOR_MANIFOLD_MISMATCH"


def test_projector_generation_method_difference_is_mismatch() -> None:
    result = _compare(_definition(method=1), _definition("Mn", method=2))

    assert result.status is ProjectorCompatibilityStatus.MISMATCH
    assert result.differences[0].field == "DFTU.ProjectorGenerationMethod"


def test_explicit_rc_does_not_match_automatic_cutoff_projector() -> None:
    result = _compare(
        _definition(record=_record(rc_bohr=0.0)),
        _definition("Mn", record=_record(rc_bohr=2.5)),
    )

    assert result.status is ProjectorCompatibilityStatus.MISMATCH
    assert any(item.field == "DFTU.Proj.rc_bohr" for item in result.differences)


def test_pao_basis_size_difference_is_mismatch() -> None:
    result = _compare(_definition(pao_basis_size="dzp"), _definition("Mn", pao_basis_size="sz"))

    assert result.status is ProjectorCompatibilityStatus.MISMATCH
    assert any(item.field == "PAO.pao_basis_size" for item in result.differences)


def test_digest_difference_is_warning_only_and_round_trips() -> None:
    lr = _definition(digests=(ProjectorArtifactDigest("psml", "a" * 64, "/lr/MnLR00.psml"),))
    target = _definition(
        "Mn",
        digests=(ProjectorArtifactDigest("psml", "b" * 64, "/target/Mn.psml"),),
    )

    result = _compare(lr, target)

    assert result.status is ProjectorCompatibilityStatus.MATCH
    assert len(result.digest_warnings) == 1
    assert result.lr_artifact_digests == lr.artifact_digests
    assert result.dftu_artifact_digests == target.artifact_digests
    restored = type(result).from_mapping(result.to_mapping())
    assert restored == result


def test_force_is_recorded_without_rewriting_mismatch() -> None:
    lr = _definition()
    target = replace(_definition("Mn"), cutoff_norm=0.95)

    result = compare_projector_definitions(
        lr,
        target,
        label_mapping=("MnLR00", "Mn"),
        force=True,
    )

    assert result.status is ProjectorCompatibilityStatus.MISMATCH
    assert result.force_requested
    assert result.application_permitted


def test_equal_artifact_digests_are_still_recorded_without_warning() -> None:
    digest = ProjectorArtifactDigest("psml", "c" * 64, "/input/Mn.psml")
    lr = _definition(digests=(digest,))
    target = _definition("Mn", digests=(digest,))

    result = _compare(lr, target)

    assert result.status is ProjectorCompatibilityStatus.MATCH
    assert not result.digest_warnings
    assert result.lr_artifact_digests == (digest,)
    assert result.dftu_artifact_digests == (digest,)


def test_missing_explicit_label_mapping_is_incomplete() -> None:
    lr = _definition("MnLR00")
    target = _definition("Mn")

    result = compare_projector_definitions(lr, target, label_mapping=None)

    assert result.status is ProjectorCompatibilityStatus.INCOMPLETE
    assert result.incomplete_reasons == (ProjectorIncompleteReason.LABEL_MAPPING_MISSING,)


def test_only_projector_definition_fields_decide_and_usage_fields_are_recorded() -> None:
    lr_record = _record()
    structural_changes = (
        ("projector_header_value", replace(lr_record, projector_header_value="2")),
        ("n", replace(lr_record, n=4)),
        ("l", replace(lr_record, l=1)),
        ("rc_bohr", replace(lr_record, rc_bohr=2.5)),
        ("omega", replace(lr_record, omega=0.1)),
    )

    for field, changed_record in structural_changes:
        result = _compare(_definition(record=lr_record), _definition("Mn", record=changed_record))
        assert result.status is ProjectorCompatibilityStatus.MISMATCH
        assert f"DFTU.Proj.{field}" in {item.field for item in result.differences}

    informational_changes = (
        ("u_ref_ev", replace(lr_record, u_ref_ev=11.117477)),
        ("j_ref_ev", replace(lr_record, j_ref_ev=0.2)),
        ("lambda_values", replace(lr_record, lambda_values=(0.2,))),
    )
    for field, changed_record in informational_changes:
        result = _compare(_definition(record=lr_record), _definition("Mn", record=changed_record))
        assert result.status is ProjectorCompatibilityStatus.MATCH
        assert not result.differences
        assert len(result.lr_informational_values) == 1
        assert len(result.dftu_informational_values) == 1
        assert getattr(result.dftu_informational_values[0], field) == getattr(changed_record, field)


def test_new_dftu_u_matches_even_when_it_differs_from_the_lr_reference_u() -> None:
    lr_record = replace(_record(), u_ref_ev=11.117477)
    dftu_record = replace(_record(), u_ref_ev=11.5325)

    result = _compare(_definition(record=lr_record), _definition("Mn", record=dftu_record))

    assert result.status is ProjectorCompatibilityStatus.MATCH
    assert not result.differences
    assert result.lr_informational_values[0].u_ref_ev == 11.117477
    assert result.dftu_informational_values[0].u_ref_ev == 11.5325
    restored = type(result).from_mapping(result.to_mapping())
    assert restored == result


def test_projector_header_numeric_spelling_is_compared_by_value() -> None:
    lr_record = replace(_record(), projector_header_value="1")
    target_record = replace(_record(), projector_header_value="1.0")

    result = _compare(_definition(record=lr_record), _definition("Mn", record=target_record))

    assert result.status is ProjectorCompatibilityStatus.MATCH


def test_pao_energy_shift_split_norm_and_species_block_are_compared() -> None:
    cases = (
        (_definition(energy_shift=0.01), _definition("Mn", energy_shift=0.02), "PAO.pao_energy_shift_ev"),
        (_definition(split_norm=0.15), _definition("Mn", split_norm=0.2), "PAO.pao_split_norm"),
        (
            _definition(basis_tokens=("n=3 2", "3.5 3.5")),
            _definition("Mn", basis_tokens=("n=3 2", "4 4")),
            "PAO.pao_basis_tokens",
        ),
    )

    for lr, target, field in cases:
        result = _compare(lr, target)
        assert result.status is ProjectorCompatibilityStatus.MISMATCH
        assert field in {item.field for item in result.differences}


def test_missing_projector_evidence_is_incomplete() -> None:
    lr = ProjectorDefinition("MnLR00", None, None, None, None, None, None, None)
    target = ProjectorDefinition("Mn", None, None, None, None, None, None, None)

    result = compare_projector_definitions(lr, target, label_mapping=("MnLR00", "Mn"))

    assert result.status is ProjectorCompatibilityStatus.INCOMPLETE
    assert ProjectorIncompleteReason.GENERATION_METHOD_MISSING in result.incomplete_reasons
    assert ProjectorIncompleteReason.RECORD_MISSING in result.incomplete_reasons
    assert ProjectorIncompleteReason.CUTOFF_NORM_MISSING in result.incomplete_reasons
    assert result.reason_code is ProjectorCompatibilityReasonCode.EVIDENCE_INCOMPLETE


def test_digest_collection_issue_is_recorded_without_deciding() -> None:
    lr = replace(_definition(), artifact_digest_issues=("psml artifact unreadable",))
    target = _definition("Mn")

    result = _compare(lr, target)

    assert result.status is ProjectorCompatibilityStatus.MATCH
    assert result.lr_artifact_digest_issues == ("psml artifact unreadable",)
    assert not result.digest_warnings
    assert type(result).from_mapping(result.to_mapping()) == result
