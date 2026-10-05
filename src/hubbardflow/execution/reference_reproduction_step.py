"""Run-local I/O for the D16 parent reproduction gate before perturbations."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path

from hubbardflow.domain.reference_reproduction import (
    ParentReproduction,
    ReferenceReproduction,
    ReproductionReason,
)
from hubbardflow.siesta_backend.reference_reproduction_evidence import reference_reproduction_evidence


def check_reference_reproduction(
    planning_output_path: Path,
    campaign_output_path: Path,
    planning_dm_sha256: str,
    campaign_dm_path: Path,
    criterion: ParentReproduction,
    expected_projectors: tuple[tuple[int, int], ...] | None = None,
) -> ReferenceReproduction:
    """Read frozen planning and fresh campaign evidence, retaining both DM identities."""
    campaign_dm_sha256 = sha256(campaign_dm_path.read_bytes()).hexdigest()
    try:
        planning_output = (
            planning_output_path.read_text(encoding="utf-8")
            if criterion is ParentReproduction.PRINT_EQUIVALENT
            else ""
        )
        campaign_output = (
            campaign_output_path.read_text(encoding="utf-8")
            if criterion is ParentReproduction.PRINT_EQUIVALENT
            else ""
        )
    except (OSError, UnicodeError) as exc:
        return ReferenceReproduction(
            criterion,
            ReproductionReason.PARENT_STATE_NOT_EQUIVALENT,
            planning_dm_sha256,
            campaign_dm_sha256,
            f"reference output unreadable: {type(exc).__name__}: {exc}",
        )
    return reference_reproduction_evidence(
        planning_output,
        campaign_output,
        planning_dm_sha256,
        campaign_dm_sha256,
        criterion,
        expected_projectors,
    )
