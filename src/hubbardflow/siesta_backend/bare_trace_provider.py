"""Fail-closed provider for native BARE semantic evidence.

This module deliberately validates evidence; it does not manufacture it.  A
standard SIESTA run does not, by itself, prove which Hartree--XC state was
used for the BARE response.  The caller must therefore provide a versioned
native trace and its sidecar, produced by an audited backend or an external
evidence provider.  The provider binds that record to the executable, parent
DM, FDF, output and trace through :mod:`bare_semantics_evidence`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .bare_semantics_evidence import (
    BareTraceExpectation,
    BareSemanticEvidenceError,
    VerifiedBareEvidence,
    verify_bare_semantics_evidence,
)


class BareTraceProviderError(ValueError):
    """A BARE trace is unavailable or fails its provenance contract."""


@dataclass(frozen=True)
class BareTraceRequest:
    """Immutable references needed to validate one BARE semantic record."""

    sidecar_path: Path
    siesta_version: str
    executable_path: Path
    reference_dm_path: Path
    input_fdf_path: Path
    output_path: Path
    selected_event_lines: tuple[int, int]
    expectation: BareTraceExpectation


@dataclass(frozen=True)
class BareTraceReceipt:
    """Proof that the supplied native trace passed the existing verifier."""

    status: str
    evidence_reference: str
    evidence_sha256: str
    selected_event_lines: tuple[int, int]


class NativeBareTraceProvider:
    """Validate versioned native BARE evidence without creating evidence.

    ``validate`` is intentionally read-only.  ``collect`` is explicit about
    the boundary: collecting a native trace requires an audited SIESTA build
    or a sanctioned backend hook, neither of which can be inferred from a
    normal ``siesta.out``.  It consequently fails closed until such a provider
    is supplied.
    """

    def validate(self, request: BareTraceRequest) -> BareTraceReceipt:
        try:
            evidence: VerifiedBareEvidence = verify_bare_semantics_evidence(
                request.sidecar_path,
                siesta_version=request.siesta_version,
                executable_path=request.executable_path,
                reference_dm_path=request.reference_dm_path,
                input_fdf_path=request.input_fdf_path,
                output_path=request.output_path,
                selected_event_lines=request.selected_event_lines,
                expectation=request.expectation,
            )
        except (BareSemanticEvidenceError, OSError, TypeError) as exc:
            raise BareTraceProviderError(
                f"native BARE evidence rejected: {exc}"
            ) from exc
        return BareTraceReceipt(
            status="VERIFIED",
            evidence_reference=evidence.evidence_reference,
            evidence_sha256=evidence.evidence_sha256,
            selected_event_lines=evidence.selected_event_lines,
        )

    def collect(self, destination: str | Path) -> Path:
        """Reject collection unless an audited native trace backend exists.

        The destination is accepted only to make the interface explicit; it
        is never created or modified by this provider.
        """

        raise BareTraceProviderError(
            "native BARE trace collection is unavailable: provide an audited "
            "versioned trace and sidecar; standard SIESTA output is not proof"
        )
