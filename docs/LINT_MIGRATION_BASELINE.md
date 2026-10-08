# Baseline de lint y tipado antes de 25c

Este documento registra la deuda existente antes de ampliar la configuración de Ruff y mypy. No se editó código para producir el baseline. Los conteos incluyen cada hallazgo/error individual; los archivos no listados no tenían hallazgos en esa herramienta.

## Comandos de baseline

Los comandos y conteos siguientes se ejecutaron antes de modificar `pyproject.toml`, en el commit `8185281f78963e8da3236597c16fe76e4aeea5d0` (Ruff 0.16.10, mypy 2.4.0). Al ejecutarlos sobre la configuración final se heredan las exclusiones de esta migración y no se reproducen los conteos originales; para reproducirlos hay que usar ese commit/configuración anterior. Ambos comandos de baseline terminaron con código de salida 1 por los hallazgos registrados.

Ruff (sobrescribe solo `include` para escanear todos los archivos Python de `src/` y `tests/`, manteniendo el resto de `pyproject.toml`):
```powershell
ruff check --config "include = ['src/*.py', 'src/**/*.py', 'tests/*.py', 'tests/**/*.py']" --output-format=json src tests
```

Mypy (raíces explícitas completas; `follow-imports=silent` limita los diagnósticos a los archivos objetivo, que también se recorren como raíces):
```powershell
mypy --strict --no-incremental --follow-imports=silent --show-error-codes src tests
```

Archivos Python rastreados en `src/` y `tests/`: **343**. Ruff: **672** hallazgos en **170** archivos. Mypy: **1662** errores en **168** archivos; mypy informó 343 archivos fuente inspeccionados.

## Ruff: hallazgos por archivo

| Archivo | Hallazgos | Códigos y conteos |
|---|---:|---|
| `src/hubbardflow/cli.py` | 3 | `I001` 3 |
| `src/hubbardflow/domain/adaptive_alpha.py` | 1 | `UP035` 1 |
| `src/hubbardflow/domain/adaptive_alpha_control.py` | 7 | `I001` 1, `SIM102` 4, `UP035` 1, `UP037` 1 |
| `src/hubbardflow/domain/alpha_grid.py` | 3 | `I001` 1, `UP006` 1, `UP035` 1 |
| `src/hubbardflow/domain/alpha_selection.py` | 2 | `TRY004` 1, `UP035` 1 |
| `src/hubbardflow/domain/backend_compatibility.py` | 4 | `UP035` 1, `UP037` 3 |
| `src/hubbardflow/domain/campaign_manifest.py` | 9 | `F401` 2, `I001` 1, `UP006` 5, `UP035` 1 |
| `src/hubbardflow/domain/cardinals.py` | 3 | `I001` 1, `UP006` 1, `UP035` 1 |
| `src/hubbardflow/domain/convergence_engine.py` | 7 | `F401` 1, `I001` 1, `UP035` 1, `UP045` 4 |
| `src/hubbardflow/domain/hubbard_parameter_semantics.py` | 2 | `I001` 1, `UP035` 1 |
| `src/hubbardflow/domain/interfaces.py` | 6 | `I001` 1, `PIE790` 3, `UP006` 1, `UP035` 1 |
| `src/hubbardflow/domain/kgrid_builder.py` | 4 | `I001` 1, `UP006` 2, `UP035` 1 |
| `src/hubbardflow/domain/lr_analysis_v2.py` | 2 | `I001` 1, `UP035` 1 |
| `src/hubbardflow/domain/lr_campaign_contract.py` | 3 | `UP035` 1, `UP037` 2 |
| `src/hubbardflow/domain/matrix_lr.py` | 13 | `I001` 1, `UP035` 1, `UP045` 11 |
| `src/hubbardflow/domain/matrix_pipeline.py` | 1 | `I001` 1 |
| `src/hubbardflow/domain/observation_provenance.py` | 2 | `I001` 1, `UP035` 1 |
| `src/hubbardflow/domain/occupation_noise_calibration.py` | 2 | `I001` 1, `UP035` 1 |
| `src/hubbardflow/domain/provenance.py` | 13 | `I001` 1, `UP006` 7, `UP035` 3, `UP045` 2 |
| `src/hubbardflow/domain/scalar_lr.py` | 16 | `I001` 1, `SIM102` 5, `UP035` 1, `UP037` 1, `UP045` 8 |
| `src/hubbardflow/domain/scientific_profile.py` | 1 | `I001` 1 |
| `src/hubbardflow/domain/semantic_validation.py` | 6 | `I001` 1, `UP006` 2, `UP035` 2, `UP045` 1 |
| `src/hubbardflow/domain/symmetry_reduction.py` | 2 | `I001` 1, `UP035` 1 |
| `src/hubbardflow/domain/u_certification.py` | 4 | `SIM101` 1, `UP035` 1, `UP037` 2 |
| `src/hubbardflow/domain/u_matrix.py` | 10 | `I001` 2, `UP006` 2, `UP035` 1, `UP045` 5 |
| `src/hubbardflow/domain/u_repeatability.py` | 1 | `UP035` 1 |
| `src/hubbardflow/execution/__init__.py` | 2 | `I001` 1, `RUF022` 1 |
| `src/hubbardflow/execution/campaign_runner.py` | 25 | `BLE001` 6, `F401` 10, `F541` 1, `I001` 2, `TRY004` 5, `UP035` 1 |
| `src/hubbardflow/execution/campaign_software_lock.py` | 1 | `I001` 1 |
| `src/hubbardflow/execution/campaign_v2.py` | 2 | `I001` 1, `UP035` 1 |
| `src/hubbardflow/execution/checkpoint_manager.py` | 11 | `F401` 4, `I001` 1, `UP006` 4, `UP035` 2 |
| `src/hubbardflow/execution/downstream_u_admission.py` | 2 | `I001` 1, `RUF023` 1 |
| `src/hubbardflow/execution/execution_profile.py` | 3 | `UP035` 1, `UP037` 2 |
| `src/hubbardflow/execution/lr_dag.py` | 2 | `I001` 1, `UP035` 1 |
| `src/hubbardflow/execution/response_grid_context.py` | 2 | `I001` 1, `UP035` 1 |
| `src/hubbardflow/execution/slurm_environment.py` | 2 | `UP035` 1, `UP037` 1 |
| `src/hubbardflow/execution/slurm_foreground.py` | 1 | `I001` 1 |
| `src/hubbardflow/execution/source_evidence.py` | 4 | `I001` 3, `UP035` 1 |
| `src/hubbardflow/execution/u_certification_node.py` | 6 | `I001` 1, `RUF059` 4, `UP035` 1 |
| `src/hubbardflow/execution/u_release_gate.py` | 3 | `I001` 2, `UP035` 1 |
| `src/hubbardflow/execution/wsl_campaign_init.py` | 3 | `I001` 2, `UP035` 1 |
| `src/hubbardflow/execution/wsl_supervisor.py` | 4 | `I001` 1, `RUF022` 1, `SIM102` 1, `UP035` 1 |
| `src/hubbardflow/reporting/evidence_exporter.py` | 5 | `I001` 1, `UP006` 3, `UP035` 1 |
| `src/hubbardflow/reporting/lr_u_report.py` | 7 | `ISC004` 6, `UP035` 1 |
| `src/hubbardflow/siesta_backend/__init__.py` | 2 | `I001` 1, `RUF022` 1 |
| `src/hubbardflow/siesta_backend/adapter.py` | 4 | `I001` 1, `UP006` 2, `UP035` 1 |
| `src/hubbardflow/siesta_backend/backend_admission.py` | 3 | `I001` 1, `UP030` 1, `UP032` 1 |
| `src/hubbardflow/siesta_backend/backend_admission_plugin.py` | 4 | `I001` 1, `RUF022` 1, `TRY203` 1, `UP007` 1 |
| `src/hubbardflow/siesta_backend/backend_identity.py` | 2 | `I001` 1, `UP007` 1 |
| `src/hubbardflow/siesta_backend/bare_semantics_evidence.py` | 2 | `I001` 1, `UP035` 1 |
| `src/hubbardflow/siesta_backend/bare_trace_provider.py` | 1 | `I001` 1 |
| `src/hubbardflow/siesta_backend/command_factory.py` | 3 | `F401` 1, `I001` 1, `UP035` 1 |
| `src/hubbardflow/siesta_backend/dftu_models.py` | 4 | `I001` 1, `UP006` 1, `UP035` 1, `UP045` 1 |
| `src/hubbardflow/siesta_backend/event_parser.py` | 13 | `F401` 4, `I001` 1, `PIE790` 2, `PLR1730` 2, `UP006` 1, `UP035` 3 |
| `src/hubbardflow/siesta_backend/fdf_builder.py` | 44 | `F401` 1, `I001` 2, `SIM102` 1, `UP006` 7, `UP035` 2, `UP045` 31 |
| `src/hubbardflow/siesta_backend/fdf_symmetry_adapter.py` | 2 | `C408` 1, `I001` 1 |
| `src/hubbardflow/siesta_backend/fdf_validator.py` | 9 | `E722` 1, `F401` 3, `I001` 1, `UP006` 1, `UP035` 3 |
| `src/hubbardflow/siesta_backend/observation_selector.py` | 8 | `F401` 1, `F821` 1, `I001` 1, `UP006` 4, `UP035` 1 |
| `src/hubbardflow/siesta_backend/occupation_precision.py` | 1 | `I001` 1 |
| `src/hubbardflow/siesta_backend/output_validator.py` | 5 | `I001` 1, `RUF046` 1, `UP030` 1, `UP032` 1, `UP035` 1 |
| `src/hubbardflow/siesta_backend/parser_models.py` | 22 | `F401` 1, `I001` 2, `SIM103` 1, `UP006` 1, `UP035` 2, `UP045` 15 |
| `src/hubbardflow/siesta_backend/production_runtime.py` | 1 | `UP035` 1 |
| `src/hubbardflow/siesta_backend/reference_magnetic_evidence.py` | 1 | `I001` 1 |
| `src/hubbardflow/siesta_backend/response_grid_semantics.py` | 3 | `FURB167` 2, `I001` 1 |
| `src/hubbardflow/siesta_backend/siesta542_bare_profile.py` | 25 | `FURB167` 3, `I001` 1, `UP006` 2, `UP030` 8, `UP032` 8, `UP035` 3 |
| `src/hubbardflow/siesta_backend/siesta542_screened_selection.py` | 4 | `UP030` 2, `UP032` 2 |
| `src/hubbardflow/siesta_backend/symmetry_materializer.py` | 1 | `I001` 1 |
| `src/hubbardflow/synthetic_backend/fit_engine.py` | 19 | `F401` 1, `I001` 2, `SIM102` 4, `UP006` 7, `UP035` 1, `UP045` 4 |
| `src/hubbardflow/synthetic_backend/fit_strategies.py` | 2 | `I001` 1, `PIE790` 1 |
| `src/hubbardflow/synthetic_backend/matrix_assembler.py` | 14 | `F401` 2, `F811` 1, `I001` 1, `UP006` 7, `UP035` 3 |
| `src/hubbardflow/synthetic_backend/noise_injection.py` | 1 | `I001` 1 |
| `src/hubbardflow/synthetic_backend/population_generator.py` | 9 | `I001` 1, `UP006` 5, `UP035` 2, `UP045` 1 |
| `src/hubbardflow/synthetic_backend/recovery.py` | 3 | `F401` 1, `I001` 2 |
| `src/hubbardflow/synthetic_backend/u_calculator.py` | 5 | `F401` 1, `I001` 1, `UP006` 1, `UP035` 2 |
| `src/symmetry_reduction_proposal.py` | 1 | `I001` 1 |
| `tests/adversarial/test_bare_unresolved.py` | 2 | `F401` 1, `I001` 1 |
| `tests/adversarial/test_cardinal_p_neq_n.py` | 2 | `F401` 1, `I001` 1 |
| `tests/adversarial/test_fdf_semantics.py` | 5 | `F401` 1, `F841` 1, `I001` 1, `PLR1711` 1, `RET501` 1 |
| `tests/adversarial/test_human_decision_types.py` | 2 | `F401` 1, `I001` 1 |
| `tests/adversarial/test_ill_conditioned_matrix.py` | 2 | `F401` 1, `I001` 1 |
| `tests/adversarial/test_install_scientific_dag_atomicity.py` | 1 | `I001` 1 |
| `tests/adversarial/test_lstsq_zone.py` | 2 | `F401` 1, `I001` 1 |
| `tests/adversarial/test_method2_preflight_cache_identity.py` | 2 | `FURB167` 1, `RUF100` 1 |
| `tests/adversarial/test_method2_reference.py` | 10 | `B010` 1, `F401` 3, `I001` 2, `RUF059` 4 |
| `tests/adversarial/test_methodology_lock.py` | 2 | `F401` 1, `I001` 1 |
| `tests/adversarial/test_missing_lock.py` | 2 | `F401` 1, `I001` 1 |
| `tests/adversarial/test_observation_selection.py` | 2 | `F401` 1, `I001` 1 |
| `tests/adversarial/test_phase4_alpha0_control.py` | 2 | `F401` 1, `I001` 1 |
| `tests/adversarial/test_pinv_prohibition.py` | 2 | `F401` 1, `I001` 1 |
| `tests/adversarial/test_rc3_mutations.py` | 7 | `F401` 1, `I001` 6 |
| `tests/adversarial/test_recommended_u_null.py` | 3 | `F401` 2, `I001` 1 |
| `tests/adversarial/test_record_completeness.py` | 2 | `F401` 1, `I001` 1 |
| `tests/adversarial/test_rectangular_primary.py` | 2 | `F401` 1, `I001` 1 |
| `tests/adversarial/test_reference_dm_chaining.py` | 2 | `F401` 1, `I001` 1 |
| `tests/adversarial/test_relaxed_geometry.py` | 2 | `F401` 1, `I001` 1 |
| `tests/adversarial/test_scientific_dag_analysis_contract.py` | 5 | `I001` 1, `RUF100` 3, `UP031` 1 |
| `tests/adversarial/test_sign_convention.py` | 2 | `F401` 1, `I001` 1 |
| `tests/adversarial/test_singular_matrix.py` | 2 | `F401` 1, `I001` 1 |
| `tests/adversarial/test_swap_chi0_chi.py` | 2 | `F401` 1, `I001` 1 |
| `tests/adversarial/test_zero_alpha_consistency.py` | 2 | `F401` 1, `I001` 1 |
| `tests/algebraic/test_matrix_constraints.py` | 1 | `I001` 1 |
| `tests/algebraic/test_phase6_matrices.py` | 2 | `F401` 1, `I001` 1 |
| `tests/algebraic/test_phase7_u_matrix.py` | 3 | `F401` 2, `I001` 1 |
| `tests/algebraic/test_synthetic_recovery.py` | 3 | `F401` 2, `I001` 1 |
| `tests/backend/test_fdf_builder.py` | 2 | `F401` 1, `I001` 1 |
| `tests/execution/test_execution_contract.py` | 2 | `F401` 1, `I001` 1 |
| `tests/package/test_verify_backbone.py` | 2 | `F401` 1, `I001` 1 |
| `tests/schemas/test_example_validation.py` | 2 | `F401` 1, `I001` 1 |
| `tests/schemas/test_schema_validity.py` | 2 | `F401` 1, `I001` 1 |
| `tests/science/test_nio_core_real_baseline.py` | 1 | `I001` 1 |
| `tests/test_adversarial_core_audit.py` | 5 | `F401` 4, `I001` 1 |
| `tests/test_cli_and_manifest.py` | 2 | `I001` 1, `PLR0402` 1 |
| `tests/test_fdf_builder_safe_materialization.py` | 1 | `I001` 1 |
| `tests/test_fdf_validation.py` | 3 | `F401` 2, `I001` 1 |
| `tests/test_fit_engine.py` | 3 | `F401` 1, `I001` 1, `RUF059` 1 |
| `tests/test_hubbard_event_parser.py` | 2 | `F401` 1, `I001` 1 |
| `tests/test_nio_polynomial_analysis.py` | 2 | `I001` 1, `RUF100` 1 |
| `tests/test_nio_shared_lru_regression.py` | 1 | `I001` 1 |
| `tests/test_population_generator.py` | 3 | `F401` 2, `I001` 1 |
| `tests/test_symmetry_reduction_proposal.py` | 1 | `I001` 1 |
| `tests/unit/test_adaptive_alpha_dag_resume.py` | 2 | `I001` 1, `RUF059` 1 |
| `tests/unit/test_alpha_grid.py` | 2 | `F401` 1, `I001` 1 |
| `tests/unit/test_backend_admission_plugin.py` | 1 | `I001` 1 |
| `tests/unit/test_bare_semantics_evidence.py` | 2 | `F401` 1, `I001` 1 |
| `tests/unit/test_bare_trace_provider.py` | 1 | `I001` 1 |
| `tests/unit/test_campaign_production.py` | 25 | `C408` 1, `F401` 2, `F811` 4, `I001` 7, `RUF046` 1, `RUF059` 7, `SIM115` 3 |
| `tests/unit/test_campaign_runner_execution_identity.py` | 2 | `I001` 2 |
| `tests/unit/test_campaign_runner_synthetic.py` | 2 | `I001` 1, `PIE807` 1 |
| `tests/unit/test_capabilities.py` | 1 | `I001` 1 |
| `tests/unit/test_convergence_engine.py` | 2 | `F401` 1, `I001` 1 |
| `tests/unit/test_cu1_archived_occupation_v3.py` | 2 | `F401` 1, `I001` 1 |
| `tests/unit/test_cu3n_symmetry_shadow_package.py` | 2 | `F401` 2 |
| `tests/unit/test_cu_one_atom_noise_calibrated_campaign.py` | 2 | `I001` 1, `RUF059` 1 |
| `tests/unit/test_fdf_symmetry_adapter.py` | 1 | `I001` 1 |
| `tests/unit/test_hubbard_parameter_semantics.py` | 1 | `I001` 1 |
| `tests/unit/test_install_scientific_dag_profiles.py` | 1 | `I001` 1 |
| `tests/unit/test_interfaces.py` | 2 | `F401` 1, `I001` 1 |
| `tests/unit/test_local_lr_gate_smoke.py` | 2 | `F401` 1, `I001` 1 |
| `tests/unit/test_lr_campaign_contract.py` | 1 | `I001` 1 |
| `tests/unit/test_lr_dag.py` | 1 | `I001` 1 |
| `tests/unit/test_matrix_lr.py` | 13 | `F401` 4, `I001` 4, `RUF013` 2, `RUF059` 3 |
| `tests/unit/test_matrix_pipeline.py` | 1 | `I001` 1 |
| `tests/unit/test_matrix_response_acceptance.py` | 1 | `I001` 1 |
| `tests/unit/test_method2_effective_fdf.py` | 3 | `RUF100` 3 |
| `tests/unit/test_method2_projector_audit.py` | 8 | `F401` 1, `F811` 1, `I001` 3, `RUF100` 2, `SIM117` 1 |
| `tests/unit/test_mno_foreground_preflight.py` | 1 | `I001` 1 |
| `tests/unit/test_mno_independent_audit_regressions.py` | 4 | `F401` 3, `I001` 1 |
| `tests/unit/test_mno_response_recovery.py` | 1 | `I001` 1 |
| `tests/unit/test_observation_provenance_integration.py` | 1 | `I001` 1 |
| `tests/unit/test_occupation_noise_calibration.py` | 1 | `I001` 1 |
| `tests/unit/test_occupation_precision.py` | 1 | `I001` 1 |
| `tests/unit/test_parametrized_cardinals.py` | 2 | `F401` 1, `I001` 1 |
| `tests/unit/test_production_benchmarks_common_analysis.py` | 6 | `B023` 4, `I001` 1, `RUF012` 1 |
| `tests/unit/test_reference_magnetic_evidence.py` | 1 | `I001` 1 |
| `tests/unit/test_runtime_adapters.py` | 1 | `PLR0402` 1 |
| `tests/unit/test_scalar_lr.py` | 3 | `F401` 2, `I001` 1 |
| `tests/unit/test_scientific_dag_gate.py` | 1 | `RUF100` 1 |
| `tests/unit/test_scientific_profile.py` | 1 | `I001` 1 |
| `tests/unit/test_semantic_validation.py` | 2 | `F401` 1, `I001` 1 |
| `tests/unit/test_siesta542_bare_profile.py` | 4 | `FLY002` 2, `FURB167` 1, `I001` 1 |
| `tests/unit/test_siesta_output_validator.py` | 1 | `I001` 1 |
| `tests/unit/test_siesta_production_runtime.py` | 1 | `I001` 1 |
| `tests/unit/test_source_evidence.py` | 1 | `I001` 1 |
| `tests/unit/test_symmetry_materializer.py` | 2 | `F841` 1, `I001` 1 |
| `tests/unit/test_symmetry_reduction_plan.py` | 1 | `C408` 1 |
| `tests/unit/test_u_certification.py` | 1 | `I001` 1 |
| `tests/unit/test_u_certification_generalization.py` | 1 | `I001` 1 |
| `tests/unit/test_u_certification_pipeline.py` | 8 | `C405` 1, `F401` 1, `F541` 1, `F811` 3, `I001` 2 |
| `tests/unit/test_u_release_gate.py` | 1 | `I001` 1 |
| `tests/unit/test_units.py` | 2 | `F401` 1, `I001` 1 |

## Mypy: errores por archivo

| Archivo | Errores | Códigos y conteos |
|---|---:|---|
| `src/hubbardflow/cli.py` | 7 | `return` 1, `return-value` 4, `str, Any` 2 |
| `src/hubbardflow/domain/adaptive_alpha_control.py` | 2 | `str, Any` 2 |
| `src/hubbardflow/domain/alpha_grid.py` | 1 | `no-untyped-def` 1 |
| `src/hubbardflow/domain/alpha_selection.py` | 3 | `Any, dtype[Any` 1, `call-overload` 1, `type-arg` 1 |
| `src/hubbardflow/domain/campaign_manifest.py` | 9 | `no-untyped-call` 1, `no-untyped-def` 6, `type-arg` 2 |
| `src/hubbardflow/domain/cardinals.py` | 4 | `Any, Any` 1, `no-untyped-def` 1, `type-arg` 2 |
| `src/hubbardflow/domain/convergence_engine.py` | 6 | `'linear', 'polynomial'` 1, `type-arg` 5 |
| `src/hubbardflow/domain/kgrid_builder.py` | 2 | `type-arg` 2 |
| `src/hubbardflow/domain/lr_analysis_v2.py` | 9 | `'linear', 'polynomial'` 2, `arg-type` 3, `no-untyped-call` 1, `str, Any` 1, `type-arg` 2 |
| `src/hubbardflow/domain/matrix_lr.py` | 21 | `Any, Any` 1, `assignment` 2, `no-untyped-call` 1, `type-arg` 17 |
| `src/hubbardflow/domain/matrix_pipeline.py` | 10 | `Any, Any` 2, `type-arg` 8 |
| `src/hubbardflow/domain/matrix_response_acceptance.py` | 6 | `Any` 2, `type-arg` 4 |
| `src/hubbardflow/domain/occupation_noise_calibration.py` | 2 | `str, Any | None` 2 |
| `src/hubbardflow/domain/provenance.py` | 12 | `int, ...` 1, `no-untyped-call` 5, `no-untyped-def` 3, `type-arg` 3 |
| `src/hubbardflow/domain/quantized_response.py` | 15 | `operator` 2, `type-arg` 13 |
| `src/hubbardflow/domain/scalar_lr.py` | 8 | `Any, Any` 1, `Any, dtype[Any` 5, `no-untyped-def` 1, `type-arg` 1 |
| `src/hubbardflow/domain/semantic_validation.py` | 1 | `type-arg` 1 |
| `src/hubbardflow/domain/symmetry_reduction.py` | 4 | `<type>` 3, `no-untyped-call` 1 |
| `src/hubbardflow/domain/u_certification.py` | 14 | `0` 1, `arg-type` 4, `call-overload` 1, `list[Fraction | Literal[0` 1, `misc` 2, `operator` 3, `tuple[Interval, Interval` 1, `type-var` 1 |
| `src/hubbardflow/domain/u_matrix.py` | 5 | `no-untyped-def` 2, `type-arg` 3 |
| `src/hubbardflow/execution/campaign_runner.py` | 26 | `'auto', 'polynomial', 'linear'` 1, `'raw', 'symmetrized'` 1, `<type>, <type>` 1, `assignment` 2, `attr-defined` 8, `has-type` 1, `no-untyped-def` 2, `str, Any` 3, `union-attr` 7 |
| `src/hubbardflow/execution/campaign_software_lock.py` | 2 | `Any` 1, `type-arg` 1 |
| `src/hubbardflow/execution/checkpoint_manager.py` | 2 | `no-untyped-def` 2 |
| `src/hubbardflow/execution/execution_profile.py` | 2 | `arg-type` 2 |
| `src/hubbardflow/execution/lr_dag.py` | 1 | `no-redef` 1 |
| `src/hubbardflow/execution/source_evidence.py` | 1 | `import-untyped` 1 |
| `src/hubbardflow/execution/u_certification_node.py` | 4 | `Any` 2, `arg-type` 1, `dict[str, Any` 1 |
| `src/hubbardflow/execution/wsl_campaign_init.py` | 1 | `arg-type` 1 |
| `src/hubbardflow/execution/wsl_supervisor.py` | 7 | `attr-defined` 7 |
| `src/hubbardflow/reporting/evidence_exporter.py` | 1 | `no-untyped-def` 1 |
| `src/hubbardflow/siesta_backend/adapter.py` | 3 | `return` 3 |
| `src/hubbardflow/siesta_backend/backend_admission_plugin.py` | 4 | `arg-type` 1, `str` 3 |
| `src/hubbardflow/siesta_backend/backend_identity.py` | 3 | `no-any-return` 1, `str` 2 |
| `src/hubbardflow/siesta_backend/event_parser.py` | 11 | `<type>` 1, `HubbardPopulationEvent | None` 1, `attr-defined` 1, `no-untyped-call` 4, `no-untyped-def` 1, `union-attr` 3 |
| `src/hubbardflow/siesta_backend/fdf_builder.py` | 12 | `<type>, <type>` 1, `attr-defined` 4, `no-any-return` 1, `no-untyped-def` 2, `type-arg` 4 |
| `src/hubbardflow/siesta_backend/fdf_symmetry_adapter.py` | 4 | `no-untyped-call` 2, `tuple[float, ...` 1, `type-arg` 1 |
| `src/hubbardflow/siesta_backend/observation_selector.py` | 1 | `name-defined` 1 |
| `src/hubbardflow/siesta_backend/output_validator.py` | 2 | `union-attr` 2 |
| `src/hubbardflow/siesta_backend/parser_models.py` | 3 | `no-untyped-def` 1, `type-arg` 2 |
| `src/hubbardflow/siesta_backend/production_runtime.py` | 1 | `str` 1 |
| `src/hubbardflow/siesta_backend/reference_magnetic_evidence.py` | 2 | `type-arg` 2 |
| `src/hubbardflow/siesta_backend/siesta542_bare_profile.py` | 2 | `arg-type` 2 |
| `src/hubbardflow/siesta_backend/siesta542_screened_selection.py` | 1 | `operator` 1 |
| `src/hubbardflow/synthetic_backend/fit_engine.py` | 5 | `assignment` 2, `no-untyped-def` 1, `type-arg` 2 |
| `src/hubbardflow/synthetic_backend/fit_strategies.py` | 9 | `Any, Any` 1, `type-arg` 8 |
| `src/hubbardflow/synthetic_backend/population_generator.py` | 6 | `comparison-overlap` 1, `str, AlphaGrid` 1, `type-arg` 3, `union-attr` 1 |
| `src/hubbardflow/synthetic_backend/recovery.py` | 1 | `type-arg` 1 |
| `src/hubbardflow/synthetic_backend/u_calculator.py` | 1 | `type-arg` 1 |
| `src/symmetry_reduction_proposal.py` | 13 | `no-untyped-call` 3, `no-untyped-def` 3, `type-arg` 7 |
| `tests/adversarial/test_bare_unresolved.py` | 2 | `arg-type` 1, `no-untyped-def` 1 |
| `tests/adversarial/test_cardinal_p_neq_n.py` | 2 | `arg-type` 1, `no-untyped-def` 1 |
| `tests/adversarial/test_fdf_semantics.py` | 25 | `no-untyped-call` 10, `no-untyped-def` 15 |
| `tests/adversarial/test_human_decision_types.py` | 6 | `arg-type` 3, `no-untyped-def` 3 |
| `tests/adversarial/test_ill_conditioned_matrix.py` | 2 | `arg-type` 1, `no-untyped-def` 1 |
| `tests/adversarial/test_install_scientific_dag_atomicity.py` | 1 | `no-untyped-def` 1 |
| `tests/adversarial/test_lstsq_zone.py` | 6 | `arg-type` 3, `no-untyped-def` 3 |
| `tests/adversarial/test_method2_preflight_cache_identity.py` | 10 | `Any, Any` 1, `import-not-found` 1, `no-untyped-def` 6, `type-arg` 2 |
| `tests/adversarial/test_method2_reference.py` | 29 | `no-untyped-def` 14, `type-arg` 1, `union-attr` 14 |
| `tests/adversarial/test_methodology_lock.py` | 2 | `arg-type` 1, `no-untyped-def` 1 |
| `tests/adversarial/test_missing_lock.py` | 2 | `arg-type` 1, `no-untyped-def` 1 |
| `tests/adversarial/test_observation_selection.py` | 29 | `no-untyped-call` 19, `no-untyped-def` 10 |
| `tests/adversarial/test_phase4_alpha0_control.py` | 5 | `attr-defined` 1, `no-untyped-def` 4 |
| `tests/adversarial/test_pinv_prohibition.py` | 3 | `arg-type` 1, `no-untyped-def` 2 |
| `tests/adversarial/test_rc3_mutations.py` | 12 | `arg-type` 2, `call-arg` 1, `no-untyped-def` 9 |
| `tests/adversarial/test_recommended_u_null.py` | 2 | `arg-type` 1, `no-untyped-def` 1 |
| `tests/adversarial/test_record_completeness.py` | 6 | `arg-type` 3, `no-untyped-def` 3 |
| `tests/adversarial/test_rectangular_primary.py` | 2 | `arg-type` 1, `no-untyped-def` 1 |
| `tests/adversarial/test_reference_dm_chaining.py` | 2 | `arg-type` 1, `no-untyped-def` 1 |
| `tests/adversarial/test_relaxed_geometry.py` | 2 | `arg-type` 1, `no-untyped-def` 1 |
| `tests/adversarial/test_scientific_dag_analysis_contract.py` | 20 | `Any, Any` 1, `import-not-found` 2, `no-untyped-def` 14, `type-arg` 3 |
| `tests/adversarial/test_sign_convention.py` | 4 | `arg-type` 2, `no-untyped-def` 2 |
| `tests/adversarial/test_singular_matrix.py` | 2 | `arg-type` 1, `no-untyped-def` 1 |
| `tests/adversarial/test_swap_chi0_chi.py` | 1 | `no-untyped-def` 1 |
| `tests/adversarial/test_zero_alpha_consistency.py` | 2 | `arg-type` 1, `no-untyped-def` 1 |
| `tests/algebraic/test_matrix_constraints.py` | 3 | `arg-type` 1, `no-untyped-def` 2 |
| `tests/algebraic/test_phase6_matrices.py` | 13 | `<type>` 1, `Any, dtype[Any` 6, `no-untyped-def` 6 |
| `tests/algebraic/test_phase7_u_matrix.py` | 6 | `no-untyped-def` 6 |
| `tests/algebraic/test_synthetic_recovery.py` | 2 | `no-untyped-def` 2 |
| `tests/backend/test_fdf_builder.py` | 2 | `no-untyped-def` 2 |
| `tests/backend/test_siesta_adapter.py` | 1 | `no-untyped-def` 1 |
| `tests/conftest.py` | 6 | `no-untyped-def` 6 |
| `tests/execution/test_execution_contract.py` | 22 | `Never` 1, `no-untyped-call` 6, `no-untyped-def` 8, `str` 6, `union-attr` 1 |
| `tests/integration/test_runner_replay_nio_p5.py` | 1 | `str, Any` 1 |
| `tests/package/test_verify_backbone.py` | 2 | `arg-type` 1, `no-untyped-def` 1 |
| `tests/schemas/test_example_validation.py` | 2 | `arg-type` 1, `no-untyped-def` 1 |
| `tests/schemas/test_schema_validity.py` | 2 | `arg-type` 1, `no-untyped-def` 1 |
| `tests/science/test_nio_core_real_baseline.py` | 4 | `no-untyped-call` 1, `no-untyped-def` 3 |
| `tests/support.py` | 6 | `no-untyped-call` 2, `no-untyped-def` 4 |
| `tests/test_adversarial_core_audit.py` | 15 | `no-untyped-call` 4, `no-untyped-def` 11 |
| `tests/test_cli_and_manifest.py` | 34 | `CampaignState.DRAFT` 1, `attr-defined` 2, `func-returns-value` 2, `no-untyped-def` 29 |
| `tests/test_fdf_builder_safe_materialization.py` | 5 | `no-untyped-def` 5 |
| `tests/test_fdf_validation.py` | 5 | `no-untyped-def` 5 |
| `tests/test_fit_engine.py` | 10 | `no-untyped-call` 4, `no-untyped-def` 6 |
| `tests/test_hubbard_event_parser.py` | 8 | `no-untyped-def` 8 |
| `tests/test_nio_polynomial_analysis.py` | 14 | `<type>` 1, `no-untyped-call` 4, `no-untyped-def` 9 |
| `tests/test_nio_shared_lru_regression.py` | 2 | `import-not-found` 1, `no-untyped-def` 1 |
| `tests/test_population_generator.py` | 5 | `no-untyped-def` 5 |
| `tests/test_symmetry_reduction_proposal.py` | 32 | `no-untyped-call` 22, `no-untyped-def` 10 |
| `tests/unit/test_adaptive_alpha.py` | 6 | `index` 1, `no-untyped-call` 2, `no-untyped-def` 3 |
| `tests/unit/test_adaptive_alpha_control.py` | 68 | `no-untyped-call` 51, `no-untyped-def` 17 |
| `tests/unit/test_adaptive_alpha_dag_resume.py` | 38 | `[Any` 1, `method-assign` 13, `misc` 1, `no-untyped-call` 7, `no-untyped-def` 9, `str, Any` 5, `str, Collection[str` 1, `str, Mapping[str, Any` 1 |
| `tests/unit/test_alpha_grid.py` | 2 | `arg-type` 1, `no-untyped-def` 1 |
| `tests/unit/test_alpha_selection_integration.py` | 9 | `index` 1, `no-untyped-call` 4, `no-untyped-def` 4 |
| `tests/unit/test_backend_admission.py` | 3 | `no-untyped-def` 3 |
| `tests/unit/test_backend_admission_plugin.py` | 6 | `no-untyped-def` 6 |
| `tests/unit/test_backend_compatibility.py` | 22 | `arg-type` 2, `no-untyped-call` 10, `no-untyped-def` 10 |
| `tests/unit/test_backend_identity.py` | 9 | `no-untyped-def` 9 |
| `tests/unit/test_bare_semantics_evidence.py` | 7 | `no-untyped-def` 6, `type-arg` 1 |
| `tests/unit/test_bare_trace_adversarial_audit.py` | 27 | `no-untyped-call` 13, `no-untyped-def` 14 |
| `tests/unit/test_bare_trace_provider.py` | 4 | `no-untyped-def` 4 |
| `tests/unit/test_campaign_production.py` | 124 | `<type>` 2, `misc` 2, `no-untyped-call` 11, `no-untyped-def` 106, `str, object` 3 |
| `tests/unit/test_campaign_runner_execution_identity.py` | 9 | `<type>, <type>` 1, `assignment` 2, `no-untyped-call` 2, `no-untyped-def` 4 |
| `tests/unit/test_campaign_runner_synthetic.py` | 34 | `arg-type` 2, `assignment` 7, `attr-defined` 1, `index` 2, `method-assign` 7, `no-untyped-call` 2, `no-untyped-def` 12, `var-annotated` 1 |
| `tests/unit/test_campaign_software_lock.py` | 6 | `arg-type` 2, `no-untyped-def` 4 |
| `tests/unit/test_capabilities.py` | 2 | `no-untyped-def` 2 |
| `tests/unit/test_convergence_engine.py` | 16 | `<type>, <type>` 1, `no-untyped-call` 2, `no-untyped-def` 13 |
| `tests/unit/test_cu1_archived_occupation_v3.py` | 6 | `<type>, <type>` 2, `attr-defined` 1, `no-untyped-def` 2, `type-arg` 1 |
| `tests/unit/test_cu3n_symmetry_shadow_package.py` | 3 | `no-untyped-def` 3 |
| `tests/unit/test_cu_one_atom_noise_calibrated_campaign.py` | 30 | `arg-type` 1, `no-untyped-call` 12, `no-untyped-def` 15, `union-attr` 2 |
| `tests/unit/test_elementwise_rounding.py` | 5 | `Any, Any` 1, `operator` 3, `type-arg` 1 |
| `tests/unit/test_fdf_symmetry_adapter.py` | 3 | `no-untyped-def` 3 |
| `tests/unit/test_feo_band_postprocessor.py` | 3 | `no-untyped-def` 3 |
| `tests/unit/test_generic_executor.py` | 14 | `no-untyped-call` 7, `no-untyped-def` 7 |
| `tests/unit/test_hash_traceability.py` | 1 | `no-untyped-def` 1 |
| `tests/unit/test_hubbard_parameter_semantics.py` | 4 | `no-untyped-def` 4 |
| `tests/unit/test_install_scientific_dag_profiles.py` | 2 | `no-untyped-def` 2 |
| `tests/unit/test_interfaces.py` | 2 | `no-untyped-def` 1, `type-arg` 1 |
| `tests/unit/test_local_lr_gate_smoke.py` | 2 | `no-untyped-def` 2 |
| `tests/unit/test_lr_analysis_v2.py` | 39 | `Any, dtype[Any` 2, `no-untyped-call` 18, `no-untyped-def` 19 |
| `tests/unit/test_lr_campaign_contract.py` | 17 | `no-untyped-call` 9, `no-untyped-def` 8 |
| `tests/unit/test_lr_dag.py` | 10 | `no-untyped-call` 5, `no-untyped-def` 5 |
| `tests/unit/test_matrix_lr.py` | 63 | `'average'` 1, `Any, Any` 8, `float` 1, `int` 1, `misc` 4, `no-untyped-call` 2, `no-untyped-def` 38, `type-arg` 3, `union-attr` 5 |
| `tests/unit/test_matrix_pipeline.py` | 5 | `no-untyped-def` 5 |
| `tests/unit/test_matrix_response_acceptance.py` | 3 | `no-untyped-def` 3 |
| `tests/unit/test_method2_effective_fdf.py` | 7 | `import-not-found` 3, `no-untyped-def` 4 |
| `tests/unit/test_method2_projector_audit.py` | 7 | `import-not-found` 2, `no-untyped-def` 5 |
| `tests/unit/test_mno_foreground_preflight.py` | 2 | `arg-type` 1, `no-untyped-def` 1 |
| `tests/unit/test_mno_independent_audit_regressions.py` | 22 | `arg-type` 1, `no-untyped-call` 5, `no-untyped-def` 11, `operator` 2, `type-arg` 1, `union-attr` 2 |
| `tests/unit/test_mno_response_recovery.py` | 7 | `arg-type` 1, `no-untyped-def` 6 |
| `tests/unit/test_observation_provenance_integration.py` | 12 | `attr-defined` 1, `no-untyped-call` 6, `no-untyped-def` 5 |
| `tests/unit/test_occupation_noise_calibration.py` | 15 | `no-untyped-call` 5, `no-untyped-def` 6, `operator` 1, `str, object` 3 |
| `tests/unit/test_occupation_precision.py` | 13 | `no-untyped-call` 5, `no-untyped-def` 8 |
| `tests/unit/test_orchestrator.py` | 1 | `no-untyped-def` 1 |
| `tests/unit/test_parametrized_cardinals.py` | 2 | `arg-type` 1, `no-untyped-def` 1 |
| `tests/unit/test_production_benchmarks_common_analysis.py` | 36 | `<type>, <type>` 1, `attr-defined` 1, `func-returns-value` 2, `no-untyped-call` 12, `no-untyped-def` 19, `var-annotated` 1 |
| `tests/unit/test_provenance_alpha_gate_integration.py` | 13 | `no-untyped-call` 11, `no-untyped-def` 2 |
| `tests/unit/test_quantized_response.py` | 6 | `has-type` 2, `misc` 1, `no-untyped-def` 3 |
| `tests/unit/test_reference_magnetic_evidence.py` | 5 | `no-untyped-def` 5 |
| `tests/unit/test_scalar_lr.py` | 28 | `no-untyped-call` 7, `no-untyped-def` 21 |
| `tests/unit/test_scientific_dag_gate.py` | 3 | `import-not-found` 1, `no-untyped-def` 2 |
| `tests/unit/test_scientific_profile.py` | 7 | `arg-type` 1, `import-untyped` 1, `no-untyped-def` 5 |
| `tests/unit/test_semantic_validation.py` | 6 | `arg-type` 3, `no-untyped-def` 3 |
| `tests/unit/test_siesta542_bare_profile.py` | 7 | `no-untyped-def` 5, `operator` 2 |
| `tests/unit/test_siesta_command_factory.py` | 5 | `call-arg` 3, `no-untyped-def` 2 |
| `tests/unit/test_siesta_output_validator.py` | 18 | `arg-type` 2, `call-arg` 1, `index` 3, `no-untyped-def` 9, `str, object` 3 |
| `tests/unit/test_siesta_production_runtime.py` | 17 | `<type>, <type>` 1, `no-untyped-def` 15, `union-attr` 1 |
| `tests/unit/test_slurm_foreground.py` | 1 | `no-untyped-def` 1 |
| `tests/unit/test_source_evidence.py` | 20 | `no-untyped-call` 4, `no-untyped-def` 15, `type-arg` 1 |
| `tests/unit/test_stage_ub_baseline_summary.py` | 1 | `no-untyped-def` 1 |
| `tests/unit/test_state_gate.py` | 1 | `no-untyped-def` 1 |
| `tests/unit/test_symmetry_evidence_contract.py` | 12 | `no-untyped-call` 7, `no-untyped-def` 5 |
| `tests/unit/test_symmetry_materializer.py` | 18 | `no-untyped-call` 10, `no-untyped-def` 8 |
| `tests/unit/test_symmetry_reduction_plan.py` | 18 | `no-untyped-call` 11, `no-untyped-def` 7 |
| `tests/unit/test_u_certification.py` | 20 | `misc` 7, `no-untyped-def` 13 |
| `tests/unit/test_u_certification_generalization.py` | 35 | `attr-defined` 1, `no-untyped-call` 21, `no-untyped-def` 13 |
| `tests/unit/test_u_certification_pipeline.py` | 13 | `arg-type` 1, `dict[str, Any` 1, `dict[str, object` 1, `no-untyped-def` 7, `object` 2, `type-arg` 1 |
| `tests/unit/test_u_release_gate.py` | 25 | `no-untyped-call` 13, `no-untyped-def` 12 |
| `tests/unit/test_units.py` | 2 | `arg-type` 1, `no-untyped-def` 1 |

## Política de cobertura en 25c

- Ruff incluye todos los `.py` de `src/` y `tests/`. Los archivos de su tabla se excluyen por ruta exacta para preservar CI sin arreglos masivos; cada exclusión incluye su conteo y motivo en `pyproject.toml`.
- Mypy usa `src/` y `tests/` como raíces completas. Los archivos de su tabla son exclusiones exactas por ruta; cada entrada documenta el error preexistente y el motivo común de diferir la corrección a cambios de tipado separados.
- Los archivos no listados siguen bajo las reglas completas. Los conteos y códigos por archivo permiten priorizar el retiro posterior de cada exclusión.
- `follow_imports = "silent"` evita errores transitivos en código fuera de las dos raíces; todos los módulos de `src/` y `tests/` se inspeccionan explícitamente.
- Esta ampliación no cambia código de producción ni pruebas; habilita detección en archivos antes fuera de la lista blanca, sin mezclar reparaciones de deuda histórica.
