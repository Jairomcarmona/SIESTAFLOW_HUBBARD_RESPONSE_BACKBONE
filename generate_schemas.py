import os
import json
from pathlib import Path

BASE_DIR = Path(r"C:\Users\Jairo\Downloads\SIESTAFLOW_HUBBARD_RESPONSE_BACKBONE_V0_1_0\schemas")

def write_schema(rel_path, schema_dict):
    p = BASE_DIR / rel_path
    p.parent.mkdir(parents=True, exist_ok=True)
    
    # Add common Draft 2020-12 header
    full_schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        **schema_dict
    }
    
    with open(p, "w", encoding="utf-8") as f:
        json.dump(full_schema, f, indent=2)

def generate_all():
    # --- CAMPAIGN ---
    write_schema("campaign/campaign_contract.schema.json", {
        "type": "object",
        "properties": {"campaign_id": {"type": "string"}, "description": {"type": "string"}},
        "required": ["campaign_id"]
    })
    write_schema("campaign/geometry.schema.json", {
        "type": "object",
        "properties": {"campaign_id": {"type": "string"}, "atoms": {"type": "array"}},
        "required": ["campaign_id"]
    })
    write_schema("campaign/hubbard_subspace.schema.json", {
        "type": "object",
        "properties": {"campaign_id": {"type": "string"}, "subspaces": {"type": "array"}},
        "required": ["campaign_id"]
    })
    write_schema("campaign/cardinals.schema.json", {
        "type": "object",
        "required": ["campaign_id", "P", "O", "N", "alpha_grids", "constraint_p_equals_n_v0_1_0"],
        "properties": {
            "campaign_id": {"type": "string"},
            "P": {"type": "integer"},
            "O": {"type": "integer"},
            "N": {"type": "integer"},
            "constraint_p_equals_n_v0_1_0": {"const": True},
            "alpha_grids": {
                "type": "object",
                "description": "Mapping from perturbation_channel_id to its alpha grid",
                "additionalProperties": {
                    "type": "object",
                    "properties": {
                        "alpha_values_ev": {"type": "array", "items": {"type": "number"}},
                        "K_p": {"type": "integer"},
                        "symmetric_pairs": {"type": "boolean"},
                        "k_negative": {"type": "integer"},
                        "k_zero": {"type": "integer"},
                        "k_positive": {"type": "integer"}
                    },
                    "required": ["alpha_values_ev", "K_p", "symmetric_pairs", "k_negative", "k_zero", "k_positive"]
                }
            }
        }
    })
    write_schema("campaign/aggregation_transform.schema.json", {
        "type": "object",
        "required": ["campaign_id", "matrix_family", "matrix_stage", "values", "row_subspace_ids", "column_observable_ids", "units", "version"],
        "properties": {
            "campaign_id": {"type": "string"},
            "matrix_family": {"const": "AGGREGATION"},
            "matrix_stage": {"const": "A_TRANSFORM"},
            "response_mode": {"const": "NOT_APPLICABLE"},
            "values": {
                "type": "array",
                "description": "NxO matrix as nested array",
                "items": {"type": "array", "items": {"type": "number"}}
            },
            "shape": {
                "type": "array",
                "items": {"type": "integer"},
                "minItems": 2,
                "maxItems": 2,
                "description": "Must be [N, O]"
            },
            "row_subspace_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "length N; one per aggregated subspace"
            },
            "column_observable_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "length O; one per observable"
            },
            "units": {"const": "dimensionless"},
            "version": {"type": "string"},
            "description": {"type": "string"}
        }
    })
    write_schema("campaign/channel_subspace_bijection.schema.json", {
        "type": "object",
        "required": ["campaign_id", "mapping", "constraint_bijective"],
        "properties": {
            "campaign_id": {"type": "string"},
            "mapping": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["perturbation_channel_id", "subspace_id"],
                    "properties": {
                        "perturbation_channel_id": {"type": "string"},
                        "subspace_id": {"type": "string"}
                    }
                }
            },
            "constraint_bijective": {
                "const": True,
                "description": "v0.1.0: bijective. Each channel maps to exactly one subspace and vice versa."
            }
        }
    })
    write_schema("campaign/perturbation_spec.schema.json", {
        "type": "object",
        "properties": {"campaign_id": {"type": "string"}},
        "required": ["campaign_id"]
    })
    write_schema("campaign/numeric_params.schema.json", {
        "type": "object",
        "properties": {
            "campaign_id": {"type": "string"},
            "zero_alpha_tolerance": {"type": "number"},
            "charge_tolerance": {"type": "number"},
            "mag_tolerance": {"type": "number"}
        },
        "required": ["campaign_id", "zero_alpha_tolerance"]
    })
    write_schema("campaign/hpc_profile.schema.json", {
        "type": "object",
        "properties": {"campaign_id": {"type": "string"}},
        "required": ["campaign_id"]
    })
    write_schema("campaign/methodology_lock.schema.json", {
        "type": "object",
        "properties": {
            "campaign_id": {"type": "string"},
            "convention_profile_v0_1_0": {
                "type": "object",
                "properties": {
                    "perturbation_operator_convention": {"const": "+alpha*n"},
                    "response_derivative_convention": {"const": "dN/dalpha"},
                    "u_formula_convention": {"const": "inv(chi0)-inv(chi)"}
                },
                "required": ["perturbation_operator_convention", "response_derivative_convention", "u_formula_convention"]
            }
        },
        "required": ["campaign_id", "convention_profile_v0_1_0"],
        "not": {"required": ["sha256"]}
    })
    
    # --- IDENTITY ---
    identity_files = [
        "pseudopotential_identity", "species_pseudopotential_map", "siesta_binary_identity",
        "siesta_banner", "mpi_runtime", "reference_dm_lock", "projector_definition", "task_identity"
    ]
    for f in identity_files:
        write_schema(f"identity/{f}.schema.json", {
            "type": "object",
            "properties": {"id": {"type": "string"}},
            "not": {"required": ["sha256"]}
        })

    # --- RESPONSE ---
    response_files = [
        "occupation_record", "occupation_records", "regression_record", "regression",
        "raw_matrix", "symmetrized_matrix", "antisymmetry", "selection_policy",
        "selected_matrix", "matrix_inverse", "residuals", "condition_number",
        "singular_values", "numerical_rank"
    ]
    for f in response_files:
        write_schema(f"response/{f}.schema.json", {
            "type": "object",
            "properties": {
                "campaign_id": {"type": "string"},
                "matrix_family": {"type": "string"},
                "matrix_stage": {"type": "string"},
                "response_mode": {"type": "string"}
            },
            "not": {"required": ["sha256"]}
        })
        
    # --- RESULTS ---
    write_schema("results/u_matrix.schema.json", {
        "type": "object",
        "properties": {
            "campaign_id": {"type": "string"},
            "values": {"type": "array"},
            "matrix_family": {"const": "HUBBARD"},
            "matrix_stage": {"const": "U_MATRIX"},
            "response_mode": {"const": "NOT_APPLICABLE"},
            "units": {"const": "eV"}
        },
        "required": ["values", "matrix_family", "matrix_stage", "response_mode", "units"],
        "not": {"required": ["sha256"]}
    })
    
    write_schema("results/candidate_evaluation.schema.json", {
        "type": "object",
        "properties": {
            "campaign_id": {"type": "string"},
            "diagonal_U_ev": {"type": "array"},
            "recommended_single_U_ev": {"type": ["null"]}
        },
        "required": ["recommended_single_U_ev"],
        "not": {"required": ["sha256"]}
    })
    
    write_schema("results/human_decision.schema.json", {
        "type": "object",
        "required": ["campaign_id", "decision_type"],
        "properties": {
            "campaign_id": {"type": "string"},
            "decision_type": {
                "enum": ["DEFER", "REJECT", "ACCEPT_FULL_MATRIX", "ACCEPT_DIAGONAL_VECTOR", "ACCEPT_SINGLE_SCALAR"]
            },
            "rationale": {"type": "string"},
            "reduction_justification": {"type": "string"},
            "u_accepted_matrix_ev": {"type": "array"},
            "u_accepted_diagonal_ev": {"type": "array"},
            "u_accepted_scalar_ev": {"type": "number"},
            "rejection_reasons": {"type": "array"},
            "precondition_refs": {"type": "array"}
        },
        "allOf": [
            {
                "if": {"properties": {"decision_type": {"const": "DEFER"}}},
                "then": {"required": ["rationale"]}
            },
            {
                "if": {"properties": {"decision_type": {"const": "REJECT"}}},
                "then": {"required": ["rationale", "rejection_reasons"]}
            },
            {
                "if": {"properties": {"decision_type": {"const": "ACCEPT_FULL_MATRIX"}}},
                "then": {"required": ["u_accepted_matrix_ev", "rationale", "precondition_refs"]}
            },
            {
                "if": {"properties": {"decision_type": {"const": "ACCEPT_DIAGONAL_VECTOR"}}},
                "then": {"required": ["u_accepted_diagonal_ev", "rationale", "reduction_justification", "precondition_refs"]}
            },
            {
                "if": {"properties": {"decision_type": {"const": "ACCEPT_SINGLE_SCALAR"}}},
                "then": {"required": ["u_accepted_scalar_ev", "rationale", "reduction_justification", "precondition_refs"]}
            }
        ],
        "not": {"required": ["sha256"]}
    })
    
    # --- WORKFLOW ---
    workflow_files = ["dag_node", "campaign_state_event", "task_state_event", "gate_result", "lock", "semantic_validation"]
    for f in workflow_files:
        write_schema(f"workflow/{f}.schema.json", {
            "type": "object",
            "properties": {"id": {"type": "string"}},
            "not": {"required": ["sha256"]}
        })
        
    write_schema("workflow/execution_observation_map.schema.json", {
        "type": "object",
        "required": ["execution_id", "task_id", "produces"],
        "properties": {
            "execution_id": {"type": "string"},
            "task_id": {"type": "string"},
            "produces": {
                "type": "array",
                "items": {"enum": ["BARE_OBSERVATION", "SCREENED_OBSERVATION"]},
                "minItems": 1,
                "maxItems": 2,
                "uniqueItems": True
            },
            "backend": {
                "type": "string",
                "description": "'synthetic_v0' produces both; 'siesta_54' may produce only SCREENED while BARE is open"
            }
        },
        "not": {"required": ["sha256"]}
    })
    
    # --- EVIDENCE ---
    evidence_files = ["artifact_ref", "evidence_package", "packaging"]
    for f in evidence_files:
        write_schema(f"evidence/{f}.schema.json", {
            "type": "object",
            "properties": {"id": {"type": "string"}},
            "not": {"required": ["sha256"]}
        })

if __name__ == '__main__':
    generate_all()
