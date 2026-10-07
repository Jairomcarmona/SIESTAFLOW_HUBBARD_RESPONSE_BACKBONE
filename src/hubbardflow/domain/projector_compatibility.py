"""Compare declared LR and DFT+U projector definitions."""

from __future__ import annotations

import math

from hubbardflow.domain.projector_compatibility_models import (
    ProjectorArtifactDigest,
    ProjectorCompatibilityError,
    ProjectorCompatibilityResult,
    ProjectorCompatibilityStatus,
    ProjectorDefinition,
    ProjectorDigestWarning,
    ProjectorFieldDifference,
    ProjectorIncompleteReason,
    ProjectorRecordDefinition,
    ProjectorValue,
)


def compare_projector_definitions(
    lr_definition: ProjectorDefinition,
    dftu_definition: ProjectorDefinition,
    *,
    label_mapping: tuple[str, str] | None,
    force: bool = False,
) -> ProjectorCompatibilityResult:
    """Compare declared projector/PAO values; file digests only make warnings.

    `label_mapping` is mandatory because LR aliases and production species
    labels are not inferred from element or chemical similarity. Missing
    structural evidence yields INCOMPLETE; differing declarations yield
    MISMATCH. Explicit force records operator intent without erasing either
    outcome.
    """
    if not isinstance(lr_definition, ProjectorDefinition) or not isinstance(
        dftu_definition, ProjectorDefinition
    ):
        raise ProjectorCompatibilityError("both inputs must be ProjectorDefinition values")
    if not isinstance(force, bool):
        raise ProjectorCompatibilityError("force must be boolean")
    reasons: set[ProjectorIncompleteReason] = set()
    if label_mapping is None:
        reasons.add(ProjectorIncompleteReason.LABEL_MAPPING_MISSING)
    elif label_mapping != (lr_definition.label, dftu_definition.label):
        raise ProjectorCompatibilityError("label_mapping must name the LR and DFT+U definition labels")
    if not lr_definition.evidence_consistent:
        reasons.add(ProjectorIncompleteReason.SOURCE_DEFINITION_INCONSISTENT)
    if not lr_definition.species_present or not dftu_definition.species_present:
        reasons.add(ProjectorIncompleteReason.SPECIES_LABEL_MISSING)
    for definition in (lr_definition, dftu_definition):
        if definition.generation_method is None:
            reasons.add(ProjectorIncompleteReason.GENERATION_METHOD_MISSING)
        if definition.record is None:
            reasons.add(ProjectorIncompleteReason.RECORD_MISSING)
        if definition.cutoff_norm is None:
            reasons.add(ProjectorIncompleteReason.CUTOFF_NORM_MISSING)
    differences: list[ProjectorFieldDifference] = []
    if lr_definition.generation_method is not None and dftu_definition.generation_method is not None:
        _append_difference(
            differences,
            "DFTU.ProjectorGenerationMethod",
            lr_definition.generation_method,
            dftu_definition.generation_method,
        )
    if lr_definition.record is not None and dftu_definition.record is not None:
        for field, lr_value, dftu_value in _record_fields(lr_definition.record, dftu_definition.record):
            _append_difference(differences, f"DFTU.Proj.{field}", lr_value, dftu_value)
    if lr_definition.cutoff_norm is not None and dftu_definition.cutoff_norm is not None:
        _append_difference(
            differences, "DFTU.CutoffNorm", lr_definition.cutoff_norm, dftu_definition.cutoff_norm
        )
    for field in ("pao_basis_size", "pao_energy_shift_ev", "pao_split_norm", "pao_basis_tokens"):
        _append_difference(
            differences, f"PAO.{field}", getattr(lr_definition, field), getattr(dftu_definition, field)
        )
    warnings = _digest_warnings(lr_definition.artifact_digests, dftu_definition.artifact_digests)
    status = (
        ProjectorCompatibilityStatus.INCOMPLETE
        if reasons
        else ProjectorCompatibilityStatus.MISMATCH
        if differences
        else ProjectorCompatibilityStatus.MATCH
    )
    return ProjectorCompatibilityResult(
        status,
        lr_definition.label,
        dftu_definition.label,
        tuple(differences),
        tuple(sorted(reasons, key=lambda item: item.value)),
        warnings,
        force,
        lr_definition.artifact_digests,
        dftu_definition.artifact_digests,
        lr_definition.artifact_digest_issues,
        dftu_definition.artifact_digest_issues,
    )


def _record_fields(
    lr: ProjectorRecordDefinition, dftu: ProjectorRecordDefinition
) -> tuple[tuple[str, ProjectorValue, ProjectorValue], ...]:
    return (
        (
            "projector_header_value",
            _numeric_or_string(lr.projector_header_value),
            _numeric_or_string(dftu.projector_header_value),
        ),
        ("n", lr.n, dftu.n),
        ("l", lr.l, dftu.l),
        ("u_ref_ev", lr.u_ref_ev, dftu.u_ref_ev),
        ("j_ref_ev", lr.j_ref_ev, dftu.j_ref_ev),
        ("rc_bohr", lr.rc_bohr, dftu.rc_bohr),
        ("omega", lr.omega, dftu.omega),
        ("lambda_values", lr.lambda_values, dftu.lambda_values),
    )


def _append_difference(
    output: list[ProjectorFieldDifference], field: str, lr_value: ProjectorValue, dftu_value: ProjectorValue
) -> None:
    if lr_value != dftu_value:
        output.append(ProjectorFieldDifference(field, lr_value, dftu_value))


def _digest_warnings(
    lr_digests: tuple[ProjectorArtifactDigest, ...], dftu_digests: tuple[ProjectorArtifactDigest, ...]
) -> tuple[ProjectorDigestWarning, ...]:
    roles = sorted({item.role for item in (*lr_digests, *dftu_digests)})
    warnings: list[ProjectorDigestWarning] = []
    for role in roles:
        lr_hashes = tuple(sorted({item.sha256 for item in lr_digests if item.role == role}))
        dftu_hashes = tuple(sorted({item.sha256 for item in dftu_digests if item.role == role}))
        if lr_hashes != dftu_hashes:
            warnings.append(ProjectorDigestWarning(role, lr_hashes, dftu_hashes))
    return tuple(warnings)


def _numeric_or_string(value: str) -> str | float:
    try:
        numeric_value = float(value)
    except ValueError:
        return value
    if not math.isfinite(numeric_value):
        raise ProjectorCompatibilityError("projector header value must be finite")
    return numeric_value


__all__ = [
    "ProjectorArtifactDigest",
    "ProjectorCompatibilityError",
    "ProjectorCompatibilityResult",
    "ProjectorCompatibilityStatus",
    "ProjectorDefinition",
    "ProjectorDigestWarning",
    "ProjectorFieldDifference",
    "ProjectorIncompleteReason",
    "ProjectorRecordDefinition",
    "ProjectorValue",
    "compare_projector_definitions",
]
