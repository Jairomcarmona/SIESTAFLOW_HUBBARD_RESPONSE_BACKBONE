"""Typed projector definitions and serializable LR-02 comparison results.

Declared numeric FDF settings are compared structurally; file digests remain
provenance and never affect compatibility.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import cast

from .validation import require_finite, require_int, require_sha256


class ProjectorCompatibilityError(ValueError):
    """Invalid declared projector definition or comparison request."""


class ProjectorCompatibilityStatus(str, Enum):
    MATCH = "MATCH"
    MISMATCH = "MISMATCH"
    INCOMPLETE = "INCOMPLETE"


class ProjectorCompatibilityReasonCode(str, Enum):
    """Stable machine-readable reason for the projector application decision."""

    MATCH = "PROJECTOR_DEFINITION_MATCH"
    MANIFOLD_MISMATCH = "DFTU_PROJECTOR_MANIFOLD_MISMATCH"
    EVIDENCE_INCOMPLETE = "DFTU_PROJECTOR_EVIDENCE_INCOMPLETE"


class ProjectorIncompleteReason(str, Enum):
    LABEL_MAPPING_MISSING = "PROJECTOR_LABEL_MAPPING_MISSING"
    SOURCE_DEFINITION_INCONSISTENT = "SOURCE_PROJECTOR_EVIDENCE_INCONSISTENT"
    GENERATION_METHOD_MISSING = "PROJECTOR_GENERATION_METHOD_MISSING"
    RECORD_MISSING = "DFTU_PROJECTOR_RECORD_MISSING"
    CUTOFF_NORM_MISSING = "PROJECTOR_CUTOFF_NORM_MISSING"
    SPECIES_LABEL_MISSING = "PROJECTOR_SPECIES_LABEL_MISSING"


ProjectorValue = str | int | float | tuple[float, ...] | tuple[str, ...] | None


@dataclass(frozen=True)
class ProjectorRecordDefinition:
    """All parsed values in one DFTU.Proj shell, excluding source spelling."""

    projector_header_value: str
    n: int
    l: int
    u_ref_ev: float
    j_ref_ev: float
    rc_bohr: float
    omega: float
    lambda_values: tuple[float, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.projector_header_value, str) or not self.projector_header_value:
            raise ProjectorCompatibilityError("projector_header_value must be non-empty")
        try:
            require_int(self.n, "n", minimum=1)
            require_int(self.l, "l", minimum=0)
            for name in ("u_ref_ev", "j_ref_ev", "rc_bohr", "omega"):
                require_finite(getattr(self, name), name)
            for value in self.lambda_values:
                require_finite(value, "lambda")
        except ValueError as exc:
            raise ProjectorCompatibilityError(str(exc)) from exc

    def to_mapping(self) -> dict[str, object]:
        return {
            "projector_header_value": self.projector_header_value,
            "n": self.n,
            "l": self.l,
            "u_ref_ev": self.u_ref_ev,
            "j_ref_ev": self.j_ref_ev,
            "rc_bohr": self.rc_bohr,
            "omega": self.omega,
            "lambda_values": list(self.lambda_values),
        }

    @classmethod
    def from_mapping(cls, value: object) -> ProjectorRecordDefinition:
        row = _mapping(value, "projector record")
        try:
            lambdas = row["lambda_values"]
            if not isinstance(lambdas, list | tuple):
                raise ProjectorCompatibilityError("lambda_values must be an array")
            return cls(
                _string(row["projector_header_value"], "projector_header_value"),
                _integer(row["n"], "n"),
                _integer(row["l"], "l"),
                _number(row["u_ref_ev"], "u_ref_ev"),
                _number(row["j_ref_ev"], "j_ref_ev"),
                _number(row["rc_bohr"], "rc_bohr"),
                _number(row["omega"], "omega"),
                tuple(_number(item, "lambda") for item in lambdas),
            )
        except KeyError as exc:
            raise ProjectorCompatibilityError(f"projector record lacks {exc.args[0]}") from exc


@dataclass(frozen=True)
class ProjectorRecordInformation:
    """Applied Hubbard values and response shifts, recorded without comparison."""

    u_ref_ev: float
    j_ref_ev: float
    lambda_values: tuple[float, ...]

    def __post_init__(self) -> None:
        try:
            require_finite(self.u_ref_ev, "u_ref_ev")
            require_finite(self.j_ref_ev, "j_ref_ev")
            for value in self.lambda_values:
                require_finite(value, "lambda")
        except ValueError as exc:
            raise ProjectorCompatibilityError(str(exc)) from exc

    def to_mapping(self) -> dict[str, object]:
        return {
            "u_ref_ev": self.u_ref_ev,
            "j_ref_ev": self.j_ref_ev,
            "lambda_values": list(self.lambda_values),
        }

    @classmethod
    def from_mapping(cls, value: object) -> ProjectorRecordInformation:
        row = _mapping(value, "informational projector values")
        try:
            lambdas = _array(row["lambda_values"], "lambda_values")
            return cls(
                _number(row["u_ref_ev"], "u_ref_ev"),
                _number(row["j_ref_ev"], "j_ref_ev"),
                tuple(_number(item, "lambda") for item in lambdas),
            )
        except KeyError as exc:
            raise ProjectorCompatibilityError(f"informational projector values lack {exc.args[0]}") from exc


@dataclass(frozen=True)
class ProjectorArtifactDigest:
    """One optional file digest attached to the projector evidence."""

    role: str
    sha256: str
    path: str

    def __post_init__(self) -> None:
        _identifier(self.role, "artifact role")
        _identifier(self.path, "artifact path")
        try:
            require_sha256(self.sha256, "artifact sha256")
        except ValueError as exc:
            raise ProjectorCompatibilityError(str(exc)) from exc

    def to_mapping(self) -> dict[str, object]:
        return {"role": self.role, "sha256": self.sha256, "path": self.path}

    @classmethod
    def from_mapping(cls, value: object) -> ProjectorArtifactDigest:
        row = _mapping(value, "artifact digest")
        try:
            return cls(
                _string(row["role"], "role"),
                _string(row["sha256"], "sha256"),
                _string(row["path"], "path"),
            )
        except KeyError as exc:
            raise ProjectorCompatibilityError(f"artifact digest lacks {exc.args[0]}") from exc


@dataclass(frozen=True)
class ProjectorDefinition:
    """FDF parameters that define the selected species projector and PAO."""

    label: str
    generation_method: int | None
    record: ProjectorRecordDefinition | None
    cutoff_norm: float | None
    pao_basis_size: str | None
    pao_energy_shift_ev: float | None
    pao_split_norm: float | None
    pao_basis_tokens: tuple[str, ...] | None
    artifact_digests: tuple[ProjectorArtifactDigest, ...] = ()
    evidence_consistent: bool = True
    species_present: bool = True
    artifact_digest_issues: tuple[str, ...] = ()
    informational_values: tuple[ProjectorRecordInformation, ...] = ()

    def __post_init__(self) -> None:
        _identifier(self.label, "projector label")
        if self.generation_method is not None:
            try:
                require_int(self.generation_method, "generation_method", minimum=1)
            except ValueError as exc:
                raise ProjectorCompatibilityError(str(exc)) from exc
        for name in ("cutoff_norm", "pao_energy_shift_ev", "pao_split_norm"):
            value = getattr(self, name)
            if value is not None:
                try:
                    require_finite(value, name)
                except ValueError as exc:
                    raise ProjectorCompatibilityError(str(exc)) from exc
        if self.pao_basis_size is not None:
            _identifier(self.pao_basis_size, "pao_basis_size")
        if self.pao_basis_tokens is not None and any(not token for token in self.pao_basis_tokens):
            raise ProjectorCompatibilityError("pao_basis_tokens cannot contain empty values")
        if any(not isinstance(item, ProjectorRecordInformation) for item in self.informational_values):
            raise ProjectorCompatibilityError("informational_values must contain ProjectorRecordInformation")

    def to_mapping(self) -> dict[str, object]:
        return {
            "label": self.label,
            "generation_method": self.generation_method,
            "record": None if self.record is None else self.record.to_mapping(),
            "cutoff_norm": self.cutoff_norm,
            "pao_basis_size": self.pao_basis_size,
            "pao_energy_shift_ev": self.pao_energy_shift_ev,
            "pao_split_norm": self.pao_split_norm,
            "pao_basis_tokens": None if self.pao_basis_tokens is None else list(self.pao_basis_tokens),
            "artifact_digests": [digest.to_mapping() for digest in self.artifact_digests],
            "evidence_consistent": self.evidence_consistent,
            "species_present": self.species_present,
            "artifact_digest_issues": list(self.artifact_digest_issues),
            "informational_values": [item.to_mapping() for item in self.informational_values],
        }

    @classmethod
    def from_mapping(cls, value: object) -> ProjectorDefinition:
        row = _mapping(value, "projector definition")
        try:
            raw_record = row["record"]
            raw_basis = row["pao_basis_tokens"]
            raw_digests = row.get("artifact_digests", [])
            raw_digest_issues = row.get("artifact_digest_issues", [])
            raw_informational_values = row.get("informational_values", [])
            if not isinstance(raw_digests, list | tuple):
                raise ProjectorCompatibilityError("artifact_digests must be an array")
            if not isinstance(raw_digest_issues, list | tuple):
                raise ProjectorCompatibilityError("artifact_digest_issues must be an array")
            if not isinstance(raw_informational_values, list | tuple):
                raise ProjectorCompatibilityError("informational_values must be an array")
            if raw_basis is not None and not isinstance(raw_basis, list | tuple):
                raise ProjectorCompatibilityError("pao_basis_tokens must be an array or null")
            return cls(
                _string(row["label"], "label"),
                _optional_integer(row["generation_method"], "generation_method"),
                None if raw_record is None else ProjectorRecordDefinition.from_mapping(raw_record),
                _optional_number(row["cutoff_norm"], "cutoff_norm"),
                _optional_string(row["pao_basis_size"], "pao_basis_size"),
                _optional_number(row["pao_energy_shift_ev"], "pao_energy_shift_ev"),
                _optional_number(row["pao_split_norm"], "pao_split_norm"),
                None if raw_basis is None else tuple(_string(item, "pao_basis_token") for item in raw_basis),
                tuple(ProjectorArtifactDigest.from_mapping(item) for item in raw_digests),
                _boolean(row["evidence_consistent"], "evidence_consistent"),
                _boolean(row["species_present"], "species_present"),
                tuple(_string(item, "artifact digest issue") for item in raw_digest_issues),
                tuple(ProjectorRecordInformation.from_mapping(item) for item in raw_informational_values),
            )
        except KeyError as exc:
            raise ProjectorCompatibilityError(f"projector definition lacks {exc.args[0]}") from exc


@dataclass(frozen=True)
class ProjectorFieldDifference:
    field: str
    lr_value: ProjectorValue
    dftu_value: ProjectorValue

    def to_mapping(self) -> dict[str, object]:
        return {
            "field": self.field,
            "lr_value": _json_value(self.lr_value),
            "dftu_value": _json_value(self.dftu_value),
        }

    @classmethod
    def from_mapping(cls, value: object) -> ProjectorFieldDifference:
        row = _mapping(value, "field difference")
        try:
            return cls(
                _string(row["field"], "field"),
                _projector_value(row["lr_value"]),
                _projector_value(row["dftu_value"]),
            )
        except KeyError as exc:
            raise ProjectorCompatibilityError(f"field difference lacks {exc.args[0]}") from exc


@dataclass(frozen=True)
class ProjectorDigestWarning:
    role: str
    lr_sha256: tuple[str, ...]
    dftu_sha256: tuple[str, ...]

    def to_mapping(self) -> dict[str, object]:
        return {"role": self.role, "lr_sha256": list(self.lr_sha256), "dftu_sha256": list(self.dftu_sha256)}

    @classmethod
    def from_mapping(cls, value: object) -> ProjectorDigestWarning:
        row = _mapping(value, "digest warning")
        try:
            lr_hashes = row["lr_sha256"]
            dftu_hashes = row["dftu_sha256"]
            if not isinstance(lr_hashes, list | tuple) or not isinstance(dftu_hashes, list | tuple):
                raise ProjectorCompatibilityError("digest warning hashes must be arrays")
            return cls(
                _string(row["role"], "role"),
                tuple(_string(item, "lr_sha256") for item in lr_hashes),
                tuple(_string(item, "dftu_sha256") for item in dftu_hashes),
            )
        except KeyError as exc:
            raise ProjectorCompatibilityError(f"digest warning lacks {exc.args[0]}") from exc


@dataclass(frozen=True)
class ProjectorCompatibilityResult:
    status: ProjectorCompatibilityStatus
    lr_label: str
    dftu_label: str
    differences: tuple[ProjectorFieldDifference, ...]
    incomplete_reasons: tuple[ProjectorIncompleteReason, ...]
    digest_warnings: tuple[ProjectorDigestWarning, ...]
    force_requested: bool
    lr_artifact_digests: tuple[ProjectorArtifactDigest, ...] = ()
    dftu_artifact_digests: tuple[ProjectorArtifactDigest, ...] = ()
    lr_artifact_digest_issues: tuple[str, ...] = ()
    dftu_artifact_digest_issues: tuple[str, ...] = ()
    lr_informational_values: tuple[ProjectorRecordInformation, ...] = ()
    dftu_informational_values: tuple[ProjectorRecordInformation, ...] = ()

    @property
    def reason_code(self) -> ProjectorCompatibilityReasonCode:
        if self.status is ProjectorCompatibilityStatus.MISMATCH:
            return ProjectorCompatibilityReasonCode.MANIFOLD_MISMATCH
        if self.status is ProjectorCompatibilityStatus.INCOMPLETE:
            return ProjectorCompatibilityReasonCode.EVIDENCE_INCOMPLETE
        return ProjectorCompatibilityReasonCode.MATCH

    @property
    def application_permitted(self) -> bool:
        return self.status is ProjectorCompatibilityStatus.MATCH or self.force_requested

    def to_mapping(self) -> dict[str, object]:
        return {
            "status": self.status.value,
            "reason_code": self.reason_code.value,
            "lr_label": self.lr_label,
            "dftu_label": self.dftu_label,
            "differences": [item.to_mapping() for item in self.differences],
            "incomplete_reasons": [item.value for item in self.incomplete_reasons],
            "digest_warnings": [item.to_mapping() for item in self.digest_warnings],
            "lr_artifact_digests": [item.to_mapping() for item in self.lr_artifact_digests],
            "dftu_artifact_digests": [item.to_mapping() for item in self.dftu_artifact_digests],
            "lr_artifact_digest_issues": list(self.lr_artifact_digest_issues),
            "dftu_artifact_digest_issues": list(self.dftu_artifact_digest_issues),
            "lr_informational_values": [item.to_mapping() for item in self.lr_informational_values],
            "dftu_informational_values": [item.to_mapping() for item in self.dftu_informational_values],
            "force_requested": self.force_requested,
            "application_permitted": self.application_permitted,
        }

    @classmethod
    def from_mapping(cls, value: object) -> ProjectorCompatibilityResult:
        row = _mapping(value, "projector compatibility result")
        try:
            differences = row["differences"]
            reasons = row["incomplete_reasons"]
            warnings = row["digest_warnings"]
            lr_digests = row.get("lr_artifact_digests", [])
            dftu_digests = row.get("dftu_artifact_digests", [])
            lr_digest_issues = row.get("lr_artifact_digest_issues", [])
            dftu_digest_issues = row.get("dftu_artifact_digest_issues", [])
            difference_rows = _array(differences, "differences")
            reason_rows = _array(reasons, "incomplete_reasons")
            warning_rows = _array(warnings, "digest_warnings")
            lr_digest_rows = _array(lr_digests, "lr_artifact_digests")
            dftu_digest_rows = _array(dftu_digests, "dftu_artifact_digests")
            lr_issue_rows = _array(lr_digest_issues, "lr_artifact_digest_issues")
            dftu_issue_rows = _array(dftu_digest_issues, "dftu_artifact_digest_issues")
            lr_information = _array(row.get("lr_informational_values", []), "lr_informational_values")
            dftu_information = _array(row.get("dftu_informational_values", []), "dftu_informational_values")
            force = _boolean(row["force_requested"], "force_requested")
            result = cls(
                ProjectorCompatibilityStatus(_string(row["status"], "status")),
                _string(row["lr_label"], "lr_label"),
                _string(row["dftu_label"], "dftu_label"),
                tuple(ProjectorFieldDifference.from_mapping(item) for item in difference_rows),
                tuple(ProjectorIncompleteReason(_string(item, "incomplete reason")) for item in reason_rows),
                tuple(ProjectorDigestWarning.from_mapping(item) for item in warning_rows),
                force,
                tuple(ProjectorArtifactDigest.from_mapping(item) for item in lr_digest_rows),
                tuple(ProjectorArtifactDigest.from_mapping(item) for item in dftu_digest_rows),
                tuple(_string(item, "LR artifact digest issue") for item in lr_issue_rows),
                tuple(_string(item, "DFT+U artifact digest issue") for item in dftu_issue_rows),
                tuple(ProjectorRecordInformation.from_mapping(item) for item in lr_information),
                tuple(ProjectorRecordInformation.from_mapping(item) for item in dftu_information),
            )
            if row.get("application_permitted") is not result.application_permitted:
                raise ProjectorCompatibilityError(
                    "application_permitted disagrees with status and force_requested"
                )
            reason_code = row.get("reason_code")
            if reason_code is not None and reason_code != result.reason_code.value:
                raise ProjectorCompatibilityError("reason_code disagrees with projector status")
            return result
        except (KeyError, TypeError, ValueError) as exc:
            raise ProjectorCompatibilityError(f"invalid projector compatibility result: {exc}") from exc


def _json_value(value: ProjectorValue) -> object:
    return list(value) if isinstance(value, tuple) else value


def _projector_value(value: object) -> ProjectorValue:
    if value is None or isinstance(value, str):
        return value
    if isinstance(value, bool):
        raise ProjectorCompatibilityError("boolean is not a projector parameter value")
    if isinstance(value, int | float):
        return float(require_finite(value, "projector parameter"))
    if isinstance(value, list):
        if all(isinstance(item, str) for item in value):
            return tuple(cast(list[str], value))
        if all(not isinstance(item, bool) and isinstance(item, int | float) for item in value):
            return tuple(float(require_finite(item, "projector parameter")) for item in value)
    raise ProjectorCompatibilityError("unsupported projector parameter value")


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or any(not isinstance(key, str) for key in value):
        raise ProjectorCompatibilityError(f"{label} must be a string-keyed mapping")
    return cast(Mapping[str, object], value)


def _identifier(value: str, label: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ProjectorCompatibilityError(
            f"{label} must be a non-empty string without surrounding whitespace"
        )
    return value


def _string(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise ProjectorCompatibilityError(f"{label} must be a string")
    return value


def _integer(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ProjectorCompatibilityError(f"{label} must be an integer")
    return value


def _optional_integer(value: object, label: str) -> int | None:
    return None if value is None else _integer(value, label)


def _number(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ProjectorCompatibilityError(f"{label} must be numeric")
    try:
        return float(require_finite(value, label))
    except ValueError as exc:
        raise ProjectorCompatibilityError(str(exc)) from exc


def _optional_number(value: object, label: str) -> float | None:
    return None if value is None else _number(value, label)


def _optional_string(value: object, label: str) -> str | None:
    return None if value is None else _string(value, label)


def _boolean(value: object, label: str) -> bool:
    if not isinstance(value, bool):
        raise ProjectorCompatibilityError(f"{label} must be a boolean")
    return value


def _array(value: object, label: str) -> list[object]:
    if not isinstance(value, list):
        raise ProjectorCompatibilityError(f"{label} must be an array")
    return value
