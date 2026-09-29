"""Minimal sequential production-campaign controller and matrix-analysis stage."""
from __future__ import annotations

import json
import hashlib
import math
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List

from production_benchmarks.campaign_state import CampaignState
from production_benchmarks.lr_arithmetic import response_observations_from_records
from siestaflow_hubbard.domain.lr_analysis_v2 import LRAnalysisPolicy, analyze_verified_lr, write_lr_analysis_v2
from siestaflow_hubbard.reporting.lr_u_report import write_lr_u_report
from siestaflow_hubbard.siesta_backend.event_parser import parse_hubbard_population_events
from siestaflow_hubbard.siesta_backend.observation_selector import Siesta542BarePolicyV1
from siestaflow_hubbard.siesta_backend.parser_models import ObservationContext


def select_semantic_observation(output_text: str, mode: str, context: ObservationContext) -> Dict[str, Any]:
    """Select a scientific BARE/SCREENED event above the raw event parser."""
    events = parse_hubbard_population_events(output_text)
    mode = mode.upper()
    if mode == 'BARE':
        selection = Siesta542BarePolicyV1.get_bare_observation(events, context)
    elif mode == 'SCREENED':
        selection = Siesta542BarePolicyV1.get_screened_observation(events, context)
    elif mode == 'REFERENCE':
        selection = Siesta542BarePolicyV1.get_reference_observation(events, context)
    else:
        raise ValueError(f'Unsupported observation mode {mode!r}')
    event = selection.event
    return {
        'mode': mode,
        'selection_role': selection.role.value,
        'selection_evidence': selection.evidence,
        'selected_occurrence_index': event.occurrence_index,
        'selected_scf_iteration': event.scf_iteration,
        'atom_indices': [atom.atom_index for atom in event.atoms],
        'occupation_vector': [atom.trace_total for atom in event.atoms],
    }


def persist_observation(campaign_dir: str, record: Dict[str, Any]) -> Path:
    common = {
        'material', 'candidate_id', 'mode', 'alpha', 'identity_key',
        'stdout_sha256', 'fdf_sha256', 'return_code', 'semantic_validation',
        'selected_occurrence_index', 'selected_scf_iteration', 'occupation_vector', 'atom_indices',
        'selection_role', 'selection_evidence',
    }
    mode = str(record.get('mode', '')).upper()
    required = common | ({'canonical_dm_sha256'} if mode == 'REFERENCE' else {
        'perturbed_site', 'parent_dm_sha256', 'selected_scf_iteration',
    })
    missing = required - set(record)
    if missing:
        raise ValueError(f'Observation missing required fields: {sorted(missing)}')
    if mode not in {'REFERENCE', 'BARE', 'SCREENED'}:
        raise ValueError(f'Unsupported observation mode {mode!r}')
    if record.get('return_code') != 0 or record.get('semantic_validation') != 'PASSED':
        raise ValueError('Only successful semantically validated observations may be persisted')
    if not record.get('identity_key') or not record.get('selection_evidence'):
        raise ValueError('Observation lacks a run identity or semantic selection evidence')
    record['mode'] = mode
    digest = observation_receipt_digest(record)
    recorded_digest = record.get('observation_payload_sha256')
    if recorded_digest is not None and recorded_digest != digest:
        raise ValueError('Observation payload digest does not match its selected event and stdout receipt')
    record['observation_payload_sha256'] = digest
    path = Path(campaign_dir) / 'observations' / record['material'].lower() / f"{record['candidate_id']}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    completed_receipt = CampaignState(campaign_dir).completed.get(record['identity_key'])
    completed_digest = (
        completed_receipt.get('observation_payload_sha256')
        if isinstance(completed_receipt, dict) else None
    )
    if isinstance(completed_receipt, dict) and not completed_digest:
        raise ValueError('Completed run receipt lacks an observation payload digest')
    rows: list[Dict[str, Any]] = []
    matching_indices: list[int] = []
    if path.exists():
        for line_number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
            if not line:
                continue
            try:
                existing = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f'Existing observations file has invalid JSON on line {line_number}') from exc
            if existing.get('identity_key') != record['identity_key']:
                rows.append(existing)
                continue
            matching_indices.append(len(rows))
            rows.append(existing)

    if completed_receipt is not None and completed_digest != digest:
        raise ValueError(f"Observation payload conflicts with completed receipt for identity_key {record['identity_key']!r}")
    if completed_receipt is not None and matching_indices:
        if len(matching_indices) != 1:
            raise ValueError(f"Completed identity {record['identity_key']!r} has duplicate observation rows")
        existing = rows[matching_indices[0]]
        try:
            existing_digest = observation_receipt_digest(existing)
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError('Completed observation row has an invalid semantic payload') from exc
        if (existing.get('observation_payload_sha256') != existing_digest
                or existing_digest != completed_digest):
            raise ValueError('Existing observation row does not match its completed receipt')
        return path
    if completed_receipt is None and matching_indices:
        if len(matching_indices) == 1:
            existing = rows[matching_indices[0]]
            try:
                existing_digest = observation_receipt_digest(existing)
            except (KeyError, TypeError, ValueError):
                existing_digest = None
            if existing.get('observation_payload_sha256') == existing_digest == digest:
                return path
        first_index = matching_indices[0]
        # A persisted row without a completion receipt is an interrupted-run
        # orphan. Replace it (and collapse any duplicates) with the result of
        # the validated retry, even when its payload changed.
        _archive_orphaned_observations(
            path, [rows[index] for index in matching_indices],
        )
        rows = [row for row in rows if row.get('identity_key') != record['identity_key']]
        rows.insert(min(first_index, len(rows)), record)
    else:
        rows.append(record)
    _atomic_replace_observation_log(path, rows)
    return path


def _atomic_replace_observation_log(path: Path, records: List[Dict[str, Any]]) -> None:
    """Atomically rewrite the small JSONL observation log after an upsert."""
    serialized = ''.join(
        json.dumps(record, sort_keys=True, allow_nan=False) + '\n'
        for record in records
    )
    fd, temporary_path = tempfile.mkstemp(
        prefix=f'.{path.name}.', suffix='.tmp', dir=str(path.parent),
    )
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as handle:
            handle.write(serialized)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
    except BaseException:
        try:
            os.unlink(temporary_path)
        except OSError:
            pass
        raise


def _archive_orphaned_observations(path: Path, orphaned: List[Dict[str, Any]]) -> None:
    """Retain each superseded pre-completion row once in an adjacent JSONL log."""
    archive_path = path.with_name(f'{path.stem}.orphaned.jsonl')
    archived: list[Dict[str, Any]] = []
    if archive_path.exists():
        for line_number, line in enumerate(archive_path.read_text(encoding='utf-8').splitlines(), 1):
            if not line:
                continue
            try:
                archived.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f'Orphan archive has invalid JSON on line {line_number}') from exc
    seen = {json.dumps(row, sort_keys=True, separators=(',', ':'), allow_nan=False) for row in archived}
    added = False
    for row in orphaned:
        encoded = json.dumps(row, sort_keys=True, separators=(',', ':'), allow_nan=False)
        if encoded not in seen:
            archived.append(row)
            seen.add(encoded)
            added = True
    if added:
        _atomic_replace_observation_log(archive_path, archived)


def observation_receipt_digest(record: Dict[str, Any]) -> str:
    """Bind the selected occupation event to the validated stdout receipt.

    The digest is copied into CampaignState before a run is marked complete;
    re-analysis recomputes it from JSONL so changing occupations, atom order,
    or the selected event while retaining stdout/FDF hashes is rejected.
    """
    mode = str(record.get('mode', '')).upper()
    if mode not in {'REFERENCE', 'BARE', 'SCREENED'}:
        raise ValueError(f'Unsupported observation mode {mode!r}')
    vector = record.get('occupation_vector')
    atom_indices = record.get('atom_indices')
    if not isinstance(vector, list) or not isinstance(atom_indices, list) or len(vector) != len(atom_indices):
        raise ValueError('Observation atom_indices and occupation_vector must be aligned lists')
    try:
        if any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in vector):
            raise ValueError('occupation values must be numeric scalars')
        if any(isinstance(value, bool) or not isinstance(value, int) for value in atom_indices):
            raise ValueError('atom indices must be integers')
        occupations = [float(value) for value in vector]
        indices = list(atom_indices)
        for hash_field in ('stdout_sha256', 'fdf_sha256'):
            digest_value = record[hash_field]
            if (not isinstance(digest_value, str) or len(digest_value) != 64
                    or any(character not in '0123456789abcdefABCDEF' for character in digest_value)):
                raise ValueError(f'{hash_field} must be a SHA256 hex digest')
        alpha = float(record['alpha'])
        selected_index = int(record['selected_occurrence_index'])
        selected_iteration = int(record['selected_scf_iteration'])
        return_code = int(record['return_code'])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        raise ValueError('Observation receipt fields are malformed') from exc
    if (not occupations or not all(math.isfinite(value) for value in occupations)
            or not math.isfinite(alpha) or selected_index < 0 or selected_iteration < 0
            or not indices or any(value < 1 for value in indices)
            or len(set(indices)) != len(indices)):
        raise ValueError('Observation receipt contains invalid event indices or occupations')
    payload: Dict[str, Any] = {
        'schema': 'siestaflow.semantic_observation_receipt.v1',
        'identity_key': str(record['identity_key']),
        'material': str(record['material']),
        'candidate_id': str(record['candidate_id']),
        'mode': mode,
        'alpha': alpha,
        'perturbed_site': int(record.get('perturbed_site', 0)),
        'stdout_sha256': str(record['stdout_sha256']),
        'fdf_sha256': str(record['fdf_sha256']),
        'return_code': return_code,
        'semantic_validation': str(record['semantic_validation']),
        'selected_occurrence_index': selected_index,
        'selected_scf_iteration': selected_iteration,
        'atom_indices': indices,
        'occupation_vector': occupations,
        'selection_role': str(record['selection_role']),
        'selection_evidence': str(record['selection_evidence']),
    }
    if mode == 'REFERENCE':
        payload['canonical_dm_sha256'] = str(record['canonical_dm_sha256'])
    else:
        payload['parent_dm_sha256'] = str(record['parent_dm_sha256'])
    try:
        encoded = json.dumps(payload, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')
    except (TypeError, ValueError) as exc:
        raise ValueError('Observation receipt cannot be serialized canonically') from exc
    return hashlib.sha256(encoded).hexdigest()


def load_observations(campaign_dir: str, material: str, candidate_id: str) -> List[Dict[str, Any]]:
    path = Path(campaign_dir) / 'observations' / material.lower() / f'{candidate_id}.jsonl'
    if not path.exists():
        raise FileNotFoundError(f'No persisted observations for {material}/{candidate_id}')
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line]


def _verified_candidate_records(
    campaign_dir: str, material: str, candidate_id: str, records: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Require each persisted row to match a completed Slurm semantic receipt."""
    state = CampaignState(campaign_dir)
    completed = state.completed
    if not completed:
        raise ValueError("No completed-run receipts are available for these observations")
    verified: list[Dict[str, Any]] = []
    for index, record in enumerate(records):
        if record.get("material", "").lower() != material.lower() or record.get("candidate_id") != candidate_id:
            raise ValueError(f"observation {index} belongs to a different material/candidate")
        identity = record.get("identity_key")
        receipt = completed.get(identity) if isinstance(identity, str) else None
        if not isinstance(receipt, dict):
            raise ValueError(f"observation {index} has no matching completed-run receipt")
        expected = {
            "identity_key": identity,
            "candidate_id": candidate_id,
            "response_mode": str(record.get("mode", "")).upper(),
            "alpha": float(record.get("alpha")),
            "perturbed_site": int(record.get("perturbed_site", 0)),
            "stdout_sha256": record.get("stdout_sha256"),
            "fdf_sha256": record.get("fdf_sha256"),
            "selected_occurrence_index": record.get("selected_occurrence_index"),
            "selection_role": record.get("selection_role"),
            "selection_evidence": record.get("selection_evidence"),
            "selected_scf_iteration": record.get("selected_scf_iteration"),
            "observation_payload_sha256": observation_receipt_digest(record),
        }
        if str(record.get("mode", "")).upper() == "REFERENCE":
            expected["canonical_dm_sha256"] = record.get("canonical_dm_sha256")
        else:
            expected["parent_dm_sha256"] = record.get("parent_dm_sha256")
        for field, value in expected.items():
            if receipt.get(field) != value:
                raise ValueError(f"observation {index} does not match its completed receipt field {field}")
        if record.get('observation_payload_sha256') != expected['observation_payload_sha256']:
            raise ValueError(f"observation {index} semantic payload digest does not match its selected event")
        if receipt.get("return_code") != 0 or receipt.get("semantic_validation") != "PASSED":
            raise ValueError(f"observation {index} has no successful semantic validation receipt")
        verified.append(record)
    return verified


def _legacy_result_fields(result: Dict[str, Any], material: str, candidate_id: str, n_sites: int) -> Dict[str, Any]:
    """Add historical keys as aliases of the canonical v2 analysis values."""
    primary = result.get("primary", {})
    u_matrix = primary.get("U_matrix_eV") if isinstance(primary, dict) else None
    condition0 = primary.get("chi0_diagnostics", {}) if isinstance(primary, dict) else {}
    condition = primary.get("chi_diagnostics", {}) if isinstance(primary, dict) else {}
    inverse = primary.get("inversion_diagnostics", {}) if isinstance(primary, dict) else {}
    inversion0 = inverse.get("chi0") if isinstance(inverse, dict) else None
    inversion = inverse.get("chi") if isinstance(inverse, dict) else None
    result.update({
        "material": material,
        "candidate_id": candidate_id,
        "n_sites": n_sites,
        "response_fit": {
            "method": result.get("selected_estimator", {}).get("method"),
            "polynomial_degree": result.get("selected_estimator", {}).get("degree"),
            "minimum_residual_dof": result.get("estimator_policy", {}).get("minimum_residual_dof"),
            "alpha_values_used": result.get("analysis_alpha_grid_eV"),
        },
        "chi0": primary.get("chi0_raw") if isinstance(primary, dict) else None,
        "chi": primary.get("chi_raw") if isinstance(primary, dict) else None,
        "inv_chi0": primary.get("chi0_inverse_eV") if isinstance(primary, dict) else None,
        "inv_chi": primary.get("chi_inverse_eV") if isinstance(primary, dict) else None,
        "U": u_matrix,
        "rank": {"chi0": condition0.get("rank"), "chi": condition.get("rank")},
        "singular_values": {
            "chi0": condition0.get("singular_values"), "chi": condition.get("singular_values"),
        },
        "condition_numbers": {
            "chi0": condition0.get("condition_number"), "chi": condition.get("condition_number"),
        },
        "inversion_residuals": {
            "chi0_left": None if inversion0 is None else inversion0.get("left_residual_frobenius"),
            "chi0_right": None if inversion0 is None else inversion0.get("right_residual_frobenius"),
            "chi_left": None if inversion is None else inversion.get("left_residual_frobenius"),
            "chi_right": None if inversion is None else inversion.get("right_residual_frobenius"),
        },
        "linearity_diagnostics": primary.get("fit_diagnostics") if isinstance(primary, dict) else None,
        "onsite_diagonal_values": None if u_matrix is None else [u_matrix[i][i] for i in range(n_sites)],
        "offdiagonal_kernel_values": None if u_matrix is None else [
            [u_matrix[i][j] for j in range(n_sites) if j != i] for i in range(n_sites)
        ],
    })
    return result


def matrix_analysis(campaign_dir: str, material: str, candidate_id: str,
                    n_sites: int, mode_5point: bool = False, *,
                    response_fit_method: str = 'linear',
                    polynomial_degree: int = 3,
                    minimum_residual_dof: int = 1) -> Path:
    """Analyze verified observations with the canonical v2 engine only."""
    if response_fit_method not in {'linear', 'polynomial'}:
        raise ValueError("response_fit_method must be 'linear' or 'polynomial'")
    if response_fit_method == 'polynomial' and not mode_5point:
        raise ValueError('polynomial response fitting requires mode_5point=True')
    records = _verified_candidate_records(
        campaign_dir, material, candidate_id,
        load_observations(campaign_dir, material, candidate_id),
    )
    observations = response_observations_from_records(records, n_sites=n_sites)
    alpha_grid = sorted({float(item.alpha) for item in observations})
    required_points = 5 if mode_5point else 3
    if len(alpha_grid) != required_points:
        raise ValueError(
            f"{'5-point' if mode_5point else '3-point'} analysis requires exactly "
            f"{required_points} unique alpha values including the shared zero; found {alpha_grid}"
        )
    analysis_policy = LRAnalysisPolicy(
        estimator=response_fit_method,
        polynomial_degree=polynomial_degree,
        minimum_residual_dof=minimum_residual_dof,
        matrix_for_inversion="raw",
    )
    result = analyze_verified_lr(
        observations,
        analysis_policy,
        campaign={
            "campaign_id": f"{material}:{candidate_id}",
            "material": material,
            "candidate_id": candidate_id,
            "backend": "slurm_or_historical_observation_store",
        },
        # The completion receipts prove the semantic parser accepted each
        # SCF output. Magnetic branch continuity is not inferred from charge
        # occupations and therefore remains unclaimed.
        scf_validated=True,
    )
    result = _legacy_result_fields(result, material, candidate_id, n_sites)
    path = Path(campaign_dir) / 'results' / material.lower() / f'{candidate_id}.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    write_lr_analysis_v2(path, result)
    candidate_result_dir = path.parent / candidate_id
    write_lr_analysis_v2(candidate_result_dir / 'lr_u_analysis.v2.json', result)
    write_lr_u_report(candidate_result_dir / 'LR_U_REPORT.md', result)
    return path


class SequentialCampaignController:
    """Stateful hand-off controller; acceptance is explicit and evidence-gated."""
    def __init__(self, campaign_dir: str):
        self.state = CampaignState(campaign_dir)
        self.campaign_dir = campaign_dir

    def plan_stage(self, material_config: Dict[str, Any], stage: str, **kwargs: Any):
        from production_benchmarks.slurm_runner import generate_convergence_stage_specs
        accepted = self.state.current_accepted_configuration.get(material_config['name'], {})
        return generate_convergence_stage_specs(material_config, stage, self.campaign_dir,
                                                current_accepted_configuration=accepted, **kwargs)

    def accept_candidate(self, material: str, stage: str, candidate_id: str,
                         candidate_configuration: Dict[str, Any]) -> None:
        result = Path(self.campaign_dir) / 'results' / material.lower() / f'{candidate_id}.json'
        if not result.is_file() or result.stat().st_size == 0:
            raise ValueError('Cannot accept candidate without MATRIX_ANALYSIS result data')
        current = dict(self.state.current_accepted_configuration.get(material, {}))
        current.update(candidate_configuration)
        self.state.current_accepted_configuration[material] = current
        self.state.set_dag_node(f'{material}:{stage}:ACCEPTED:{candidate_id}')
        self.state.save()
