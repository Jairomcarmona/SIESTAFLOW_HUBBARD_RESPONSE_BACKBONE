"""Read campaign projector evidence and compare it with an application FDF."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from hubbardflow.domain.projector_compatibility import compare_projector_definitions
from hubbardflow.domain.projector_compatibility_models import (
    ProjectorCompatibilityError,
    ProjectorCompatibilityResult,
    ProjectorCompatibilityStatus,
)
from hubbardflow.siesta_backend.projector_compatibility_inputs import (
    ProjectorCompatibilityInputError,
    campaign_relative,
    definition_from_fdf,
    inventory_projector_records,
    load_json_object,
    parse_projector_fdf,
    record_by_label,
    source_record,
)


@dataclass(frozen=True)
class ProjectorCompatibilityReport:
    campaign_path: str
    target_fdf_path: str
    results: tuple[ProjectorCompatibilityResult, ...]
    force_requested: bool

    @property
    def status(self) -> ProjectorCompatibilityStatus:
        if any(item.status is ProjectorCompatibilityStatus.MISMATCH for item in self.results):
            return ProjectorCompatibilityStatus.MISMATCH
        if any(item.status is ProjectorCompatibilityStatus.INCOMPLETE for item in self.results):
            return ProjectorCompatibilityStatus.INCOMPLETE
        return ProjectorCompatibilityStatus.MATCH

    @property
    def application_permitted(self) -> bool:
        return self.status is ProjectorCompatibilityStatus.MATCH or self.force_requested

    def to_mapping(self) -> dict[str, object]:
        return {
            "schema": "hubbardflow.projector_compatibility.v1",
            "campaign": self.campaign_path,
            "target_fdf": self.target_fdf_path,
            "status": self.status.value,
            "force_requested": self.force_requested,
            "application_permitted": self.application_permitted,
            "comparisons": [item.to_mapping() for item in self.results],
        }

    @classmethod
    def from_mapping(cls, value: object) -> ProjectorCompatibilityReport:
        if not isinstance(value, Mapping) or value.get("schema") != "hubbardflow.projector_compatibility.v1":
            raise ProjectorCompatibilityInputError("projector report has an unsupported schema")
        raw_results = value.get("comparisons")
        if not isinstance(raw_results, list) or not raw_results:
            raise ProjectorCompatibilityInputError("projector report comparisons must be a non-empty array")
        try:
            results = tuple(ProjectorCompatibilityResult.from_mapping(item) for item in raw_results)
            force = value["force_requested"]
            if not isinstance(force, bool):
                raise ProjectorCompatibilityInputError("force_requested must be boolean")
            report = cls(
                _required_string(value["campaign"], "campaign"),
                _required_string(value["target_fdf"], "target_fdf"),
                results,
                force,
            )
            if value.get("status") != report.status.value:
                raise ProjectorCompatibilityInputError("report status disagrees with its comparisons")
            if value.get("application_permitted") is not report.application_permitted:
                raise ProjectorCompatibilityInputError("report permission disagrees with status and force")
            return report
        except (KeyError, TypeError, ValueError) as exc:
            raise ProjectorCompatibilityInputError(f"invalid projector report: {exc}") from exc


def _required_string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ProjectorCompatibilityInputError(f"{label} must be a non-empty string")
    return value


def check_campaign_projectors(
    campaign_path: str | Path,
    target_fdf_path: str | Path,
    label_mappings: Sequence[tuple[str, str]],
    *,
    force: bool = False,
    artifact_dirs: Sequence[str | Path] = (),
) -> ProjectorCompatibilityReport:
    """Compare explicitly mapped campaign species against a DFT+U FDF.

    Campaign numeric evidence is sourced from the frozen resolved plan and
    checked against its saved reference FDF. File digests are collected from
    the reference and target artifact directories, but the domain comparison
    treats them only as warnings.
    """
    if not label_mappings:
        raise ProjectorCompatibilityInputError("at least one explicit --map LR_LABEL=DFTU_LABEL is required")
    if not isinstance(force, bool):
        raise ProjectorCompatibilityInputError("force must be boolean")
    campaign_file = Path(campaign_path).resolve(strict=True)
    target_file = Path(target_fdf_path).resolve(strict=True)
    campaign_root = campaign_file.parent
    campaign = load_json_object(campaign_file, "campaign manifest")
    if campaign.get("schema") != "siestaflow.campaign.v2":
        raise ProjectorCompatibilityInputError("campaign file must use siestaflow.campaign.v2")
    reference_path = campaign_relative(campaign_root, campaign.get("reference_fdf"), "reference_fdf")
    plan_path = campaign_relative(
        campaign_root, campaign.get("resolved_perturbation_plan_file"), "resolved_perturbation_plan_file"
    )
    plan = load_json_object(plan_path, "resolved perturbation plan")
    if plan.get("schema") != "hubbardflow.resolved_perturbation_plan.v1":
        raise ProjectorCompatibilityInputError("resolved plan has an unsupported schema")
    source_model = parse_projector_fdf(reference_path, "campaign reference FDF")
    target_model = parse_projector_fdf(target_file, "target DFT+U FDF")
    source_roots = (
        campaign_root / "pseudopotentials",
        campaign_root / "runs" / "00_REFERENCE",
        campaign_root,
    )
    target_roots = (
        target_file.parent,
        target_file.parent / "pseudopotentials",
        *tuple(Path(item) for item in artifact_dirs),
    )
    source_inventory = inventory_projector_records(plan)
    results: list[ProjectorCompatibilityResult] = []
    for lr_label, dftu_label in label_mappings:
        if not lr_label or not dftu_label or lr_label != lr_label.strip() or dftu_label != dftu_label.strip():
            raise ProjectorCompatibilityInputError("label mappings must contain non-empty exact labels")
        source_evidence, source_consistent = source_record(source_inventory, lr_label, source_model)
        source_definition = definition_from_fdf(
            source_model,
            lr_label,
            source_evidence,
            source_roots,
            evidence_consistent=source_consistent,
        )
        target_record = record_by_label(target_model, dftu_label)
        target_definition = definition_from_fdf(
            target_model,
            dftu_label,
            target_record,
            target_roots,
            evidence_consistent=True,
        )
        try:
            results.append(
                compare_projector_definitions(
                    source_definition,
                    target_definition,
                    label_mapping=(lr_label, dftu_label),
                    force=force,
                )
            )
        except ProjectorCompatibilityError as exc:
            raise ProjectorCompatibilityInputError(str(exc)) from exc
    return ProjectorCompatibilityReport(str(campaign_file), str(target_file), tuple(results), force)
