"""Parse campaign projector evidence and FDF declarations."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import cast

from hubbardflow.domain.projector_compatibility_models import (
    ProjectorArtifactDigest,
    ProjectorCompatibilityError,
    ProjectorDefinition,
    ProjectorRecordDefinition,
)
from hubbardflow.siesta_backend.fdf_model import DftuRecord, FdfModel, parse_effective_fdf


class ProjectorCompatibilityInputError(ValueError):
    """Campaign evidence or FDF inputs cannot be parsed unambiguously."""


_CUT_NORM_DEFAULT = 0.9
# Effective SIESTA defaults are resolved so omitted and explicit equivalent PAO settings match.
_PAO_BASIS_SIZE_DEFAULT = "DZP"
_PAO_ENERGY_SHIFT_DEFAULT_EV = 0.01 * 13.605693122994
_PAO_SPLIT_NORM_DEFAULT = 0.15
_RY_TO_EV = Decimal("13.605693122994")
_DIRECTIVE = re.compile(r"^\s*([^%\s]+)\s+(.+?)\s*$")
_NUMBER = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[EeDd][+-]?\d+)?$")


def definition_from_fdf(
    model: FdfModel,
    label: str,
    record: ProjectorRecordDefinition | None,
    roots: Sequence[Path],
    *,
    evidence_consistent: bool,
) -> ProjectorDefinition:
    record_in_fdf = record_by_label(model, label)
    if record is not None and record_in_fdf != record:
        evidence_consistent = False
    cutoff = _cutoff_norm(model.effective_text)
    basis_by_label = dict(model.pao_basis_blocks)
    basis_lines = basis_by_label.get(label)
    pao_basis = (
        None if basis_lines is None else tuple(_normalise_numeric_tokens(line) for line in basis_lines)
    )
    species = next((item for item in model.chemical_species_labels if item.label == label), None)
    energy_shift_ev = _pao_energy_shift_ev(model.effective_text)
    split_norm = _pao_split_norm(model.effective_text)
    default_split_norm = (
        0.45 if species is not None and species.atomic_number == 1 else _PAO_SPLIT_NORM_DEFAULT
    )
    artifact_digests, artifact_digest_issues = _artifact_digests(label, roots)
    return ProjectorDefinition(
        label=label,
        generation_method=_generation_method(model.effective_text, model.dftu_method),
        record=record,
        cutoff_norm=cutoff,
        pao_basis_size=(model.pao_basis_size or _PAO_BASIS_SIZE_DEFAULT).casefold(),
        pao_energy_shift_ev=_PAO_ENERGY_SHIFT_DEFAULT_EV if energy_shift_ev is None else energy_shift_ev,
        pao_split_norm=default_split_norm if split_norm is None else split_norm,
        pao_basis_tokens=pao_basis,
        artifact_digests=artifact_digests,
        evidence_consistent=evidence_consistent,
        species_present=species is not None,
        artifact_digest_issues=artifact_digest_issues,
    )


def parse_projector_fdf(path: Path, description: str) -> FdfModel:
    try:
        return parse_effective_fdf(path)
    except (OSError, UnicodeError, ValueError) as exc:
        raise ProjectorCompatibilityInputError(f"cannot parse {description}: {exc}") from exc


def record_by_label(model: FdfModel, label: str) -> ProjectorRecordDefinition | None:
    rows = [record for record in model.dftu_records if record.label == label]
    if len(rows) != 1:
        return None
    return _record_definition(rows[0])


def _record_definition(record: DftuRecord) -> ProjectorRecordDefinition:
    return ProjectorRecordDefinition(
        record.projector_header_value,
        record.n,
        record.l,
        record.u_ref_ev,
        record.j_ref_ev,
        record.rc_bohr,
        record.omega,
        record.lambda_values,
    )


def inventory_projector_records(
    plan: Mapping[str, object],
) -> dict[str, tuple[ProjectorRecordDefinition, ...]]:
    inventory = plan.get("inventory")
    if not isinstance(inventory, Mapping):
        return {}
    raw_subspaces = inventory.get("subspaces")
    if not isinstance(raw_subspaces, list):
        return {}
    records: dict[str, list[ProjectorRecordDefinition]] = {}
    for item in raw_subspaces:
        if not isinstance(item, Mapping):
            continue
        label = item.get("species_label")
        raw_record = item.get("dftu_record")
        if not isinstance(label, str) or not isinstance(raw_record, Mapping):
            continue
        try:
            record = ProjectorRecordDefinition.from_mapping(raw_record)
        except ProjectorCompatibilityError:
            continue
        records.setdefault(label, []).append(record)
    return {label: tuple(rows) for label, rows in records.items()}


def source_record(
    evidence: Mapping[str, tuple[ProjectorRecordDefinition, ...]], label: str, source_model: FdfModel
) -> tuple[ProjectorRecordDefinition | None, bool]:
    rows = evidence.get(label, ())
    if not rows:
        return None, False
    unique = set(rows)
    if len(unique) != 1:
        return None, False
    record = next(iter(unique))
    return record, record_by_label(source_model, label) == record


def _cutoff_norm(text: str) -> float:
    modern = _directive_values(text, "DFTU.CutoffNorm")
    legacy = _directive_values(text, "LDAU.CutoffNorm")
    values = modern if modern else legacy
    if len(values) > 1:
        raise ProjectorCompatibilityInputError("duplicate effective DFTU.CutoffNorm declarations")
    if not values:
        return _CUT_NORM_DEFAULT
    value = _single_number(values[0], "DFTU.CutoffNorm")
    if not 0.0 < value < 1.0:
        raise ProjectorCompatibilityInputError("DFTU.CutoffNorm must be strictly between zero and one")
    return value


def _generation_method(text: str, parsed_method: int | None) -> int | None:
    modern = _directive_values(text, "DFTU.ProjectorGenerationMethod")
    legacy = _directive_values(text, "LDAU.ProjectorGenerationMethod")
    canonical = _directive_values(text, "DFTU.Method")
    chosen = canonical or modern or legacy
    if len(chosen) > 1:
        raise ProjectorCompatibilityInputError("duplicate projector generation method declarations")
    if chosen:
        value = _single_number(chosen[0], "DFTU.ProjectorGenerationMethod")
        if value != math.floor(value) or value < 1:
            raise ProjectorCompatibilityInputError(
                "DFTU.ProjectorGenerationMethod must be a positive integer"
            )
        return int(value)
    return parsed_method


def _pao_energy_shift_ev(text: str) -> float | None:
    values = _directive_values(text, "PAO.EnergyShift")
    if len(values) > 1:
        raise ProjectorCompatibilityInputError("duplicate PAO.EnergyShift declarations")
    if not values:
        return None
    fields = values[0].split()
    if len(fields) != 2:
        raise ProjectorCompatibilityInputError("PAO.EnergyShift must include its energy unit")
    value = _decimal(fields[0], "PAO.EnergyShift")
    unit = fields[1].casefold()
    if unit == "ev":
        scale = Decimal(1)
    elif unit in {"ry", "rydberg"}:
        scale = _RY_TO_EV
    elif unit in {"ha", "hartree"}:
        scale = 2 * _RY_TO_EV
    else:
        raise ProjectorCompatibilityInputError(f"unsupported PAO.EnergyShift unit {unit!r}")
    result = float(value * scale)
    if not math.isfinite(result):
        raise ProjectorCompatibilityInputError("PAO.EnergyShift must be finite")
    return result


def _pao_split_norm(text: str) -> float | None:
    values = _directive_values(text, "PAO.SplitNorm")
    if len(values) > 1:
        raise ProjectorCompatibilityInputError("duplicate PAO.SplitNorm declarations")
    return None if not values else _single_number(values[0], "PAO.SplitNorm")


def _directive_values(text: str, key: str) -> list[str]:
    from hubbardflow.siesta_backend.fdf_labels import canonical_fdf_label

    values: list[str] = []
    in_block = False
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if re.match(r"%block\b", line, re.IGNORECASE):
            in_block = True
            continue
        if re.match(r"%endblock\b", line, re.IGNORECASE):
            in_block = False
            continue
        if in_block or not line:
            continue
        match = _DIRECTIVE.match(line)
        if match and canonical_fdf_label(match.group(1)) == canonical_fdf_label(key):
            values.append(match.group(2).strip())
    return values


def _single_number(text: str, label: str) -> float:
    fields = text.split()
    if len(fields) != 1:
        raise ProjectorCompatibilityInputError(f"{label} must contain one numeric value")
    result = float(_decimal(fields[0], label))
    if not math.isfinite(result):
        raise ProjectorCompatibilityInputError(f"{label} must be finite")
    return result


def _decimal(value: str, label: str) -> Decimal:
    if _NUMBER.fullmatch(value) is None:
        raise ProjectorCompatibilityInputError(f"{label} value {value!r} is not numeric")
    try:
        result = Decimal(value.replace("D", "E").replace("d", "e"))
    except InvalidOperation as exc:
        raise ProjectorCompatibilityInputError(f"{label} value {value!r} is not numeric") from exc
    if not result.is_finite():
        raise ProjectorCompatibilityInputError(f"{label} must be finite")
    return result


def _normalise_numeric_tokens(line: str) -> str:
    tokens: list[str] = []
    for token in line.split():
        key, separator, raw_value = token.partition("=")
        value = raw_value if separator else token
        if _NUMBER.fullmatch(value):
            canonical = format(_decimal(value, "PAO.Basis").normalize(), "f")
            tokens.append(f"{key.casefold()}={canonical}" if separator else canonical)
        else:
            tokens.append(token.casefold())
    return " ".join(tokens)


def _artifact_digests(
    label: str, roots: Sequence[Path]
) -> tuple[tuple[ProjectorArtifactDigest, ...], tuple[str, ...]]:
    suffixes = (("psml", ".psml"), ("ion", ".ion"), ("dftu_proj", ".dftu_proj"))
    candidates: dict[str, set[Path]] = {role: set() for role, _ in suffixes}
    for root in roots:
        for role, suffix in suffixes:
            candidate = root / f"{label}{suffix}"
            if candidate.is_file():
                candidates[role].add(candidate.resolve())
    digests: list[ProjectorArtifactDigest] = []
    issues: list[str] = []
    for role in sorted(candidates):
        for path in sorted(candidates[role], key=str):
            try:
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
            except OSError as exc:
                issues.append(f"{role} artifact {path} could not be hashed: {exc}")
                continue
            digests.append(ProjectorArtifactDigest(role, digest, str(path)))
    return tuple(digests), tuple(issues)


def campaign_relative(root: Path, value: object, label: str) -> Path:
    if not isinstance(value, str) or not value:
        raise ProjectorCompatibilityInputError(f"campaign manifest lacks {label}")
    candidate = Path(value)
    resolved = candidate if candidate.is_absolute() else root / candidate
    try:
        return resolved.resolve(strict=True)
    except OSError as exc:
        raise ProjectorCompatibilityInputError(f"campaign {label} does not exist: {resolved}") from exc


def load_json_object(path: Path, description: str) -> Mapping[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ProjectorCompatibilityInputError(f"cannot read {description}: {exc}") from exc
    if not isinstance(value, Mapping):
        raise ProjectorCompatibilityInputError(f"{description} must be a JSON object")
    return cast(Mapping[str, object], value)
