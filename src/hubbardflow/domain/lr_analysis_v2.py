"""Versioned, material-agnostic analysis contract for verified LR-U data.

This layer reports numerical candidates and their estimator sensitivity.  It
does not translate scalar charge-response U into a DFT+U functional parameter
or declare physical acceptance.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import math
import re
from pathlib import Path
from typing import Any, Literal, Mapping, Sequence

import numpy as np

from .elementwise_rounding import (
    InverseBoundStatus,
    bound_inverse_diagonal,
    bound_u_diagonal,
    fitted_print_interval,
)
from .u_certification import Interval
from .matrix_lr import (
    MatrixResponseResult,
    ResponseFitPolicy,
    ResponseObservation,
    analyze_matrix_response_campaign,
)
from .response_grid_reproducibility import ValidatedResponseGridCalibration


class LRAnalysisError(ValueError):
    """The supplied verified observations cannot define the requested fit."""


@dataclass(frozen=True)
class LRAnalysisPolicy:
    """Estimator and reportability policy, frozen with each new campaign."""

    estimator: Literal["auto", "polynomial", "linear"] = "auto"
    polynomial_degree: int = 3
    minimum_residual_dof: int = 1
    matrix_for_inversion: Literal["raw", "symmetrized"] = "raw"
    sensitivity_tolerance_eV: float | None = None
    sensitivity_tolerance_provided_via: Literal["config", "cli"] = "config"
    u_precision_tolerance_eV: float | None = None
    occupation_precision_requirement: Literal["f20.12"] | None = None

    def response_context(self) -> dict[str, Any]:
        """Return only policy fields that define the analyzed response.

        Acceptance tolerances are deliberately excluded: changing a threshold
        used to judge a result does not change the response measurements or
        estimator. Occupation precision remains included because it changes
        which printed values are admissible for analysis.
        """
        self.validate()
        return {
            "estimator": self.estimator,
            "polynomial_degree": self.polynomial_degree,
            "minimum_residual_dof": self.minimum_residual_dof,
            "matrix_for_inversion": self.matrix_for_inversion,
            "occupation_precision_requirement": self.occupation_precision_requirement,
        }

    def validate(self) -> None:
        if self.estimator not in {"auto", "polynomial", "linear"}:
            raise LRAnalysisError("estimator must be auto, polynomial, or linear")
        if isinstance(self.polynomial_degree, bool) or not isinstance(self.polynomial_degree, int):
            raise LRAnalysisError("polynomial_degree must be an integer")
        if not 1 <= self.polynomial_degree <= 3:
            raise LRAnalysisError("polynomial_degree must be between 1 and 3")
        if isinstance(self.minimum_residual_dof, bool) or not isinstance(self.minimum_residual_dof, int):
            raise LRAnalysisError("minimum_residual_dof must be an integer")
        if self.minimum_residual_dof < 1:
            raise LRAnalysisError("minimum_residual_dof must be positive")
        if self.matrix_for_inversion not in {"raw", "symmetrized"}:
            raise LRAnalysisError("matrix_for_inversion must be raw or symmetrized")
        if self.sensitivity_tolerance_eV is not None and (
            isinstance(self.sensitivity_tolerance_eV, bool)
            or not isinstance(self.sensitivity_tolerance_eV, (int, float))
            or not math.isfinite(float(self.sensitivity_tolerance_eV))
            or self.sensitivity_tolerance_eV < 0
        ):
            raise LRAnalysisError("sensitivity_tolerance_eV must be finite and nonnegative")
        if self.sensitivity_tolerance_provided_via not in {"config", "cli"}:
            raise LRAnalysisError("sensitivity_tolerance_provided_via must be config or cli")
        if self.u_precision_tolerance_eV is not None and (
            not math.isfinite(self.u_precision_tolerance_eV) or self.u_precision_tolerance_eV <= 0
        ):
            raise LRAnalysisError("u_precision_tolerance_eV must be finite and positive")
        if self.occupation_precision_requirement not in {None, "f20.12"}:
            raise LRAnalysisError("occupation_precision_requirement must be omitted or f20.12")


def _validate_observations(observations: Sequence[ResponseObservation]) -> tuple[list[int], dict[int, list[ResponseObservation]]]:
    if not observations:
        raise LRAnalysisError("no verified response observations were provided")
    labels = list(observations[0].site_labels)
    if not labels or len(set(labels)) != len(labels):
        raise LRAnalysisError("site labels must be non-empty and unique")
    by_site: dict[int, list[ResponseObservation]] = {label: [] for label in labels}
    for item in observations:
        if item.site_labels != labels:
            raise LRAnalysisError("response observations use inconsistent site labels")
        if item.perturbation_site not in by_site:
            raise LRAnalysisError(f"unknown perturbed site {item.perturbation_site}")
        if not math.isfinite(float(item.alpha)):
            raise LRAnalysisError("alpha values must be finite")
        for field_name in ("occupations_ref", "occupations_bare", "occupations_screened"):
            values = getattr(item, field_name)
            if len(values) != len(labels) or not np.all(np.isfinite(np.asarray(values, dtype=float))):
                raise LRAnalysisError(f"{field_name} must contain one finite value per site")
        by_site[item.perturbation_site].append(item)

    common_alphas: tuple[float, ...] | None = None
    for label, group in by_site.items():
        if not group:
            raise LRAnalysisError(f"missing response column for perturbed site {label}")
        alphas = [float(item.alpha) for item in group]
        if len(set(alphas)) != len(alphas):
            raise LRAnalysisError(f"duplicate alpha observations for perturbed site {label}")
        normalized = tuple(sorted(alphas))
        if common_alphas is None:
            common_alphas = normalized
        elif len(normalized) != len(common_alphas) or not np.allclose(
            normalized, common_alphas, rtol=1e-12, atol=1e-14
        ):
            raise LRAnalysisError("every perturbed site must use the same alpha grid")
    assert common_alphas is not None
    if min(common_alphas) >= 0.0 or max(common_alphas) <= 0.0:
        raise LRAnalysisError("alpha grid must contain negative and positive amplitudes")
    return labels, by_site


def _is_symmetric_grid(alphas: Sequence[float]) -> bool:
    values = np.asarray(alphas, dtype=float)
    negative = np.sort(values[values < 0.0])
    positive = np.sort(values[values > 0.0])
    return len(negative) == len(positive) and len(negative) > 0 and bool(
        np.allclose(-negative, positive[::-1], rtol=1e-10, atol=1e-14)
    )


def _fit_method(policy: LRAnalysisPolicy, alphas: Sequence[float]) -> tuple[str, str | None]:
    enough_points = len(alphas) >= policy.polynomial_degree + 1 + policy.minimum_residual_dof
    if policy.estimator == "linear":
        return "linear", None
    if policy.estimator == "polynomial":
        if not enough_points:
            raise LRAnalysisError(
                f"degree-{policy.polynomial_degree} fit needs at least "
                f"{policy.polynomial_degree + 1 + policy.minimum_residual_dof} alpha points"
            )
        if not _is_symmetric_grid(alphas):
            raise LRAnalysisError("polynomial policy requires a symmetric alpha grid")
        return "polynomial", None
    if enough_points and _is_symmetric_grid(alphas):
        return "polynomial", None
    reason = "insufficient_alpha_points" if not enough_points else "alpha_grid_not_symmetric"
    return "linear", reason


def _finite_json(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return [_finite_json(item) for item in value.tolist()]
    if isinstance(value, np.generic):
        return _finite_json(value.item())
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {str(key): _finite_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_finite_json(item) for item in value]
    return value


def _fit_diagnostics(result: MatrixResponseResult) -> list[dict[str, Any]]:
    def fit_record(fit: Any) -> dict[str, Any]:
        record = asdict(fit)
        if "degree" not in record:
            record["degree"] = 1
        if "coefficients" not in record:
            record["coefficients"] = [record.get("intercept"), record.get("slope")]
        residuals = record.get("residuals") or []
        n_points = record.get("n_points")
        if "residual_dof" not in record and isinstance(n_points, int):
            record["residual_dof"] = max(0, n_points - (record["degree"] + 1))
        if "residual_rms" not in record and residuals:
            record["residual_rms"] = math.sqrt(sum(float(value) ** 2 for value in residuals) / len(residuals))
        return record

    diagnostics: list[dict[str, Any]] = []
    for item in result.element_diagnostics:
        diagnostics.append({
            "observed_site": item.obs_site,
            "perturbed_site": item.pert_site,
            "mode": item.mode.upper(),
            "primary": fit_record(item.fit_full),
            "same_grid_linear": fit_record(item.fit_full_linear),
            "inner_linear": fit_record(item.fit_inner),
        })
    return diagnostics


def _matrix_summary(result: MatrixResponseResult) -> dict[str, Any]:
    u_by_site = None if result.U_matrix is None else {
        str(label): float(result.U_matrix[i, i])
        for i, label in enumerate(result.site_labels)
    }
    inversion_chi0 = result.inversion_chi0
    inversion_chi = result.inversion_chi
    return {
        "method": result.response_fit_method,
        "degree": result.response_polynomial_degree,
        "minimum_residual_dof": result.response_minimum_residual_dof,
        "alpha_window_ev": result.response_alpha_window_ev,
        "chi0_raw": result.chi0_raw,
        "chi_raw": result.chi_raw,
        "chi0_symmetrized": result.chi0_sym,
        "chi_symmetrized": result.chi_sym,
        "matrix_for_inversion": result.matrix_for_inversion,
        "matrix_used_chi0": result.chi0_selected,
        "matrix_used_chi": result.chi_selected,
        "chi0_inverse_eV": None if inversion_chi0 is None else inversion_chi0.inverse,
        "chi_inverse_eV": None if inversion_chi is None else inversion_chi.inverse,
        "inversion_diagnostics": {
            "chi0": None if inversion_chi0 is None else {
                "method": inversion_chi0.method,
                "left_residual_frobenius": inversion_chi0.left_residual,
                "right_residual_frobenius": inversion_chi0.right_residual,
            },
            "chi": None if inversion_chi is None else {
                "method": inversion_chi.method,
                "left_residual_frobenius": inversion_chi.left_residual,
                "right_residual_frobenius": inversion_chi.right_residual,
            },
        },
        "U_matrix_eV": result.U_matrix,
        "U_by_site_eV": u_by_site,
        "matrix_status": result.matrix_status,
        "chi0_diagnostics": asdict(result.condition_chi0),
        "chi_diagnostics": asdict(result.condition_chi),
        "fit_diagnostics": _fit_diagnostics(result),
    }


def _slope_rounding_bound(
    alpha: Sequence[float], half_widths: Sequence[float], *, degree: int,
) -> tuple[float, list[float]]:
    """Bound the fitted c1 coefficient for independent printed-value intervals.

    For a least-squares response fit, c1 is a linear functional of the input
    occupations.  The absolute row sum of its design-matrix coefficients
    therefore propagates bounded print rounding without assigning a
    statistical confidence level.
    """
    a = np.asarray(alpha, dtype=float)
    h = np.asarray(half_widths, dtype=float)
    if a.ndim != 1 or h.shape != a.shape or len(a) < degree + 1:
        raise ValueError("alpha and occupation half-width arrays do not support the requested fit")
    if (not np.all(np.isfinite(a)) or not np.all(np.isfinite(h)) or np.any(h < 0.0)
            or np.unique(a).size != len(a)):
        raise ValueError("alpha and occupation half-width arrays must be finite and valid")
    scale = float(np.max(np.abs(a)))
    if not math.isfinite(scale) or scale <= 0.0:
        raise ValueError("alpha scale must be positive and finite")
    design = np.polynomial.polynomial.polyvander(a / scale, degree)
    if np.linalg.matrix_rank(design) != degree + 1:
        raise ValueError("response fit design is rank deficient")
    # For the reduced QR factorization design = Q @ R, the least-squares
    # coefficient operator is R^-1 @ Q.T.  Its c1 row is
    # (Q @ solve(R.T, e1))^T.  This computes the same OLS functional without
    # forming a pseudoinverse or normal equations.  Physical c1 is scaled c1
    # divided by alpha_scale.
    q, r = np.linalg.qr(design, mode="reduced")
    c1_basis = np.zeros(degree + 1, dtype=float)
    c1_basis[1] = 1.0
    weights = (q @ np.linalg.solve(r.T, c1_basis)) / scale
    return float(np.abs(weights) @ h), [float(value) for value in weights]


def _response_slope_rounding_matrices(
    observations: Sequence[ResponseObservation],
    labels: Sequence[int],
    trace_half_widths_electron: Mapping[tuple[int, float, str], Sequence[float]] | None,
    *,
    degree: int,
    additional_uniform_half_width_e: float = 0.0,
    coordinate_extra_half_widths_e: Mapping[tuple[int, float, str, int], float] | None = None,
) -> tuple[np.ndarray | None, np.ndarray | None, list[str]]:
    """Build componentwise chi0/chi c1 bounds from the verified print widths."""
    if (trace_half_widths_electron is None and additional_uniform_half_width_e <= 0.0
            and coordinate_extra_half_widths_e is None):
        return None, None, ["matrix_trace_half_widths_not_supplied"]
    size = len(labels)
    chi0_widths = np.zeros((size, size), dtype=float)
    chi_widths = np.zeros((size, size), dtype=float)
    missing: list[str] = []
    for column, site_label in enumerate(labels):
        column_observations = sorted(
            (item for item in observations if item.perturbation_site == site_label),
            key=lambda item: item.alpha,
        )
        alphas = [float(item.alpha) for item in column_observations]
        for row in range(size):
            for mode, matrix in (("bare", chi0_widths), ("screened", chi_widths)):
                widths: list[float] = []
                for item in column_observations:
                    key = (int(item.perturbation_site), float(item.alpha), mode)
                    extra_key = (int(item.perturbation_site), float(item.alpha), mode.upper(), int(labels[row]))
                    extra = None if coordinate_extra_half_widths_e is None else coordinate_extra_half_widths_e.get(extra_key)
                    if coordinate_extra_half_widths_e is not None and extra is None:
                        missing.append(f"response_grid_calibration:{extra_key}")
                        break
                    values = None if trace_half_widths_electron is None else trace_half_widths_electron.get(key)
                    if values is None and additional_uniform_half_width_e > 0.0:
                        widths.append(additional_uniform_half_width_e)
                        continue
                    if values is None and extra is not None:
                        widths.append(float(extra))
                        continue
                    if values is None or len(values) != size:
                        missing.append(f"{key}:{row}")
                        break
                    try:
                        value = float(values[row])
                    except (TypeError, ValueError):
                        missing.append(f"{key}:{row}")
                        break
                    if not math.isfinite(value) or value < 0.0:
                        missing.append(f"{key}:{row}")
                        break
                    widths.append(value + additional_uniform_half_width_e + (0.0 if extra is None else float(extra)))
                if len(widths) != len(column_observations):
                    continue
                try:
                    bound, _ = _slope_rounding_bound(alphas, widths, degree=degree)
                except ValueError as exc:
                    missing.append(f"column={site_label},row={labels[row]},mode={mode}:{exc}")
                    continue
                matrix[row, column] = bound
    if missing:
        return None, None, sorted(set(missing))
    return chi0_widths, chi_widths, []


def _inverse_rounding_summary(matrix: np.ndarray, widths: np.ndarray) -> dict[str, Any]:
    """A raw-matrix inverse bound valid for any perturbation in the box.

    The Frobenius norm of the componentwise half-width matrix bounds the
    spectral norm of every allowed perturbation.  The Neumann-series bound
    then proves invertibility when beta < 1.  This deliberately does not
    symmetrize raw matrices.
    """
    value = np.asarray(matrix, dtype=float)
    interval = np.asarray(widths, dtype=float)
    if value.ndim != 2 or value.shape[0] != value.shape[1] or interval.shape != value.shape:
        raise ValueError("response matrix and component widths must be equally sized square matrices")
    if (not np.all(np.isfinite(value)) or not np.all(np.isfinite(interval))
            or np.any(interval < 0.0)):
        raise ValueError("response matrix and component widths must be finite; widths nonnegative")
    rank = int(np.linalg.matrix_rank(value))
    condition = float(np.linalg.cond(value))
    if rank != len(value):
        return {
            "robustly_invertible": False, "rank": rank, "condition_number": condition,
            "beta": None, "inverse_error_bound_eV": None,
        }
    inverse = np.linalg.inv(value)
    inverse_norm = float(np.linalg.norm(inverse, 2))
    delta_norm = float(np.linalg.norm(interval, "fro"))
    beta = inverse_norm * delta_norm
    robust = beta < 1.0
    error = inverse_norm ** 2 * delta_norm / (1.0 - beta) if robust else None
    return {
        "robustly_invertible": robust, "rank": rank, "condition_number": condition,
        "beta": beta, "inverse_error_bound_eV": error,
    }


def _rounding_summary(
    result: MatrixResponseResult,
    observations: Sequence[ResponseObservation],
    trace_half_widths_electron: Mapping[tuple[int, float, str], Sequence[float]] | None,
    *,
    degree: int,
    matrix_for_inversion: str,
    occupation_source: str = "printed Hubbard projector-matrix diagonal tokens summed as trace_total",
    additional_uniform_half_width_e: float = 0.0,
    coordinate_extra_half_widths_e: Mapping[tuple[int, float, str, int], float] | None = None,
) -> dict[str, Any]:
    chi0_widths, chi_widths, missing = _response_slope_rounding_matrices(
        observations, result.site_labels, trace_half_widths_electron, degree=degree,
        additional_uniform_half_width_e=additional_uniform_half_width_e,
        coordinate_extra_half_widths_e=coordinate_extra_half_widths_e,
    )
    if chi0_widths is None or chi_widths is None:
        return {
            "status": "UNAVAILABLE", "reason": "matrix_trace_print_half_widths_incomplete",
            "missing_inputs": missing,
            "rounding_source": occupation_source,
            "quantity": "deterministic_occupation_print_rounding_bound_not_statistical_uncertainty",
            "chi0_slope_half_width_eV_inv": None,
            "chi_slope_half_width_eV_inv": None,
            "U_scalar_half_width_by_site_eV": None,
        }
    if matrix_for_inversion == "symmetrized":
        chi0_matrix = np.asarray(result.chi0_sym, dtype=float)
        chi_matrix = np.asarray(result.chi_sym, dtype=float)
        chi0_widths_used = (chi0_widths + chi0_widths.T) / 2.0
        chi_widths_used = (chi_widths + chi_widths.T) / 2.0
    else:
        chi0_matrix = np.asarray(result.chi0_raw, dtype=float)
        chi_matrix = np.asarray(result.chi_raw, dtype=float)
        chi0_widths_used = chi0_widths
        chi_widths_used = chi_widths
    inverse0 = _inverse_rounding_summary(chi0_matrix, chi0_widths_used)
    inverse = _inverse_rounding_summary(chi_matrix, chi_widths_used)
    robust = inverse0["robustly_invertible"] and inverse["robustly_invertible"]
    point = None if result.U_matrix is None else np.diag(result.U_matrix).astype(float)
    if not robust or point is None:
        per_site = None
        maximum = None
        intervals = None
        status = "UNBOUNDED_MATRIX_SINGULARITY_NOT_EXCLUDED"
    else:
        common_bound = float(inverse0["inverse_error_bound_eV"] + inverse["inverse_error_bound_eV"])
        per_site = {str(label): common_bound for label in result.site_labels}
        intervals = {
            str(label): [float(point[index] - common_bound), float(point[index] + common_bound)]
            for index, label in enumerate(result.site_labels)
        }
        maximum = common_bound
        status = "BOUNDED"
    summary = {
        "status": status,
        "reason": None if robust else "print_intervals_do_not_guarantee_invertibility",
        "rounding_source": occupation_source,
        "quantity": "deterministic_occupation_print_rounding_bound_not_statistical_uncertainty",
        "matrix_for_inversion": matrix_for_inversion,
        "chi0_slope_half_width_eV_inv": chi0_widths,
        "chi_slope_half_width_eV_inv": chi_widths,
        "chi0_inverse_error_bound_eV": inverse0["inverse_error_bound_eV"],
        "chi_inverse_error_bound_eV": inverse["inverse_error_bound_eV"],
        "chi0_invertibility": {key: value for key, value in inverse0.items() if key != "inverse_error_bound_eV"},
        "chi_invertibility": {key: value for key, value in inverse.items() if key != "inverse_error_bound_eV"},
        "U_scalar_half_width_by_site_eV": per_site,
        "U_scalar_interval_by_site_eV": intervals,
        "maximum_U_scalar_half_width_eV": maximum,
    }

    if occupation_source == "siesta_occupations_total" and point is not None:
        summary["legacy_uniform_norm_bound"] = dict(summary)
        summary.update(_elementwise_rounding_summary(
            result, observations, trace_half_widths_electron, degree=degree,
            matrix_for_inversion=matrix_for_inversion,
            additional_uniform_half_width_e=additional_uniform_half_width_e,
            coordinate_extra_half_widths_e=coordinate_extra_half_widths_e,
        ))
    return summary


def _elementwise_rounding_summary(
    result: MatrixResponseResult,
    observations: Sequence[ResponseObservation],
    trace_half_widths_electron: Mapping[tuple[int, float, str], Sequence[float]] | None,
    *, degree: int, matrix_for_inversion: str,
    additional_uniform_half_width_e: float,
    coordinate_extra_half_widths_e: Mapping[tuple[int, float, str, int], float] | None,
) -> dict[str, Any]:
    """Retain print intervals through OLS and a verified inverse majorant.

    This v3 path recomputes the exact mathematical OLS center and accounts for
    its displacement from the reported floating fit. The v2/V6 path retains its
    existing norm propagation. No SCF uncertainty is inferred from print widths.
    """
    labels = result.site_labels
    boxes: dict[str, list[list[Interval]]] = {
        mode: [[Interval(0, 0) for _ in labels] for _ in labels]
        for mode in ("bare", "screened")
    }
    for column, label in enumerate(labels):
        group = sorted((x for x in observations if x.perturbation_site == label), key=lambda x: x.alpha)
        for row, observed_label in enumerate(labels):
            for mode in ("bare", "screened"):
                widths = []
                for item in group:
                    values = None if trace_half_widths_electron is None else trace_half_widths_electron.get(
                        (label, float(item.alpha), mode)
                    )
                    extra = 0.0 if coordinate_extra_half_widths_e is None else coordinate_extra_half_widths_e[
                        (label, float(item.alpha), mode.upper(), observed_label)
                    ]
                    components = [0.0 if values is None else float(values[row]),
                                  additional_uniform_half_width_e, float(extra)]
                    # Enclose both constituent conversion and summation, without
                    # an empirical epsilon or any policy tolerance.
                    widths.append(math.nextafter(math.fsum(
                        math.nextafter(x, math.inf) if x > 0.0 else x for x in components
                    ), math.inf) if any(components) else 0.0)
                boxes[mode][row][column] = fitted_print_interval(
                    [float(x.alpha) for x in group],
                    [float(getattr(x, "occupations_" + mode)[row]) for x in group],
                    widths, degree=degree,
                )
    if matrix_for_inversion == "symmetrized":
        for mode in ("bare", "screened"):
            original = boxes[mode]
            boxes[mode] = [[Interval((original[i][j].lo + original[j][i].lo) / 2,
                                    (original[i][j].hi + original[j][i].hi) / 2)
                            for j in range(len(labels))] for i in range(len(labels))]
    bare = bound_inverse_diagonal(boxes["bare"])
    screened = bound_inverse_diagonal(boxes["screened"])
    proof = {"chi0": bare.to_mapping(), "chi": screened.to_mapping()}
    common = {
        "propagation_method": "verified_elementwise_neumann_with_exact_OLS_print_box",
        "elementwise_inverse_proof": proof,
        "elementwise_response_boxes_exact": {
            mode: [[x.as_json() for x in row] for row in boxes[mode]]
            for mode in ("bare", "screened")
        },
    }
    if bare.status != InverseBoundStatus.BOUNDED or screened.status != InverseBoundStatus.BOUNDED:
        return {**common, "status": "UNBOUNDED_MATRIX_SINGULARITY_NOT_EXCLUDED",
                "reason": "elementwise_print_box_contraction_not_proven",
                "U_scalar_half_width_by_site_eV": None,
                "U_scalar_interval_by_site_eV": None, "maximum_U_scalar_half_width_eV": None}
    assert result.U_matrix is not None
    bounds = bound_u_diagonal(bare, screened, np.diag(result.U_matrix).tolist()).to_mapping()
    return {**common, "status": "BOUNDED", "reason": None,
            "U_scalar_half_width_by_site_eV": dict(zip(map(str, labels), bounds["half_width_eV"])),
            "U_scalar_interval_by_site_eV": dict(zip(map(str, labels), bounds["intervals_eV"])),
            "maximum_U_scalar_half_width_eV": max(bounds["half_width_eV"])}


def _response_grid_empirical_widths(
    observations: Sequence[ResponseObservation],
    trace_half_widths_electron: Mapping[tuple[int, float, str], Sequence[float]] | None,
    calibration: ValidatedResponseGridCalibration | Mapping[str, Any] | None,
    *,
    primary_campaign_id: str | None,
    primary_source_root: str | None,
    primary_execution_attempt_ids: Sequence[str] | None,
) -> tuple[dict[tuple[int, float, str, int], float] | None, dict[str, Any]]:
    """Compare every independent replica coordinate directly with primary data.

    The expanded width contains observed primary-to-replica spread, replica
    quantization, and the primary quantization is retained separately in the
    deterministic print propagation.  This is conditional repeatability,
    never a confidence interval or a truth bound.
    """
    if calibration is None:
        return None, {"status": "NOT_PROVIDED", "reason": "response_grid_calibration_not_configured"}
    if not isinstance(calibration, ValidatedResponseGridCalibration):
        return None, {
            "status": str(calibration.get("validation_status", "UNVERIFIED_MEASUREMENT_VALUES")),
            "reason": str(calibration.get(
                "reason", "only the semantic validation function can produce an admitted response-grid calibration"
            )),
        }
    if (not primary_campaign_id or not primary_source_root
            or primary_campaign_id in calibration.replica_campaign_ids
            or str(Path(primary_source_root).resolve()) in calibration.replica_source_roots):
        return None, {
            "status": "PRIMARY_NOT_INDEPENDENT_OF_REPLICA_SET",
            "reason": "primary_campaign_uuid_or_source_root_is_shared_with_a_replica",
            "scope": "NO_EMPIRICAL_ENVELOPE_EMITTED",
        }
    if (not isinstance(primary_execution_attempt_ids, (list, tuple, set))
            or not primary_execution_attempt_ids
            or any(not isinstance(item, str) or not item for item in primary_execution_attempt_ids)):
        return None, {
            "status": "PRIMARY_EXECUTION_IDENTITY_UNAVAILABLE",
            "reason": "primary_reference_and_response_attempt_ids_are_required",
            "scope": "NO_EMPIRICAL_ENVELOPE_EMITTED",
        }
    shared_attempts = set(primary_execution_attempt_ids).intersection(calibration.execution_attempt_ids)
    if shared_attempts:
        return None, {
            "status": "PRIMARY_NOT_INDEPENDENT_OF_REPLICA_SET",
            "reason": "primary_and_replica_execution_attempt_ids_are_shared",
            "shared_attempt_ids": sorted(shared_attempts),
            "scope": "NO_EMPIRICAL_ENVELOPE_EMITTED",
        }
    try:
        samples = calibration.observed_replicas_by_coordinate
        replica_widths = calibration.replica_print_half_widths_by_coordinate
        safety = float(calibration.safety_factor)
        floor = float(calibration.deterministic_floor_e)
        replica_count = int(calibration.replica_count)
    except (AttributeError, TypeError, ValueError) as exc:
        return None, {"status": "INVALID_OR_UNAVAILABLE", "reason": f"validated calibration payload malformed: {exc}"}
    if replica_count < 3 or not math.isfinite(safety) or safety < 1.0 or not math.isfinite(floor) or floor <= 0.0:
        return None, {"status": "INVALID_OR_UNAVAILABLE", "reason": "calibration replicate/safety/floor contract is invalid"}
    if trace_half_widths_electron is None:
        return None, {"status": "INCOMPLETE_PRIMARY_QUANTIZATION", "reason": "primary occupation print widths are missing"}
    widths: dict[tuple[int, float, str, int], float] = {}
    rows: list[dict[str, Any]] = []
    missing: list[str] = []
    for item in observations:
        for mode, primary_values in (("BARE", item.occupations_bare), ("SCREENED", item.occupations_screened)):
            source_key = (int(item.perturbation_site), float(item.alpha), mode.lower())
            primary_half_widths = trace_half_widths_electron.get(source_key)
            if primary_half_widths is None or len(primary_half_widths) != len(item.site_labels):
                missing.append(f"primary_print_widths:{source_key}")
                continue
            for row, observed_site in enumerate(item.site_labels):
                coordinate = (int(item.perturbation_site), float(item.alpha), mode, int(observed_site))
                values = samples.get(coordinate)
                quantization = replica_widths.get(coordinate)
                if (not isinstance(values, (list, tuple)) or len(values) != replica_count
                        or not isinstance(quantization, (list, tuple)) or len(quantization) != replica_count):
                    missing.append(str(coordinate))
                    continue
                primary_value = float(primary_values[row])
                try:
                    differences = [abs(float(value) - primary_value) for value in values]
                    replica_q = [float(value) for value in quantization]
                    primary_q = float(primary_half_widths[row])
                except (TypeError, ValueError, IndexError):
                    missing.append(f"invalid_values:{coordinate}")
                    continue
                if (not all(math.isfinite(value) for value in (*differences, *replica_q, primary_q))
                        or any(value < 0.0 for value in replica_q) or primary_q < 0.0):
                    missing.append(f"invalid_quantization_or_value:{coordinate}")
                    continue
                observed_spread = safety * max(differences, default=0.0)
                max_replica_quantization = max(replica_q, default=0.0)
                expanded = max(floor, observed_spread) + max_replica_quantization
                widths[coordinate] = expanded
                rows.append({
                    "perturbed_site": coordinate[0], "alpha_eV": coordinate[1],
                    "mode": mode, "observed_site": coordinate[3],
                    "primary_to_replica_max_abs_difference_e": max(differences, default=0.0),
                    "safety_expanded_empirical_repeatability_e": observed_spread,
                    "replica_print_half_width_max_e": max_replica_quantization,
                    "primary_print_half_width_e": primary_q,
                    "conditional_occupation_half_width_e": expanded + primary_q,
                })
    if missing:
        return None, {
            "status": "INCOMPLETE_ACTIVE_GRID_COVERAGE",
            "reason": "missing_primary_or_replica_coordinate_or_quantization",
            "missing_coordinates": sorted(set(missing)),
            "scope": "EMPIRICAL_REPRODUCIBILITY_ONLY_NOT_A_TOTAL_ERROR_BOUND",
        }
    return widths, {
        "status": "COMPLETE_EMPIRICAL_RESPONSE_GRID_REPLICAS",
        "scope": calibration.scope,
        "replica_count": replica_count,
        "safety_factor": safety,
        "primary_observation_comparison": "each replica is compared directly to the primary campaign observation",
        "quantization": "primary and per-replica print half-widths are propagated separately with empirical spread",
        "coordinates": rows,
        "interpretation": "conditional numerical reproducibility envelope; not probabilistic confidence or mathematical error bound",
    }


def analyze_verified_lr(
    observations: Sequence[ResponseObservation],
    policy: LRAnalysisPolicy,
    *,
    campaign: Mapping[str, Any] | None = None,
    magnetic_state_labels: Mapping[float, str] | None = None,
    scf_validated: bool | None = None,
    active_window_ev: float | None = None,
    trace_half_widths_electron: Mapping[tuple[int, float, str], Sequence[float]] | None = None,
    occupation_source: str = "printed Hubbard projector-matrix diagonal tokens summed as trace_total",
    occupation_noise_calibration: Mapping[str, Any] | None = None,
    response_grid_reproducibility_calibration: ValidatedResponseGridCalibration | Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Analyze verified observations, retain candidates, and report sensitivity.

    Branch and SCF evidence are explicit optional inputs. Missing evidence
    lowers the numerical status to ``NUMERICAL_CANDIDATE_SENSITIVE`` while
    preserving a computable U value. A contradictory state label suppresses
    a single combined U. No acceptance policy is inferred from literature.
    """
    policy.validate()
    calibration_evidence: dict[str, Any] | None = None
    calibrated_noise_e: float | None = None
    if occupation_noise_calibration is not None:
        try:
            calibrated_noise_e = float(occupation_noise_calibration["occupation_noise_e"])
            validation_status = str(occupation_noise_calibration["validation_status"])
            result_digest = str(occupation_noise_calibration["result_sha256"])
            lock_digest = str(occupation_noise_calibration["lock_sha256"])
            control_alpha = float(occupation_noise_calibration["control_alpha_eV"])
            scope = str(occupation_noise_calibration["scope"])
            campaign_id = str(occupation_noise_calibration["campaign_id"])
        except (KeyError, TypeError, ValueError) as exc:
            raise LRAnalysisError("occupation noise calibration must be a validated calibration receipt") from exc
        if (not math.isfinite(calibrated_noise_e) or calibrated_noise_e <= 0.0
                or not re.fullmatch(r"[0-9a-f]{64}", result_digest)
                or not re.fullmatch(r"[0-9a-f]{64}", lock_digest)
                or not math.isfinite(control_alpha) or control_alpha != 0.0
                or scope != "INDEPENDENT_ZERO_SHIFT_CONTROL_REPEATABILITY_ONLY"
                or validation_status != "VERIFIED_IMMUTABLE_CALIBRATION_RECEIPT"
                or not campaign_id):
            raise LRAnalysisError("occupation noise calibration receipt has invalid value, digest, or scope")
        calibration_evidence = {
            "campaign_id": campaign_id,
            "result_sha256": result_digest,
            "lock_sha256": lock_digest,
            "occupation_noise_e": calibrated_noise_e,
            "control_alpha_eV": control_alpha,
            "scope": scope,
            "transfer_to_nonzero_alpha_established": False,
            "evidence_status": "EMPIRICAL_CONTROL_REPEATABILITY_ONLY",
        }
    if occupation_source not in {
        "printed Hubbard projector-matrix diagonal tokens summed as trace_total",
        "siesta_occupations_total",
    }:
        raise LRAnalysisError("occupation_source must identify a supported printed occupation observable")
    labels, by_site = _validate_observations(observations)
    all_alphas = sorted(float(item.alpha) for item in by_site[labels[0]])
    active_observations = list(observations)
    if active_window_ev is not None:
        if not math.isfinite(float(active_window_ev)) or float(active_window_ev) <= 0.0:
            raise LRAnalysisError("active_window_ev must be positive and finite")
        active_observations = [
            item for item in observations
            if abs(float(item.alpha)) <= float(active_window_ev) + 1e-14
        ]
        if not active_observations:
            raise LRAnalysisError("active alpha window contains no verified observations")
        _, active_by_site = _validate_observations(active_observations)
        alphas = sorted(float(item.alpha) for item in active_by_site[labels[0]])
        required = (
            policy.polynomial_degree + 1 + policy.minimum_residual_dof
            if policy.estimator == "polynomial"
            else 2 + policy.minimum_residual_dof
        )
        if len(alphas) < required:
            raise LRAnalysisError(
                f"active alpha window has {len(alphas)} points; the declared estimator/DoF require {required}"
            )
    else:
        alphas = all_alphas
    selected_method, fallback_reason = _fit_method(policy, alphas)
    primary_policy = ResponseFitPolicy(
        method=selected_method,
        polynomial_degree=policy.polynomial_degree,
        minimum_residual_dof=policy.minimum_residual_dof,
    )
    primary = analyze_matrix_response_campaign(
        active_observations,
        matrix_for_inversion=policy.matrix_for_inversion,
        fit_policy=primary_policy,
    )

    same_grid_linear = primary if selected_method == "linear" else analyze_matrix_response_campaign(
        active_observations,
        matrix_for_inversion=policy.matrix_for_inversion,
        fit_policy=ResponseFitPolicy(method="linear"),
    )

    positive_levels = sorted({abs(value) for value in alphas if value > 0.0})
    window_results: list[dict[str, Any]] = []
    for level in positive_levels:
        window_policy = ResponseFitPolicy(method="linear", alpha_window_ev=level)
        window_observations = [item for item in active_observations if abs(float(item.alpha)) <= level + 1e-14]
        try:
            window_result = analyze_matrix_response_campaign(
                window_observations,
                matrix_for_inversion=policy.matrix_for_inversion,
                fit_policy=window_policy,
            )
        except ValueError:
            continue
        n_points = len({float(item.alpha) for item in window_observations})
        residual_dof = max(0, n_points - 2)
        eligible = residual_dof >= policy.minimum_residual_dof
        summary = {"alpha_window_ev": level, **_matrix_summary(window_result)}
        summary.update({
            "window_diagnostic_type": (
                "FIT_WINDOW_STABILITY_SAMPLE" if eligible
                else "CENTRAL_DIFFERENCE" if n_points == 2
                else "LINEAR_DIAGNOSTIC_INSUFFICIENT_DOF"
            ),
            "fit_window_stability_eligible": eligible,
            "window_point_count": n_points,
            "linear_fit_residual_dof": residual_dof,
            "window_classification": (
                "eligible_linear_fit_window" if eligible
                else "resolution_limited_two_point_central_difference" if n_points == 2
                else "insufficient_residual_degrees_of_freedom"
            ),
            "rounding_bound": _rounding_summary(
            window_result, window_observations, trace_half_widths_electron,
            degree=1, matrix_for_inversion=policy.matrix_for_inversion,
            occupation_source=occupation_source,
            ),
        })
        window_results.append(summary)

    # The all-point fit is explicitly diagnostic when the policy declares an
    # active window. It never replaces the round's primary response matrices.
    full_grid_diagnostic: dict[str, Any] | None = None
    if active_window_ev is not None and len(active_observations) != len(observations):
        try:
            full_result = analyze_matrix_response_campaign(
                list(observations),
                matrix_for_inversion=policy.matrix_for_inversion,
                fit_policy=ResponseFitPolicy(
                    method=selected_method,
                    polynomial_degree=policy.polynomial_degree,
                    minimum_residual_dof=policy.minimum_residual_dof,
                ),
            )
            full_grid_diagnostic = _matrix_summary(full_result)
        except ValueError as exc:
            full_grid_diagnostic = {"status": "UNAVAILABLE", "reason": str(exc)}

    state_values: list[str] | None = None
    if magnetic_state_labels is not None:
        expected_keys = {float(value) for value in all_alphas}
        supplied_keys = {float(value) for value in magnetic_state_labels}
        if supplied_keys != expected_keys or any(not str(value).strip() for value in magnetic_state_labels.values()):
            raise LRAnalysisError("magnetic state labels must cover the alpha grid exactly")
        state_values = [str(magnetic_state_labels[value]) for value in alphas]
    mixed_states = state_values is not None and len(set(state_values)) > 1

    primary_by_site = None if primary.U_matrix is None else np.diag(primary.U_matrix).astype(float)
    model_sensitivity: dict[str, float | None] | None = None
    window_sensitivity: dict[str, float | None] | None = None
    max_sensitivity: float | None = None
    # A linear primary fit compared with the same full-grid linear fit is the
    # same estimator twice; reporting a zero difference would falsely imply a
    # model comparison.  Only compare polynomial vs linear when both are
    # genuinely distinct fits over the same observations.
    model_diagonal = (
        None if selected_method != "polynomial" or same_grid_linear.U_matrix is None
        else np.diag(same_grid_linear.U_matrix).astype(float)
    )
    window_diagonals = [
        np.asarray([item["U_by_site_eV"][str(label)] for label in labels], dtype=float)
        for item in window_results
        if item.get("fit_window_stability_eligible") is True
        and isinstance(item.get("U_by_site_eV"), dict)
    ]
    if primary_by_site is not None:
        model_sensitivity = {
            str(label): (abs(float(primary_by_site[i] - model_diagonal[i])) if model_diagonal is not None else None)
            for i, label in enumerate(labels)
        }
        window_sensitivity = {
            str(label): (
                float(max(vector[i] for vector in window_diagonals) - min(vector[i] for vector in window_diagonals))
                if len(window_diagonals) > 1 else None
            )
            for i, label in enumerate(labels)
        }
        available_sensitivities = [
            value for value in [*model_sensitivity.values(), *window_sensitivity.values()]
            if value is not None
        ]
        if available_sensitivities:
            max_sensitivity = max(available_sensitivities)

    primary_rounding = _rounding_summary(
        primary, active_observations, trace_half_widths_electron,
        degree=policy.polynomial_degree if selected_method == "polynomial" else 1,
        matrix_for_inversion=policy.matrix_for_inversion,
        occupation_source=occupation_source,
    )
    grid_extra_widths, grid_repeatability = _response_grid_empirical_widths(
        active_observations, trace_half_widths_electron,
        response_grid_reproducibility_calibration,
        primary_campaign_id=(str(campaign.get("campaign_id")) if campaign else None),
        primary_source_root=(str(campaign.get("source_root")) if campaign and campaign.get("source_root") else None),
        primary_execution_attempt_ids=(campaign.get("execution_attempt_ids") if campaign else None),
    )
    response_grid_conditional_envelope = None
    if grid_extra_widths is not None:
        response_grid_conditional_envelope = _rounding_summary(
            primary, active_observations, trace_half_widths_electron,
            degree=policy.polynomial_degree if selected_method == "polynomial" else 1,
            matrix_for_inversion=policy.matrix_for_inversion,
            occupation_source="primary deterministic print intervals plus coordinate-wise independent response-grid replica spread",
            coordinate_extra_half_widths_e=grid_extra_widths,
        )
        response_grid_conditional_envelope["status"] = (
            "CONDITIONALLY_BOUNDED_EMPIRICAL_REPRODUCIBILITY"
            if response_grid_conditional_envelope.get("status") == "BOUNDED"
            else response_grid_conditional_envelope.get("status")
        )
        response_grid_conditional_envelope["interpretation"] = (
            "conditional numerical reproducibility envelope; not probabilistic confidence, a mathematical error bound, or a truth guarantee"
        )
    # This is an explicitly conditional propagation: the observed zero-shift
    # repeatability is applied uniformly to response observations only to show
    # the consequence of that assumption.  The current calibration contract
    # does not validate this transfer, so this is never a total-U interval.
    same_grid_linear_rounding = _rounding_summary(
        same_grid_linear, active_observations, trace_half_widths_electron,
        degree=1, matrix_for_inversion=policy.matrix_for_inversion,
        occupation_source=occupation_source,
    )
    model_sensitivity_available = selected_method == "polynomial" and model_diagonal is not None
    window_sensitivity_available = window_sensitivity is not None and all(
        value is not None for value in window_sensitivity.values()
    )
    sensitivity_metrics_complete = (
        model_sensitivity_available and window_sensitivity_available
        if selected_method == "polynomial" else window_sensitivity_available
    )

    reasons: list[str] = []
    sensitivity_state = "UNASSESSED"
    if fallback_reason:
        reasons.append(f"linear_fallback:{fallback_reason}")
    if selected_method == "linear":
        reasons.append("model_sensitivity_unavailable_for_linear_primary")
    sensitivity_assessment: str
    if primary.U_matrix is None:
        numerical_status = "NO_NUMERICAL_U"
        reasons.append(primary.matrix_status)
    elif mixed_states:
        numerical_status = "NO_SINGLE_STATE_U"
        reasons.append("electronic_or_magnetic_state_changed_across_alpha")
    else:
        sensitivity_ok = policy.sensitivity_tolerance_eV is not None and (
            max_sensitivity is not None and max_sensitivity <= policy.sensitivity_tolerance_eV
        )
        evidence_complete = state_values is not None and scf_validated is True
        sensitivity_exceeded = (
            policy.sensitivity_tolerance_eV is not None
            and max_sensitivity is not None
            and max_sensitivity > policy.sensitivity_tolerance_eV
        )
        if policy.sensitivity_tolerance_eV is None:
            sensitivity_assessment = "UNASSESSED_TOLERANCE_MISSING"
            sensitivity_state = "UNASSESSED"
            numerical_status = "NUMERICAL_CANDIDATE_UNASSESSED"
        elif sensitivity_exceeded:
            sensitivity_assessment = "MEASURED_EXCEEDS_TOLERANCE"
            sensitivity_state = "SENSITIVE"
            numerical_status = "NUMERICAL_CANDIDATE_SENSITIVE"
        elif not sensitivity_metrics_complete:
            sensitivity_assessment = "UNASSESSED_REQUIRED_METRIC_UNAVAILABLE"
            sensitivity_state = "UNASSESSED"
            numerical_status = "NUMERICAL_CANDIDATE_UNASSESSED"
        elif sensitivity_ok and evidence_complete:
            sensitivity_assessment = "WITHIN_TOLERANCE"
            sensitivity_state = "NUMERICAL_CANDIDATE"
            numerical_status = "NUMERICAL_CANDIDATE"
        else:
            sensitivity_assessment = (
                "WITHIN_TOLERANCE_EVIDENCE_INCOMPLETE" if sensitivity_ok
                else "UNASSESSED_REQUIRED_METRIC_UNAVAILABLE"
            )
            sensitivity_state = (
                "WITHIN_TOLERANCE_EVIDENCE_INCOMPLETE" if sensitivity_ok else "UNASSESSED"
            )
            numerical_status = "NUMERICAL_CANDIDATE_SENSITIVE"
        if policy.sensitivity_tolerance_eV is None:
            reasons.append("sensitivity_tolerance_not_configured")
        elif sensitivity_exceeded:
            reasons.append("estimator_or_window_sensitivity_exceeds_policy")
        elif not sensitivity_metrics_complete:
            reasons.append("required_model_or_window_sensitivity_unavailable")
        if max_sensitivity is None:
            reasons.append("model_or_window_sensitivity_not_fully_available")
        if state_values is None:
            reasons.append("electronic_state_continuity_not_provided")
        if scf_validated is not True:
            reasons.append("scf_validation_not_provided")

    primary_summary = _matrix_summary(primary)
    primary_summary["rounding_bound"] = primary_rounding
    linear_summary = _matrix_summary(same_grid_linear)
    linear_summary["rounding_bound"] = same_grid_linear_rounding
    max_rounding_bound = primary_rounding.get("maximum_U_scalar_half_width_eV")
    conditional_half_widths = (
        (response_grid_conditional_envelope or {}).get("U_scalar_half_width_by_site_eV")
        if isinstance(response_grid_conditional_envelope, Mapping) else None
    )
    conditional_max_half_width = (
        max((float(value) for value in conditional_half_widths.values()), default=None)
        if isinstance(conditional_half_widths, Mapping) else None
    )
    # Decompose the future total-precision check into disjoint input sources.
    # The deterministic term uses only primary-output quantization.  The
    # repeatability-only propagation uses replica quantization plus observed
    # primary-to-replica spread, with no primary print widths, so the latter
    # are not counted twice when the two propagated half-widths are summed.
    repeatability_only = None
    if grid_extra_widths is not None:
        repeatability_only = _rounding_summary(
            primary, active_observations, None,
            degree=policy.polynomial_degree if selected_method == "polynomial" else 1,
            matrix_for_inversion=policy.matrix_for_inversion,
            occupation_source="independent response-grid replica quantization plus empirical spread; primary quantization excluded",
            coordinate_extra_half_widths_e=grid_extra_widths,
        )
    rounding_by_site = primary_rounding.get("U_scalar_half_width_by_site_eV")
    repeatability_by_site = None if repeatability_only is None else repeatability_only.get(
        "U_scalar_half_width_by_site_eV"
    )
    total_precision_envelope_by_site: dict[str, float] | None = None
    total_precision_components_by_site: dict[str, dict[str, float]] | None = None
    total_precision_envelope_status = "NOT_ASSESSED_TOTAL_COMPONENTS_UNAVAILABLE"
    if (primary_by_site is not None and policy.sensitivity_tolerance_eV is not None
            and isinstance(rounding_by_site, Mapping)
            and isinstance(repeatability_by_site, Mapping) and model_sensitivity is not None
            and window_sensitivity is not None):
        component_rows: dict[str, dict[str, float]] = {}
        total_widths: dict[str, float] = {}
        for label in labels:
            key = str(label)
            components = (
                rounding_by_site.get(key), model_sensitivity.get(key),
                window_sensitivity.get(key), repeatability_by_site.get(key),
            )
            if any(value is None for value in components):
                break
            numeric = tuple(float(value) for value in components)
            if not all(math.isfinite(value) and value >= 0.0 for value in numeric):
                break
            round_width, model_width, window_width, repeatability_width = numeric
            # Model/window terms are observed estimator/window difference
            # envelopes.  They are added conservatively to the two separately
            # propagated occupation-width terms; empirical terms keep the
            # resulting envelope explicitly conditional.
            components_by_site = {
                "deterministic_print_rounding_eV": round_width,
                "estimator_difference_envelope_eV": model_width,
                "window_difference_envelope_eV": window_width,
                "conditional_scf_repeatability_envelope_eV": repeatability_width,
            }
            component_rows[key] = components_by_site
            total_widths[key] = math.fsum(components_by_site.values())
        if len(total_widths) == len(labels):
            total_precision_components_by_site = component_rows
            total_precision_envelope_by_site = total_widths
            total_precision_envelope_status = "CONDITIONAL_TOTAL_REPRODUCIBILITY_ENVELOPE"
    total_precision_max_half_width = (
        max(total_precision_envelope_by_site.values(), default=None)
        if total_precision_envelope_by_site is not None else None
    )
    conditional_state_evidence_ok = state_values is not None and not mixed_states and scf_validated is True
    if policy.u_precision_tolerance_eV is None:
        precision_assessment = "NOT_ASSESSED_TOLERANCE_MISSING"
    elif primary.U_matrix is None or mixed_states:
        precision_assessment = "NOT_ASSESSED_NO_SINGLE_STATE_NUMERICAL_U"
    elif total_precision_envelope_by_site is None:
        precision_assessment = "NOT_ASSESSED_TOTAL_PRECISION_COMPONENT_UNAVAILABLE"
    elif not conditional_state_evidence_ok:
        precision_assessment = "NOT_ASSESSED_SCF_OR_BRANCH_EVIDENCE_MISSING"
    elif total_precision_max_half_width is not None and total_precision_max_half_width <= policy.u_precision_tolerance_eV:
        precision_assessment = "CONDITIONALLY_REPRODUCIBLE_WITHIN_TOTAL_TOLERANCE"
    else:
        precision_assessment = "CONDITIONAL_TOTAL_ENVELOPE_EXCEEDS_TOLERANCE"

    window_summaries = window_results
    if numerical_status == "NO_SINGLE_STATE_U":
        # Preserve response matrices and fit evidence, but don't leave an
        # alternate estimator's mixed-branch U looking usable in the JSON.
        summaries = [primary_summary, linear_summary, *window_summaries]
        for summary in summaries:
            summary["U_by_site_eV"] = None
            summary["U_matrix_eV"] = None

    provenance = {
        "parent_dm_sha256": sorted({item.parent_dm_sha256 for item in observations if item.parent_dm_sha256}),
        "bare_fdf_sha256": sorted({item.bare_fdf_sha256 for item in observations if item.bare_fdf_sha256}),
        "bare_out_sha256": sorted({item.bare_out_sha256 for item in observations if item.bare_out_sha256}),
        "screened_fdf_sha256": sorted({item.screened_fdf_sha256 for item in observations if item.screened_fdf_sha256}),
        "screened_out_sha256": sorted({item.screened_out_sha256 for item in observations if item.screened_out_sha256}),
        "projector_fingerprints": sorted({digest for item in observations for digest in item.projector_fingerprints.values() if digest}),
    }
    estimator_policy = asdict(policy)
    # Declaration channel is report provenance, not estimator identity. Keeping
    # it out of this mapping preserves replay comparisons across config/CLI use.
    estimator_policy.pop("sensitivity_tolerance_provided_via", None)
    result = {
        "schema_version": (
            "siestaflow.lr_u_analysis.v3"
            if occupation_source == "siesta_occupations_total"
            else "siestaflow.lr_u_analysis.v2"
        ),
        "occupation_source": occupation_source,
        "campaign": dict(campaign or {}),
        "quantity": "U_scalar_charge",
        "units": "eV",
        "site_labels": labels,
        "alpha_grid_eV": all_alphas,
        "analysis_alpha_grid_eV": alphas,
        "analysis_active_window_eV": active_window_ev,
        "full_grid_diagnostic": full_grid_diagnostic,
        "estimator_policy": estimator_policy,
        "selected_estimator": {"method": selected_method, "degree": policy.polynomial_degree if selected_method == "polynomial" else 1},
        "primary": primary_summary,
        "same_grid_linear": linear_summary,
        "window_results": window_summaries,
        "window_sensitivity_eV": window_sensitivity,
        "model_sensitivity_eV": model_sensitivity,
        "printing_rounding_bound_eV": max_rounding_bound,
        "printing_rounding_bound_reason": (
            f"deterministic bound propagated from {occupation_source} print intervals"
            if max_rounding_bound is not None else str(primary_rounding.get("reason") or primary_rounding.get("status"))
        ),
        "printing_rounding_bounds": primary_rounding,
        "occupation_noise_calibration": calibration_evidence,
        "alpha_zero_calibration_transfer": "NOT_APPLIED_RESPONSE_GRID_CALIBRATION_REQUIRED",
        "response_grid_reproducibility_calibration": grid_repeatability,
        "conditional_response_grid_reproducibility_envelope": response_grid_conditional_envelope,
        "total_numerical_U_interval": {
            "status": "NOT_ESTABLISHED_EMPIRICAL_REPLICAS_ARE_NOT_A_TOTAL_ERROR_BOUND",
            "interval_by_site_eV": None,
            "reason": "observed response-grid repeatability is conditional and does not bound mathematical or physical error",
        },
        "u_precision_assessment": {
            "predeclared_tolerance_eV": policy.u_precision_tolerance_eV,
            "status": precision_assessment,
            "assessment_type": "conditional_numerical_reproducibility_under_declared_response_grid_replica_protocol",
            "conditional_max_half_width_eV": conditional_max_half_width,
            "total_reproducibility_envelope_status": total_precision_envelope_status,
            "total_reproducibility_half_width_by_site_eV": total_precision_envelope_by_site,
            "total_reproducibility_components_by_site_eV": total_precision_components_by_site,
            "total_reproducibility_max_half_width_eV": total_precision_max_half_width,
            "total_reproducibility_formula": (
                "deterministic_print_rounding + estimator_difference_envelope + "
                "window_difference_envelope + conditional_SCF_repeatability_envelope; "
                "per site, empirical terms make the result conditional"
            ),
            "max_estimator_window_difference_eV": max_sensitivity,
            "total_error_bound": "NOT_ESTABLISHED",
            "physical_acceptance": "NOT_ESTABLISHED",
        },
        "scf_and_magnetic_diagnostics": {
            "scf_validated": scf_validated,
            "magnetic_state_by_alpha": None if magnetic_state_labels is None else {
                str(key): value for key, value in magnetic_state_labels.items()
            },
            "state_continuity_confirmed": state_values is not None and not mixed_states,
        },
        "sensitivity_summary": {
            "max_abs_u_difference_eV": max_sensitivity,
            "per_site_model_sensitivity_eV": model_sensitivity,
            "per_site_window_sensitivity_eV": window_sensitivity,
            "threshold_eV": policy.sensitivity_tolerance_eV,
            "state": sensitivity_state,
            "declared_by": "config" if policy.sensitivity_tolerance_eV is not None else None,
            "provided_via": (
                policy.sensitivity_tolerance_provided_via
                if policy.sensitivity_tolerance_eV is not None else None
            ),
            "assessment": sensitivity_assessment if primary.U_matrix is not None and not mixed_states else "NOT_ASSESSED",
            "required_metrics_complete": sensitivity_metrics_complete,
            "eligible_window_count": sum(item.get("fit_window_stability_eligible") is True for item in window_results),
            "excluded_resolution_limited_window_count": sum(item.get("fit_window_stability_eligible") is False for item in window_results),
        },
        "numerical_status": numerical_status,
        "physical_acceptance": "NOT_ESTABLISHED",
        "reasons": reasons,
        "provenance": provenance,
    }
    return _finite_json(result)


def write_lr_analysis_v2(path: str | Path, result: Mapping[str, Any]) -> Path:
    """Atomically write the canonical JSON result without NaN/Infinity."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    safe = _finite_json(dict(result))
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(
        json.dumps(safe, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(destination)
    return destination
