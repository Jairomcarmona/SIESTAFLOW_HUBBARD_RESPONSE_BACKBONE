"""Bind the pure planner to portable campaign inputs and immutable resume locks.

Diagnostic coverage records candidates while the legacy all-column DAG remains
executable. Missing reference evidence lowers qualification, never fabricates a
reference or changes the existing fixed-grid estimator selection.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from enum import Enum
from hashlib import sha256
from pathlib import Path
from typing import cast

from hubbardflow.domain.coverage import UserCoveragePolicy, qualify_coverage
from hubbardflow.domain.coverage_models import CoverageQualification, CoverageReferenceEvidence
from hubbardflow.domain.lr_analysis_v2 import LRAnalysisPolicy, _fit_method
from hubbardflow.domain.perturbation_plan import AlphaStrategy, ResolvedPerturbationPlan
from hubbardflow.domain.perturbation_planner import resolve_perturbation_plan
from hubbardflow.domain.response_protocol import (
    EstimatorKind,
    PerturbationStrategy,
    protocol_from_fixed_grid,
)
from hubbardflow.domain.state_evidence import (
    EvidenceStatus,
    OccupationSpectraStatus,
    ReferenceStateEvidence,
    StateEvidenceReason,
)
from hubbardflow.domain.subspace_inventory import (
    CorrelatedSubspaceInventory,
    InventoryStatus,
    build_inventory,
)
from hubbardflow.domain.symmetry_operation_models import (
    bind_symmetry_model,
)
from hubbardflow.execution.campaign_coverage_policy import campaign_coverage_policy


class CampaignPlanError(ValueError):
    """Campaign inputs disagree with the inventory or frozen planning identity."""


class CampaignCoverage(str, Enum):
    DISABLED = "DISABLED"
    DIAGNOSTIC = "DIAGNOSTIC"
    TRANSLATION_SHADOWED = "TRANSLATION_SHADOWED"


@dataclass(frozen=True)
class CampaignPlanning:
    plan: ResolvedPerturbationPlan
    diagnostic_coverage: CoverageQualification

    def to_mapping(self) -> dict[str, object]:
        return {"plan": self.plan.to_mapping(), "diagnostic_coverage": self.diagnostic_coverage.to_mapping()}

    @classmethod
    def from_mapping(cls, row: Mapping[str, object]) -> CampaignPlanning:
        return cls(
            ResolvedPerturbationPlan.from_mapping(cast(Mapping[str, object], row["plan"])),
            CoverageQualification.from_mapping(cast(Mapping[str, object], row["diagnostic_coverage"])),
        )


def campaign_inventory(fdf: Path, identity_dirs: Sequence[Path]) -> CorrelatedSubspaceInventory:
    """Use the single audited parser, including the atom/species/projector map."""
    from hubbardflow.siesta_backend.fdf_model import parse_effective_fdf, species_identity

    model = parse_effective_fdf(fdf)
    return build_inventory(model, species_identity(model, identity_dirs))


def inventory_sites(inventory: CorrelatedSubspaceInventory) -> tuple[tuple[str, int], ...]:
    """Keep legacy unique labels and convert canonical zero-based indices once.

    Missing semantic basis evidence excludes reduction but does not erase a valid
    static mapping. Shared labels must await generated split-identity evidence.
    """
    if inventory.status is InventoryStatus.SHARED_LABEL_NEEDS_SPLIT:
        raise CampaignPlanError("SHARED_LABEL_NEEDS_SPLIT: auto_split_species is disabled")
    if inventory.status is InventoryStatus.NOT_SUPPORTED or not inventory.subspaces:
        raise CampaignPlanError(f"inventory cannot supply campaign targets: {inventory.status.value}")
    rows = tuple((s.species_label, s.atom_index + 1) for s in inventory.subspaces)
    if len({s for s, _ in rows}) != len(rows) or len({i for _, i in rows}) != len(rows):
        raise CampaignPlanError("SUBSPACE_MAPPING_NOT_ESTABLISHED: unique label/atom targets required")
    return rows


def resolve_campaign_plan(fdf: Path, config: Mapping[str, object]) -> ResolvedPerturbationPlan:
    """Return the frozen execution plan from the full diagnostic resolution."""
    return resolve_campaign_planning(fdf, config).plan


def resolve_campaign_planning(fdf: Path, config: Mapping[str, object]) -> CampaignPlanning:
    """Expose actionable campaign errors while retaining conservative domain states."""
    try:
        return _resolve_campaign_planning(fdf, config)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise CampaignPlanError(f"cannot resolve campaign plan: {exc}") from exc


def _resolve_campaign_planning(fdf: Path, config: Mapping[str, object]) -> CampaignPlanning:
    """Freeze static inputs and optional single-output reference via TASK 7–12.

    The legacy estimator selector is called with its own versioned policy. The
    declared TASK 9 profile supplies bands; custom bands must be explicit. All
    columns remain direct in DIAGNOSTIC, even when candidates could save runs.
    """
    from hubbardflow.siesta_backend.coverage_reference import build_coverage_reference_evidence
    from hubbardflow.siesta_backend.fdf_model import parse_effective_fdf, species_identity

    model = parse_effective_fdf(fdf)
    pseudo = cast(Mapping[str, str], config["pseudopotentials"])
    dirs = tuple(sorted({Path(p).parent for p in pseudo.values()}, key=str))
    identities = species_identity(model, dirs)
    inventory = build_inventory(model, identities)
    inventory_sites(inventory)
    source_digest = sha256(fdf.read_bytes()).hexdigest()
    output = config.get("planning_reference_output")
    if output is None:
        state = ReferenceStateEvidence(
            model.effective_fdf_sha256,
            sha256(b"").hexdigest(),
            False,
            False,
            (),
            None,
            None,
            OccupationSpectraStatus.NOT_AVAILABLE,
            (),
            EvidenceStatus.REFERENCE_NOT_ADMISSIBLE,
            (
                StateEvidenceReason.NORMAL_COMPLETION_MISSING,
                StateEvidenceReason.OCCUPATION_SPECTRA_NOT_AVAILABLE,
            ),
        )
        reference = CoverageReferenceEvidence(
            state, source_digest, None, False, False, False, EvidenceStatus.REFERENCE_NOT_ADMISSIBLE, None
        )
    else:
        reference = build_coverage_reference_evidence(fdf, cast(str, output), inventory.subspaces)
    parent = config.get("planning_reference_dm")
    if parent is not None:
        reference = replace(
            reference, parent_dm_sha256=sha256(Path(cast(str, parent)).read_bytes()).hexdigest()
        )
    mode = CampaignCoverage(cast(str, config.get("coverage", CampaignCoverage.DIAGNOSTIC.value)))
    policy = campaign_coverage_policy(config)
    coverage = qualify_coverage(
        inventory,
        reference,
        bind_symmetry_model(model, identities),
        policy,
        UserCoveragePolicy("campaign-coverage-v1", mode is not CampaignCoverage.DISABLED, ()),
    )
    grid = tuple(cast(Sequence[float], config["alpha_grid_ev"]))
    analysis = LRAnalysisPolicy(**cast(dict[str, object], config.get("analysis_policy", {})))  # type: ignore[arg-type]
    analysis.validate()
    method, _ = _fit_method(analysis, grid)
    estimator = (
        EstimatorKind.POLYNOMIAL_LSQ
        if method == "polynomial"
        else EstimatorKind.CENTRAL
        if len(grid) == 2
        else EstimatorKind.LINEAR_LSQ
    )
    strategy = AlphaStrategy(cast(str, config.get("alpha_strategy", AlphaStrategy.FIXED_PROTOCOL_GRID.value)))
    protocol = protocol_from_fixed_grid(
        tuple(s.site_id for s in inventory.subspaces),
        grid,
        estimator=estimator,
        polynomial_degree=analysis.polynomial_degree if method == "polynomial" else None,
        scf_level_id="base",
        reference_node_id="reference",
        observable_id="siesta_occupations_total",
        strategy=PerturbationStrategy(strategy.value),
        protocol_version="campaign-fixed-grid-v1",
    )
    backend = sha256(Path(cast(str, config["version_text_source"])).read_bytes()).hexdigest()
    registry = sha256(Path(cast(str, config["compatibility_registry_source"])).read_bytes()).hexdigest()
    plan = resolve_perturbation_plan(
        inventory,
        coverage,
        protocol,
        source_fdf_sha256=source_digest,
        alpha_strategy=strategy,
        planner_version="campaign-planner-v2",
        backend_identity=f"{config['declared_executable']}:{backend}:{registry}",
        tau_u_ev=None,
        explicit_sites=None
        if mode is CampaignCoverage.TRANSLATION_SHADOWED
        else tuple(s.site_id for s in inventory.subspaces),
    )
    return CampaignPlanning(plan, coverage)


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def planning_config_digest(config: Mapping[str, object]) -> str:
    """Portable identity binds file bytes rather than the staging directory name."""
    raw = dict(config)
    for field in ("pseudopotentials", "static_artifacts"):
        raw[field] = {
            label: sha256(Path(path).read_bytes()).hexdigest()
            for label, path in sorted(cast(Mapping[str, str], config[field]).items())
        }
    for field in (
        "planning_reference_output",
        "planning_reference_dm",
        "version_text_source",
        "compatibility_registry_source",
    ):
        path = config.get(field)
        raw[field] = None if path is None else sha256(Path(cast(str, path)).read_bytes()).hexdigest()
    return sha256(_canonical(raw).encode()).hexdigest()


def freeze_campaign_plan(root: Path, resolved: CampaignPlanning, config: Mapping[str, object]) -> None:
    """Write plan and lock together before production; never replace an old lock."""
    path = root / "resolved_perturbation_plan.json"
    lock = root / "campaign.lock"
    if path.exists() or lock.exists():
        raise CampaignPlanError("campaign plan is already frozen; validate it on resume")
    plan = resolved.plan
    raw = plan.to_mapping()
    path.write_text(_canonical(raw) + "\n", encoding="utf-8")
    lock.write_text(
        _canonical(
            {
                "schema": "hubbardflow.campaign_plan_lock.v1",
                "plan_digest": plan.digest,
                "coverage": config["coverage"],
                "coverage_qualification": resolved.diagnostic_coverage.to_mapping(),
                "planning_config_digest": planning_config_digest(config),
            }
        )
        + "\n",
        encoding="utf-8",
    )


def verify_frozen_campaign_plan(root: Path, config: Mapping[str, object]) -> ResolvedPerturbationPlan:
    """Compare recomputed input, parent-DM, policy and reference identities on resume."""
    try:
        row = json.loads((root / "resolved_perturbation_plan.json").read_text(encoding="utf-8"))
        lock = json.loads((root / "campaign.lock").read_text(encoding="utf-8"))
        plan = ResolvedPerturbationPlan.from_mapping(row)
        current = resolve_campaign_planning(root / "reference.fdf", config)
        if (
            lock["schema"] != "hubbardflow.campaign_plan_lock.v1"
            or lock["plan_digest"] != plan.digest
            or lock["coverage_qualification"]
            != json.loads(_canonical(current.diagnostic_coverage.to_mapping()))
            or lock["coverage"] != config["coverage"]
            or lock["planning_config_digest"] != planning_config_digest(config)
            or current.plan.digest != plan.digest
        ):
            raise CampaignPlanError("campaign plan invalidated: inputs, parent DM, bands or policy changed")
        return plan
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise CampaignPlanError(f"cannot resume frozen campaign plan: {exc}") from exc
