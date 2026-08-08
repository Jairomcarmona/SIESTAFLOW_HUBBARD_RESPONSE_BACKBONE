# Compliance Matrix

This matrix tracks the validation status of every P0 requirement defined in the ANTIGRAVITY MASTER DIRECTIVE for achieving a scientifically valid Hubbard U.

| ID | SEVERITY | REQUIREMENT | IMPLEMENTATION FILE/SYMBOL | TEST | EVIDENCE | STATUS |
|----|----------|-------------|----------------------------|------|----------|--------|
| P0-001 | P0 | DFTU.Proj grammar matches SIESTA 5.4.2 method-2 | `dftu_models.py`, `fdf_builder.py:construct_dftu_proj_block` | `test_fdf_builder_safe_materialization.py` | `docs/SIESTA_542_DFTU_PROJ_GRAMMAR.md` — IMPLEMENTED: strict 3/4-line format. | COMPLETED |
| P0-002 | P0 | Alpha mapped via DFTU.PotentialShift, typed separation | `fdf_builder.py` | `test_fdf_builder_safe_materialization.py` | IMPLEMENTED: U=alpha, J=0, rc/omega invariant. | COMPLETED |
| P0-003A | P0 | Mandatory booleans enforced by value, not presence | `fdf_builder.py:replace_or_append_fdf_key` | `test_fdf_builder_safe_materialization.py` | IMPLEMENTED: Overrides pre-existing false values by value. | COMPLETED |
| P0-003B | P0 | Explicit DFTU.FirstIteration for auditability | `fdf_builder.py` | `test_fdf_builder_safe_materialization.py` | IMPLEMENTED: Explicitly serialized to true. | COMPLETED |
| P0-004 | P0 | Parser preserves all Hubbard atoms/events (no last-block) | `event_parser.py:parse_hubbard_population_events` | `test_hubbard_event_parser.py` | `SUBAGENT_B_EVENT_PARSER_REPORT.md` — VALIDATED: 100% extraction, trace checksums, no `last-block` heuristic. | VALIDATED |
| P0-005 | P0 | BARE & SCREENED scientific mapping | `fit_engine.py:fit_slopes` | `test_fit_engine.py` | `PHYSICAL_BENCHMARK_REPORT.md` — VALIDATED: Asymmetry verified, NCs executed, cubic R² checked, theoretical inversion verified. | VALIDATED |
| P0-006 | P0 | Regression diagnostics data-derived (no fabrication) | `fit_engine.py:fit_slopes`, `fit_strategies.py` | `test_fit_engine.py` | Source audit — CONFIRMED: std error, condition number, design rank, residuals generated dynamically via `RegressionQualityPolicy`. | VALIDATED |
| P0-007 | P0 | CLI/reporting executes real operations | `cli.py` | `test_cli_and_manifest.py` | `SUBAGENT_E_TEST_CLI_AUDIT.md` — VALIDATED: converge/run/resume/report all simulate state changes properly on CampaignState. | VALIDATED |
| P0-008 | P0 | Replace placeholder tests with adversarial mutations | 36 test files | All 97 tests | `SUBAGENT_E_TEST_CLI_AUDIT.md` — VALIDATED: 0 placeholder tests remaining. 97 meaningful tests passing. | VALIDATED |
