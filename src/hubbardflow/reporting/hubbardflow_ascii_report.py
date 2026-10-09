"""ASCII-only, fixed-width researcher report rendered from saved JSON data."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from hubbardflow.reporting.hubbardflow_ascii_formatting import (
    additional_report_sections as _additional_report_sections,
)
from hubbardflow.reporting.hubbardflow_ascii_formatting import (
    alpha_key,
)
from hubbardflow.reporting.hubbardflow_ascii_formatting import (
    fixed_decimal as _fixed_decimal,
)
from hubbardflow.reporting.hubbardflow_ascii_formatting import (
    mapping as _map,
)
from hubbardflow.reporting.hubbardflow_ascii_formatting import (
    matrix_lines as _matrix_lines,
)
from hubbardflow.reporting.hubbardflow_ascii_formatting import (
    path_lines as _path_lines,
)
from hubbardflow.reporting.hubbardflow_ascii_formatting import (
    quality_check_lines as _quality_check_lines,
)
from hubbardflow.reporting.hubbardflow_ascii_formatting import (
    report_list as _list,
)
from hubbardflow.reporting.hubbardflow_ascii_formatting import (
    report_value as _value,
)
from hubbardflow.reporting.hubbardflow_ascii_formatting import (
    run_inventory as _run_inventory,
)
from hubbardflow.reporting.hubbardflow_ascii_formatting import (
    section_header as _section_header,
)
from hubbardflow.reporting.hubbardflow_ascii_formatting import (
    site_names as _site_names,
)
from hubbardflow.reporting.hubbardflow_ascii_formatting import (
    source_records as _source_records,
)
from hubbardflow.reporting.hubbardflow_ascii_formatting import (
    wrap_lines as _wrap_lines,
)


def render_hubbardflow_out(source: Mapping[str, Any]) -> str:
    """Render the saved JSON report source as an ASCII-only SIESTA-style file."""
    analysis = _map(source.get("analysis"))
    context = _map(source.get("context"))
    dataset = _map(analysis.get("response_observation_dataset"))
    provenance = _map(source.get("occupation_provenance"))
    provenance_records = provenance.get("records")
    total_derived = isinstance(provenance_records, list) and any(
        isinstance(item, Mapping) and item.get("total_derived") is True for item in provenance_records
    )
    state_gate = _map(source.get("state_gate"))
    campaign = _map(analysis.get("campaign"))
    primary = _map(analysis.get("primary"))
    names = _site_names(analysis, dataset)
    source_index = _source_records(provenance)
    lines: list[str] = [
        "HUBBARDFLOW LINEAR-RESPONSE REPORT",
        "Generated from saved JSON evidence; this text file is a rendered view.",
        *_section_header("RESULT SUMMARY"),
    ]
    u_by_site = _map(primary.get("U_by_site_eV"))
    fit_rows = primary.get("fit_diagnostics")
    max_residual: dict[str, float | None] = {}
    if isinstance(fit_rows, list):
        for row in fit_rows:
            if not isinstance(row, Mapping):
                continue
            site_index = row.get("observed_site")
            fit = _map(row.get("primary"))
            residual = fit.get("max_abs_residual")
            if isinstance(site_index, int) and isinstance(residual, (int, float)):
                current = max_residual.get(str(site_index))
                max_residual[str(site_index)] = max(float(residual), current or 0.0)
    window_sensitivity = _map(analysis.get("window_sensitivity_eV"))
    for key, value in sorted(u_by_site.items(), key=lambda item: str(item[0])):
        site_id = names.get(int(key), str(key)) if str(key).isdigit() else str(key)
        lines.append(
            f"  {site_id}: U = {_value(value)} eV; max fit residual = "
            f"{_value(max_residual.get(str(key)))} e; window sensitivity = "
            f"{_value(window_sensitivity.get(str(key)))} eV"
        )
    if not u_by_site:
        lines.append("  U by site: NOT_ASSESSED")
    projector = _map(context.get("projector"))
    lines.append(
        "  Definition: one-shot U_LR^DFT, projector method "
        f"{_value(projector.get('method'))}, CutoffNorm {_value(projector.get('cutoff_norm'))}, "
        "rc and omega as listed below, atomic non-orthogonalized; not comparable with "
        "orthogonalized-atomic literature values."
    )
    lines.extend(_section_header("[01] HEADER"))
    version = _map(context.get("hubbardflow"))
    siesta = _map(context.get("siesta"))
    lines.extend(
        [
            f"  HubbardFlow: {_value(version.get('version'))}; commit: {_value(version.get('commit'))}",
            f"  Date (UTC): {_value(context.get('generated_at_utc'))}; host: {_value(context.get('host'))}",
            f"  SIESTA: {_value(siesta.get('version'))}; binary SHA-256: {_value(siesta.get('binary_sha256'))}",
        ]
    )
    workflow_state = _map(source.get("campaign_state"))
    lines.append(f"  Campaign status: {_value(workflow_state.get('status'))}")
    hash_warnings = source.get("traceability_warnings")
    if isinstance(hash_warnings, list) and hash_warnings:
        lines.append("  Hash warnings (traceability only): " + "; ".join(_value(x) for x in hash_warnings))
    else:
        lines.append("  Hash warnings (traceability only): NONE RECORDED")

    system = _map(context.get("system"))
    geometry = _map(system.get("geometry"))
    basis = _map(system.get("basis"))
    k_grid = _map(system.get("k_grid"))
    lines.extend(_section_header("[02] SYSTEM"))
    lines.append(
        f"  Material: {_value(campaign.get('material'))}; functional: {_value(system.get('functional'))}"
    )
    if total_derived:
        lines.append("  spin treatment: non-polarized; occupation = 2 x printed per-spin value")
    lines.append(
        f"  Geometry: {_value(geometry.get('number_of_atoms'))} atoms; "
        f"{_value(geometry.get('number_of_species'))} species; "
        f"coordinates {_value(geometry.get('coordinate_format'))}; "
        f"lattice constant {_value(geometry.get('lattice_constant_angstrom'))} Ang"
    )
    species = geometry.get("species")
    if isinstance(species, list) and species:
        labels = [
            f"{_value(item.get('label'))} (Z={_value(item.get('atomic_number'))})"
            for item in species
            if isinstance(item, Mapping)
        ]
        lines.append(f"  Species: {', '.join(labels) if labels else 'NOT_ASSESSED'}")
    else:
        lines.append("  Species: NOT_ASSESSED")
    vectors = geometry.get("lattice_vectors_angstrom")
    lines.append("  Lattice vectors (Ang): " + _list(vectors))
    lines.append(
        f"  Basis: PAO.BasisSize={_value(basis.get('pao_basis_size'))}; "
        f"PAO.BasisType={_value(basis.get('pao_basis_type'))}; "
        f"PAO.EnergyShift={_value(basis.get('pao_energy_shift'))}; "
        f"PAO.SplitNorm={_value(basis.get('pao_split_norm'))}; "
        f"MeshCutoff={_value(system.get('mesh_cutoff'))}"
    )
    basis_blocks = basis.get("blocks")
    if isinstance(basis_blocks, Mapping) and basis_blocks:
        for label, rows in sorted(basis_blocks.items()):
            lines.append(f"  PAO.Basis {label}:")
            if isinstance(rows, list):
                lines.extend(f"    {_value(row)}" for row in rows)
            else:
                lines.append("    NOT_ASSESSED")
    else:
        lines.append("  PAO.Basis blocks: NOT_ASSESSED")
    lines.append(f"  k-grid: {_list(k_grid.get('block'))}; cutoff: {_value(k_grid.get('cutoff'))}")
    pseudopotentials = system.get("pseudopotentials")
    if isinstance(pseudopotentials, Mapping) and pseudopotentials:
        for label, item in sorted(pseudopotentials.items()):
            pseudo = _map(item)
            lines.append(f"  Pseudopotential {label}: {_value(pseudo.get('path'))}")
            lines.append(f"    SHA-256 (traceability only): {_value(pseudo.get('sha256'))}")
    else:
        lines.append("  Pseudopotentials: NOT_ASSESSED")

    lines.extend(_section_header("[03] PROJECTOR"))
    lines.append(
        f"  Method: {_value(projector.get('method'))}; CutoffNorm: {_value(projector.get('cutoff_norm'))}"
    )
    lines.append("  U depends on the declared projector; M1 changed by 1.3589 eV between")
    lines.append("    CutoffNorm 0.85 and 0.90 (tests/fixtures/projector_curve_m1.json).")
    records = projector.get("records")
    if isinstance(records, list) and records:
        for record in records:
            if isinstance(record, Mapping):
                lines.append(
                    f"  {record.get('label')}: n={record.get('n')} l={record.get('l')} "
                    f"rc={_value(record.get('rc_bohr'))} bohr omega={_value(record.get('omega'))}"
                )
    else:
        lines.append("  Projector records: NOT_ASSESSED")
    if projector.get("method") == 2:
        warning = _map(projector.get("warning"))
        lines.append(f"  Permanent scheme warning (record-only): {_value(warning.get('code'))}")
        lines.append(f"    {_value(warning.get('message'))}")
    else:
        lines.append("  Projector scheme warning: NOT_ASSESSED")

    protocol = _map(context.get("protocol"))
    estimator = _map(protocol.get("estimator"))
    lines.extend(_section_header("[04] PROTOCOL"))
    protocol_sites = protocol.get("sites")
    if isinstance(protocol_sites, list) and protocol_sites:
        labels = [str(item.get("site_id")) for item in protocol_sites if isinstance(item, Mapping)]
        lines.append(f"  Perturbed sites: {', '.join(labels) if labels else 'NOT_ASSESSED'}")
    else:
        lines.append("  Perturbed sites: NOT_ASSESSED")
    lines.append(f"  Alpha grid (eV): {_list(analysis.get('alpha_grid_eV'))}")
    lines.append(
        f"  Fit: method={_value(estimator.get('estimator'))}; degree={_value(estimator.get('polynomial_degree'))}; "
        f"residual DOF={_value(estimator.get('minimum_residual_dof'))}; "
        f"window (eV)={_value(primary.get('alpha_window_ev'))}"
    )

    lines.extend(_section_header("[05] RUN INVENTORY"))
    lines.append("  NODE | MODE | ALPHA (eV) | STATE")
    for node, folder, mode, alpha, state in _run_inventory(dataset):
        lines.append(f"  {node} | {mode} | {alpha} | {state}")
        lines.extend(_path_lines(folder))
    if not dataset:
        lines.append("  NOT_ASSESSED: response observation dataset is unavailable.")

    lines.extend(_section_header("[06] REFERENCE STATE"))
    reference = dataset.get("reference_reproduction")
    if isinstance(reference, Mapping):
        lines.append(
            f"  Parent-state comparison: result={_value(reference.get('equivalent'))}; "
            f"reason={_value(reference.get('reason'))}; "
            f"occupation status={_value(reference.get('occupation_equivalence'))}; "
            f"Fermi status={_value(reference.get('fermi_equivalence'))}"
        )
        lines.append(
            f"  Max occupation difference/tolerance (e): "
            f"{_value(reference.get('max_occupation_difference_e'))}/"
            f"{_value(reference.get('occupation_tolerance_e'))}; "
            f"Fermi difference/tolerance (eV): {_value(reference.get('max_fermi_difference_ev'))}/"
            f"{_value(reference.get('fermi_tolerance_ev'))}"
        )
        lines.append("  Parent DM digests (traceability only):")
        lines.append(f"PLAN_PARENT_DM={_value(reference.get('planning_parent_dm_sha256'))}")
        lines.append(f"RUN_PARENT_DM={_value(reference.get('campaign_parent_dm_sha256'))}")
    else:
        lines.append("  Parent-state comparison: NOT_ASSESSED")
    rows = dataset.get("rows")
    if isinstance(rows, list) and rows:
        first = rows[0]
        observed = first.get("observed_sites", []) if isinstance(first, Mapping) else []
        for item in observed if isinstance(observed, list) else []:
            if not isinstance(item, Mapping):
                continue
            occ = _map(item.get("occupations_electron"))
            site_index = int(item.get("observed_site_index", -1))
            lines.append(
                f"  {names.get(site_index, str(site_index))}: parent n={_value(occ.get('reference'))} e"
            )
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            values = row.get("observed_sites", [])
            for item in values if isinstance(values, list) else []:
                if not isinstance(item, Mapping):
                    continue
                occ = _map(item.get("occupations_electron"))
                site_index = int(item.get("observed_site_index", -1))
                lines.append(
                    f"  Child {row.get('perturbed_site_id')} alpha={_value(row.get('alpha_eV'))} "
                    f"{names.get(site_index, str(site_index))}: BARE={_value(occ.get('bare'))} e; "
                    f"SCREENED={_value(occ.get('screened'))} e"
                )
    else:
        lines.append("  Parent and child occupations: NOT_ASSESSED")

    lines.extend(_section_header("[07] RESPONSE DATA"))
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            for item in row.get("observed_sites", []) if isinstance(row.get("observed_sites"), list) else []:
                if not isinstance(item, Mapping):
                    continue
                site_index = int(item.get("observed_site_index", -1))
                site_id = str(item.get("observed_site_id", names.get(site_index, site_index)))
                key_prefix = (str(row.get("perturbed_site_id") or ""), alpha_key(row.get("alpha_eV")))
                fields = []
                for mode in ("BARE", "SCREENED"):
                    origin = source_index.get((mode, *key_prefix, site_index), {})
                    fields.append(
                        f"{mode}={_value(_map(item.get('occupations_electron')).get(mode.lower()))} e "
                        f"[{_value(origin.get('file'))}:{_value(origin.get('selected_block_line'))}]"
                    )
                lines.append(
                    f"  J={row.get('perturbed_site_id')} alpha={_value(row.get('alpha_eV'))} eV "
                    f"I={site_id}: " + "; ".join(fields)
                )
    if not rows:
        lines.append("  NOT_ASSESSED: response occupations are unavailable.")

    lines.extend(_section_header("[08] FITS"))
    alpha_values = _list(analysis.get("analysis_alpha_grid_eV"))
    if isinstance(fit_rows, list) and fit_rows:
        for row in fit_rows:
            if not isinstance(row, Mapping):
                continue
            fit = _map(row.get("primary"))
            i = row.get("observed_site")
            j = row.get("perturbed_site")
            lines.append(
                f"  I={names.get(int(i), str(i)) if i is not None else 'NOT_ASSESSED'} "
                f"J={names.get(int(j), str(j)) if j is not None else 'NOT_ASSESSED'} "
                f"mode={_value(row.get('mode'))}: alpha={alpha_values}; "
                f"degree={_value(fit.get('degree'))}; max residual={_value(fit.get('max_abs_residual'))} e; "
                f"slope={_value(fit.get('slope'))} e/eV"
            )
    else:
        lines.append("  Fit diagnostics: NOT_ASSESSED")
    lines.append("  chi0_IJ / chi_IJ uses the derivative at alpha=0 of the declared fitted model.")

    lines.extend(_section_header("[09] MATRICES"))
    lines.extend(_matrix_lines("  CHI0 RAW (e/eV)", primary.get("chi0_raw"), names))
    lines.extend(_matrix_lines("  CHI RAW (e/eV)", primary.get("chi_raw"), names))

    lines.extend(_section_header("[10] INVERSION"))
    for key, label in (("chi0_diagnostics", "CHI0"), ("chi_diagnostics", "CHI")):
        diagnostic = _map(primary.get(key))
        shape = diagnostic.get("shape")
        size = shape[0] if isinstance(shape, list) and shape else None
        lines.append(
            f"  {label}: rank={_value(diagnostic.get('rank'))}/{_value(size)}; "
            f"condition={_value(diagnostic.get('condition_number'))}; "
            f"status={_value(diagnostic.get('matrix_status'))}"
        )
    estimator_policy = _map(analysis.get("estimator_policy"))
    lines.append(f"  Matrix policy: {_value(estimator_policy.get('matrix_for_inversion'))}")
    inverse_chi0 = primary.get("chi0_inverse_eV")
    inverse_chi = primary.get("chi_inverse_eV")
    for key, value in sorted(u_by_site.items(), key=lambda item: str(item[0])):
        index = int(key) if str(key).isdigit() else -1
        chi0_ii = (
            inverse_chi0[index][index]
            if isinstance(inverse_chi0, list)
            and 0 <= index < len(inverse_chi0)
            and isinstance(inverse_chi0[index], list)
            and index < len(inverse_chi0[index])
            else None
        )
        chi_ii = (
            inverse_chi[index][index]
            if isinstance(inverse_chi, list)
            and 0 <= index < len(inverse_chi)
            and isinstance(inverse_chi[index], list)
            and index < len(inverse_chi[index])
            else None
        )
        lines.append(f"  {names.get(index, str(key))}:")
        lines.append(f"    [inverse(CHI0)]_ii = {_fixed_decimal(chi0_ii)} eV")
        lines.append(f"    [inverse(CHI)]_ii = {_fixed_decimal(chi_ii)} eV")
        lines.append(
            f"    U_i = {_fixed_decimal(chi0_ii)} - {_fixed_decimal(chi_ii)} = {_fixed_decimal(value)} eV"
        )

    lines.extend(_section_header("[11] SYMMETRY"))
    shadow = _map(dataset.get("translation_shadow"))
    outcomes = shadow.get("outcomes")
    if isinstance(outcomes, list) and outcomes:
        lines.append(f"  Calculated/reconstructed evidence: {len(outcomes)} shadow outcomes.")
        for outcome in outcomes:
            if isinstance(outcome, Mapping):
                lines.append(
                    f"  {outcome.get('representative')} -> {outcome.get('shadow')}: "
                    f"{_value(outcome.get('status'))}; operation={_value(outcome.get('operation_id'))}"
                )
        maps = shadow.get("reconstruction_maps")
        for item in maps if isinstance(maps, list) else []:
            if isinstance(item, Mapping):
                lines.append(
                    f"  Reconstruct {item.get('destination')} from {item.get('representative')} "
                    f"using {item.get('operation_id')}"
                )
    else:
        lines.append("  Calculated versus reconstructed columns: NOT_ASSESSED")
    lines.append(f"  Complete state gate: {_value(shadow.get('complete_state_gate'))}")

    lines.extend(_section_header("[12] DIAGNOSTICS"))
    projector_diagnostics = _map(analysis.get("projector_diagnostics"))
    projector_sites = projector_diagnostics.get("sites")
    if isinstance(projector_sites, list) and projector_sites:
        lines.append("  Occupation/formal/free-atom and U*abs(CHI0): see per-site values below.")
        for item in projector_sites:
            if isinstance(item, Mapping):
                lines.append(
                    f"  {item.get('site_id')}: n_ref={_value(item.get('reference_occupation_e'))} e; "
                    f"formal_d={_value(item.get('formal_d_electrons'))} e; "
                    f"free_atom_d={_value(item.get('free_atom_d_electrons'))} e; "
                    f"U*abs(CHI0_ii)={_value(item.get('u_times_abs_chi0'))}; "
                    f"status={_value(item.get('regime_indicator_status'))}"
                )
        if total_derived:
            lines.append("  Reference total d-shell occupation (derived from printed per-spin values):")
            for item in projector_sites:
                if isinstance(item, Mapping):
                    lines.append(f"    {item.get('site_id')}: {_value(item.get('reference_occupation_e'))} e")
    else:
        lines.append("  Occupation/formal/free-atom and U*abs(CHI0): NOT_ASSESSED")

    lines.extend(_section_header("[13] FILE MAP"))
    file_map = _map(source.get("file_map"))
    for label, value in sorted(file_map.items()):
        if isinstance(value, list):
            lines.append(f"  {label}:")
            lines.extend(f"    {_value(item)}" for item in value)
        else:
            lines.append(f"  {label}: {_value(value)}")
    if not file_map:
        lines.append("  Campaign files: NOT_ASSESSED")

    geometry_preflight = _map(source.get("geometry_preflight"))
    lines.extend(_section_header("[14] REFERENCE GEOMETRY PREFLIGHT"))
    lines.append(f"  Status: {_value(geometry_preflight.get('state'))}; role: RECORD_ONLY")
    lines.append(
        f"  Reference XC: {_value(geometry_preflight.get('xc_functional'))} / "
        f"{_value(geometry_preflight.get('xc_authors'))}"
    )
    lines.append(f"  Reference output: {_value(geometry_preflight.get('reference_output_path'))}")
    lines.append(
        f"  Output SHA-256 (traceability only): {_value(geometry_preflight.get('reference_output_sha256'))}"
    )
    lines.append(
        f"  Max force: {_value(geometry_preflight.get('maximum_force_ev_ang'))} eV/Ang; "
        f"Res: {_value(geometry_preflight.get('residual_ev_ang'))} eV/Ang"
    )
    lines.append(
        f"  Max constrained: {_value(geometry_preflight.get('maximum_constrained_force_ev_ang'))} "
        f"eV/Ang; constraints detected: {_value(geometry_preflight.get('constraints_detected'))}"
    )
    stress = geometry_preflight.get("stress_voigt_kbar")
    if isinstance(stress, list) and len(stress) == 6:
        lines.append("  Stress Voigt x,y,z,yz,xz,xy (kbar):")
        lines.append("    " + ", ".join(_value(item) for item in stress))
    else:
        lines.append("  Stress Voigt x,y,z,yz,xz,xy (kbar): NOT_ASSESSED")
    lines.append(
        f"  Mean pressure: {_value(geometry_preflight.get('mean_pressure_kbar'))} kbar; "
        f"max shear: {_value(geometry_preflight.get('maximum_shear_kbar'))} kbar"
    )
    policy = _map(geometry_preflight.get("policy"))
    lines.append(
        "  Advisory limits: force "
        f"{_value(policy.get('max_force_ev_ang'))} eV/Ang; abs pressure "
        f"{_value(policy.get('max_abs_mean_pressure_kbar'))} kbar; shear "
        f"{_value(policy.get('max_shear_kbar'))} kbar; source "
        f"{_value(policy.get('declared_by'))}"
    )
    hubbard_context = geometry_preflight.get("hubbard_context")
    if isinstance(hubbard_context, list) and hubbard_context:
        for item in hubbard_context:
            if isinstance(item, Mapping):
                lines.append(
                    f"  U context {item.get('label')}: U_ref={_value(item.get('u_ref_ev'))} eV; "
                    f"J_ref={_value(item.get('j_ref_ev'))} eV; "
                    f"PotentialShift={_value(item.get('potential_shift'))}"
                )
    else:
        lines.append("  U context: NOT_ASSESSED")
    source_lines = _map(geometry_preflight.get("source_lines"))
    if source_lines:
        lines.append(
            "  Source lines: " + ", ".join(f"{key}={value}" for key, value in sorted(source_lines.items()))
        )
    lines.append("U computed for the geometry as supplied; no relaxation performed by HubbardFlow.")
    lines.append("  A geometry relaxed with another functional (e.g. PBE+U) may appear unrelaxed.")
    lines.append("  Advisory limits account for MeshCutoff, egg-box effects, and finite basis.")
    lines.append("  No Pulay-stress attribution is made by this diagnostic.")
    additional_states = geometry_preflight.get("additional_states")
    if isinstance(additional_states, list) and additional_states:
        lines.append("  Additional status: " + ", ".join(_value(item) for item in additional_states))

    lines.extend(_quality_check_lines(source, state_gate))
    lines.extend(_additional_report_sections(source, context, analysis, geometry, system, basis, k_grid))
    return "\n".join(_wrap_lines(lines)) + "\n"
