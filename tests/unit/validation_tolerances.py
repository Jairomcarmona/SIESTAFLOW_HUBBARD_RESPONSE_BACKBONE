"""Single source for provisional tolerances in the published regression cases.

These values are review proposals for regression comparisons only. They do not
set a scientific acceptance threshold or authorize a Hubbard U.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ToleranceStatus(str, Enum):
    PROVISIONAL = "PROVISIONAL"
    PENDING_ARTIFACT = "PENDING_ARTIFACT"
    NOT_NUMERIC = "NOT_NUMERIC"


@dataclass(frozen=True)
class ValidationTolerance:
    value: float | None
    unit: str
    status: ToleranceStatus
    justification: str


MNO_LAPTOP_U_TOLERANCE = ValidationTolerance(
    None,
    "eV",
    ToleranceStatus.PENDING_ARTIFACT,
    "No matched laptop MnO output/analysis artifact is checked into the repository; do not substitute another run.",
)

CU3N_MATRIX_PERMUTATION_TOLERANCE = ValidationTolerance(
    0.0,
    "electrons/eV",
    ToleranceStatus.PROVISIONAL,
    "The archived Cu3N audit reports exactly zero residual for the eight certified translation permutations; this checks archive self-consistency only.",
)

CU3N_U_SPREAD_RECOMPUTATION_TOLERANCE_EV = ValidationTolerance(
    1.0e-12,
    "eV",
    ToleranceStatus.PROVISIONAL,
    "Arithmetic allowance for recomputing orbit spreads from the full-precision archived site-U array; not a physical equivalence threshold.",
)

M1_PROBE_CAMPAIGN_DELTA_TOLERANCE_EV = ValidationTolerance(
    1.0e-4,
    "eV",
    ToleranceStatus.PROVISIONAL,
    "Difference of two reported U values, each printed to four decimal places: sum of their 0.00005 eV half-quanta.",
)

M1_PROJECTOR_SCAN_U_TOLERANCE_EV = ValidationTolerance(
    5.0e-5,
    "eV",
    ToleranceStatus.PROVISIONAL,
    "One half-quantum for the four-decimal U values in the nine-point Yoltla fixture.",
)

LR06_OCCUPATION_TOLERANCE_E = ValidationTolerance(
    5.0e-7,
    "electron",
    ToleranceStatus.PROVISIONAL,
    "One half-quantum for the six-decimal Occupations values printed in the verified Yoltla trace.",
)

SIGNAL_RESTART_TOLERANCE = ValidationTolerance(
    None,
    "state",
    ToleranceStatus.NOT_NUMERIC,
    "Restart correctness is an exact state/receipt assertion, not a numerical comparison; no archived end-to-end signal-interrupted campaign is present.",
)
