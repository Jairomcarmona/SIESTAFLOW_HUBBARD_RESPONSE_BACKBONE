# Compliance Matrix

This matrix tracks the validation status of every P0 requirement defined in the ANTIGRAVITY MASTER DIRECTIVE for achieving a scientifically valid Hubbard U.

| ID | SEVERITY | REQUIREMENT | IMPLEMENTATION FILE/SYMBOL | TEST | EVIDENCE | STATUS |
|----|----------|-------------|----------------------------|------|----------|--------|
| P0-001 | P0 | DFTU.Proj grammar matches SIESTA 5.4.2 method-2 | `fdf_builder.py:construct_dftu_proj_block` | TBD | `docs/SIESTA_542_DFTU_PROJ_GRAMMAR.md` — CONFIRMED FROM SOURCE: SYNTAX potentially valid (parser reads j_val as lambda), SEMANTICS invalid (rc read as U, width read as J, u_val as rc). | BLOCKED (grammar confirmed, serializer not yet fixed) |
| P0-002 | P0 | Alpha mapped via DFTU.PotentialShift, typed separation | `fdf_builder.py` | TBD | `docs/audits/SUBAGENT_A_SIESTA_542_PHYSICS_AUDIT.md` — CONFIRMED: U=alpha when PotentialShift=true, J=0 | BLOCKED (implementation needed) |
| P0-003A | P0 | Mandatory booleans enforced by value, not presence | `fdf_builder.py:modify_fdf_content` | TBD | Audit Record 5 — CONFIRMED: must override, not append-if-absent. | BLOCKED (implementation needed) |
| P0-003B | P0 | Explicit DFTU.FirstIteration for auditability | `fdf_builder.py` | TBD | Audit Record 3 — CONFIRMED FROM SOURCE: `dftu_init` is forced `.true.` internally if `dftu_shift` is true. Lack of explicit FirstIteration in FDF is an auditability deficiency, not a physical failure. | BLOCKED (implementation needed) |
| P0-004 | P0 | Parser preserves all Hubbard atoms/events (no last-block) | `adapter.py:parse_converged_hubbard_occupations` | TBD | Source audit — CONFIRMED: single-atom, last-block regex only | NOT_STARTED |
| P0-005 | P0 | BARE observation mapping validated experimentally | TBD | TBD | `docs/audits/SUBAGENT_A_SIESTA_542_PHYSICS_AUDIT.md` — SOURCE MAPPING COMPLETE: n0(alpha) evaluated on D_in before diagonalization; n(alpha) evaluated after convergence. Must be tested experimentally in Phase 4. | NOT_STARTED |
| P0-006 | P0 | Regression diagnostics data-derived (no fabrication) | `fit_engine.py:fit_slopes` | TBD | Source audit — CONFIRMED: r²=1.0, residual=0.0, cond=1.0 hardcoded | NOT_STARTED |
| P0-007 | P0 | CLI/reporting executes real operations | `cli.py` | TBD | Docs audit — CONFIRMED: converge/run/resume/report all simulate | NOT_STARTED |
| P0-008 | P0 | Replace placeholder tests with adversarial mutations | 36 test files | TBD | Test audit — CONFIRMED: 36/79 tests are `pass` stubs | NOT_STARTED |
