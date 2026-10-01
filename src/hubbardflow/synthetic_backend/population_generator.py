from dataclasses import dataclass
from typing import Tuple, List, Optional
import numpy as np

from ..domain.cardinals import Cardinals
from .noise_injection import NoiseParams


@dataclass
class OccupationRecord:
    """Record representing a single synthetic orbital occupation measurement.

    Attributes:
        response_mode: Perturbation mode ('BARE' or 'SCREENED').
        channel_index: Index p of the perturbed channel (0..P-1).
        alpha_ev: Perturbation strength alpha in eV.
        observable_index: Index o of the measured observable (0..O-1).
        occupation: Measured occupation value n.
    """
    response_mode: str
    channel_index: int
    alpha_ev: float
    observable_index: int
    occupation: float


def generate_populations(
    R_bare_true: np.ndarray,
    R_screened_true: np.ndarray,
    cardinals: Cardinals,
    intercepts: np.ndarray,
    noise_params: Optional[NoiseParams] = None,
) -> Tuple[List[OccupationRecord], List[OccupationRecord]]:
    """Generates synthetic occupation records for BARE and SCREENED response modes.

    One execution produces both BARE and SCREENED observation sets.

    Parameters:
        R_bare_true: True bare response slope matrix of shape (O, P).
        R_screened_true: True screened response slope matrix of shape (O, P).
        cardinals: Cardinals instance defining dimensions P, O, N, and alpha grids.
        intercepts: Baseline occupations of shape (O,).
        noise_params: Optional NoiseParams for adding Gaussian noise.

    Returns:
        Tuple of (bare_records, screened_records), each containing a list of OccupationRecord.
        Total records per mode = O * sum(K_p for all channels).
    """
    rng = np.random.default_rng(noise_params.seed) if (noise_params is not None and noise_params.sigma > 0) else None

    bare_records: List[OccupationRecord] = []
    screened_records: List[OccupationRecord] = []

    modes = [('BARE', R_bare_true, bare_records), ('SCREENED', R_screened_true, screened_records)]

    for response_mode, R_true, records in modes:
        for p in range(cardinals.P):
            if isinstance(cardinals.alpha_grids, dict):
                if p in cardinals.alpha_grids:
                    grid = cardinals.alpha_grids[p]
                elif f"P{p}" in cardinals.alpha_grids:
                    grid = cardinals.alpha_grids[f"P{p}"]
                elif str(p) in cardinals.alpha_grids:
                    grid = cardinals.alpha_grids[str(p)]
                else:
                    grid = list(cardinals.alpha_grids.values())[p]
            else:
                grid = cardinals.alpha_grids[p]

            for alpha_k in grid.alpha_values_ev:
                for o in range(cardinals.O):
                    if alpha_k == 0 or alpha_k == 0.0:
                        value = float(intercepts[o])
                    else:
                        value = float(intercepts[o] + R_true[o, p] * alpha_k)

                    if noise_params is not None and noise_params.sigma > 0:
                        value += float(rng.normal(0.0, noise_params.sigma))

                    record = OccupationRecord(
                        response_mode=response_mode,
                        channel_index=p,
                        alpha_ev=float(alpha_k),
                        observable_index=o,
                        occupation=value,
                    )
                    records.append(record)

    return (bare_records, screened_records)
