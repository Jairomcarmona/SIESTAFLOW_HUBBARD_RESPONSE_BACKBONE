from dataclasses import dataclass, field
from typing import List, Optional
import numpy as np

from ..domain.cardinals import Cardinals
from ..domain.exceptions import RecordCompletenessError
from .population_generator import OccupationRecord
from .fit_strategies import FitterStrategy, OLSFitterStrategy, WeightedFitterStrategy


class FitRejectionError(Exception):
    pass

@dataclass
class RegressionQualityPolicy:
    """Configurable gates for accepting a regression fit."""
    min_r_squared: Optional[float] = None
    max_absolute_residual: Optional[float] = None
    max_relative_asymmetry: Optional[float] = None
    max_design_condition: Optional[float] = None
    require_symmetric_grid: bool = False

from ..domain.provenance import ScientificArtifact

@dataclass
class RegressionRecord(ScientificArtifact):
    """Record containing fit results and diagnostics for an (observable, channel) pair.

    Attributes:
        observable_index: Index o of the observable (0..O-1).
        channel_index: Index p of the perturbed channel (0..P-1).
        slope: Fitted linear response slope dn/dalpha in 1/eV.
        intercept: Fitted occupation value at alpha=0.
        residual_norm: Norm of the residual vector from lstsq fit.
        r_squared: Coefficient of determination (R^2) goodness of fit.
        n_points: Number of alpha sample points used in regression.
        design_condition_number: Condition number of the design matrix X.
        design_rank: Rank of the design matrix X.
        design_singular_values: Singular values of the design matrix X.
        residuals: List of residuals for each point.
        max_abs_residual: Maximum absolute residual.
        asymmetry: Absolute asymmetry between positive and negative perturbations.
        asymmetry_available: Whether a symmetric grid permitted asymmetry calculation.
        slope_std_err: Standard error of the slope estimate.
        diagnostic_status: String categorical status of the fit.
    """
    observable_index: int
    channel_index: int
    slope: float
    intercept: float
    residual_norm: float
    r_squared: float
    n_points: int
    design_condition_number: float
    design_rank: int = 2
    design_singular_values: List[float] = field(default_factory=list)
    residuals: List[float] = field(default_factory=list)
    max_abs_residual: float = 0.0
    asymmetry: float = 0.0
    asymmetry_available: bool = False
    slope_std_err: float = float('nan')
    diagnostic_status: str = "FIT_VALID"
    
    def __post_init__(self):
        self.artifact_type = "RegressionRecord"
        payload = {
            "artifact_type": self.artifact_type,
            "schema_version": self.schema_version,
            "observable_index": self.observable_index,
            "channel_index": self.channel_index,
            "slope": self.slope,
            "intercept": self.intercept,
            "residual_norm": self.residual_norm,
            "r_squared": self.r_squared,
            "n_points": self.n_points,
            "design_condition_number": self.design_condition_number,
            "design_rank": self.design_rank,
            "design_singular_values": self.design_singular_values,
            "residuals": self.residuals,
            "max_abs_residual": self.max_abs_residual,
            "asymmetry": self.asymmetry,
            "asymmetry_available": self.asymmetry_available,
            "slope_std_err": self.slope_std_err,
            "diagnostic_status": self.diagnostic_status,
            "methodology_lock_hash": self.methodology_lock_hash,
            "source_artifact_ids": self.source_artifact_ids
        }
        self.generate_identity(payload)

class FitEngine:
    def __init__(self, strategy: FitterStrategy = None, policy: RegressionQualityPolicy = None):
        self.strategy = strategy or OLSFitterStrategy()
        self.policy = policy or RegressionQualityPolicy()


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

                slope, intercept, diags = self.strategy.fit(
                    alpha_values, occupation_values
                )
                
                r_squared = diags["r_squared"]
                residuals = diags["residuals"]
                residual_norm = float(np.linalg.norm(residuals))
                max_abs_residual = float(np.max(np.abs(residuals))) if len(residuals) > 0 else 0.0
                
                diag_status = diags["diagnostic_status"]
                
                # Check policy rejections
                if self.policy.min_r_squared is not None and not np.isnan(r_squared):
                    if r_squared < self.policy.min_r_squared:
                        diag_status = "FIT_REJECTED_BY_LOCKED_POLICY"
                        raise FitRejectionError(
                            f"Regression rejected: R^2 ({r_squared:.4f}) is below the policy threshold ({self.policy.min_r_squared}). "
                            f"Observable {o}, Channel {p}."
                        )
                
                if self.policy.max_absolute_residual is not None:
                    if max_abs_residual > self.policy.max_absolute_residual:
                        diag_status = "FIT_REJECTED_BY_LOCKED_POLICY"
                        raise FitRejectionError(
                            f"Regression rejected: Max absolute residual ({max_abs_residual:.4f}) exceeds policy threshold ({self.policy.max_absolute_residual})."
                        )
                
                if self.policy.require_symmetric_grid and not diags["asymmetry_available"]:
                    diag_status = "FIT_REJECTED_BY_LOCKED_POLICY"
                    raise FitRejectionError("Regression rejected: Symmetric grid required by policy but not available.")
                    
                if self.policy.max_relative_asymmetry is not None and diags["asymmetry_available"]:
                    if abs(diags["asymmetry"]) > self.policy.max_relative_asymmetry:
                        diag_status = "FIT_REJECTED_BY_LOCKED_POLICY"
                        raise FitRejectionError(f"Regression rejected: Asymmetry ({diags['asymmetry']:.4f}) exceeds threshold.")
                        
                if self.policy.max_design_condition is not None:
                    if diags["design_condition_number"] > self.policy.max_design_condition:
                        diag_status = "FIT_REJECTED_BY_LOCKED_POLICY"
                        raise FitRejectionError(f"Regression rejected: Design condition number ({diags['design_condition_number']:.4f}) exceeds threshold.")
                
                if not np.isnan(r_squared) and r_squared < 0.5 and diag_status == "FIT_VALID":
                    diag_status = "FIT_QUALITY_WARNING"

                regression_records.append(
                    RegressionRecord(
                        observable_index=o,
                        channel_index=p,
                        slope=slope,
                        intercept=intercept,
                        residual_norm=residual_norm,
                        r_squared=r_squared,
                        n_points=n_points,
                        design_condition_number=diags["design_condition_number"],
                        design_rank=diags["design_rank"],
                        design_singular_values=diags["design_singular_values"],
                        residuals=residuals,
                        max_abs_residual=max_abs_residual,
                        asymmetry=diags["asymmetry"],
                        asymmetry_available=diags["asymmetry_available"],
                        slope_std_err=diags["slope_std_err"],
                        diagnostic_status=diag_status
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
