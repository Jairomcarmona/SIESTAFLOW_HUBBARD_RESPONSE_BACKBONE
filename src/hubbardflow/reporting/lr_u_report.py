"""Human-readable Markdown view of a canonical LR-U analysis v2 JSON."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping


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
        "Este diagnóstico no modifica el análisis ni la admisión de la campaña.",
        "",
        "| Columna | Modo | Veredicto | α admisibles (eV) | α excluidos (eV) | G4 | Razones |",
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
    lines.extend(["", "G3 suavidad: `NOT_ESTABLISHED: SMOOTHNESS_REQUIRES_SCF_LADDER`.", ""])
    return lines


def reference_reproduction_report_lines(evidence: Mapping[str, Any]) -> list[str]:
    """Render recorded D16 evidence for completed and rejected TS references."""
    return [
        "", "## Reference reproduction (D16)", "",
        f"- Criterion: `{_cell(evidence.get('criterion'))}`; equivalent: `{_cell(evidence.get('equivalent'))}`.",
        f"- Planning parent DM SHA-256: `{_cell(evidence.get('planning_parent_dm_sha256'))}`.",
        f"- Campaign parent DM SHA-256: `{_cell(evidence.get('campaign_parent_dm_sha256'))}`.",
        f"- Reason: `{_cell(evidence.get('reason'))}`; {_cell(evidence.get('detail'))}.",
        f"- Maximum occupation difference (e): {_fmt(evidence.get('max_occupation_difference_e'))}; comparison quanta (e): {_json_compact(evidence.get('occupation_comparison_quanta_e'))}.",
        f"- Fermi difference (eV): {_fmt(evidence.get('max_fermi_difference_ev'))}; comparison quantum (eV): {_fmt(evidence.get('fermi_comparison_quantum_ev'))}.",
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
        return [*lines, "No disponible en este análisis.", ""]
    size = len(matrix)
    block_width = 8
    for start in range(0, size, block_width):
        stop = min(start + block_width, size)
        if size > block_width:
            lines.append(f"Columnas de sitios perturbados {_fmt(start + 1)}–{_fmt(stop)}.")
            lines.append("")
        headings = [_display_site(index, names) for index in range(start, stop)]
        lines.append("| Sitio observado \\ Sitio perturbado | " + " | ".join(_cell(value) for value in headings) + " |")
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
    lines = [f"### Diagnóstico de inversión: {label}", "", "| Matriz | Método | Residuo izquierdo Frobenius | Residuo derecho Frobenius |", "|---|---|---:|---:|"]
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
        lines.extend([
            f"**Condición de {title}:** rango {_fmt(item.get('rank'))}/{_fmt((item.get('shape') or [None])[0] if item.get('shape') else None)}; "
            f"determinante {_fmt(item.get('det'))}; número de condición {_fmt(item.get('condition_number'))}; "
            f"estado `{_cell(item.get('matrix_status'))}`.",
            "",
        ])
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


def render_lr_u_report(
    analysis: Mapping[str, Any], *, state_gate: Mapping[str, Any] | None = None
) -> str:
    """Render a deterministic report from analysis JSON; old v2 files remain readable."""
    schema = analysis.get("schema_version")
    if schema == "siestaflow.lr_u_analysis.v3" and analysis.get("occupation_source") != "siesta_occupations_total":
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
    precision_tolerance = precision.get("predeclared_tolerance_eV", estimator_policy.get("u_precision_tolerance_eV"))
    precision_status = precision.get("status", "NOT_ASSESSED_TOTAL_INTERVAL_NOT_RECORDED")
    total_interval = analysis.get("total_numerical_U_interval")
    total_interval = total_interval if isinstance(total_interval, Mapping) else {}
    conditional_noise = analysis.get("conditional_response_grid_reproducibility_envelope")
    conditional_noise = conditional_noise if isinstance(conditional_noise, Mapping) else {}
    grid_calibration = analysis.get("response_grid_reproducibility_calibration")
    grid_calibration = grid_calibration if isinstance(grid_calibration, Mapping) else {}
    rounding_bound = analysis.get("printing_rounding_bound_eV")
    if isinstance(rounding_bound, (int, float)) and isinstance(precision_tolerance, (int, float)):
        rounding_comparison = "WITHIN_TOLERANCE_ALONE" if rounding_bound <= precision_tolerance else "EXCEEDS_TOLERANCE_ALONE"
    else:
        rounding_comparison = "NOT_COMPARABLE"

    lines = [
        "# Informe de respuesta lineal de Hubbard",
        "",
        f"- **Campaña:** {_cell(campaign.get('campaign_id') or campaign.get('name'))}",
        f"- **Material:** {_cell(campaign.get('material') or campaign.get('system_label'))}",
        f"- **Funcional:** {_cell(campaign.get('functional'))}",
        f"- **Versión SIESTA:** {_cell(runtime_provenance.get('version'))}",
        f"- **Analizador:** {_cell(implementation.get('package'))} {_cell(implementation.get('package_version'))} — {_cell(implementation.get('schema'))}",
        f"- **Cantidad calculada:** `{_cell(analysis.get('quantity', 'U_scalar_charge'))}` ({_cell(analysis.get('units', 'eV'))})",
        f"- **Estado numérico:** **{_cell(state)}**",
        f"- **Aceptación física:** **{_cell(analysis.get('physical_acceptance', 'NOT_ESTABLISHED'))}**",
        f"- **Precisión numérica total:** `{_cell(precision_status)}`; tolerancia predeclarada: {_fmt(precision_tolerance)} eV.",
        f"- **Estimador principal:** {_cell(estimator)}, grado {_fmt(degree)}",
        f"- **Malla α (eV):** `{', '.join(_fmt(value) for value in analysis.get('alpha_grid_eV', []))}`",
        f"- **Acción DAG registrada:** `{_cell(dag_action)}`",
        "",
        "El resultado corresponde a `U_scalar_charge` de la respuesta de carga declarada. "
        "No se convierte automáticamente en `Ueff_Dudarev` ni implica aceptación física.",
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
        lines.extend([
            "## Estado de refinamiento adaptativo",
            "",
            f"- Decisión de campaña: **{_cell(analysis.get('campaign_status', decision.get('decision', 'UNKNOWN')))}**.",
            f"- Estado del candidato: **{_cell(analysis.get('candidate_status', state))}**.",
            f"- Motivo: `{_cell(decision.get('reason'))}`.",
            f"- Métrica de ventana para refinamiento: {_fmt(decision.get('truncation_metric_eV'))} eV; base: `{_cell(decision.get('truncation_metric_basis'))}`.",
            f"- Umbral de truncación declarado: {_fmt(refinement_policy.get('truncation_threshold_eV'))} eV. Si la métrica observada supera este valor, se propone `shrink`, sujeto a la precedencia de otras decisiones y a los límites de rondas y presupuesto; la métrica es una sensibilidad empírica, no una cota de error.",
            f"- Tolerancia de aumento de sensibilidad entre rondas: {_fmt(refinement_policy.get('sensitivity_delta_tolerance_eV'))} eV. Solo compara el aumento frente a la ronda previa; no es un umbral absoluto de aceptación ni una cota de error.",
            f"- Ronda final: {_fmt(latest.get('round_index'))}; dirección: `{_cell(latest.get('direction'))}`; "
            f"ventana activa: {_fmt(latest.get('active_window_eV'))} eV; nivel SCF: `{_cell(latest.get('effective_scf_level_id') or latest.get('scf_level_id'))}`.",
            f"- Presupuesto reservado: {_fmt(budget.get('reserved_nodes'))}/{_fmt(budget.get('total_siesta_node_budget'))} nodos SIESTA; "
            f"restantes: {_fmt(budget.get('remaining_nodes'))}.",
            "- La diferencia entre niveles SCF se interpreta como sensibilidad empírica; no es una cota rigurosa del error de U.",
            "",
            "| Ronda | Dirección | α medidos (eV) | Ventana activa (eV) | Nivel SCF | Candidato | Estado |",
            "|---:|---|---|---:|---|---|---|",
        ])
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
    lines.extend([
        "## 1. Resumen de U por sitio",
        "",
        "| Cantidad | Sitio | Valor (eV) | Método | Sensibilidad al modelo (eV) | Sensibilidad a ventana (eV) | Estado numérico | Acción DAG |",
        "|---|---|---:|---|---:|---:|---|---|",
    ])
    site_labels = analysis.get("site_labels", list(u_by_site))
    for site in site_labels:
        key = str(site)
        lines.append(
            f"| U_scalar_charge | {_cell(_display_site(site, names))} | {_fmt(u_by_site.get(key))} | "
            f"{_cell(estimator)} | {_fmt(model_sensitivity.get(key))} | {_fmt(window_sensitivity.get(key))} | "
            f"{_cell(state)} | {_cell(dag_action)} |"
        )
    if not site_labels:
        lines.append(f"| U_scalar_charge | — | — | {_cell(estimator)} | — | — | {_cell(state)} | {_cell(dag_action)} |")

    additional_observables = campaign.get("observables", [])
    if isinstance(additional_observables, list) and additional_observables:
        lines.extend([
            "",
            "### Otras observables registradas",
            "",
            "| Observable | Sitio/estado | Valor | Unidad | Referencia/fuente | Estado |",
            "|---|---|---:|---|---|---|",
        ])
        for item in additional_observables:
            item = item if isinstance(item, Mapping) else {}
            lines.append(
                f"| {_cell(item.get('name'))} | {_cell(item.get('site_or_state'))} | "
                f"{_fmt(item.get('value'))} | {_cell(item.get('unit'))} | "
                f"{_cell(item.get('reference') or item.get('source'))} | {_cell(item.get('status'))} |"
            )

    lines.extend([
        "",
        "## 2. Convención y cálculo matemático",
        "",
        "El índice de fila `I` identifica el sitio cuya ocupación se observa; el índice de columna `J` identifica el sitio al que se aplica la perturbación α. Las ocupaciones se expresan en electrones y α en eV.",
        "",
        "Para cada sitio perturbado `J`, se ajusta la respuesta de cada sitio observado `I` alrededor de α = 0:",
        "",
        "```text",
        "n_I(α_J) = c_0 + c_1 α_J + c_2 α_J² + …",
        "χ⁰_IJ = (∂n⁰_I / ∂α_J)|₀   [BARE, eV⁻¹]",
        "χ_IJ  = (∂n_I  / ∂α_J)|₀   [SCREENED, eV⁻¹]",
        "U_matrix = (χ⁰)⁻¹ − χ⁻¹   [eV]",
        "U_scalar_charge(I) = U_matrix[I,I]",
        "```",
        "",
        f"El análisis usó ajuste `{_cell(primary.get('method'))}` de grado {_fmt(primary.get('degree'))}; para el cúbico, la derivada en cero es el coeficiente lineal `c₁`. La inversión se hizo con las matrices `{_cell(primary.get('matrix_for_inversion'))}`. No se aplica pseudoinversa ni regularización silenciosa.",
        "",
        "## 3. Ocupaciones verificadas usadas por el análisis",
        "",
    ])
    if dataset.get("status") == "AVAILABLE" and isinstance(dataset.get("rows"), list):
        width_key = (
            "occupation_half_widths_electron"
            if schema == "siestaflow.lr_u_analysis.v3"
            or dataset.get("schema_version") == "siestaflow.lr_u_verified_dataset.v2"
            else "matrix_trace_half_widths_electron"
        )
        width_heading = (
            "½ ancho del observable impreso (ref/BARE/SCREENED, e)"
            if width_key == "occupation_half_widths_electron"
            else "½ ancho de traza por impresión (ref/BARE/SCREENED, e)"
        )
        lines.extend([
            f"Dataset `{_cell(dataset.get('schema_version'))}`; α en {_cell((dataset.get('units') or {}).get('alpha'))}, ocupación en {_cell((dataset.get('units') or {}).get('occupations'))}.",
            "",
            f"| Sitio perturbado | α (eV) | Sitio observado | n referencia (e) | n BARE (e) | n SCREENED (e) | {width_heading} |",
            "|---|---:|---|---:|---:|---:|---|",
        ])
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
        reason = dataset.get("reason") or "este análisis v2 anterior no guardaba las ocupaciones verificadas"
        lines.append(f"Datos de ocupación no disponibles: {_cell(reason)}.")
    lines.extend([
        "",
        "## 4. Ajustes elemento por elemento",
        "",
        "Cada fila corresponde a (sitio observado `I`, sitio perturbado `J`, modo). La pendiente del ajuste principal forma el elemento χ⁰_IJ (BARE) o χ_IJ (SCREENED). Los residuos son `n calculada − n ajustada` en el orden de α indicado por el análisis.",
        "",
        "| Sitio observado I | Sitio perturbado J | Modo | Ajuste | Grado | Puntos | gl residuales | Pendiente c₁ (e·eV⁻¹) | Coeficientes con unidades | R² | Condición diseño | RMS residuo (e) | Máx. abs. residuo (e) | Residuos (e) |",
        "|---|---|---|---|---:|---:|---:|---:|---|---:|---:|---:|---:|---|",
    ])
    diagnostics = primary.get("fit_diagnostics", [])
    for item in diagnostics if isinstance(diagnostics, list) else []:
        for fit_key, fit_label in (("primary", "principal"), ("same_grid_linear", "lineal_misma_malla"), ("inner_linear", "lineal_interior")):
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
        lines.append("Ajustes detallados no disponibles en este análisis.")

    lines.extend(["", "## 5. Matrices de respuesta, inversas y U", ""])
    lines.append(f"Representación seleccionada para inversión: `{_cell(primary.get('matrix_for_inversion'))}`. Las matrices raw y simetrizadas se conservan como evidencia.")
    lines.append("")
    for key, title in (
        ("chi0_raw", "χ⁰ raw (BARE)"), ("chi_raw", "χ raw (SCREENED)"),
        ("chi0_symmetrized", "χ⁰ simetrizada"), ("chi_symmetrized", "χ simetrizada"),
        ("matrix_used_chi0", "χ⁰ usada para inversión"), ("matrix_used_chi", "χ usada para inversión"),
        ("chi0_inverse_eV", "(χ⁰)⁻¹"), ("chi_inverse_eV", "χ⁻¹"), ("U_matrix_eV", "U_matrix"),
    ):
        unit = "eV" if "inverse" in key or key == "U_matrix_eV" else "eV⁻¹"
        lines.extend(_matrix_table(title, primary.get(key), names, unit=unit))
    lines.extend(_diagnostic_table(primary, names, "ajuste principal"))

    lines.extend(["## 6. Sensibilidad, diagnósticos y estado", ""])
    lines.extend([
        "| Análisis | Ventana máxima α (eV) | Método | Tipo de ventana | Estado de matriz | U por sitio (eV) | Cota de impresión (eV) |",
        "|---|---:|---|---|---|---|---:|",
    ])
    alternatives = [("Principal", primary), ("Lineal misma malla", analysis.get("same_grid_linear") or {})]
    alternatives.extend(("Ventana", item) for item in analysis.get("window_results", []) if isinstance(item, Mapping))
    for label, item in alternatives:
        values = item.get("U_by_site_eV")
        if isinstance(values, Mapping):
            rendered = "; ".join(f"{_cell(_display_site(site, names))}: {_fmt(value)}" for site, value in values.items())
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
    lines.extend([
        "",
        f"- Diferencia máxima de U entre modelos/ventanas informada: {_fmt(sensitivity.get('max_abs_u_difference_eV'))} eV.",
        f"- Evaluación frente al umbral: `{_cell(sensitivity.get('assessment', 'UNASSESSED'))}`; métricas requeridas completas: {_fmt(sensitivity.get('required_metrics_complete'))}.",
        f"- Umbral configurado para sensibilidad: {_fmt(sensitivity.get('threshold_eV'))} eV.",
        f"- Precisión numérica total: `{_cell(precision_status)}`; tolerancia predeclarada de U: {_fmt(precision_tolerance)} eV.",
        f"- Intervalo total de U por sitio: `{_cell(total_interval.get('status', 'NOT_RECORDED'))}`; causa: `{_cell(total_interval.get('reason', 'no se registró intervalo total'))}`.",
        f"- Redondeo determinista solamente: {_fmt(rounding_bound)} eV; comparación aislada con la tolerancia: `{rounding_comparison}`. Este resultado de redondeo por sí solo no acepta precisión total ni física.",
        f"- Calibración de repetibilidad de malla: `{_cell(grid_calibration.get('status', 'NOT_PROVIDED'))}`; motivo: `{_cell(grid_calibration.get('reason', 'no configurada'))}`.",
        f"- Envolvente condicional por coordenada: `{_cell(conditional_noise.get('status', 'NOT_AVAILABLE'))}`; alcance: `{_cell(conditional_noise.get('interpretation', 'sin calibración completa de la malla'))}`.",
        f"- Intervalo condicional por sitio (no total ni garantía): `{_json_compact(conditional_noise.get('U_scalar_interval_by_site_eV'))}`.",
        f"- Comparación de reproducibilidad numérica con tolerancia predeclarada: `{_cell(precision_status)}`. Sólo se interpreta bajo el protocolo de réplicas declarado; no es aceptación física.",
        "- Sensibilidad de estimador/ventana, redondeo determinista y variación observada entre réplicas son evidencias distintas; se informan por separado y no se presentan como cota matemática total.",
        "- La falta de una envolvente completa significa que la reproducibilidad condicionada no está demostrada; no invalida el valor U calculado ni elimina los diagnósticos de estabilidad que se muestran arriba.",
        *(
            [f"- Fuente de ocupación ajustada: `{_cell(analysis.get('occupation_source'))}`.",
             f"- Cota determinista de redondeo de la fuente de ocupación impresa: {_fmt(analysis.get('printing_rounding_bound_eV'))} eV; causa: {_cell(analysis.get('printing_rounding_bound_reason'))}. No es un intervalo estadístico ni incluye ruido SCF."]
            if schema == "siestaflow.lr_u_analysis.v3" else
            [f"- Cota determinista por redondeo de tokens diagonales de la traza de matriz impresa: {_fmt(analysis.get('printing_rounding_bound_eV'))} eV; causa: {_cell(analysis.get('printing_rounding_bound_reason'))}. No es un intervalo estadístico ni incluye ruido SCF."]
        ),
        f"- Validación SCF: {_fmt((analysis.get('scf_and_magnetic_diagnostics') or {}).get('scf_validated'))}.",
        f"- Continuidad de estado: {_fmt((analysis.get('scf_and_magnetic_diagnostics') or {}).get('state_continuity_confirmed'))}.",
        "",
        "Causas y advertencias registradas:",
    ])
    reasons = analysis.get("reasons") or []
    lines.extend([f"- `{_cell(reason)}`" for reason in reasons] or ["- Sin incidencias registradas."])

    lines.extend([
        "",
        "## 7. Procedencia y archivos fuente",
        "",
        "| Tipo | SHA-256 registrados |",
        "|---|---|",
    ])
    for label, value in sorted(provenance.items()):
        if label == "campaign_inputs":
            continue
        rendered = ", ".join(_json_compact(item) for item in value) if isinstance(value, list) else _json_compact(value)
        lines.append(f"| {_cell(label)} | {_cell(rendered)} |")

    declared_inputs = input_provenance.get("declared_inputs") or {}
    if isinstance(declared_inputs, Mapping) and declared_inputs:
        lines.extend([
            "",
            "### Entradas declaradas de la campaña",
            "",
            "| Archivo | Ruta | SHA-256 |",
            "|---|---|---|",
        ])
        for label, item in sorted(declared_inputs.items()):
            item = item if isinstance(item, Mapping) else {}
            lines.append(f"| {_cell(label)} | {_cell(item.get('path'))} | {_cell(item.get('sha256'))} |")

    pseudopotentials = input_provenance.get("pseudopotentials") or {}
    if isinstance(pseudopotentials, Mapping) and pseudopotentials:
        lines.extend([
            "",
            "### Pseudopotenciales declarados",
            "",
            "| Especie | Archivo | SHA-256 |",
            "|---|---|---|",
        ])
        for label, item in sorted(pseudopotentials.items()):
            item = item if isinstance(item, Mapping) else {}
            lines.append(f"| {_cell(label)} | {_cell(item.get('path'))} | {_cell(item.get('sha256'))} |")

    runtime = input_provenance.get("siesta_runtime") or {}
    if isinstance(runtime, Mapping) and runtime:
        lines.extend([
            "",
            "### Ejecutable y versión de SIESTA",
            "",
            "| Ejecutable declarado | Ruta ejecutable | Versión admitida | Archivo de versión | SHA-256 del archivo de versión |",
            "|---|---|---|---|---|",
            f"| {_cell(runtime.get('declared_executable'))} | {_cell(runtime.get('runtime_executable'))} | "
            f"{_cell(runtime.get('version'))} | {_cell(runtime.get('version_text_path'))} | {_cell(runtime.get('version_text_sha256'))} |",
        ])

    if dataset.get("status") == "AVAILABLE":
        lines.extend([
            "",
            "### Archivos de cada respuesta validada",
            "",
            "| α perturbado | Sitio perturbado | Modo | Nodo | FDF | .out | SHA-256 FDF / .out | Digest de evidencia del recibo |",
            "|---:|---|---|---|---|---|---|---|",
        ])
        reference_source = dataset.get("reference_source")
        if isinstance(reference_source, Mapping):
            lines.extend(_source_lines(reference_source, "—", "Referencia"))
        for row in dataset.get("rows", []):
            for mode in ("bare", "screened"):
                source = (row.get("sources") or {}).get(mode)
                lines.extend(_source_lines(source, row.get("alpha_eV"), row.get("perturbed_site_id")))
    else:
        lines.append("No se archivó el vínculo por punto de respuesta en este JSON v2.")

    rounding_footer = (
        "La cota determinista de redondeo se calcula desde los tokens del total `Occupations:` impreso; si faltan esos tokens, queda como no disponible."
        if schema == "siestaflow.lr_u_analysis.v3" else
        "La cota de redondeo se calcula desde los tokens diagonales impresos de la traza de matriz; si faltan esos tokens, queda como no disponible."
    )
    lines.extend([
        "",
        "La sensibilidad entre estimadores y ventanas es un diagnóstico y no un intervalo de confianza. " + rounding_footer,
        "",
    ])
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
