"""Minimal sequential production-campaign controller and matrix-analysis stage."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List

from production_benchmarks.campaign_state import CampaignState
from production_benchmarks.lr_arithmetic import (
    build_chi_matrix_3point, build_chi_matrix_5point, compute_U_matrix,
)
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
    required = {'material', 'candidate_id', 'mode', 'perturbed_site', 'alpha',
                'parent_dm_sha256', 'selected_occurrence_index', 'occupation_vector'}
    missing = required - set(record)
    if missing:
        raise ValueError(f'Observation missing required fields: {sorted(missing)}')
    path = Path(campaign_dir) / 'observations' / record['material'].lower() / f"{record['candidate_id']}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8', newline='\n') as fh:
        fh.write(json.dumps(record, sort_keys=True) + '\n')
    return path


def load_observations(campaign_dir: str, material: str, candidate_id: str) -> List[Dict[str, Any]]:
    path = Path(campaign_dir) / 'observations' / material.lower() / f'{candidate_id}.jsonl'
    if not path.exists():
        raise FileNotFoundError(f'No persisted observations for {material}/{candidate_id}')
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line]


def matrix_analysis(campaign_dir: str, material: str, candidate_id: str,
                    n_sites: int, mode_5point: bool = False) -> Path:
    """Perform MATRIX_ANALYSIS only; it creates no SIESTA RunSpecs."""
    records = load_observations(campaign_dir, material, candidate_id)
    obs = {(int(r['perturbed_site']), float(r['alpha']), r['mode'].upper()): r['occupation_vector']
           for r in records}
    positive = sorted({abs(float(r['alpha'])) for r in records if abs(float(r['alpha'])) > 1e-15})
    if not positive:
        raise ValueError('No non-zero perturbations available for matrix analysis')
    delta = positive[0]
    if mode_5point:
        bare = build_chi_matrix_5point(obs, n_sites, delta, 'BARE')
        screened = build_chi_matrix_5point(obs, n_sites, delta, 'SCREENED')
        chi0, chi = bare['matrix'], screened['matrix']
        linearity = {'bare': {k: v for k, v in bare.items() if k != 'matrix'},
                     'screened': {k: v for k, v in screened.items() if k != 'matrix'}}
    else:
        chi0 = build_chi_matrix_3point(obs, n_sites, delta, 'BARE')
        chi = build_chi_matrix_3point(obs, n_sites, delta, 'SCREENED')
        linearity = {}
    u = compute_U_matrix(chi0, chi)
    result = {
        'material': material, 'candidate_id': candidate_id, 'n_sites': n_sites,
        'chi0': chi0.tolist(), 'chi': chi.tolist(), 'inv_chi0': u['inv_chi0'].tolist(),
        'inv_chi': u['inv_chi'].tolist(), 'U': u['U'].tolist(),
        'rank': {'chi0': u['chi0_rank'], 'chi': u['chi_rank']},
        'singular_values': {'chi0': u['chi0_svd'], 'chi': u['chi_svd']},
        'condition_numbers': {'chi0': u['chi0_cond'], 'chi': u['chi_cond']},
        'inversion_residuals': {'chi0_left': u['chi0_left_residual'], 'chi0_right': u['chi0_right_residual'],
                                'chi_left': u['chi_left_residual'], 'chi_right': u['chi_right_residual']},
        'linearity_diagnostics': linearity,
        'onsite_diagonal_values': [u['U'][i, i] for i in range(n_sites)],
        'offdiagonal_kernel_values': [[u['U'][i, j] for j in range(n_sites) if j != i] for i in range(n_sites)],
    }
    path = Path(campaign_dir) / 'results' / material.lower() / f'{candidate_id}.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding='utf-8')
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
