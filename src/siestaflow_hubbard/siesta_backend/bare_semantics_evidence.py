"""Fail-closed verification of a version-specific SIESTA BARE trace.

The Cococcioni ``chi0`` branch cannot be established from ``MaxSCFIterations``
or a population-event index.  A diagnostic SIESTA build (or a sanctioned
native trace) must emit an ordered trace for the *same* BARE run.  This module
binds that trace to the executable, parent DM and output transcript before the
existing selector may promote an observation to ``VERIFIED_BARE``.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import re


_HASH = re.compile(r"^[0-9a-f]{64}$")
_SCHEMA = "siestaflow-bare-semantics-v1"
_MARKER_KEYS = (
    "reference_dm_loaded",
    "perturbation_applied",
    "selected_population",
    "hxc_rebuild_after_selected_population",
)


class BareSemanticEvidenceError(ValueError):
    """The BARE sidecar is absent, malformed, or not bound to this run."""


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require_hash(value: object, name: str) -> str:
    if not isinstance(value, str) or _HASH.fullmatch(value) is None:
        raise BareSemanticEvidenceError(f"{name} must be a lowercase SHA-256 digest")
    return value


def _safe_relative(base: Path, reference: object, name: str) -> Path:
    if not isinstance(reference, str) or not reference or Path(reference).is_absolute():
        raise BareSemanticEvidenceError(f"{name} must be a non-empty relative path")
    candidate = (base / reference).resolve()
    try:
        candidate.relative_to(base.resolve())
    except ValueError as exc:
        raise BareSemanticEvidenceError(f"{name} escapes the evidence directory") from exc
    if not candidate.is_file():
        raise BareSemanticEvidenceError(f"{name} does not name a file")
    return candidate


@dataclass(frozen=True)
class VerifiedBareEvidence:
    """Immutable result suitable for constructing an ObservationContext."""

    evidence_reference: str
    evidence_sha256: str
    selected_event_lines: tuple[int, int]


def verify_bare_semantics_evidence(
    sidecar_path: str | Path,
    *,
    siesta_version: str,
    executable_path: str | Path,
    reference_dm_path: str | Path,
    output_path: str | Path,
    selected_event_lines: tuple[int, int],
) -> VerifiedBareEvidence:
    """Verify that one BARE output has a matching, ordered native trace.

    The trace must contain exact, unique diagnostic markers in the order
    ``DM -> perturbation -> selected population -> Hxc rebuild``.  The final
    marker deliberately proves Hxc rebuild occurs *after* the population used
    for ``chi0``.  This is a certificate verifier, not a substitute for the
    source/debug-build audit that generated the markers.
    """

    sidecar = Path(sidecar_path).resolve()
    if not sidecar.is_file():
        raise BareSemanticEvidenceError("bare semantic sidecar is missing")
    try:
        payload = json.loads(sidecar.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BareSemanticEvidenceError("bare semantic sidecar is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise BareSemanticEvidenceError("bare semantic sidecar must be a JSON object")

    required = {
        "schema_version", "status", "siesta_version", "executable_sha256", "source_revision",
        "reference_dm_sha256", "output_sha256", "selected_event_lines",
        "hxc_rebuild_excluded_before_selected_event", "trace_reference", "trace_sha256",
        "trace_markers",
    }
    if set(payload) != required:
        raise BareSemanticEvidenceError("bare semantic sidecar has an unexpected schema")
    if payload["schema_version"] != _SCHEMA or payload["status"] != "PASS":
        raise BareSemanticEvidenceError("bare semantic sidecar is not an accepted PASS record")
    if payload["siesta_version"] != siesta_version:
        raise BareSemanticEvidenceError("SIESTA version differs from the certified build")
    if not isinstance(payload["source_revision"], str) or not payload["source_revision"].strip():
        raise BareSemanticEvidenceError("source_revision is required for a semantic trace")
    if payload["hxc_rebuild_excluded_before_selected_event"] is not True:
        raise BareSemanticEvidenceError("sidecar does not assert frozen-Hxc ordering")

    executable = Path(executable_path)
    reference_dm = Path(reference_dm_path)
    output = Path(output_path)
    if not all(path.is_file() for path in (executable, reference_dm, output)):
        raise BareSemanticEvidenceError("executable, parent DM, and output must exist")
    for key, actual in (
        ("executable_sha256", _sha256_file(executable)),
        ("reference_dm_sha256", _sha256_file(reference_dm)),
        ("output_sha256", _sha256_file(output)),
    ):
        if _require_hash(payload[key], key) != actual:
            raise BareSemanticEvidenceError(f"{key} does not match the audited artifact")

    lines = payload["selected_event_lines"]
    if (
        not isinstance(lines, list) or len(lines) != 2
        or any(type(line) is not int or line < 1 for line in lines)
        or lines[0] > lines[1] or tuple(lines) != selected_event_lines
    ):
        raise BareSemanticEvidenceError("selected event line interval differs from parser provenance")
    output_lines = output.read_text(encoding="utf-8", errors="replace").splitlines()
    if lines[1] > len(output_lines) or not any("hubbard_term" in line.lower() for line in output_lines[lines[0] - 1:lines[1]]):
        raise BareSemanticEvidenceError("selected output interval does not contain a Hubbard population event")

    trace = _safe_relative(sidecar.parent, payload["trace_reference"], "trace_reference")
    if _require_hash(payload["trace_sha256"], "trace_sha256") != _sha256_file(trace):
        raise BareSemanticEvidenceError("trace_sha256 does not match the native trace")
    markers = payload["trace_markers"]
    if not isinstance(markers, dict) or set(markers) != set(_MARKER_KEYS):
        raise BareSemanticEvidenceError("trace_markers must declare the four ordered events")
    if any(not isinstance(markers[key], str) or not markers[key] for key in _MARKER_KEYS):
        raise BareSemanticEvidenceError("trace markers must be non-empty exact strings")
    trace_text = trace.read_text(encoding="utf-8", errors="replace")
    positions = []
    for key in _MARKER_KEYS:
        count = trace_text.count(markers[key])
        if count != 1:
            raise BareSemanticEvidenceError(f"trace marker {key} must occur exactly once")
        positions.append(trace_text.index(markers[key]))
    if positions != sorted(positions):
        raise BareSemanticEvidenceError("native trace does not prove the required BARE ordering")

    return VerifiedBareEvidence(
        evidence_reference=f"{sidecar.name}#{_sha256_file(sidecar)}",
        evidence_sha256=_sha256_file(sidecar),
        selected_event_lines=selected_event_lines,
    )
