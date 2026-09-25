"""Strict loader for reference evidence consumed by symmetry reduction.

This adapter does not infer symmetry and never reads ``DM.InitSpin``.  It only
normalizes a versioned, hash-bound evidence record produced from an accepted
reference calculation.  Missing or unknown fields fail closed.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from siestaflow_hubbard.domain.symmetry_reduction import (
    SymmetryEvidenceBundle,
    SymmetryPlanError,
)


class SymmetryEvidenceFormatError(SymmetryPlanError):
    """The reference evidence cannot be used for symmetry authorization."""


def _required_text(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value:
        raise SymmetryEvidenceFormatError(f"missing non-empty evidence field: {key}")
    return value


def load_symmetry_evidence(path: str | Path) -> SymmetryEvidenceBundle:
    """Load the strict v1 evidence bundle without trusting extra fields."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SymmetryEvidenceFormatError("cannot read symmetry evidence JSON") from exc
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        raise SymmetryEvidenceFormatError("unsupported symmetry evidence schema")
    fingerprints = data.get("subspace_fingerprints")
    if not isinstance(fingerprints, list):
        raise SymmetryEvidenceFormatError("subspace_fingerprints must be a list")
    if any(not isinstance(value, str) or not value for value in fingerprints):
        raise SymmetryEvidenceFormatError("subspace_fingerprints contains invalid values")
    return SymmetryEvidenceBundle(
        certificate_input_hash=_required_text(data, "certificate_input_hash"),
        reference_fdf_sha256=_required_text(data, "reference_fdf_sha256"),
        reference_output_sha256=_required_text(data, "reference_output_sha256"),
        magnetic_evidence_sha256=_required_text(data, "magnetic_evidence_sha256"),
        subspace_fingerprints=tuple(fingerprints),
        magnetic_evidence_complete=data.get("magnetic_evidence_complete") is True,
        reference_output_normal=data.get("reference_output_normal") is True,
        source_format=data.get("source_format", ""),
    )
