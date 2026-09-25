"""Deterministic acceptance checks for a finite-response matrix."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np


@dataclass(frozen=True)
class MatrixResponseAcceptancePolicy:
    max_antisymmetry_relative: float
    max_condition_number: float
    max_inverse_relative_error: float
    noise_multiplier: float = 1.0

    def validate(self) -> None:
        values = np.asarray(list(asdict(self).values()), dtype=float)
        if not np.all(np.isfinite(values)) or np.any(values <= 0.0):
            raise ValueError("matrix acceptance policy requires positive finite values")


def _relative_antisymmetry(matrix: np.ndarray) -> float:
    return float(np.linalg.norm(matrix - matrix.T, ord=2) / max(np.linalg.norm(matrix, ord=2), 1e-300))


def _check_one(name: str, raw: np.ndarray, uncertainty: np.ndarray, policy: MatrixResponseAcceptancePolicy) -> dict[str, Any]:
    if raw.ndim != 2 or raw.shape[0] != raw.shape[1] or uncertainty.shape != raw.shape:
        raise ValueError("response matrix and uncertainty must be equally sized square arrays")
    if not np.all(np.isfinite(raw)) or not np.all(np.isfinite(uncertainty)) or np.any(uncertainty < 0.0):
        raise ValueError("response matrix or uncertainty is invalid")
    antisymmetry = _relative_antisymmetry(raw)
    matrix = (raw + raw.T) / 2.0
    rank = int(np.linalg.matrix_rank(matrix))
    condition = float(np.linalg.cond(matrix))
    uncertainty_norm = float(np.linalg.norm((uncertainty + uncertainty.T) / 2.0, ord=2) * policy.noise_multiplier)
    inverse_relative_bound = float(np.linalg.norm(np.linalg.inv(matrix), ord=2) * uncertainty_norm) if rank == matrix.shape[0] else float("inf")
    accepted = (
        antisymmetry <= policy.max_antisymmetry_relative
        and rank == matrix.shape[0]
        and condition <= policy.max_condition_number
        and inverse_relative_bound < 1.0
        and inverse_relative_bound / (1.0 - inverse_relative_bound) <= policy.max_inverse_relative_error
    )
    return {"name": name, "accepted": accepted, "antisymmetry_relative": antisymmetry, "rank": rank,
            "condition_number": condition, "uncertainty_norm": uncertainty_norm,
            "inverse_relative_error_bound": inverse_relative_bound, "matrix": matrix}


def accept_response_matrices(chi0_raw: np.ndarray, chi_raw: np.ndarray, chi0_uncertainty: np.ndarray,
                             chi_uncertainty: np.ndarray, policy: MatrixResponseAcceptancePolicy) -> dict[str, Any]:
    policy.validate()
    chi0 = _check_one("chi0", chi0_raw, chi0_uncertainty, policy)
    chi = _check_one("chi", chi_raw, chi_uncertainty, policy)
    return {"accepted": bool(chi0["accepted"] and chi["accepted"]), "policy": asdict(policy),
            "chi0": {key: value for key, value in chi0.items() if key != "matrix"},
            "chi": {key: value for key, value in chi.items() if key != "matrix"},
            "chi0_matrix": chi0["matrix"], "chi_matrix": chi["matrix"]}
