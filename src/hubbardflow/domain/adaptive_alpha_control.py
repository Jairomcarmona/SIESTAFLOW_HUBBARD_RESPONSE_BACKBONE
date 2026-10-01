"""Versioned, fail-closed control rules for adaptive LR-U alpha rounds.

The controller consumes diagnostics from validated observations.  It does not
launch SIESTA, select an electronic branch, or invent tolerance values.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
import math
from typing import Any, Mapping, Sequence


POLICY_SCHEMA = "siestaflow.adaptive_alpha_policy.v1"


class AdaptiveAlphaControlError(ValueError):
    """The adaptive policy or round evidence is incomplete or inconsistent."""


class AdaptiveDecision(str, Enum):
    STOP_STABLE = "STOP_STABLE"
    REFINE = "REFINE"
    IMPROVE_SCF_FIRST = "IMPROVE_SCF_FIRST"
    STOP_LIMIT_SENSITIVE = "STOP_LIMIT_SENSITIVE"
    STOP_INVALID = "STOP_INVALID"
    # Internal transition: the runner materializes only the predeclared probe
    # nodes, then calls decide_round again with their validated receipt.
    PROBE_SCF = "PROBE_SCF"


@dataclass(frozen=True)
class AdaptiveAlphaPolicy:
    """Complete v1 campaign policy; scientifically calibrated values stay explicit."""

    h_ev: float
    alpha_seed_span_ev: float
    alpha_ceiling_ev: float | None
    max_refinement_rounds: int
    max_alpha_points: int
    total_siesta_node_budget: int
    round_analysis: Mapping[str, Any]
    probe_trigger_ratio: float | None
    tol_abs_ev: float | None
    tol_rel: float | None
    truncation_threshold_ev: float | None
    sensitivity_delta_tolerance_ev: float | None
    scf_materiality_ratio: float | None
    rho_min: float | None
    scf_probe_level: Mapping[str, Any] | None

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "AdaptiveAlphaPolicy":
        if payload.get("schema") != POLICY_SCHEMA:
            raise AdaptiveAlphaControlError(f"adaptive alpha policy schema must be {POLICY_SCHEMA!r}")
        required = {
            "h_eV", "alpha_seed_span_eV", "alpha_ceiling_eV", "max_refinement_rounds",
            "max_alpha_points", "total_siesta_node_budget", "round_analysis",
        }
        missing = sorted(required - set(payload))
        if missing:
            raise AdaptiveAlphaControlError(f"adaptive alpha policy lacks explicit fields: {missing}")
        optional = {
            "probe_trigger_ratio", "tol_abs_eV", "tol_rel", "truncation_threshold_eV",
            "sensitivity_delta_tolerance_eV", "scf_materiality_ratio", "rho_min", "scf_probe_level",
        }
        unknown = set(payload) - required - optional - {"schema"}
        if unknown:
            raise AdaptiveAlphaControlError(f"unsupported adaptive alpha policy fields: {sorted(unknown)}")
        policy = cls(
            h_ev=payload["h_eV"], alpha_seed_span_ev=payload["alpha_seed_span_eV"],
            alpha_ceiling_ev=payload["alpha_ceiling_eV"],
            max_refinement_rounds=payload["max_refinement_rounds"],
            max_alpha_points=payload["max_alpha_points"],
            total_siesta_node_budget=payload["total_siesta_node_budget"],
            round_analysis=payload["round_analysis"],
            probe_trigger_ratio=payload.get("probe_trigger_ratio"),
            tol_abs_ev=payload.get("tol_abs_eV"), tol_rel=payload.get("tol_rel"),
            truncation_threshold_ev=payload.get("truncation_threshold_eV"),
            sensitivity_delta_tolerance_ev=payload.get("sensitivity_delta_tolerance_eV"),
            scf_materiality_ratio=payload.get("scf_materiality_ratio"),
            rho_min=payload.get("rho_min"),
            scf_probe_level=payload.get("scf_probe_level"),
        )
        policy.validate()
        return policy

    def validate(self) -> None:
        _positive_finite(self.h_ev, "h_eV")
        _positive_finite(self.alpha_seed_span_ev, "alpha_seed_span_eV")
        if not math.isclose(self.alpha_seed_span_ev, 3.0 * self.h_ev, rel_tol=1e-12, abs_tol=1e-14):
            raise AdaptiveAlphaControlError("alpha_seed_span_eV must equal 3*h_eV for the seven-point seed")
        if self.alpha_ceiling_ev is not None:
            _positive_finite(self.alpha_ceiling_ev, "alpha_ceiling_eV")
            if self.alpha_ceiling_ev <= self.alpha_seed_span_ev:
                raise AdaptiveAlphaControlError("alpha_ceiling_eV must exceed the seed span to enable expansion")
        _integer(self.max_refinement_rounds, "max_refinement_rounds", minimum=0)
        # Two consecutive comparisons require the initial round and at least
        # two refinement rounds before STOP_STABLE can be reached.
        if (self.tol_abs_ev is not None or self.tol_rel is not None) and self.max_refinement_rounds < 2:
            raise AdaptiveAlphaControlError("max_refinement_rounds must be at least 2 when stability tolerances are set")
        smallest_shrink = float(self.h_ev) / (2 ** self.max_refinement_rounds)
        if self.max_refinement_rounds and not _fdf_representable(smallest_shrink):
            raise AdaptiveAlphaControlError("configured shrink amplitudes must be representable to 1e-4 eV")
        _integer(self.max_alpha_points, "max_alpha_points", minimum=7)
        if self.max_alpha_points < 7 + 2 * self.max_refinement_rounds:
            raise AdaptiveAlphaControlError("max_alpha_points (including alpha=0) cannot hold the configured symmetric refinements")
        _integer(self.total_siesta_node_budget, "total_siesta_node_budget", minimum=1)
        if not isinstance(self.round_analysis, Mapping) or set(self.round_analysis) != {"initial", "shrink", "expand"}:
            raise AdaptiveAlphaControlError("round_analysis must declare initial, shrink, and expand fit policies")
        if not isinstance(self.round_analysis["initial"], Mapping):
            raise AdaptiveAlphaControlError("round_analysis.initial must be an object")
        for direction in ("shrink", "expand"):
            branch = self.round_analysis[direction]
            if not isinstance(branch, Sequence) or isinstance(branch, (str, bytes)) or len(branch) != self.max_refinement_rounds:
                raise AdaptiveAlphaControlError(
                    f"round_analysis.{direction} must declare one active fit policy per configured refinement round"
                )
        fit_specs = [("initial", 0, self.round_analysis["initial"])]
        for direction in ("shrink", "expand"):
            fit_specs.extend((direction, index, fit) for index, fit in enumerate(self.round_analysis[direction]))
        for direction, index, fit in fit_specs:
            if not isinstance(fit, Mapping):
                raise AdaptiveAlphaControlError(f"round_analysis.{direction}[{index}] must be an object")
            fields = {"active_window_eV", "estimator", "polynomial_degree", "minimum_residual_dof", "matrix_for_inversion"}
            if set(fit) != fields:
                raise AdaptiveAlphaControlError(f"round_analysis.{direction}[{index}] must declare exactly {sorted(fields)}")
            _positive_finite(fit["active_window_eV"], f"round_analysis.{direction}[{index}].active_window_eV")
            window_limit = (
                self.alpha_ceiling_ev if direction == "expand" and self.alpha_ceiling_ev is not None
                else self.alpha_seed_span_ev
            )
            if fit["active_window_eV"] > window_limit:
                raise AdaptiveAlphaControlError(
                    f"round_analysis.{direction}[{index}].active_window_eV exceeds its declared alpha range"
                )
            if fit["estimator"] not in {"polynomial", "linear"}:
                raise AdaptiveAlphaControlError(f"round_analysis.{direction}[{index}].estimator must be polynomial or linear")
            _integer(fit["polynomial_degree"], f"round_analysis.{direction}[{index}].polynomial_degree", minimum=1)
            if int(fit["polynomial_degree"]) > 3:
                raise AdaptiveAlphaControlError(
                    f"round_analysis.{direction}[{index}].polynomial_degree must be between 1 and 3"
                )
            _integer(fit["minimum_residual_dof"], f"round_analysis.{direction}[{index}].minimum_residual_dof", minimum=1)
            if fit["matrix_for_inversion"] not in {"raw", "symmetrized"}:
                raise AdaptiveAlphaControlError(f"round_analysis.{direction}[{index}].matrix_for_inversion must be raw or symmetrized")
            candidate_grid = [
                -3.0 * float(self.h_ev), -2.0 * float(self.h_ev), -float(self.h_ev),
                float(self.h_ev), 2.0 * float(self.h_ev), 3.0 * float(self.h_ev),
            ]
            if direction == "shrink":
                candidate_grid.extend(
                    value for step in range(1, index + 2)
                    for value in (-float(self.h_ev) / (2 ** step), float(self.h_ev) / (2 ** step))
                )
            elif direction == "expand":
                candidate_grid.extend(
                    value for shell in range(4, 4 + index + 1)
                    for value in (-shell * float(self.h_ev), shell * float(self.h_ev))
                )
            in_window = sum(abs(value) <= float(fit["active_window_eV"]) + 1e-14 for value in candidate_grid)
            required_points = int(fit["polynomial_degree"]) + 1 + int(fit["minimum_residual_dof"])
            if fit["estimator"] == "linear":
                required_points = 2 + int(fit["minimum_residual_dof"])
            if in_window < required_points:
                raise AdaptiveAlphaControlError(
                    f"round_analysis.{direction}[{index}] active window has {in_window} possible points; "
                    f"the declared estimator/DoF require {required_points}"
                )
        paired = (self.tol_abs_ev, self.tol_rel)
        if (paired[0] is None) != (paired[1] is None):
            raise AdaptiveAlphaControlError("tol_abs_eV and tol_rel must both be supplied or both be omitted")
        for value, name in (
            (self.probe_trigger_ratio, "probe_trigger_ratio"),
            (self.tol_abs_ev, "tol_abs_eV"), (self.tol_rel, "tol_rel"),
            (self.truncation_threshold_ev, "truncation_threshold_eV"),
            (self.sensitivity_delta_tolerance_ev, "sensitivity_delta_tolerance_eV"),
            (self.scf_materiality_ratio, "scf_materiality_ratio"),
            (self.rho_min, "rho_min"),
        ):
            if value is not None:
                _positive_finite(value, name)
        if self.probe_trigger_ratio is not None and self.scf_probe_level is None:
            raise AdaptiveAlphaControlError("probe_trigger_ratio requires a predeclared scf_probe_level")
        if self.scf_probe_level is not None:
            level = self.scf_probe_level
            if not isinstance(level, Mapping) or not isinstance(level.get("level_id"), str) or not level["level_id"].strip():
                raise AdaptiveAlphaControlError("scf_probe_level requires a non-empty level_id")
            overrides = level.get("fdf_overrides")
            if not isinstance(overrides, Mapping) or not overrides:
                raise AdaptiveAlphaControlError("scf_probe_level requires explicit fdf_overrides")
            if any(
                not isinstance(key, str) or not key.strip()
                or not isinstance(value, (str, int, float))
                or isinstance(value, bool)
                or (isinstance(value, str) and (not value.strip() or "\n" in value or "\r" in value or "#" in value))
                for key, value in overrides.items()
            ):
                raise AdaptiveAlphaControlError("scf_probe_level fdf_overrides must map FDF keys to scalar values")
            allowed_nonprefix = {"maxscfiterations", "dm.tolerance", "dm.numberpulay"}
            if any(not key.casefold().startswith("scf.") and key.casefold() not in allowed_nonprefix for key in overrides):
                raise AdaptiveAlphaControlError("scf_probe_level overrides may change only SCF controls")

    @property
    def seed_grid_ev(self) -> tuple[float, ...]:
        self.validate()
        h = float(self.h_ev)
        return tuple(-factor * h for factor in (3, 2, 1)) + tuple(factor * h for factor in (1, 2, 3))

    def to_mapping(self) -> dict[str, Any]:
        self.validate()
        result = asdict(self)
        result["schema"] = POLICY_SCHEMA
        # Use the public manifest field spelling in persisted evidence.
        renames = {
            "h_ev": "h_eV", "alpha_seed_span_ev": "alpha_seed_span_eV",
            "alpha_ceiling_ev": "alpha_ceiling_eV",
            "tol_abs_ev": "tol_abs_eV",
            "truncation_threshold_ev": "truncation_threshold_eV",
            "sensitivity_delta_tolerance_ev": "sensitivity_delta_tolerance_eV",
        }
        return {renames.get(key, key): value for key, value in result.items()}

    def analysis_for_round(self, round_index: int, direction: str | None = None) -> Mapping[str, Any]:
        """Return the frozen fit policy for this round's chosen refinement branch."""
        self.validate()
        if round_index == 0:
            return self.round_analysis["initial"]
        if direction not in {"shrink", "expand"} or round_index > self.max_refinement_rounds:
            raise AdaptiveAlphaControlError("a refinement round requires its persisted shrink/expand direction")
        return self.round_analysis[direction][round_index - 1]


def decide_round(
    policy: AdaptiveAlphaPolicy,
    *,
    round_index: int,
    current_grid_ev: Sequence[float],
    completed_node_count: int,
    site_count: int,
    candidate_u_by_site_ev: Mapping[str, float] | None,
    previous_u_by_site_ev: Mapping[str, float] | None,
    stable_comparisons: int,
    matrix_usable: bool,
    branch_consistent: bool | None,
    scf_converged: bool,
    truncation_metric_ev: float | None,
    sensitivity_metric_ev: float | None,
    previous_sensitivity_metric_ev: float | None,
    signal_vectors_by_mode_column: Mapping[str, Mapping[str, Any]] | None = None,
    current_fit_signature: Mapping[str, Any] | None = None,
    previous_fit_signature: Mapping[str, Any] | None = None,
    scf_probe: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Choose one auditable action using only configured numeric predicates.

    Precedence is: invalid evidence; required SCF probe; material SCF response;
    two stable comparisons; shrink for declared truncation; conditional expand;
    otherwise sensitive stop. Missing thresholds never authorize STOP_STABLE or
    expansion.
    """
    policy.validate()
    if round_index < 0 or site_count < 1 or completed_node_count < 0:
        raise AdaptiveAlphaControlError("round and node counts must be non-negative and site_count positive")
    grid = sorted({float(value) for value in current_grid_ev})
    if len(grid) != len(current_grid_ev) or any(not math.isfinite(value) or value == 0.0 for value in grid):
        raise AdaptiveAlphaControlError("round alpha grid must contain distinct finite non-zero amplitudes")
    remaining = policy.total_siesta_node_budget - completed_node_count
    candidate_ok = candidate_u_by_site_ev is not None and bool(candidate_u_by_site_ev)
    if not scf_converged or not matrix_usable or not candidate_ok or branch_consistent is False:
        reason = "scf_not_converged" if not scf_converged else "matrix_not_usable" if not matrix_usable else "no_numeric_candidate" if not candidate_ok else "electronic_or_magnetic_branch_changed"
        return _decision(AdaptiveDecision.STOP_INVALID, reason, round_index, remaining, consumed=completed_node_count)

    signal_vectors = signal_vectors_by_mode_column or {}
    weak_keys: list[str] = []
    if policy.probe_trigger_ratio is not None and signal_vectors:
        for key, item in signal_vectors.items():
            signal_vector = item.get("signal_vector_electron")
            rounding_vector = item.get("rounding_bound_vector_electron")
            if (not isinstance(signal_vector, Sequence) or not isinstance(rounding_vector, Sequence)
                    or len(signal_vector) == 0 or len(signal_vector) != len(rounding_vector)
                    or not all(_is_nonnegative_finite(value) for value in rounding_vector)
                    or not all(_is_finite_number(value) for value in signal_vector)):
                continue
            signal_norm = math.sqrt(sum(float(value) ** 2 for value in signal_vector))
            rounding_norm = math.sqrt(sum(float(value) ** 2 for value in rounding_vector))
            if rounding_norm > 0 and signal_norm <= policy.probe_trigger_ratio * rounding_norm:
                weak_keys.append(str(key))
    signal_is_weak: bool | None = True if weak_keys else (False if signal_vectors and policy.probe_trigger_ratio is not None else None)
    probe_required = bool(weak_keys) and scf_probe is None
    if probe_required:
        affected_site_ids = sorted({str(signal_vectors[key].get("perturbed_site_id")) for key in weak_keys})
        if not affected_site_ids or "None" in affected_site_ids:
            return _decision(AdaptiveDecision.STOP_LIMIT_SENSITIVE, "scf_probe_affected_columns_not_identified", round_index, remaining, consumed=completed_node_count)
        expansion_probe_possible = (
            policy.rho_min is not None
            and symmetric_refinement_pair(policy, grid, "expand") is not None
        )
        probe_site_ids = list(affected_site_ids)
        probe_scope = "weak_sites"
        if expansion_probe_possible:
            all_site_ids = sorted({
                str(item.get("perturbed_site_id")) for item in signal_vectors.values()
                if item.get("perturbed_site_id") is not None
            })
            common_scope_keys = {
                f"{site_id}|{mode}" for site_id in all_site_ids for mode in ("BARE", "SCREENED")
            }
            if len(all_site_ids) != site_count or set(signal_vectors) != common_scope_keys:
                return _decision(
                    AdaptiveDecision.STOP_LIMIT_SENSITIVE,
                    "probe_scope_incomplete_for_common_grid_expansion", round_index, remaining,
                    consumed=completed_node_count, required_mode_columns=sorted(common_scope_keys),
                )
            # Alpha expansion changes the common grid, so probe every site and
            # both response modes before dispatch. The weak columns still
            # determine empirical SCF materiality; the full scope is required
            # for the rho gate that can authorize the global expansion.
            probe_site_ids = all_site_ids
            probe_scope = "all_sites_all_modes_for_common_grid_expansion"
        # One strict-level reference is shared by the requested scope. Each
        # probed site contributes +/-h for both BARE and SCREENED.
        probe_cost = 1 + 4 * len(probe_site_ids)
        if remaining < probe_cost:
            return _decision(
                AdaptiveDecision.STOP_LIMIT_SENSITIVE, "scf_probe_exceeds_remaining_budget",
                round_index, remaining, consumed=completed_node_count, required_budget=probe_cost,
            )
        return _decision(
            AdaptiveDecision.PROBE_SCF, "response_signal_near_print_resolution",
            round_index, remaining, consumed=completed_node_count, required_budget=probe_cost,
            affected_site_ids=affected_site_ids, affected_mode_columns=weak_keys,
            probe_site_ids=probe_site_ids, probe_scope=probe_scope,
        )

    probe_material: bool | None = None
    probe_metrics: dict[str, Any] = {}
    if weak_keys and scf_probe is not None:
        probe_data = scf_probe.get("by_mode_column") if scf_probe.get("validated", False) else None
        if not isinstance(probe_data, Mapping):
            return _decision(AdaptiveDecision.STOP_LIMIT_SENSITIVE, "scf_probe_not_validated", round_index, remaining, consumed=completed_node_count)
        if not set(weak_keys).issubset(probe_data):
            return _decision(
                AdaptiveDecision.STOP_LIMIT_SENSITIVE,
                "probe_scope_incomplete_for_common_grid_expansion", round_index, remaining,
                consumed=completed_node_count,
                missing_weak_mode_columns=sorted(set(weak_keys) - set(probe_data)),
            )
        if policy.scf_materiality_ratio is None:
            return _decision(AdaptiveDecision.STOP_LIMIT_SENSITIVE, "scf_materiality_predicate_not_configured", round_index, remaining, consumed=completed_node_count)
        probe_material = False
        for key in weak_keys:
            item = probe_data[key]
            base_vector = item.get("v_base_electron")
            strict_vector = item.get("v_strict_electron")
            rounding_vector = item.get("q_rounding_bound_electron")
            if (not item.get("branch_consistent", False)
                    or not isinstance(base_vector, Sequence) or not isinstance(strict_vector, Sequence)
                    or not isinstance(rounding_vector, Sequence) or not base_vector
                    or len(base_vector) != len(strict_vector) or len(base_vector) != len(rounding_vector)
                    or not all(_is_finite_number(value) for value in (*base_vector, *strict_vector))
                    or not all(_is_nonnegative_finite(value) for value in rounding_vector)):
                return _decision(AdaptiveDecision.STOP_LIMIT_SENSITIVE, "scf_probe_channel_vectors_or_branch_incomplete", round_index, remaining, consumed=completed_node_count)
            eta = math.sqrt(sum((float(a) - float(b)) ** 2 for a, b in zip(strict_vector, base_vector)))
            q = math.sqrt(sum(float(value) ** 2 for value in rounding_vector))
            if q <= 0:
                return _decision(AdaptiveDecision.STOP_LIMIT_SENSITIVE, "scf_probe_rounding_bound_missing", round_index, remaining, consumed=completed_node_count)
            ratio = eta / q
            probe_metrics[key] = {"eta_electron": eta, "q_rounding_bound_electron": q,
                                  "eta_to_q_ratio": ratio, "quantity": "empirical_scf_sensitivity"}
            probe_material = probe_material or ratio >= float(policy.scf_materiality_ratio)
        if probe_material:
            # Strict-level reference is one shared node; response nodes cover
            # the complete alpha/site/mode matrix so no SCF levels are mixed.
            rerun_total = 1 + 2 * site_count * len(grid)
            pre_reserved = int(scf_probe.get("pre_reserved_rerun_node_count", 0))
            if pre_reserved < 0 or pre_reserved > rerun_total:
                return _decision(
                    AdaptiveDecision.STOP_LIMIT_SENSITIVE, "invalid_pre_reserved_scf_rerun_count",
                    round_index, remaining, consumed=completed_node_count,
                )
            rerun_cost = rerun_total - pre_reserved
            if remaining < rerun_cost:
                return _decision(
                    AdaptiveDecision.STOP_LIMIT_SENSITIVE, "strict_scf_consistent_rerun_exceeds_remaining_budget",
                    round_index, remaining, consumed=completed_node_count, required_budget=rerun_cost,
                )
            return _decision(
                AdaptiveDecision.IMPROVE_SCF_FIRST, "scf_probe_change_is_material_empirical_sensitivity",
                round_index, remaining, consumed=completed_node_count,
                required_budget=rerun_cost, scf_probe_metrics=probe_metrics,
                probe_is_error_bound=False,
            )

    delta_u: float | None = None
    tolerance_u: float | None = None
    equivalent_fit = _equivalent_fit_signature(current_fit_signature, previous_fit_signature)
    if previous_u_by_site_ev is not None and equivalent_fit:
        current = _aligned_vector(candidate_u_by_site_ev, previous_u_by_site_ev)
        if current is not None and policy.tol_abs_ev is not None and policy.tol_rel is not None:
            delta_u = max(abs(a - b) for a, b in zip(current[0], current[1]))
            tolerance_u = max(float(policy.tol_abs_ev), float(policy.tol_rel) * max(abs(value) for value in current[0]))
    sensitivity_nonadverse: bool | None = None
    if sensitivity_metric_ev is not None and previous_sensitivity_metric_ev is not None:
        if policy.sensitivity_delta_tolerance_ev is not None:
            sensitivity_nonadverse = (
                sensitivity_metric_ev <= previous_sensitivity_metric_ev + policy.sensitivity_delta_tolerance_ev
            )
    stable_now = (
        delta_u is not None and tolerance_u is not None and delta_u <= tolerance_u
        and branch_consistent is True and matrix_usable and sensitivity_nonadverse is True
    )
    next_stable = stable_comparisons + 1 if stable_now else 0
    if next_stable >= 2:
        return _decision(
            AdaptiveDecision.STOP_STABLE, "two_consecutive_equivalent_round_comparisons_passed",
            round_index, remaining, consumed=completed_node_count, delta_u_eV=delta_u,
            tolerance_u_eV=tolerance_u, stable_comparisons=next_stable,
            scf_probe_metrics=probe_metrics or None,
        )

    refine_direction: str | None = None
    if policy.truncation_threshold_ev is not None and truncation_metric_ev is not None:
        if truncation_metric_ev > policy.truncation_threshold_ev:
            refine_direction = "shrink"
    locally_regular = (
        truncation_metric_ev is not None and policy.truncation_threshold_ev is not None
        and truncation_metric_ev <= policy.truncation_threshold_ev
    )
    if (refine_direction is None and signal_is_weak and scf_probe is not None
            and probe_material is False and locally_regular and branch_consistent is True):
        # Expand only after a validated probe finds small empirical SCF change,
        # and only under a declared ceiling and node budget.
        if policy.alpha_ceiling_ev is not None and policy.alpha_ceiling_ev > max(abs(value) for value in grid):
            if policy.rho_min is not None:
                probe_data = scf_probe.get("by_mode_column", {})
                # The common grid expansion applies to all sites and modes, so
                # require validated probe vectors for every such combination.
                all_site_ids = sorted({
                    str(item.get("perturbed_site_id")) for item in signal_vectors.values()
                    if item.get("perturbed_site_id") is not None
                })
                required_keys = {
                    f"{site_id}|{mode}" for site_id in all_site_ids for mode in ("BARE", "SCREENED")
                }
                if len(all_site_ids) != site_count or set(signal_vectors) != required_keys:
                    return _decision(
                        AdaptiveDecision.STOP_LIMIT_SENSITIVE,
                        "probe_scope_incomplete_for_common_grid_expansion", round_index, remaining,
                        consumed=completed_node_count, affected_mode_columns=weak_keys,
                        required_mode_columns=sorted(required_keys),
                    )
                if not required_keys.issubset(probe_data):
                    return _decision(
                        AdaptiveDecision.STOP_LIMIT_SENSITIVE, "probe_scope_incomplete_for_common_grid_expansion",
                        round_index, remaining, consumed=completed_node_count,
                        affected_mode_columns=weak_keys, required_mode_columns=sorted(required_keys),
                        scf_probe_metrics=probe_metrics or None,
                    )
                if required_keys.issubset(probe_data):
                    next_alpha = max(abs(value) for value in grid) + policy.h_ev
                    next_abs_alpha = next_alpha
                    rho_values: dict[str, float] = {}
                    for key in sorted(required_keys):
                        item = probe_data[key]
                        strict_vector = item.get("v_strict_electron")
                        base_vector = item.get("v_base_electron")
                        q_vector = item.get("q_rounding_bound_electron")
                        if (not item.get("branch_consistent", False)
                                or not isinstance(strict_vector, Sequence) or not isinstance(base_vector, Sequence)
                                or not isinstance(q_vector, Sequence) or not strict_vector
                                or len(strict_vector) != len(base_vector) or len(strict_vector) != len(q_vector)
                                or not all(_is_finite_number(value) for value in (*strict_vector, *base_vector))
                                or not all(_is_nonnegative_finite(value) for value in q_vector)):
                            rho_values = {}
                            break
                        eta = math.sqrt(sum((float(a) - float(b)) ** 2 for a, b in zip(strict_vector, base_vector)))
                        q = math.sqrt(sum(float(value) ** 2 for value in q_vector))
                        strict_norm = math.sqrt(sum(float(value) ** 2 for value in strict_vector))
                        rho_values[key] = ((next_abs_alpha / policy.h_ev) * strict_norm / (eta + q)) if eta + q > 0 else 0.0
                    if rho_values and min(rho_values.values()) >= policy.rho_min:
                        refine_direction = "expand"
                        probe_metrics = {
                            key: {**dict(probe_metrics.get(key, {})), "rho_next_alpha": value,
                                  "rho_min": policy.rho_min, "next_alpha_eV": next_abs_alpha}
                            for key, value in rho_values.items()
                        }
    if round_index >= policy.max_refinement_rounds:
        return _decision(
            AdaptiveDecision.STOP_LIMIT_SENSITIVE, "maximum_refinement_rounds_reached",
            round_index, remaining, consumed=completed_node_count, delta_u_eV=delta_u,
            tolerance_u_eV=tolerance_u, stable_comparisons=next_stable,
            scf_probe_metrics=probe_metrics or None,
        )
    if refine_direction is None:
        return _decision(
            AdaptiveDecision.STOP_LIMIT_SENSITIVE, "decision_predicate_or_threshold_not_satisfied",
            round_index, remaining, consumed=completed_node_count, delta_u_eV=delta_u,
            tolerance_u_eV=tolerance_u, stable_comparisons=next_stable,
            scf_probe_metrics=probe_metrics or None,
        )
    additions = symmetric_refinement_pair(policy, grid, refine_direction)
    if additions is None or len(grid) + 1 + 2 > policy.max_alpha_points:
        return _decision(
            AdaptiveDecision.STOP_LIMIT_SENSITIVE, f"{refine_direction}_not_permitted_by_grid_limits",
            round_index, remaining, consumed=completed_node_count, stable_comparisons=next_stable,
            scf_probe_metrics=probe_metrics or None,
        )
    required = 2 * site_count * len(additions)
    if remaining < required:
        return _decision(
            AdaptiveDecision.STOP_LIMIT_SENSITIVE, "refinement_exceeds_remaining_budget",
            round_index, remaining, consumed=completed_node_count, required_budget=required,
            scf_probe_metrics=probe_metrics or None,
        )
    return _decision(
        AdaptiveDecision.REFINE, f"declared_{refine_direction}_predicate_passed",
        round_index, remaining, consumed=completed_node_count, required_budget=required,
        direction=refine_direction, add_alpha_ev=list(additions), delta_u_eV=delta_u,
        tolerance_u_eV=tolerance_u, stable_comparisons=next_stable,
        scf_probe_metrics=probe_metrics or None,
    )


def symmetric_refinement_pair(
    policy: AdaptiveAlphaPolicy, grid: Sequence[float], direction: str,
) -> tuple[float, float] | None:
    """Return the next symmetric inner or outer pair, or None at declared limits."""
    policy.validate()
    values = sorted({abs(float(value)) for value in grid if float(value) != 0.0})
    if not values:
        return None
    if direction == "shrink":
        candidate = values[0] / 2.0
        if candidate == 0.0 or any(math.isclose(candidate, value, rel_tol=1e-12, abs_tol=1e-14) for value in values):
            return None
    elif direction == "expand":
        candidate = values[-1] + policy.h_ev
        if policy.alpha_ceiling_ev is None or candidate > policy.alpha_ceiling_ev + 1e-14 or not _fdf_representable(candidate):
            return None
    else:
        raise AdaptiveAlphaControlError("refinement direction must be shrink or expand")
    return -candidate, candidate


def initial_siesta_node_cost(site_count: int, nonzero_alpha_count: int) -> int:
    """Count actual seed jobs: one shared reference plus both modes per grid point."""
    if isinstance(site_count, bool) or not isinstance(site_count, int) or site_count < 1:
        raise AdaptiveAlphaControlError("site_count must be a positive integer")
    if isinstance(nonzero_alpha_count, bool) or not isinstance(nonzero_alpha_count, int) or nonzero_alpha_count < 1:
        raise AdaptiveAlphaControlError("nonzero_alpha_count must be a positive integer")
    return 1 + 2 * site_count * nonzero_alpha_count


def _decision(decision: AdaptiveDecision, reason: str, round_index: int, remaining: int, **details: Any) -> dict[str, Any]:
    return {
        "schema": "siestaflow.adaptive_alpha_decision.v1",
        "decision": decision.value,
        "reason": reason,
        "round_index": round_index,
        "budget_remaining_nodes": remaining,
        **details,
    }


def _aligned_vector(
    current: Mapping[str, float] | None, previous: Mapping[str, float] | None,
) -> tuple[list[float], list[float]] | None:
    if current is None or previous is None or set(current) != set(previous):
        return None
    current_values = [float(current[key]) for key in sorted(current)]
    previous_values = [float(previous[key]) for key in sorted(previous)]
    if not all(math.isfinite(value) for value in (*current_values, *previous_values)):
        return None
    return current_values, previous_values


def _equivalent_fit_signature(
    current: Mapping[str, Any] | None, previous: Mapping[str, Any] | None,
) -> bool:
    """Active windows may move on the frozen schedule; fit family may not."""
    if current is None or previous is None:
        return False
    keys = (
        "estimator", "polynomial_degree", "minimum_residual_dof",
        "matrix_for_inversion", "window_selection_rule", "scf_level_id", "policy_digest",
    )
    return all(key in current and key in previous and current[key] == previous[key] for key in keys)


def _positive_finite(value: Any, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)) or float(value) <= 0:
        raise AdaptiveAlphaControlError(f"{name} must be positive and finite")


def _is_positive_finite(value: Any) -> bool:
    return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(float(value)) and float(value) > 0


def _is_nonnegative_finite(value: Any) -> bool:
    return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(float(value)) and float(value) >= 0


def _is_finite_number(value: Any) -> bool:
    return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(float(value))


def _fdf_representable(value: float) -> bool:
    return abs(float(value) - float(f"{float(value):+.4f}")) <= 1e-12


def _integer(value: Any, name: str, *, minimum: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise AdaptiveAlphaControlError(f"{name} must be an integer >= {minimum}")
