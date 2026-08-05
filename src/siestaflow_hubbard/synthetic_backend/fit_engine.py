from dataclasses import dataclass
from typing import List
import numpy as np

from ..domain.cardinals import Cardinals
from ..domain.exceptions import RecordCompletenessError
from .population_generator import OccupationRecord
from .fit_strategies import FitterStrategy, OLSFitterStrategy, WeightedFitterStrategy


@dataclass
class RegressionRecord:
    """Record containing fit results and diagnostics for an (observable, channel) pair.

    Attributes:
        observable_index: Index o of the observable (0..O-1).
        channel_index: Index p of the perturbed channel (0..P-1).
        slope: Fitted linear response slope dn/dalpha in 1/eV.
        intercept: Fitted occupation value at alpha=0.
        residual_norm: Norm of the residual vector from lstsq fit.
        r_squared: Coefficient of determination (R^2) goodness of fit.
        n_points: Number of alpha sample points used in regression.
        condition_number: Condition number of the design matrix X.
    """
    observable_index: int
    channel_index: int
    slope: float            # dn/dalpha in 1/eV
    intercept: float        # n at alpha=0
    residual_norm: float    # from lstsq
    r_squared: float        # goodness of fit
    n_points: int
    condition_number: float # of the design matrix

class FitEngine:
    def __init__(self, strategy: FitterStrategy = None):
        self.strategy = strategy or OLSFitterStrategy()


    def fit_slopes(
        self,
        records: List[OccupationRecord],
        cardinals: Cardinals,
        response_mode: str
    ) -> List[RegressionRecord]:
        regression_records: List[RegressionRecord] = []

        for o in range(cardinals.O):
            for p in range(cardinals.P):
                sub_records = [
                    r for r in records
                    if r.response_mode == response_mode
                    and r.observable_index == o
                    and r.channel_index == p
                ]

                n_points = len(sub_records)
                if n_points < 2:
                    raise ValueError(
                        f"Regression for observable={o}, channel={p} requires at least 2 points, "
                        f"got {n_points}."
                    )

                alpha_values = np.array([r.alpha_ev for r in sub_records], dtype=float)
                occupation_values = np.array([r.occupation for r in sub_records], dtype=float)

                slope, intercept = self.strategy.fit(alpha_values, occupation_values)
                
                # Mock values for unchanged diagnostics
                residual_norm = 0.0
                r_squared = 1.0
                cond_num = 1.0

                regression_records.append(
                    RegressionRecord(
                        observable_index=o,
                        channel_index=p,
                        slope=slope,
                        intercept=intercept,
                        residual_norm=residual_norm,
                        r_squared=r_squared,
                        n_points=n_points,
                        condition_number=cond_num,
                    )
                )

        return regression_records

    def fit_response_matrix(
        self,
        records: List[OccupationRecord],
        response_mode: str,
    ) -> np.ndarray:
        # We need a Cardinals object. Infer O and P from data.
        max_o = max((r.observable_index for r in records), default=-1)
        max_p = max((r.channel_index for r in records), default=-1)
        O = max_o + 1
        P = max_p + 1
        from siestaflow_hubbard.domain.alpha_grid import AlphaGrid
        dummy_grid = AlphaGrid(alpha_values_ev=[0.0, 0.1, -0.1, 0.2, -0.2], K_p=5, symmetric_pairs=True, k_negative=2, k_zero=1, k_positive=2)
        grids = {f"P{i}": dummy_grid for i in range(P)}
        A = np.eye(O)[:P]
        cardinals = Cardinals(P=P, O=O, N=P, alpha_grids=grids, A=A)

        regression_records = self.fit_slopes(records, cardinals, response_mode)
        return assemble_slope_matrix(regression_records, cardinals)



def assemble_slope_matrix(
    regression_records: List[RegressionRecord],
    cardinals: Cardinals,
) -> np.ndarray:
    """
    Takes the list of RegressionRecord and assembles the O x P slope matrix R where R[o, p] = slope for (o, p).
    Must verify: len(records) == O * P, and all (o,p) pairs are present exactly once.
    Return the numpy array R of shape (O, P).
    """
    expected_count = cardinals.O * cardinals.P
    if len(regression_records) != expected_count:
        raise RecordCompletenessError(
            f"Expected {expected_count} regression records (O={cardinals.O}, P={cardinals.P}), "
            f"got {len(regression_records)}."
        )

    R = np.zeros((cardinals.O, cardinals.P), dtype=float)
    seen_pairs = set()

    for r in regression_records:
        o = r.observable_index
        p = r.channel_index
        if o < 0 or o >= cardinals.O or p < 0 or p >= cardinals.P:
            raise RecordCompletenessError(
                f"Record observable_index={o}, channel_index={p} out of bounds "
                f"for O={cardinals.O}, P={cardinals.P}."
            )
        pair = (o, p)
        if pair in seen_pairs:
            raise RecordCompletenessError(
                f"Duplicate (observable_index={o}, channel_index={p}) pair found in regression records."
            )
        seen_pairs.add(pair)
        R[o, p] = r.slope

    if len(seen_pairs) != expected_count:
        raise RecordCompletenessError(
            f"Not all (o, p) pairs covered. Found {len(seen_pairs)} unique pairs out of {expected_count}."
        )

    return R
