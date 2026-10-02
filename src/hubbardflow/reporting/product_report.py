"""Render exact plan evidence and unresolved product admission requirements."""

from __future__ import annotations

from hashlib import sha256

from hubbardflow.execution.product_models import ProductBoundary, ProductSnapshot, canonical


def render_product_report(snapshot: ProductSnapshot, boundary: ProductBoundary | None = None) -> str:
    """Retain every upstream decision; downstream quantities await execution."""
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
            "",
            "```json",
            canonical(coverage.to_mapping()),
            "```",
        ]
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
                "The complete diagnostic records each F1–F8 classification, measured value, band, operation, "
                "class and mandatory shadow. The frozen plan records execution coverage and reconstruction maps."
            ),
            "",
            "```json",
            canonical(snapshot.planning.to_mapping()),
            "```",
        ]
    lines += [
        "",
        "## Actions required",
        "",
        (
            "Resolve the recorded AMBIGUOUS, NOT_ESTABLISHED or REVIEW reasons using bound input evidence. "
            "Supply parent DM and an admissible reference when their identities are absent. "
            "Production requires the complete FDRC I.5 state producer. Pilot reuse awaits a declared source "
            "and complete identity receipt. CALIBRATED requires the SCF ESTIMATE and recorded T0–T4 validation. "
            "Automatic species splitting awaits verified SIESTA-generated alias identity."
        ),
        "",
        "## Downstream results",
        "",
        (
            "Matrix gates: NOT_ASSESSED. χ0/χ: NOT_ASSESSED. U and budgets: NOT_ASSESSED. "
            "Qualification: NOT_ASSESSED. Existing downstream certification: NOT_ASSESSED."
        ),
    ]
    if boundary is not None:
        lines += ["", "## Execution admission", "", "```json", canonical(boundary.to_mapping()), "```"]
    return "\n".join(lines) + "\n"
