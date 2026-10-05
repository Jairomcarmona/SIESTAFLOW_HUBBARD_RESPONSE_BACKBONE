"""Run-local I/O for the D16 parent reproduction gate before perturbations."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path

from hubbardflow.domain.reference_reproduction import (
    ParentReproduction,
    ReferenceReproduction,
    ReproductionReason,
    ToleranceSource,
)
from hubbardflow.siesta_backend.reference_reproduction_evidence import reference_reproduction_evidence


def check_reference_reproduction(
    planning_output_path: Path,
    campaign_output_path: Path,
    planning_dm_sha256: str | None,
    campaign_dm_path: Path,
    criterion: ParentReproduction,
    expected_projectors: tuple[tuple[int, int], ...] | None = None,
    scf_dm_tolerance: float | None = None,
    tolerance_factor: float | None = None,
    tol_fermi_ev: float | None = None,
    fermi_tolerance_source: ToleranceSource | None = None,
) -> ReferenceReproduction:
    """Read frozen planning and fresh campaign evidence, retaining both DM identities."""
    campaign_dm_sha256 = sha256(campaign_dm_path.read_bytes()).hexdigest()
    try:
        planning_output = planning_output_path.read_text(encoding="utf-8")
        campaign_output = campaign_output_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        return ReferenceReproduction(
            criterion,
            ReproductionReason.EQUIVALENCE_NOT_ASSESSED,
            planning_dm_sha256,
            campaign_dm_sha256,
            f"reference output unreadable: {type(exc).__name__}: {exc}",
            declared_fermi_tolerance_ev=tol_fermi_ev,
            fermi_tolerance_source=fermi_tolerance_source,
        )
    return reference_reproduction_evidence(
        planning_output,
        campaign_output,
        planning_dm_sha256,
        campaign_dm_sha256,
        criterion,
        expected_projectors,
        scf_dm_tolerance,
        tolerance_factor,
        tol_fermi_ev,
        fermi_tolerance_source,
    )
