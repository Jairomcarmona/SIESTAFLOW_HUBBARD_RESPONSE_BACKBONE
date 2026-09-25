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
from typing import Mapping


_HASH = re.compile(r"^[0-9a-f]{64}$")
_SCHEMA = "siestaflow-bare-semantics-v2"
_MARKER_KEYS = (
    "reference_dm_loaded",
    "selected_population",
    "perturbation_applied",
    "hxc_rebuild_after_selected_population",
)
_UNACCEPTABLE_TERMINATION = re.compile(
    r"ABNORMAL_TERMINATION|MPI_Abort",
    re.IGNORECASE,
)
_NORMAL_TERMINATION = re.compile(r">>\s*End of run|normal completion", re.IGNORECASE)
_SCF_MUST_CONVERGE_FALSE = re.compile(
    r"^\s*SCF\.MustConverge\s+(?:F|false)\b", re.IGNORECASE | re.MULTILINE
)


class BareSemanticEvidenceError(ValueError):
    """The BARE sidecar is absent, malformed, or not bound to this run."""


@dataclass(frozen=True)
class BareTraceExpectation:
    """Trusted identity of one audited native BARE trace grammar.

    The expectation is supplied by the campaign contract, never by the
    sidecar being checked.  This is deliberately separate from a SIESTA
    version: two builds reporting the same version may expose different
    diagnostic source revisions or trace grammars.
    """

    source_revision: str
    trace_markers: Mapping[str, str]

    def __post_init__(self) -> None:
        if not isinstance(self.source_revision, str) or not self.source_revision.strip():
            raise BareSemanticEvidenceError("expected source_revision is required")
        if set(self.trace_markers) != set(_MARKER_KEYS):
            raise BareSemanticEvidenceError("expected trace grammar must declare the four ordered events")
        if any(
            not isinstance(self.trace_markers[key], str) or not self.trace_markers[key]
            for key in _MARKER_KEYS
        ):
            raise BareSemanticEvidenceError("expected trace grammar markers must be non-empty strings")


def write_bare_semantics_sidecar(
    sidecar_path: str | Path,
    *,
    siesta_version: str,
    source_revision: str,
    executable_path: str | Path,
    reference_dm_path: str | Path,
    input_fdf_path: str | Path,
    output_path: str | Path,
    trace_path: str | Path,
    selected_event_lines: tuple[int, int],
    selected_iscf: int,
    population_cycle: int,
) -> Path:
    """Create one immutable BARE certificate from a converged native trace.

    This writer is intentionally narrow: it knows the diagnostic marker grammar
    introduced for the audited SIESTA 5.4.2 path and refuses an incomplete,
    aborted, ambiguous, or reused certificate. It never infers BARE
    semantics merely from an SCF iteration number; both indices select an
    already observed trace event.
    """

    destination = Path(sidecar_path)
    executable = Path(executable_path)
    reference_dm = Path(reference_dm_path)
    input_fdf = Path(input_fdf_path)
    output = Path(output_path)
    trace = Path(trace_path)
    if destination.exists():
        raise BareSemanticEvidenceError("refusing to overwrite a BARE semantic sidecar")
    if not isinstance(siesta_version, str) or not siesta_version.strip():
        raise BareSemanticEvidenceError("siesta_version is required")
    if not isinstance(source_revision, str) or not source_revision.strip():
        raise BareSemanticEvidenceError("source_revision is required")
    if type(selected_iscf) is not int or selected_iscf < 0:
        raise BareSemanticEvidenceError("selected_iscf must be a non-negative integer")
    if type(population_cycle) is not int or population_cycle < 1:
        raise BareSemanticEvidenceError("population_cycle must be a positive integer")
    if (
        not isinstance(selected_event_lines, tuple) or len(selected_event_lines) != 2
        or any(type(line) is not int or line < 1 for line in selected_event_lines)
        or selected_event_lines[0] > selected_event_lines[1]
    ):
        raise BareSemanticEvidenceError("selected_event_lines must be an ordered positive pair")
    if not all(path.is_file() for path in (executable, reference_dm, input_fdf, output, trace)):
        raise BareSemanticEvidenceError("executable, parent DM, input FDF, output, and trace must exist")
    input_fdf_text = input_fdf.read_text(encoding="utf-8", errors="replace")
    if _SCF_MUST_CONVERGE_FALSE.search(input_fdf_text) is None:
        raise BareSemanticEvidenceError("BARE input must explicitly set SCF.MustConverge F")

    output_text = output.read_text(encoding="utf-8", errors="replace")
    if _UNACCEPTABLE_TERMINATION.search(output_text) or not _NORMAL_TERMINATION.search(output_text):
        raise BareSemanticEvidenceError("BARE output is not a normal non-aborted SIESTA termination")
    output_lines = output_text.splitlines()
    if selected_event_lines[1] > len(output_lines) or not any(
        "hubbard_term" in line.lower()
        for line in output_lines[selected_event_lines[0] - 1:selected_event_lines[1]]
    ):
        raise BareSemanticEvidenceError("selected output interval does not contain a Hubbard population event")

    suffix = f"iscf={selected_iscf} population_cycle={population_cycle}"
    markers = {
        "reference_dm_loaded": "TRACE: LR_BARE reference_dm_accepted",
        "perturbation_applied": f"TRACE: LR_BARE perturbation_hamiltonian_built {suffix}",
        "selected_population": f"TRACE: LR_BARE population_evaluated {suffix}",
        "hxc_rebuild_after_selected_population": f"TRACE: LR_BARE hxc_rebuild_after_perturbation iscf={selected_iscf}",
    }
    trace_text = trace.read_text(encoding="utf-8", errors="replace")
    positions = []
    for key in _MARKER_KEYS:
        count = trace_text.count(markers[key])
        if count != 1:
            raise BareSemanticEvidenceError(f"trace marker {key} must occur exactly once")
        positions.append(trace_text.index(markers[key]))
    if positions != sorted(positions):
        raise BareSemanticEvidenceError("native trace does not prove the required BARE ordering")

    try:
        trace_reference = trace.resolve().relative_to(destination.parent.resolve())
    except ValueError as exc:
        raise BareSemanticEvidenceError("trace must be stored beside the sidecar") from exc
    payload = {
        "schema_version": _SCHEMA,
        "status": "PASS",
        "siesta_version": siesta_version,
        "executable_sha256": _sha256_file(executable),
        "source_revision": source_revision,
        "reference_dm_sha256": _sha256_file(reference_dm),
        "input_fdf_sha256": _sha256_file(input_fdf),
        "bare_scf_must_converge_false": True,
        "output_sha256": _sha256_file(output),
        "selected_event_lines": list(selected_event_lines),
        "hxc_rebuild_excluded_before_selected_event": True,
        "trace_reference": str(trace_reference),
        "trace_sha256": _sha256_file(trace),
        "trace_markers": markers,
    }
    destination.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return destination


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
    input_fdf_path: str | Path,
    output_path: str | Path,
    selected_event_lines: tuple[int, int],
    expectation: BareTraceExpectation,
) -> VerifiedBareEvidence:
    """Verify that one BARE output has a matching, ordered native trace.

    The trace must contain exact, unique diagnostic markers in the order
    ``DM -> selected population -> perturbation Hamiltonian -> Hxc rebuild``.
    The final marker deliberately proves Hxc rebuild occurs *after* the
    population used for ``chi0``. This is a certificate verifier, not a
    substitute for the source/debug-build audit that generated the markers.
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
        "reference_dm_sha256", "input_fdf_sha256", "bare_scf_must_converge_false",
        "output_sha256", "selected_event_lines",
        "hxc_rebuild_excluded_before_selected_event", "trace_reference", "trace_sha256",
        "trace_markers",
    }
    if set(payload) != required:
        raise BareSemanticEvidenceError("bare semantic sidecar has an unexpected schema")
    if payload["schema_version"] != _SCHEMA or payload["status"] != "PASS":
        raise BareSemanticEvidenceError("bare semantic sidecar is not an accepted PASS record")
    if payload["siesta_version"] != siesta_version:
        raise BareSemanticEvidenceError("SIESTA version differs from the certified build")
    if not isinstance(expectation, BareTraceExpectation):
        raise BareSemanticEvidenceError("an audited BARE trace expectation is required")
    if payload["source_revision"] != expectation.source_revision:
        raise BareSemanticEvidenceError("source_revision differs from the audited native trace")
    if payload["hxc_rebuild_excluded_before_selected_event"] is not True:
        raise BareSemanticEvidenceError("sidecar does not assert frozen-Hxc ordering")

    executable = Path(executable_path)
    reference_dm = Path(reference_dm_path)
    input_fdf = Path(input_fdf_path)
    output = Path(output_path)
    if not all(path.is_file() for path in (executable, reference_dm, input_fdf, output)):
        raise BareSemanticEvidenceError("executable, parent DM, input FDF, and output must exist")
    if payload["bare_scf_must_converge_false"] is not True or _SCF_MUST_CONVERGE_FALSE.search(
        input_fdf.read_text(encoding="utf-8", errors="replace")
    ) is None:
        raise BareSemanticEvidenceError("BARE sidecar is not bound to SCF.MustConverge F")
    output_text = output.read_text(encoding="utf-8", errors="replace")
    if _UNACCEPTABLE_TERMINATION.search(output_text) or not _NORMAL_TERMINATION.search(output_text):
        raise BareSemanticEvidenceError("BARE output is not a normal non-aborted SIESTA termination")
    for key, actual in (
        ("executable_sha256", _sha256_file(executable)),
        ("reference_dm_sha256", _sha256_file(reference_dm)),
        ("input_fdf_sha256", _sha256_file(input_fdf)),
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
    if dict(markers) != dict(expectation.trace_markers):
        raise BareSemanticEvidenceError("trace markers differ from the audited native grammar")
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
