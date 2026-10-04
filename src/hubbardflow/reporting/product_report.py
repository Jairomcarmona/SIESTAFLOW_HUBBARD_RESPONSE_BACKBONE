"""Render compact plan evidence and actions derived from recorded requirements."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from hashlib import sha256

from hubbardflow.domain.coverage_models import CoverageQualification
from hubbardflow.domain.symmetry_operations import OperationClassification
from hubbardflow.execution.product_models import ProductBoundary, ProductSnapshot, canonical


def _first_failing_condition(classification: OperationClassification) -> str | None:
    """Name the first failed F-condition without promoting diagnostic evidence."""
    if classification.accepted:
        return None
    for condition in classification.conditions:
        status = condition.status.value
        if status not in {"EQUAL", "NOT_APPLICABLE"} and not (
            condition.condition == "F8"
            and classification.operation.rotation_int == ((1, 0, 0), (0, 1, 0), (0, 0, 1))
        ):
            return condition.condition
    return None


def _append_coverage_summary(lines: list[str], coverage: CoverageQualification) -> None:
    lines += [
        "",
        "### Translation classes",
        "",
        "| Representative | Shadow | Members | Status | Reasons |",
        "|---|---|---:|---|---|",
    ]
    for group in coverage.classes:
        reasons = ", ".join(reason.value for reason in group.reasons) or "—"
        lines.append(
            f"| {group.representative} | {group.shadow or '—'} | {len(group.members)} | "
            f"{group.status.value} | {reasons} |"
        )

    exactness_counts = Counter(row.operation.exactness_class.value for row in coverage.operations)
    first_failures = Counter(
        failure for row in coverage.operations if (failure := _first_failing_condition(row)) is not None
    )
    rejection_reasons = Counter(
        row.reasons[0].value
        for row in coverage.operations
        if not row.accepted and _first_failing_condition(row) is None and row.reasons
    )
    accepted_count = sum(row.accepted for row in coverage.operations)
    lines += [
        "",
        "### Operation summary",
        "",
        f"Total operations: {len(coverage.operations)}; accepted: {accepted_count}.",
        "",
        "| Exactness class | Count |",
        "|---|---:|",
    ]
    for name, count in sorted(exactness_counts.items()):
        lines.append(f"| {name} | {count} |")
    lines += ["", "| First failing condition | Count |", "|---|---:|"]
    if first_failures:
        for condition, count in sorted(first_failures.items()):
            lines.append(f"| {condition} | {count} |")
    else:
        lines.append("| None | 0 |")
    lines += ["", "| Rejected without a failed F-condition | Count |", "|---|---:|"]
    if rejection_reasons:
        for reason, count in sorted(rejection_reasons.items()):
            lines.append(f"| {reason} | {count} |")
    else:
        lines.append("| None | 0 |")


def _admission_mapping(boundary: ProductBoundary | None) -> Mapping[str, object] | None:
    if boundary is None:
        return None
    raw = boundary.to_mapping().get("execution_admission")
    return raw if isinstance(raw, Mapping) else None


def _actions_required(snapshot: ProductSnapshot, boundary: ProductBoundary | None) -> list[str]:
    """Turn recorded blockers into next steps without inventing missing producers."""
    product_reasons = {reason.value for reason in snapshot.reasons}
    inventory_reasons = {reason.value for reason in snapshot.inventory.reason_codes}
    plan_reasons: set[str] = set()
    coverage_reasons: set[str] = set()
    if snapshot.planning is not None:
        plan_reasons = {reason.value for reason in snapshot.planning.plan.reason_codes}
        coverage_reasons = {reason.value for reason in snapshot.planning.diagnostic_coverage.reasons}
    elif snapshot.diagnostic_coverage is not None:
        coverage_reasons = {reason.value for reason in snapshot.diagnostic_coverage.reasons}

    admission = _admission_mapping(boundary)
    admission_reasons: set[str] = set()
    admission_status: str | None = None
    if admission is not None:
        raw_status = admission.get("status")
        admission_status = raw_status if isinstance(raw_status, str) else None
        raw_reasons = admission.get("reason_codes", [])
        if isinstance(raw_reasons, list):
            admission_reasons = {str(reason) for reason in raw_reasons}

    actions: list[str] = []
    if "PARENT_DM_NOT_ESTABLISHED" in plan_reasons or "PARENT_DM_REQUIRED" in admission_reasons:
        actions.append(
            "Run `hubbardflow reference`, then pass its files with `--reference-output` and `--reference-dm`."
        )
    if "REFERENCE_NOT_ADMISSIBLE" in plan_reasons | coverage_reasons | admission_reasons:
        actions.append("Provide a reference output and parent DM that satisfy the recorded reference checks.")
    if "SPECIES_IDENTITY_NOT_ESTABLISHED" in inventory_reasons | coverage_reasons:
        actions.append(
            "Check the source for its concrete identity cause: a missing or mismatched pseudopotential, an FDF "
            "block outside the species-neutral allowlist, or an enabled `User.Basis`/`User.Basis.NetCDF` directive; "
            "correct the applicable cause and re-plan."
        )
    if "PLAN_NOT_READY" in product_reasons or "PLAN_REASONS_PRESENT" in admission_reasons:
        reasons = sorted(plan_reasons or product_reasons)
        actions.append("Resolve the recorded plan reasons: " + ", ".join(reasons) + ".")
    if "SHADOW_PENDING" in plan_reasons | coverage_reasons:
        actions.append(
            "Run the mandatory representative and shadow columns to validate the proposed reduction."
        )
    if "PILOT_REUSE_NOT_ESTABLISHED" in product_reasons:
        actions.append(
            "Declare a pilot source and provide its complete identity receipt before requesting reuse."
        )
    if "SCIENTIFIC_STATE_NOT_ESTABLISHED" in product_reasons:
        actions.append("Provide the required validated scientific-state evidence for this plan.")
    if "CALIBRATED_VALIDATION_NOT_ESTABLISHED" in product_reasons:
        actions.append(
            "Complete the declared SCF estimate and recorded T0–T4 validation before calibrated execution."
        )
    if "CALIBRATION_PROTOCOL_REQUIRED" in product_reasons:
        actions.append(
            "Provide an explicit versioned calibration protocol before selecting a calibrated grid."
        )
    if "STAGED_PENDING_GENERATED_IDENTITY" in product_reasons:
        actions.append("Verify the generated SIESTA species aliases and record their exact identity receipt.")
    if "SHARED_LABEL_NEEDS_SPLIT" in product_reasons:
        actions.append("Use verified generated species aliases to resolve the shared DFTU label.")
    if admission_status in {"ADMISSIBLE_LEGACY_EQUIVALENT", "ADMISSIBLE_TRANSLATION_SHADOWED"}:
        actions.append("Ready: run with `--profile` and the required execution options.")
    if not actions:
        actions.append("No additional action is identified by the recorded plan and admission reasons.")
    return actions


def _append_admission(lines: list[str], boundary: ProductBoundary | None) -> None:
    lines += ["", "### Execution admission"]
    admission = _admission_mapping(boundary)
    if admission is None:
        lines.append("Not evaluated.")
        return
    lines.append(f"Status: **{admission.get('status', 'UNKNOWN')}**")
    reasons = admission.get("reason_codes", [])
    if not isinstance(reasons, list):
        reasons = []
    lines.append("Reasons: " + (", ".join(str(reason) for reason in reasons) or "None"))


def render_product_report(snapshot: ProductSnapshot, boundary: ProductBoundary | None = None) -> str:
    """Retain links to full evidence while keeping summaries readable and actionable."""
    lines = [
        "# HubbardFlow product planning report",
        "",
        f"Plan state: **{snapshot.status.value}**",
        f"Campaign identity: `{snapshot.campaign_identity}`",
        "",
        "| Site | Atom index (0-based) | Species | Identity |",
        "|---|---:|---|---|",
    ]
    for site in snapshot.inventory.subspaces:
        lines.append(
            f"| {site.site_id} | {site.atom_index} | {site.species_label} | {site.identity_digest} |"
        )
    lines += [
        "",
        f"Inventory: {snapshot.inventory.status.value}",
        "Inventory reasons: " + ", ".join(r.value for r in snapshot.inventory.reason_codes),
        "Product reasons: " + ", ".join(r.value for r in snapshot.reasons),
    ]
    if snapshot.detail:
        lines += ["", snapshot.detail]
    if snapshot.planning is None and snapshot.diagnostic_coverage is not None:
        coverage = snapshot.diagnostic_coverage
        lines += [
            "",
            f"Reference: {coverage.reference.status.value}",
            f"Coverage: {coverage.strategy.value}",
            f"Candidate representatives: {coverage.would_reduce_to}",
            "Coverage reasons: " + ", ".join(r.value for r in coverage.reasons),
        ]
        _append_coverage_summary(lines, coverage)
    if snapshot.planning is not None:
        plan = snapshot.planning.plan
        coverage = snapshot.planning.diagnostic_coverage
        lines += [
            "",
            f"Resolved plan digest: `{plan.digest}`",
            f"Reference: {plan.reference.status.value}",
            f"Reference state digest: `{sha256(canonical(plan.reference.to_mapping()['state']).encode()).hexdigest()}`",
            f"Parent DM: `{plan.reference.parent_dm_sha256}`",
            f"Coverage: {plan.coverage.strategy.value}",
            f"Candidate representatives: {coverage.would_reduce_to}",
            f"Computed columns: {len(plan.computed_columns)}",
            "Plan reasons: " + ", ".join(r.value for r in plan.reason_codes),
            "",
            "| Column | Mode | Amplitudes (eV) | Estimator | SCF level | Qualification |",
            "|---|---|---|---|---|---|",
        ]
        for row in plan.calibration:
            column = row.column_plan
            lines.append(
                f"| {column.site_id} | {column.mode.value} | {column.amplitudes_ev} | "
                f"{column.estimator.kind.value} | {column.scf_level_id} | {row.qualification.status.value} |"
            )
        lines += [
            "",
            "## Decisions and evidence",
            "",
            (
                "Full evidence is unchanged in [resolved_perturbation_plan.json](resolved_perturbation_plan.json) "
                "and [product_plan.json](product_plan.json)."
            ),
        ]
        _append_coverage_summary(lines, coverage)
        _append_admission(lines, boundary)
    lines += ["", "## Actions required", ""]
    lines.extend(f"- {action}" for action in _actions_required(snapshot, boundary))
    lines += [
        "",
        "## Downstream results",
        "",
        (
            "Matrix gates: NOT_ASSESSED. χ0/χ: NOT_ASSESSED. U and budgets: NOT_ASSESSED. "
            "Qualification: NOT_ASSESSED. Existing downstream certification: NOT_ASSESSED."
        ),
    ]
    if boundary is not None and snapshot.planning is None:
        _append_admission(lines, boundary)
    return "\n".join(lines) + "\n"
