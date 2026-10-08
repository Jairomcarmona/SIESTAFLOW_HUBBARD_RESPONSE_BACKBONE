"""Human-readable Markdown view of a canonical LR-U analysis v2 JSON."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from ..domain.projector_diagnostics import METHOD2_PROJECTOR_WARNING


def _cell(value: Any) -> str:
    if value is None:
        return "—"
    return str(value).replace("|", r"\|").replace("\r", " ").replace("\n", " ")


def _fmt(value: Any, digits: int = 9) -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, (float, int)):
        return f"{value:.{digits}g}"
    return _cell(value)


def _json_compact(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(_fmt(item) for item in value) + "]"
    if isinstance(value, dict):
        return "; ".join(f"{_cell(key)}={_json_compact(item)}" for key, item in value.items())
    return _fmt(value)


def _state_gate_section(state_gate: Mapping[str, Any]) -> list[str]:
    pairs = state_gate.get("pairs")
    if not isinstance(pairs, list):
        return []
    lines = [
        "",
        "## I.5 state consistency (diagnostic)",
        "",
        "This diagnostic does not change campaign analysis or admission.",
        "",
        "| Column | Mode | Verdict | Admissible α (eV) | Excluded α (eV) | G4 | Reasons |",
        "|---|---|---|---:|---:|---|---|",
    ]
    for pair in pairs:
        if not isinstance(pair, Mapping):
            continue
        g4_outcomes: set[str] = set()
        amplitudes = pair.get("amplitudes", [])
        if isinstance(amplitudes, list):
            for amplitude in amplitudes:
                if not isinstance(amplitude, Mapping):
                    continue
                for sign in ("positive", "negative"):
                    point = amplitude.get(sign)
                    checks = point.get("checks", []) if isinstance(point, Mapping) else []
                    if isinstance(checks, list):
                        g4_outcomes.update(
                            str(item.get("outcome"))
                            for item in checks
                            if isinstance(item, Mapping) and item.get("check") == "G4"
                        )
        reasons = pair.get("reasons", [])
        reason_text = ", ".join(str(item) for item in reasons) if isinstance(reasons, list) else ""
        admissible = pair.get("admissible_amplitudes_ev", [])
        excluded = pair.get("excluded_amplitudes_ev", [])
        cells = (
            pair.get("column_id"),
            pair.get("mode"),
            pair.get("verdict"),
            ", ".join(_fmt(value) for value in admissible) if isinstance(admissible, list) else "—",
            ", ".join(_fmt(value) for value in excluded) if isinstance(excluded, list) else "—",
            ", ".join(sorted(g4_outcomes)) or "—",
            reason_text or "—",
        )
        lines.append("| " + " | ".join(_cell(value) for value in cells) + " |")
    lines.extend(["", "G3 smoothness: `NOT_ESTABLISHED: SMOOTHNESS_REQUIRES_SCF_LADDER`.", ""])
    return lines


def reference_reproduction_report_lines(evidence: Mapping[str, Any]) -> list[str]:
    """Render recorded D16 evidence for completed and rejected TS references."""
    return [
        "",
        "## Reference reproduction (D16)",
        "",
        f"- Criterion: `{_cell(evidence.get('criterion'))}`; equivalent: `{_cell(evidence.get('equivalent'))}`.",
        f"- Planning parent DM SHA-256: `{_cell(evidence.get('planning_parent_dm_sha256'))}`.",
        f"- Campaign parent DM SHA-256: `{_cell(evidence.get('campaign_parent_dm_sha256'))}`.",
        f"- Reason: `{_cell(evidence.get('reason'))}`; {_cell(evidence.get('detail'))}.",
        f"- Maximum occupation difference (e): {_fmt(evidence.get('max_occupation_difference_e'))}; comparison quanta (e): {_json_compact(evidence.get('occupation_comparison_quanta_e'))}.",
        f"- Fermi difference (eV): {_fmt(evidence.get('max_fermi_difference_ev'))}; comparison quantum (eV): {_fmt(evidence.get('fermi_comparison_quantum_ev'))}.",
        f"- Occupation tolerances used (e): {_json_compact(evidence.get('occupation_tolerances_e'))}; maximum (e): {_fmt(evidence.get('occupation_tolerance_e'))}.",
        f"- Declared SCF.DM.Tolerance: {_fmt(evidence.get('scf_dm_tolerance'))}; policy factor: {_fmt(evidence.get('tolerance_factor'))}.",
        f"- Occupation assessment: `{_cell(evidence.get('occupation_equivalence', 'NOT_ASSESSED'))}`.",
        f"- Fermi assessment: {_cell(evidence.get('fermi_equivalence', 'RECORDED_NOT_ASSESSED'))}; tolerance used (eV): {_fmt(evidence.get('fermi_tolerance_ev'))}; declared (eV): {_fmt(evidence.get('declared_fermi_tolerance_ev'))}; source: {_cell(evidence.get('fermi_tolerance_source'))}.",
        f"- Fermi print half-widths (eV): {_json_compact(evidence.get('fermi_print_half_widths_ev'))}; warnings: {_json_compact(evidence.get('warnings', []))}.",
        f"- Affected atom indices: {_json_compact(evidence.get('affected_atom_indices'))}; all reduced classes affected: {_fmt(evidence.get('all_reduced_classes_affected'))}.",
    ]


def _coefficients_with_units(fit: Mapping[str, Any]) -> str:
    coefficients = fit.get("coefficients")
    if not isinstance(coefficients, list):
        coefficients = [fit.get("intercept"), fit.get("slope")]
    rendered = []
    for order, value in enumerate(coefficients):
        power = str(order).translate(str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹"))
        unit = "e" if order == 0 else f"e·eV⁻{power}"
        rendered.append(f"c{order}={_fmt(value)} {unit}")
    return "; ".join(rendered)


def _display_site(index: Any, names: Mapping[str, str]) -> str:
    key = str(index)
    return names.get(key, key)


def _site_names(analysis: Mapping[str, Any], dataset: Mapping[str, Any]) -> dict[str, str]:
    explicit = dataset.get("matrix_index_to_site_id")
    if isinstance(explicit, Mapping):
        return {str(index): str(site_id) for index, site_id in explicit.items()}
    result: dict[str, str] = {}
    sites = (analysis.get("campaign") or {}).get("sites", [])
    if isinstance(sites, list):
        for index, site in enumerate(sites):
            if isinstance(site, Mapping) and site.get("site_id") is not None:
                result[str(index)] = str(site["site_id"])
    return result


def _matrix_table(title: str, matrix: Any, names: Mapping[str, str], *, unit: str) -> list[str]:
    lines = [f"### {title} ({unit})", ""]
    if not isinstance(matrix, list) or not matrix:
        return [*lines, "Not available in this analysis.", ""]
    size = len(matrix)
    block_width = 8
    for start in range(0, size, block_width):
        stop = min(start + block_width, size)
        if size > block_width:
            lines.append(f"Perturbed-site columns {_fmt(start + 1)}–{_fmt(stop)}.")
            lines.append("")
        headings = [_display_site(index, names) for index in range(start, stop)]
        lines.append(
            "| Observed site \\ Perturbed site | " + " | ".join(_cell(value) for value in headings) + " |"
        )
        lines.append("|---|" + "---:|" * len(headings))
        for index, row in enumerate(matrix):
            if not isinstance(row, list):
                values = ["—"] * len(headings)
            else:
                values = [_fmt(row[column]) if column < len(row) else "—" for column in range(start, stop)]
            lines.append(f"| {_cell(_display_site(index, names))} | " + " | ".join(values) + " |")
        lines.append("")
    return lines


def _diagnostic_table(summary: Mapping[str, Any], names: Mapping[str, str], label: str) -> list[str]:
    lines = [
        f"### Inversion diagnostics: {label}",
        "",
        "| Matrix | Method | Left Frobenius residual | Right Frobenius residual |",
        "|---|---|---:|---:|",
    ]
    diagnostics = summary.get("inversion_diagnostics") or {}
    for key, title in (("chi0", "χ⁰"), ("chi", "χ")):
        item = diagnostics.get(key) if isinstance(diagnostics, Mapping) else None
        item = item if isinstance(item, Mapping) else {}
        lines.append(
            f"| {title} | {_cell(item.get('method'))} | "
            f"{_fmt(item.get('left_residual_frobenius'))} | {_fmt(item.get('right_residual_frobenius'))} |"
        )
    lines.append("")
    for key, title in (("chi0_diagnostics", "χ⁰"), ("chi_diagnostics", "χ")):
        item = summary.get(key)
        item = item if isinstance(item, Mapping) else {}
        lines.extend(
            [
                f"**{title} condition:** rank {_fmt(item.get('rank'))}/{_fmt((item.get('shape') or [None])[0] if item.get('shape') else None)}; "
                f"determinant {_fmt(item.get('det'))}; condition number {_fmt(item.get('condition_number'))}; "
                f"status `{_cell(item.get('matrix_status'))}`.",
                "",
            ]
        )
    return lines


def _source_lines(source: Any, alpha: Any, site_id: Any) -> list[str]:
    if not isinstance(source, Mapping):
        return [f"| {_fmt(alpha)} | {_cell(site_id)} | — | — | — | — | — | — |"]
    return [
        f"| {_fmt(alpha)} | {_cell(site_id)} | {_cell(source.get('mode'))} | {_cell(source.get('node_id'))} | "
        f"{_cell(source.get('fdf_path'))} | {_cell(source.get('out_path'))} | "
        f"{_cell(source.get('fdf_sha256'))} / {_cell(source.get('out_sha256'))} | "
        f"{_cell(source.get('evidence_digest'))} |"
    ]


def render_lr_u_report(analysis: Mapping[str, Any], *, state_gate: Mapping[str, Any] | None = None) -> str:
    """Render a deterministic report from analysis JSON; old v2 files remain readable."""
    schema = analysis.get("schema_version")
    if (
        schema == "siestaflow.lr_u_analysis.v3"
        and analysis.get("occupation_source") != "siesta_occupations_total"
    ):
        raise ValueError("v3 LR-U analysis requires occupation_source=siesta_occupations_total")
    if schema not in {"siestaflow.lr_u_analysis.v2", "siestaflow.lr_u_analysis.v3"}:
        raise ValueError("unsupported LR-U analysis schema")

    campaign = analysis.get("campaign") or {}
    primary = analysis.get("primary") or {}
    provenance = analysis.get("provenance") or {}
    input_provenance = provenance.get("campaign_inputs") or {}
    runtime_provenance = input_provenance.get("siesta_runtime") or {}
    implementation = input_provenance.get("analysis_implementation") or {}
    dataset = analysis.get("response_observation_dataset") or {}
    dataset = dataset if isinstance(dataset, Mapping) else {}
    names = _site_names(analysis, dataset)
    state = analysis.get("numerical_status", "UNKNOWN")
    dag_action = analysis.get("dag_action")
    u_by_site = primary.get("U_by_site_eV") or {}
    model_sensitivity = analysis.get("model_sensitivity_eV") or {}
    window_sensitivity = analysis.get("window_sensitivity_eV") or {}
    selected = analysis.get("selected_estimator") or {}
    estimator = primary.get("method", selected.get("method"))
    degree = primary.get("degree", selected.get("degree"))
    precision = analysis.get("u_precision_assessment")
    precision = precision if isinstance(precision, Mapping) else {}
    estimator_policy = analysis.get("estimator_policy") or {}
    estimator_policy = estimator_policy if isinstance(estimator_policy, Mapping) else {}
    precision_tolerance = precision.get(
        "predeclared_tolerance_eV", estimator_policy.get("u_precision_tolerance_eV")
    )
    precision_status = precision.get("status", "NOT_ASSESSED_TOTAL_INTERVAL_NOT_RECORDED")
    total_interval = analysis.get("total_numerical_U_interval")
    total_interval = total_interval if isinstance(total_interval, Mapping) else {}
    conditional_noise = analysis.get("conditional_response_grid_reproducibility_envelope")
    conditional_noise = conditional_noise if isinstance(conditional_noise, Mapping) else {}
    grid_calibration = analysis.get("response_grid_reproducibility_calibration")
    grid_calibration = grid_calibration if isinstance(grid_calibration, Mapping) else {}
    rounding_bound = analysis.get("printing_rounding_bound_eV")
    if isinstance(rounding_bound, (int, float)) and isinstance(precision_tolerance, (int, float)):
        rounding_comparison = (
            "WITHIN_TOLERANCE_ALONE" if rounding_bound <= precision_tolerance else "EXCEEDS_TOLERANCE_ALONE"
        )
    else:
        rounding_comparison = "NOT_COMPARABLE"

    lines = [
        "# Hubbard Linear-Response Report",
        "",
        f"- **Campaign:** {_cell(campaign.get('campaign_id') or campaign.get('name'))}",
        f"- **Material:** {_cell(campaign.get('material') or campaign.get('system_label'))}",
        f"- **Functional:** {_cell(campaign.get('functional'))}",
        f"- **SIESTA version:** {_cell(runtime_provenance.get('version'))}",
        f"- **Analyzer:** {_cell(implementation.get('package'))} {_cell(implementation.get('package_version'))} — {_cell(implementation.get('schema'))}",
        f"- **Calculated quantity:** `{_cell(analysis.get('quantity', 'U_scalar_charge'))}` ({_cell(analysis.get('units', 'eV'))})",
        f"- **Numerical status:** **{_cell(state)}**",
        f"- **Physical acceptance:** **{_cell(analysis.get('physical_acceptance', 'NOT_ESTABLISHED'))}**",
        f"- **Total numerical precision:** `{_cell(precision_status)}`; predeclared tolerance: {_fmt(precision_tolerance)} eV.",
        f"- **Primary estimator:** {_cell(estimator)}, degree {_fmt(degree)}",
        f"- **α grid (eV):** `{', '.join(_fmt(value) for value in analysis.get('alpha_grid_eV', []))}`",
        f"- **Recorded DAG action:** `{_cell(dag_action)}`",
        "",
        "The result is the declared charge-response `U_scalar_charge`. "
        "It is not automatically converted to `Ueff_Dudarev` and does not imply physical acceptance.",
        "",
    ]
    refinement = analysis.get("refinement_decision")
    rounds = analysis.get("alpha_rounds")
    if isinstance(refinement, Mapping) or isinstance(rounds, list):
        decision = refinement if isinstance(refinement, Mapping) else {}
        refinement_policy = analysis.get("refinement_policy") or {}
        refinement_policy = refinement_policy if isinstance(refinement_policy, Mapping) else {}
        budget = analysis.get("adaptive_budget") or {}
        latest = rounds[-1] if isinstance(rounds, list) and rounds and isinstance(rounds[-1], Mapping) else {}
        lines.extend(
            [
                "## Adaptive refinement status",
                "",
                f"- Campaign decision: **{_cell(analysis.get('campaign_status', decision.get('decision', 'UNKNOWN')))}**.",
                f"- Candidate status: **{_cell(analysis.get('candidate_status', state))}**.",
                f"- Reason: `{_cell(decision.get('reason'))}`.",
                f"- Refinement window metric: {_fmt(decision.get('truncation_metric_eV'))} eV; basis: `{_cell(decision.get('truncation_metric_basis'))}`.",
                f"- Declared truncation threshold: {_fmt(refinement_policy.get('truncation_threshold_eV'))} eV. If the observed metric exceeds this value, `shrink` is proposed, subject to the precedence of other decisions and round and budget limits; this metric is empirical sensitivity, not an error bound.",
                f"- Tolerance for sensitivity increase between rounds: {_fmt(refinement_policy.get('sensitivity_delta_tolerance_eV'))} eV. It compares only the increase from the previous round; it is neither an absolute acceptance threshold nor an error bound.",
                f"- Final round: {_fmt(latest.get('round_index'))}; direction: `{_cell(latest.get('direction'))}`; "
                f"active window: {_fmt(latest.get('active_window_eV'))} eV; SCF level: `{_cell(latest.get('effective_scf_level_id') or latest.get('scf_level_id'))}`.",
                f"- Reserved budget: {_fmt(budget.get('reserved_nodes'))}/{_fmt(budget.get('total_siesta_node_budget'))} SIESTA nodes; "
                f"remaining: {_fmt(budget.get('remaining_nodes'))}.",
                "- Differences between SCF levels are interpreted as empirical sensitivity; they are not a rigorous bound on U error.",
                "",
                "| Round | Direction | Measured α (eV) | Active window (eV) | SCF level | Candidate | Status |",
                "|---:|---|---|---:|---|---|---|",
            ]
        )
        for item in rounds if isinstance(rounds, list) else []:
            if not isinstance(item, Mapping):
                continue
            grid = ", ".join(_fmt(value) for value in item.get("alpha_grid_ev", []))
            lines.append(
                f"| {_fmt(item.get('round_index'))} | `{_cell(item.get('direction'))}` | `{grid}` | "
                f"{_fmt(item.get('active_window_eV'))} | `{_cell(item.get('effective_scf_level_id') or item.get('scf_level_id'))}` | "
                f"{_cell(item.get('candidate_status'))} | `{_cell(item.get('status'))}` |"
            )
        lines.append("")
    lines.extend(
        [
            "## 1. U summary by site",
            "",
            "| Quantity | Site | Value (eV) | Method | Model sensitivity (eV) | Window sensitivity (eV) | Numerical status | DAG action |",
            "|---|---|---:|---|---:|---:|---|---|",
        ]
    )
    site_labels = analysis.get("site_labels", list(u_by_site))
    for site in site_labels:
        key = str(site)
        lines.append(
            f"| U_scalar_charge | {_cell(_display_site(site, names))} | {_fmt(u_by_site.get(key))} | "
            f"{_cell(estimator)} | {_fmt(model_sensitivity.get(key))} | {_fmt(window_sensitivity.get(key))} | "
            f"{_cell(state)} | {_cell(dag_action)} |"
        )
    if not site_labels:
        lines.append(
            f"| U_scalar_charge | — | — | {_cell(estimator)} | — | — | {_cell(state)} | {_cell(dag_action)} |"
        )

    projector_diagnostics = analysis.get("projector_diagnostics")
    projector_diagnostics = projector_diagnostics if isinstance(projector_diagnostics, Mapping) else {}
    method2_warning = projector_diagnostics.get("method2_warning")
    method2_warning = (
        method2_warning if isinstance(method2_warning, Mapping) else METHOD2_PROJECTOR_WARNING.to_mapping()
    )
    projector_sites = projector_diagnostics.get("sites")
    projector_sites = projector_sites if isinstance(projector_sites, list) else []
    lines.extend(
        [
            "",
            "## Projector diagnostics (record-only)",
            "",
            "These diagnostics do not change U calculation, acceptance, or campaign status.",
            "",
            f"- Permanent scheme warning `{_cell(method2_warning.get('code'))}`: {_cell(method2_warning.get('message'))}",
            f"- Decision role: `{_cell(method2_warning.get('decision_role', 'RECORD_ONLY'))}`.",
            "- The occupation comparisons use only electron counts explicitly declared in `lr-config`; missing declarations remain `NOT_ASSESSED`.",
            "- `U × |χ⁰ᵢᵢ|` is a dimensionless regime indicator; it is approximately constant when screened and bare responses remain proportional.",
            "",
            "| Site | n reference (e) | Formal d (e) | Δ from formal (e) | Free atom d (e) | Δ from free atom (e) | Ligand charge capture | U (eV) | χ⁰ᵢᵢ (eV⁻¹) | U × \\|χ⁰ᵢᵢ\\| | Status |",
            "|---|---:|---:|---:|---:|---:|---|---:|---:|---:|---|",
        ]
    )
    for item in projector_sites:
        if not isinstance(item, Mapping):
            continue
        lines.append(
            f"| {_cell(item.get('site_id'))} | {_fmt(item.get('reference_occupation_e'))} | "
            f"{_fmt(item.get('formal_d_electrons'))} | {_fmt(item.get('difference_from_formal_d_e'))} | "
            f"{_fmt(item.get('free_atom_d_electrons'))} | {_fmt(item.get('difference_from_free_atom_d_e'))} | "
            f"`{_cell(item.get('ligand_charge_capture', 'NOT_ASSESSED'))}` | {_fmt(item.get('u_ev'))} | "
            f"{_fmt(item.get('chi0_diagonal_per_ev'))} | {_fmt(item.get('u_times_abs_chi0'))} | "
            f"`{_cell(item.get('regime_indicator_status', 'NOT_ASSESSED'))}` |"
        )
    if not projector_sites:
        lines.append("| — | — | — | — | — | — | `NOT_ASSESSED` | — | — | — | `NOT_ASSESSED` |")
    if projector_diagnostics.get("diagnostic_error"):
        lines.append(
            f"\nDiagnostic input issue (record-only): `{_cell(projector_diagnostics.get('diagnostic_error'))}`."
        )

    additional_observables = campaign.get("observables", [])
    if isinstance(additional_observables, list) and additional_observables:
        lines.extend(
            [
                "",
                "### Other recorded observables",
                "",
                "| Observable | Site/state | Value | Unit | Reference/source | Status |",
                "|---|---|---:|---|---|---|",
            ]
        )
        for item in additional_observables:
            item = item if isinstance(item, Mapping) else {}
            lines.append(
                f"| {_cell(item.get('name'))} | {_cell(item.get('site_or_state'))} | "
                f"{_fmt(item.get('value'))} | {_cell(item.get('unit'))} | "
                f"{_cell(item.get('reference') or item.get('source'))} | {_cell(item.get('status'))} |"
            )

    lines.extend(
        [
            "",
            "## 2. Conventions and mathematical calculation",
            "",
            "Row index `I` identifies the site whose occupation is observed; column index `J` identifies the site receiving perturbation α. Occupations are in electrons and α is in eV.",
            "",
            "For each perturbed site `J`, the response of each observed site `I` is fitted around α = 0:",
            "",
            "```text",
            "n_I(α_J) = c_0 + c_1 α_J + c_2 α_J² + …",
            "χ⁰_IJ = (∂n⁰_I / ∂α_J)|₀   [BARE, eV⁻¹]",
            "χ_IJ  = (∂n_I  / ∂α_J)|₀   [SCREENED, eV⁻¹]",
            "U_matrix = (χ⁰)⁻¹ − χ⁻¹   [eV]",
            "U_scalar_charge(I) = U_matrix[I,I]",
            "```",
            "",
            f"The analysis used a degree-{_fmt(primary.get('degree'))} `{_cell(primary.get('method'))}` fit; for a cubic fit, the derivative at zero is the linear coefficient `c₁`. The matrices `{_cell(primary.get('matrix_for_inversion'))}` were inverted. No pseudoinverse or silent regularization is used.",
            "",
            "## 3. Verified occupations used by the analysis",
            "",
        ]
    )
    if dataset.get("status") == "AVAILABLE" and isinstance(dataset.get("rows"), list):
        width_key = (
            "occupation_half_widths_electron"
            if schema == "siestaflow.lr_u_analysis.v3"
            or dataset.get("schema_version") == "siestaflow.lr_u_verified_dataset.v2"
            else "matrix_trace_half_widths_electron"
        )
        width_heading = (
            "Printed observable half-width (ref/BARE/SCREENED, e)"
            if width_key == "occupation_half_widths_electron"
            else "Printed trace half-width (ref/BARE/SCREENED, e)"
        )
        lines.extend(
            [
                f"Dataset `{_cell(dataset.get('schema_version'))}`; α in {_cell((dataset.get('units') or {}).get('alpha'))}, occupation in {_cell((dataset.get('units') or {}).get('occupations'))}.",
                "",
                f"| Perturbed site | α (eV) | Observed site | Reference n (e) | BARE n (e) | SCREENED n (e) | {width_heading} |",
                "|---|---:|---|---:|---:|---:|---|",
            ]
        )
        for row in dataset["rows"]:
            for observed in row.get("observed_sites", []):
                occupations = observed.get("occupations_electron", {})
                trace_widths = observed.get(width_key, {})
                trace_widths = trace_widths if isinstance(trace_widths, Mapping) else {}
                lines.append(
                    f"| {_cell(row.get('perturbed_site_id'))} | {_fmt(row.get('alpha_eV'))} | "
                    f"{_cell(observed.get('observed_site_id'))} | {_fmt(occupations.get('reference'))} | "
                    f"{_fmt(occupations.get('bare'))} | {_fmt(occupations.get('screened'))} | "
                    f"{_fmt(trace_widths.get('reference'))} / {_fmt(trace_widths.get('bare'))} / "
                    f"{_fmt(trace_widths.get('screened'))} |"
                )
    else:
        reason = dataset.get("reason") or "this earlier v2 analysis did not store verified occupations"
        lines.append(f"Occupation data unavailable: {_cell(reason)}.")
    lines.extend(
        [
            "",
            "## 4. Element-by-element fits",
            "",
            "Each row corresponds to (observed site `I`, perturbed site `J`, mode). The primary fit slope forms χ⁰_IJ (BARE) or χ_IJ (SCREENED). Residuals are `calculated n − fitted n`, ordered by α as listed in the analysis.",
            "",
            "| Observed site I | Perturbed site J | Mode | Fit | Degree | Points | Residual DoF | Slope c₁ (e·eV⁻¹) | Coefficients with units | R² | Design condition | Residual RMS (e) | Max abs. residual (e) | Residuals (e) |",
            "|---|---|---|---|---:|---:|---:|---:|---|---:|---:|---:|---:|---|",
        ]
    )
    diagnostics = primary.get("fit_diagnostics", [])
    for item in diagnostics if isinstance(diagnostics, list) else []:
        for fit_key, fit_label in (
            ("primary", "primary"),
            ("same_grid_linear", "same-grid linear"),
            ("inner_linear", "inner-window linear"),
        ):
            fit = item.get(fit_key)
            if not isinstance(fit, Mapping):
                continue
            lines.append(
                f"| {_cell(_display_site(item.get('observed_site'), names))} | "
                f"{_cell(_display_site(item.get('perturbed_site'), names))} | {_cell(item.get('mode'))} | "
                f"{fit_label} | {_fmt(fit.get('degree', 1))} | {_fmt(fit.get('n_points'))} | "
                f"{_fmt(fit.get('residual_dof'))} | {_fmt(fit.get('slope'))} | "
                f"{_coefficients_with_units(fit)} | {_fmt(fit.get('r_squared'))} | "
                f"{_fmt(fit.get('design_condition_number'))} | {_fmt(fit.get('residual_rms'))} | "
                f"{_fmt(fit.get('max_abs_residual'))} | "
                f"{_json_compact(fit.get('residuals'))} |"
            )
    if not diagnostics:
        lines.append("Detailed fits are not available in this analysis.")

    lines.extend(["", "## 5. Response matrices, inverses, and U", ""])
    lines.append(
        f"Representation selected for inversion: `{_cell(primary.get('matrix_for_inversion'))}`. Raw and symmetrized matrices are retained as evidence."
    )
    lines.append("")
    for key, title in (
        ("chi0_raw", "χ⁰ raw (BARE)"),
        ("chi_raw", "χ raw (SCREENED)"),
        ("chi0_symmetrized", "symmetrized χ⁰"),
        ("chi_symmetrized", "symmetrized χ"),
        ("matrix_used_chi0", "χ⁰ used for inversion"),
        ("matrix_used_chi", "χ used for inversion"),
        ("chi0_inverse_eV", "(χ⁰)⁻¹"),
        ("chi_inverse_eV", "χ⁻¹"),
        ("U_matrix_eV", "U_matrix"),
    ):
        unit = "eV" if "inverse" in key or key == "U_matrix_eV" else "eV⁻¹"
        lines.extend(_matrix_table(title, primary.get(key), names, unit=unit))
    lines.extend(_diagnostic_table(primary, names, "primary fit"))

    lines.extend(["## 6. Sensitivity, diagnostics, and status", ""])
    lines.extend(
        [
            "| Analysis | Maximum α window (eV) | Method | Window type | Matrix status | U by site (eV) | Printing bound (eV) |",
            "|---|---:|---|---|---|---|---:|",
        ]
    )
    alternatives = [("Primary", primary), ("Same-grid linear", analysis.get("same_grid_linear") or {})]
    alternatives.extend(
        ("Window", item) for item in analysis.get("window_results", []) if isinstance(item, Mapping)
    )
    for label, item in alternatives:
        values = item.get("U_by_site_eV")
        if isinstance(values, Mapping):
            rendered = "; ".join(
                f"{_cell(_display_site(site, names))}: {_fmt(value)}" for site, value in values.items()
            )
        else:
            rendered = "—"
        rounding = item.get("rounding_bound")
        rounding = rounding if isinstance(rounding, Mapping) else {}
        lines.append(
            f"| {_cell(label)} | {_fmt(item.get('alpha_window_ev'))} | {_cell(item.get('method'))} | "
            f"{_cell(item.get('window_classification') or item.get('window_diagnostic_type'))} | "
            f"{_cell(item.get('matrix_status'))} | {rendered} | {_fmt(rounding.get('maximum_U_scalar_half_width_eV'))} |"
        )
    sensitivity = analysis.get("sensitivity_summary") or {}
    lines.extend(
        [
            "",
            f"- Maximum reported U difference across models/windows: {_fmt(sensitivity.get('max_abs_u_difference_eV'))} eV.",
            f"- Assessment against threshold: `{_cell(sensitivity.get('assessment', 'UNASSESSED'))}`; required metrics complete: {_fmt(sensitivity.get('required_metrics_complete'))}.",
            f"- Configured sensitivity threshold: {_fmt(sensitivity.get('threshold_eV'))} eV.",
            f"- Sensitivity status: `{_cell(sensitivity.get('state', 'UNASSESSED'))}`; declared by: `{_cell(sensitivity.get('declared_by', 'not declared'))}`; via: `{_cell(sensitivity.get('provided_via', '—'))}`.",
            f"- Total numerical precision: `{_cell(precision_status)}`; predeclared U tolerance: {_fmt(precision_tolerance)} eV.",
            f"- Total U interval by site: `{_cell(total_interval.get('status', 'NOT_RECORDED'))}`; reason: `{_cell(total_interval.get('reason', 'total interval was not recorded'))}`.",
            f"- Deterministic rounding alone: {_fmt(rounding_bound)} eV; standalone comparison with tolerance: `{rounding_comparison}`. Rounding alone does not establish total numerical precision or physical acceptance.",
            f"- Grid repeatability calibration: `{_cell(grid_calibration.get('status', 'NOT_PROVIDED'))}`; reason: `{_cell(grid_calibration.get('reason', 'not configured'))}`.",
            f"- Conditional coordinate envelope: `{_cell(conditional_noise.get('status', 'NOT_AVAILABLE'))}`; scope: `{_cell(conditional_noise.get('interpretation', 'grid calibration is incomplete'))}`.",
            f"- Conditional interval by site (not total and not a guarantee): `{_json_compact(conditional_noise.get('U_scalar_interval_by_site_eV'))}`.",
            f"- Numerical reproducibility assessment under the predeclared tolerance: `{_cell(precision_status)}`. It is interpreted only under the declared replication protocol and is not physical acceptance.",
            "- Estimator/window sensitivity, deterministic rounding, and observed replicate variation are distinct evidence; they are reported separately and are not presented as a total mathematical bound.",
            "- An incomplete envelope means conditional reproducibility has not been established; it does not invalidate calculated U or remove the stability diagnostics above.",
            *(
                [
                    f"- Fitted occupation source: `{_cell(analysis.get('occupation_source'))}`.",
                    f"- Deterministic rounding bound for the printed occupation source: {_fmt(analysis.get('printing_rounding_bound_eV'))} eV; reason: {_cell(analysis.get('printing_rounding_bound_reason'))}. It is not a statistical interval and does not include SCF noise.",
                ]
                if schema == "siestaflow.lr_u_analysis.v3"
                else [
                    f"- Deterministic rounding bound for diagonal tokens in the printed matrix trace: {_fmt(analysis.get('printing_rounding_bound_eV'))} eV; reason: {_cell(analysis.get('printing_rounding_bound_reason'))}. It is not a statistical interval and does not include SCF noise."
                ]
            ),
            f"- SCF validation: {_fmt((analysis.get('scf_and_magnetic_diagnostics') or {}).get('scf_validated'))}.",
            f"- State continuity: {_fmt((analysis.get('scf_and_magnetic_diagnostics') or {}).get('state_continuity_confirmed'))}.",
            "",
            "Recorded reasons and warnings:",
        ]
    )
    reasons = analysis.get("reasons") or []
    lines.extend([f"- `{_cell(reason)}`" for reason in reasons] or ["- No issues recorded."])

    lines.extend(
        [
            "",
            "## 7. Provenance and source files",
            "",
            "| Tipo | SHA-256 registrados |",
            "|---|---|",
        ]
    )
    for label, value in sorted(provenance.items()):
        if label == "campaign_inputs":
            continue
        rendered = (
            ", ".join(_json_compact(item) for item in value)
            if isinstance(value, list)
            else _json_compact(value)
        )
        lines.append(f"| {_cell(label)} | {_cell(rendered)} |")

    declared_inputs = input_provenance.get("declared_inputs") or {}
    if isinstance(declared_inputs, Mapping) and declared_inputs:
        lines.extend(
            [
                "",
                "### Declared campaign inputs",
                "",
                "| File | Path | SHA-256 |",
                "|---|---|---|",
            ]
        )
        for label, item in sorted(declared_inputs.items()):
            item = item if isinstance(item, Mapping) else {}
            lines.append(f"| {_cell(label)} | {_cell(item.get('path'))} | {_cell(item.get('sha256'))} |")

    pseudopotentials = input_provenance.get("pseudopotentials") or {}
    if isinstance(pseudopotentials, Mapping) and pseudopotentials:
        lines.extend(
            [
                "",
                "### Declared pseudopotentials",
                "",
                "| Species | File | SHA-256 |",
                "|---|---|---|",
            ]
        )
        for label, item in sorted(pseudopotentials.items()):
            item = item if isinstance(item, Mapping) else {}
            lines.append(f"| {_cell(label)} | {_cell(item.get('path'))} | {_cell(item.get('sha256'))} |")

    runtime = input_provenance.get("siesta_runtime") or {}
    if isinstance(runtime, Mapping) and runtime:
        lines.extend(
            [
                "",
                "### SIESTA executable and version",
                "",
                "| Declared executable | Executable path | Admitted version | Version file | Version-file SHA-256 |",
                "|---|---|---|---|---|",
                f"| {_cell(runtime.get('declared_executable'))} | {_cell(runtime.get('runtime_executable'))} | "
                f"{_cell(runtime.get('version'))} | {_cell(runtime.get('version_text_path'))} | {_cell(runtime.get('version_text_sha256'))} |",
            ]
        )

    if dataset.get("status") == "AVAILABLE":
        lines.extend(
            [
                "",
                "### Files for each validated response",
                "",
                "| Perturbation α | Perturbed site | Mode | Node | FDF | .out | FDF / .out SHA-256 | Receipt evidence digest |",
                "|---:|---|---|---|---|---|---|---|",
            ]
        )
        reference_source = dataset.get("reference_source")
        if isinstance(reference_source, Mapping):
            lines.extend(_source_lines(reference_source, "—", "Referencia"))
        for row in dataset.get("rows", []):
            for mode in ("bare", "screened"):
                source = (row.get("sources") or {}).get(mode)
                lines.extend(_source_lines(source, row.get("alpha_eV"), row.get("perturbed_site_id")))
    else:
        lines.append("Per-response-point provenance was not archived in this v2 JSON.")

    rounding_footer = (
        "The deterministic rounding bound is calculated from the printed `Occupations:` total tokens; if those tokens are missing, the bound is unavailable."
        if schema == "siestaflow.lr_u_analysis.v3"
        else "The rounding bound is calculated from the printed diagonal tokens in the matrix trace; if those tokens are missing, the bound is unavailable."
    )
    lines.extend(
        [
            "",
            "Sensitivity across estimators and windows is a diagnostic, not a confidence interval. "
            + rounding_footer,
            "",
        ]
    )
    if state_gate is not None:
        lines.extend(_state_gate_section(state_gate))
    reproduction = dataset.get("reference_reproduction")
    if isinstance(reproduction, Mapping):
        lines.extend(reference_reproduction_report_lines(reproduction))
    return "\n".join(lines)


def write_lr_u_report(
    path: str | Path,
    analysis: Mapping[str, Any],
    *,
    state_gate: Mapping[str, Any] | None = None,
) -> Path:
    """Atomically write the Markdown report; repeated writes are deterministic."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(render_lr_u_report(analysis, state_gate=state_gate), encoding="utf-8", newline="\n")
    temporary.replace(destination)
    return destination
