import os
import json

base_dir = r"c:\Users\Jairo\Downloads\SIESTAFLOW_HUBBARD_RESPONSE_BACKBONE_V0_1_0\examples"
synth_dir = os.path.join(base_dir, "synthetic_campaign")

os.makedirs(synth_dir, exist_ok=True)
os.makedirs(os.path.join(synth_dir, "identity"), exist_ok=True)
os.makedirs(os.path.join(synth_dir, "response"), exist_ok=True)
os.makedirs(os.path.join(synth_dir, "results"), exist_ok=True)
os.makedirs(os.path.join(synth_dir, "workflow"), exist_ok=True)

def write_json(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)

def write_md(path, content):
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)

# 1. README.md
write_md(os.path.join(base_dir, "README.md"), """# SIESTAFLOW Hubbard Response Backbone v0.1.0 - Examples

This directory contains examples of the JSON schema instantiations for the SIESTAFLOW Hubbard Response Backbone.

## Synthetic Campaign (SYNTH_CAMPAIGN_001)

This is a synthetic 2-site, spin-resolved campaign designed for backbone validation. It does not correspond to a real material.
- P = 2 (Channels)
- O = 4 (Observables)
- N = 2 (Subspaces)
- K_p = 5 (Alpha points per channel)
- No real material, uses fictitious species `X_SYNTH`.
""")

# 2. campaign_contract.json
write_json(os.path.join(synth_dir, "campaign_contract.json"), {
  "campaign_id": "SYNTH_CAMPAIGN_001",
  "version": "0.1.0",
  "description": "Synthetic 2-site spin-resolved campaign for backbone validation",
  "required_modes": ["BARE", "SCREENED"],
  "geometry_ref": "geometry.json",
  "cardinals_ref": "cardinals.json",
  "aggregation_transform_ref": "aggregation_transform_A.json",
  "channel_subspace_bijection_ref": "channel_subspace_bijection.json",
  "observable_registry_ref": "observable_registry.json",
  "perturbation_spec_ref": "perturbation_spec.json",
  "numeric_params_ref": "numeric_params.json",
  "hpc_profile_ref": "hpc_profile.json",
  "methodology_lock_ref": "methodology_lock.json",
  "reference_state_fingerprint_ref": "reference_state_fingerprint.json",
  "alpha_grid_lock_ref": "alpha_grid_lock.json"
})

# 3. geometry.json
write_json(os.path.join(synth_dir, "geometry.json"), {
  "campaign_id": "SYNTH_CAMPAIGN_001",
  "lattice_vectors": {
    "units": "angstrom",
    "values": [[5.0, 0, 0], [0, 5.0, 0], [0, 0, 5.0]]
  },
  "periodicity": [True, True, True],
  "coordinate_representation": "fractional",
  "canonical_atom_order": "input_order",
  "sites": [
    {"site_id": "SITE_000", "species": "X_SYNTH", "coordinates": [0.0, 0.0, 0.0], "hubbard_subspace_id": "S0"},
    {"site_id": "SITE_001", "species": "X_SYNTH", "coordinates": [0.5, 0.5, 0.5], "hubbard_subspace_id": "S1"}
  ],
  "geometry_hash": "PLACEHOLDER_GEOM_HASH",
  "fixed_geometry_policy": "frozen",
  "materialized_fdf_ref": None
})

# 4. cardinals.json
write_json(os.path.join(synth_dir, "cardinals.json"), {
  "campaign_id": "SYNTH_CAMPAIGN_001",
  "P": 2,
  "O": 4,
  "N": 2,
  "constraint_p_equals_n_v0_1_0": True,
  "A_shape": [2, 4],
  "A_ref": "aggregation_transform_A.json",
  "A_version": "0.1.0"
})

# 5. aggregation_transform_A.json
write_json(os.path.join(synth_dir, "aggregation_transform_A.json"), {
  "campaign_id": "SYNTH_CAMPAIGN_001",
  "matrix_family": "AGGREGATION",
  "matrix_stage": "A_TRANSFORM",
  "response_mode": "NOT_APPLICABLE",
  "shape": [2, 4],
  "values": [[1, 1, 0, 0], [0, 0, 1, 1]]
})

# 6. channel_subspace_bijection.json
write_json(os.path.join(synth_dir, "channel_subspace_bijection.json"), {
  "campaign_id": "SYNTH_CAMPAIGN_001",
  "mapping": [
    {"perturbation_channel_id": "P0", "subspace_id": "S0"},
    {"perturbation_channel_id": "P1", "subspace_id": "S1"}
  ],
  "constraint_bijective": True
})

# 7. observable_registry.json
write_json(os.path.join(synth_dir, "observable_registry.json"), {
  "campaign_id": "SYNTH_CAMPAIGN_001",
  "observables": [
    {"observable_id": "S0_UP", "subspace_id": "S0", "site_id": "SITE_000", "quantity": "HUBBARD_OCCUPATION", "spin_channel": "UP", "orbital_resolution": "TRACE_OVER_MANIFOLD", "units": "dimensionless"},
    {"observable_id": "S0_DOWN", "subspace_id": "S0", "site_id": "SITE_000", "quantity": "HUBBARD_OCCUPATION", "spin_channel": "DOWN", "orbital_resolution": "TRACE_OVER_MANIFOLD", "units": "dimensionless"},
    {"observable_id": "S1_UP", "subspace_id": "S1", "site_id": "SITE_001", "quantity": "HUBBARD_OCCUPATION", "spin_channel": "UP", "orbital_resolution": "TRACE_OVER_MANIFOLD", "units": "dimensionless"},
    {"observable_id": "S1_DOWN", "subspace_id": "S1", "site_id": "SITE_001", "quantity": "HUBBARD_OCCUPATION", "spin_channel": "DOWN", "orbital_resolution": "TRACE_OVER_MANIFOLD", "units": "dimensionless"}
  ]
})

# 8. hubbard_subspaces.json
write_json(os.path.join(synth_dir, "hubbard_subspaces.json"), {
  "campaign_id": "SYNTH_CAMPAIGN_001",
  "subspaces": [
    {"subspace_id": "S0", "site_id": "SITE_000", "orbital_manifold": "d", "dimension": 5},
    {"subspace_id": "S1", "site_id": "SITE_001", "orbital_manifold": "d", "dimension": 5}
  ]
})

# 9. perturbation_spec.json
write_json(os.path.join(synth_dir, "perturbation_spec.json"), {
  "campaign_id": "SYNTH_CAMPAIGN_001",
  "required_modes": ["BARE", "SCREENED"],
  "channels": [
    {"channel_id": "P0", "subspace_id": "S0", "type": "POTENTIAL_SHIFT"},
    {"channel_id": "P1", "subspace_id": "S1", "type": "POTENTIAL_SHIFT"}
  ]
})

# 10. numeric_params.json
write_json(os.path.join(synth_dir, "numeric_params.json"), {
  "campaign_id": "SYNTH_CAMPAIGN_001",
  "zero_alpha_tolerance": 1e-6,
  "charge_tolerance": 1e-4,
  "condition_number_threshold": 1000.0,
  "inversion_tolerance": 1e-12,
  "antisymmetry_threshold": 0.001,
  "residual_norm_threshold": 1e-10
})

# 11. hpc_profile.json
write_json(os.path.join(synth_dir, "hpc_profile.json"), {
  "campaign_id": "SYNTH_CAMPAIGN_001",
  "scheduler": "local",
  "n_tasks": 1,
  "memory_gb": 4,
  "walltime_s": 3600
})

# 12. methodology_lock.json
write_json(os.path.join(synth_dir, "methodology_lock.json"), {
  "methodology_lock_id": "MLOCK_001",
  "campaign_id": "SYNTH_CAMPAIGN_001",
  "locked_by": "SYNTHETIC_SETUP",
  "locked_at": "2025-01-01T00:00:00Z",
  "response_matrix_formulation": "LOCALIZED_SUBSPACES_ONLY",
  "background_degree_of_freedom": "EXCLUDED",
  "inversion_profile": "FULL_RANK_DIRECT",
  "nullspace_treatment": "UNSUPPORTED",
  "convention_profile_id": "SIESTA_LR_PLUS_ALPHA_DN_DALPHA_V1",
  "perturbation_operator_convention": "H=H0+alpha*P",
  "response_derivative_convention": "dn/dalpha",
  "u_formula_convention": "inverse_chi0_minus_inverse_chi",
  "geometry_policy": "FIXED_DURING_LINEAR_RESPONSE",
  "dft_xc": "PBE",
  "spin_polarized": True,
  "relativistic": False,
  "matrix_selection_policy": "symmetrized",
  "antisymmetry_metric_id": "RELATIVE_FROBENIUS_V1",
  "antisymmetry_metric_version": "1.0.0",
  "antisymmetry_threshold": 0.001,
  "projector_definition_refs": ["PROJ_S0", "PROJ_S1"],
  "regression_config": {
    "fit_algorithm": "OLS",
    "fit_algorithm_version": "0.1.0",
    "loo_enabled": True
  }
})

# 13, 14. alpha_grid_plan.json and alpha_grid_lock.json
alpha_grid_data = {
  "campaign_id": "SYNTH_CAMPAIGN_001",
  "channels": [
    {"channel_id": "P0", "points": [-0.10, -0.05, 0.0, 0.05, 0.10], "units": "eV", "status": "LOCKED"},
    {"channel_id": "P1", "points": [-0.10, -0.05, 0.0, 0.05, 0.10], "units": "eV", "status": "LOCKED"}
  ]
}
write_json(os.path.join(synth_dir, "alpha_grid_plan.json"), alpha_grid_data)
write_json(os.path.join(synth_dir, "alpha_grid_lock.json"), alpha_grid_data)

# 15. reference_state_fingerprint.json
write_json(os.path.join(synth_dir, "reference_state_fingerprint.json"), {
  "campaign_id": "SYNTH_CAMPAIGN_001",
  "observables": {
    "S0_UP": 2.50,
    "S0_DOWN": 2.50,
    "S1_UP": 2.50,
    "S1_DOWN": 2.50
  },
  "total_charge": 10.0,
  "total_magnetic_moment": 0.0
})

# 16-19. Identity folder
write_json(os.path.join(synth_dir, "identity", "pseudopotential_identity.json"), {
  "campaign_id": "SYNTH_CAMPAIGN_001",
  "species": "X_SYNTH",
  "filename": "synth.psml",
  "format": "psml"
})
write_json(os.path.join(synth_dir, "identity", "siesta_binary_identity.json"), {
  "campaign_id": "SYNTH_CAMPAIGN_001",
  "path": "/usr/local/bin/siesta_synth",
  "version_string": "synthetic_v0.1.0"
})
write_json(os.path.join(synth_dir, "identity", "reference_dm_lock.json"), {
  "campaign_id": "SYNTH_CAMPAIGN_001",
  "reference_dm_task_id": "TASK_REF_SCF",
  "locked": True,
  "chaining_prohibited": True
})
write_json(os.path.join(synth_dir, "identity", "task_identity.json"), {
  "campaign_id": "SYNTH_CAMPAIGN_001",
  "task_id": "TASK_PERT_BARE_P0_M0_10",
  "task_type": "PERTURBATIVE",
  "response_mode": "BARE",
  "channel_id": "P0",
  "alpha_value": -0.10,
  "reference_dm_lock_ref": "reference_dm_lock.json",
  "siesta_binary_identity_ref": "siesta_binary_identity.json",
  "methodology_lock_ref": "methodology_lock.json"
})

# Responses computation
alphas = [-0.10, -0.05, 0.0, 0.05, 0.10]
R_bare = [[-0.50, -0.05], [-0.50, -0.05], [-0.05, -0.50], [-0.05, -0.50]]
R_screened = [[-0.40, -0.04], [-0.40, -0.04], [-0.04, -0.40], [-0.04, -0.40]]
obs_names = ["S0_UP", "S0_DOWN", "S1_UP", "S1_DOWN"]
channels = ["P0", "P1"]

def generate_records(mode, R_matrix):
    records = []
    for c_idx, channel in enumerate(channels):
        for alpha in alphas:
            for o_idx, obs in enumerate(obs_names):
                val = 2.50 + R_matrix[o_idx][c_idx] * alpha
                records.append({
                    "response_mode": mode,
                    "channel_id": channel,
                    "alpha": alpha,
                    "observable_id": obs,
                    "value": round(val, 5)
                })
    return records

write_json(os.path.join(synth_dir, "response", "occupation_records_bare.json"), {"records": generate_records("BARE", R_bare)})
write_json(os.path.join(synth_dir, "response", "occupation_records_screened.json"), {"records": generate_records("SCREENED", R_screened)})

def generate_regression(mode, R_matrix):
    records = []
    for c_idx, channel in enumerate(channels):
        for o_idx, obs in enumerate(obs_names):
            slope = R_matrix[o_idx][c_idx]
            records.append({
                "response_mode": mode,
                "channel_id": channel,
                "observable_id": obs,
                "slope": slope,
                "intercept": 2.50,
                "r_squared": 1.0,
                "loo_slopes": [slope]*5
            })
    return records

write_json(os.path.join(synth_dir, "response", "regression_bare.json"), {"records": generate_regression("BARE", R_bare)})
write_json(os.path.join(synth_dir, "response", "regression_screened.json"), {"records": generate_regression("SCREENED", R_screened)})

# Matrices
write_json(os.path.join(synth_dir, "response", "raw_matrix_chi0.json"), {
  "matrix_family": "SUSCEPTIBILITY", "matrix_stage": "RAW", "response_mode": "BARE", "units": "1/eV", "shape": [2, 2], "values": [[-1.0, -0.1], [-0.1, -1.0]]
})
write_json(os.path.join(synth_dir, "response", "raw_matrix_chi.json"), {
  "matrix_family": "SUSCEPTIBILITY", "matrix_stage": "RAW", "response_mode": "SCREENED", "units": "1/eV", "shape": [2, 2], "values": [[-0.8, -0.08], [-0.08, -0.8]]
})

for stage in ["symmetrized_matrix", "selected_matrix"]:
    write_json(os.path.join(synth_dir, "response", f"{stage}_chi0.json"), {
      "matrix_family": "SUSCEPTIBILITY", "matrix_stage": stage.split("_")[0].upper(), "response_mode": "BARE", "units": "1/eV", "shape": [2, 2], "values": [[-1.0, -0.1], [-0.1, -1.0]]
    })
    write_json(os.path.join(synth_dir, "response", f"{stage}_chi.json"), {
      "matrix_family": "SUSCEPTIBILITY", "matrix_stage": stage.split("_")[0].upper(), "response_mode": "SCREENED", "units": "1/eV", "shape": [2, 2], "values": [[-0.8, -0.08], [-0.08, -0.8]]
    })

write_json(os.path.join(synth_dir, "response", "antisymmetry_chi0.json"), {
  "matrix_family": "DIAGNOSTIC", "response_mode": "BARE", "values": [[0.0, 0.0], [0.0, 0.0]], "frobenius_norm": 0.0, "relative_frobenius": 0.0
})
write_json(os.path.join(synth_dir, "response", "antisymmetry_chi.json"), {
  "matrix_family": "DIAGNOSTIC", "response_mode": "SCREENED", "values": [[0.0, 0.0], [0.0, 0.0]], "frobenius_norm": 0.0, "relative_frobenius": 0.0
})

write_json(os.path.join(synth_dir, "response", "selection_policy.json"), {
  "policy": "symmetrized", "methodology_lock_ref": "MLOCK_001", "antisymmetry_gate_passed": True
})

write_json(os.path.join(synth_dir, "response", "condition_number_chi0.json"), {"condition_number": 1.222222222222222})
write_json(os.path.join(synth_dir, "response", "condition_number_chi.json"), {"condition_number": 1.222222222222222})

write_json(os.path.join(synth_dir, "response", "singular_values_chi0.json"), {"values": [1.1, 0.9]})
write_json(os.path.join(synth_dir, "response", "singular_values_chi.json"), {"values": [0.88, 0.72]})

write_json(os.path.join(synth_dir, "response", "numerical_rank_chi0.json"), {"rank": 2, "tolerance": 1e-12, "full_rank": True})
write_json(os.path.join(synth_dir, "response", "numerical_rank_chi.json"), {"rank": 2, "tolerance": 1e-12, "full_rank": True})

write_json(os.path.join(synth_dir, "response", "matrix_inverse_chi0.json"), {
  "matrix_family": "INVERSE_SUSCEPTIBILITY", "response_mode": "BARE", "units": "eV", "shape": [2, 2],
  "values": [[-1.01010101010101, 0.10101010101010], [0.10101010101010, -1.01010101010101]]
})
write_json(os.path.join(synth_dir, "response", "matrix_inverse_chi.json"), {
  "matrix_family": "INVERSE_SUSCEPTIBILITY", "response_mode": "SCREENED", "units": "eV", "shape": [2, 2],
  "values": [[-1.26262626262626, 0.12626262626263], [0.12626262626263, -1.26262626262626]]
})

write_json(os.path.join(synth_dir, "response", "residuals_chi0.json"), {"left_residual_norm": 0.0, "right_residual_norm": 0.0})
write_json(os.path.join(synth_dir, "response", "residuals_chi.json"), {"left_residual_norm": 0.0, "right_residual_norm": 0.0})

# Results
write_json(os.path.join(synth_dir, "results", "u_matrix.json"), {
  "matrix_family": "HUBBARD", "matrix_stage": "U_MATRIX", "response_mode": "NOT_APPLICABLE", "units": "eV", "shape": [2, 2],
  "values": [[0.25252525252525, -0.02525252525253], [-0.02525252525253, 0.25252525252525]]
})
write_json(os.path.join(synth_dir, "results", "candidate_evaluation.json"), {
  "diagonal_U_ev": [0.25252525252525, 0.25252525252525], "recommended_single_U_ev": None
})
write_json(os.path.join(synth_dir, "results", "human_decision.json"), {
  "decision_type": "DEFER", "rationale": "Awaiting peer review and additional projector candidates before accepting U values. Backbone validation only."
})

# Workflow
write_json(os.path.join(synth_dir, "workflow", "execution_observation_map.json"), {
  "campaign_id": "SYNTH_CAMPAIGN_001", "observations": ["BARE_OBSERVATION", "SCREENED_OBSERVATION"]
})
write_json(os.path.join(synth_dir, "workflow", "semantic_validation.json"), {
  "campaign_id": "SYNTH_CAMPAIGN_001", "status": "PASSED", "checks": []
})

# Gates
write_json(os.path.join(synth_dir, "gate_result.json"), {
  "gates": [
    {"name": "ZERO_ALPHA_REFERENCE_CONSISTENCY", "status": "PASSED"},
    {"name": "MATRIX_DIMENSION", "status": "PASSED"},
    {"name": "CONDITION_NUMBER", "status": "PASSED"},
    {"name": "ANTISYMMETRY", "status": "PASSED"},
    {"name": "RESIDUAL", "status": "PASSED"}
  ]
})
write_json(os.path.join(synth_dir, "lock_example.json"), {"campaign_id": "SYNTH_CAMPAIGN_001", "locked": True})
write_json(os.path.join(synth_dir, "evidence_package.json"), {"campaign_id": "SYNTH_CAMPAIGN_001", "package": "complete"})

print("Done generating JSON examples.")
