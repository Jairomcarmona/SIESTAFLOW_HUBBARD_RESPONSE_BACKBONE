# Phase 2 close summary

Branch: `fdebq/r3-task20-fixes` (from `84b8eb6`). No PR or SIESTA campaign was run. The full-suite command was `pytest tests -q -rfE --continue-on-collection-errors`; final failures match `BASELINE_FAILURES` exactly.

| Item | Commit / status | Premises and auditor | Tests and authorized test edits | Conservative decision |
|---|---|---|---|---|
| 20.1 | `6163c4e` | P1–P4 TRUE; auditor not required | 30 focused tests; legacy resume tests added | Preserve legacy resume validation while binding inventory. |
| 20.2 | `f629220` | P1–P5 TRUE; `RISK_COVERED` after R1 | 107 focused; no existing test edits | Reject recognized noncanonical managed labels; positive read case is unmanaged `Long_Output`. |
| R6 / 20.2 correction | `b37246e` | R6/P1–P5 TRUE; `RISK_COVERED` | Unsafe restart test unchanged; added `file_dm_init` rejection | Check `File.DM.Init` immediately after include resolution, before parsing. |
| 20.3 | `8278d9d` | P1–P9 TRUE; `RISK_COVERED` | Focused SCF-ladder tests; R5 changed only v1 materialization expectation in the explicitly authorized test | Require ladder protocol v2 and verify safety before protocol rejection. |
| 20.4 | `5ca79ba` | P1–P4 TRUE; audit confirmed the R5 fixture edit | Positive Mn aliases rebuilt with `relabel_ion_bytes`; added wrong-header `MISMATCH`; R2 real FeLR0/FeLR1 assertion updated | Compare canonical label-normalized ion bytes; do not accept raw-hash equality alone. |
| 20.5 | `b6a85d1` | P1–P8 TRUE; R9 re-audit `RISK_COVERED` | Rational-ring tests include all k/4 and k/8; R5 changed only the authorized F8 exactness assertion | Exact reductions require rational mapping and mesh commensurability. Lost near-symmetry triggers and non-orthogonal rotations remain Phase 3 savings limitations before TASK 22. |
| 20.6 | `b9388f6` | P1–P5 TRUE; auditor not required | 74 focused plus 13 POSIX tests; updated only the named read-only manifest-path test | Fail closed on protected destinations across platforms. |
| 20.7 | `c4b0cb6` | P1 TRUE; auditor not required | 10 focused CLI tests added; no test edits | Reject product-only options on legacy `run` targets. |
| 20.8 | **Stopped; no implementation commit** (`50751cf` records risk) | Premises TRUE; independent auditor `RISK_UNCOVERED` | No implementation tests committed | Supplied SCF estimates can bypass envelope-based order/tail/truncation budgeting and falsely qualify; stop pending a scientific correction. |
| 20.9 | `dba0788` | P1 TRUE; R10 archive comparison exact | Added NiO P5 archived golden generator, fixture and current-code test; no existing test edits | Compare in manifest namespace. NiO P5 matches 24 identities and 25 FDF hashes; CoO, MnO and Cu3N are `NOT_COVERED`. |
| 20.11 | **Skipped; `PREMISE_FALSE`** (recorded in `374d257`) | R10 leaves one compatible 20.9 archive chain, not the four DISABLED 20.9 plans required by this item's golden | No code/tests changed | Do not invent three historical digests from TASK 13/TASK 21 evidence. |
| 20.10 | `6627e10` | P1–P5 TRUE; 20.5 prerequisite met | 86 focused tests; new AST architecture test; no existing test edits | Move include resolution to the backend and retain the campaign exception wrapper. Architecture allowlist has 44 explicit `# phase 3` entries and rejects new/stale violations. |
| TASK 21 | `8e287bb` | P1–P8 TRUE; auditor not required | TASK 21 gate: 85 passed; full suite below | Enable only fixed explicit, unreduced legacy-equivalent execution. Real numerical CoO equivalence remains a user SIESTA check; no SIESTA was run. |

## Final gates

- 70 scientific regressions: `70 passed`.
- Ruff: `All checks passed!`; format: `91 files already formatted`; strict mypy: `Success: no issues found in 91 source files`.
- New architecture suite and relevant focused tests: `86 passed`.
- TASK 21 CLI/path/admission/execution gates: `85 passed`.
- V6 integrity: `V6 GATE OK`.
- Pre-existing `campaign_v2.py` static debt stayed unchanged: Ruff `2 → 2` on untouched lines; strict mypy `0 → 0`.

Final full suite: `20 failed, 1345 passed, 24 skipped, 2 warnings, 5 collection errors, 4 subtests passed in 304.40s`. All 20 failed test IDs and all five collection errors equal the complete §0.2 `BASELINE_FAILURES` lists; there are no new failures. The exact IDs are recorded in `PHASE2_CLOSE_LOG.md` under §0.2.
