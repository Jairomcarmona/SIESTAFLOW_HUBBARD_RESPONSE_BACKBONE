# TASK 23 — Translation-shadowed production

## Item status and commits

| Item | Result | Commit |
|---|---|---|
| 23.0 | Task specification and decisions D14a–D14e recorded | `632725e` |
| 23.1 | Species identity from the global basis and MnO planning | `7bf8ac6` |
| 23.2 | Complete I.5 shadow state gate | `a54e9bb` |
| 23.3 | TS admission, parent-DM check, rejection policy and replay | `b020002` |
| 23.4 | Validated reference-only product run | `bc1ef2d` |
| 23.5 | Compact plan report and reason-derived actions | `1623d91` |
| 23.6 | **PAUSADO** at safe node boundary; real validation incomplete | pending stop-record commit |
| 23.7 | Not run per user direction; no Cu3N campaign or TS probe | — |

No premise checked for 23.1–23.5 was false. Premise commands, code/test scope, review notes and item verification evidence are recorded in [TASK23_LOG.md](TASK23_LOG.md). No scientific baseline files were changed.

## Changes and test/golden record

- 23.1 updated only the authorized identity/planning tests and the CoO identity expectation. Four task10 report goldens (CoO, NiO, FeO and Cu3N) changed only by removal of `SPECIES_IDENTITY_NOT_ESTABLISHED`; no strategy or reduction fields changed. The NiO replay manifest changes were limited to the authorized manifest, campaign config and resolved-plan paths. Exact hashes and summaries are in the log.
- 23.2 added `test_shadow_state_gate.py` for complete, incomplete and reconstructed-column evidence, and updated the authorized campaign-shadow oracle signature. No golden changed.
- 23.3 added/updated only product admission, CLI, campaign-plan and campaign-shadow tests; added the authorized MnO TS POSIX replay. No golden or replay fixture changed.
- 23.4 updated only the authorized campaign-runner and product CLI tests and added the product-reference POSIX integration test. No golden changed.
- 23.5 updated only the authorized MnO product-report test. No golden changed.
- Verification summaries across 23.1–23.5, including focused and full-suite runs, are recorded per item in `TASK23_LOG.md`; the MnO TS replay passed before the real campaign. The exact authorized golden differences are listed in the 23.1 log section.

## MnO real campaign — partial evidence, PAUSADO

The campaign used the frozen checkout `code_1623d91` and its recorded `hubbardflow.__file__`. `hubbardflow stop` requested the campaign's safe boundary stop at 2026-10-05 03:18:21 UTC (2026-10-04 21:18:21 -0600). At that instant, 22 of 48 response nodes were complete; `response:lr_s001_p0p05_screened` was active at SCF iteration 5. Safe-stop semantics allowed that node to finish and launched no following node.

At 2026-10-05 03:53:18 UTC (2026-10-04 21:53:18 -0600), the campaign reported `STOPPED / safe_stop_requested`, no active node and 23 of 48 response nodes validated. The final node completed 10 SCF iterations. Its run duration was included in the campaign wall time of 18 h 11 min 49.63 s. A fresh WSL shell rechecked the stopped status and process table; no SIESTA process, MPI launcher or campaign worker remained.

The planning and campaign reference DM matched (SHA-256 `c8fae5a1f51f7b256bc9e474feab80155f4b3665ba8599f9f8516620ff0587d1`) and differed from archived parent DM `65d418d1a21b4b4052d41d68554639fc4bc4682566bb780c0d072fd4cfe5eb47`. The plan contained two eight-site translation classes, four computed columns and 48 response nodes. Since the run was intentionally paused before completion, gates a–e remain unevaluated, there is no production U-by-site table, and no real-run verdict is assigned: **23.6 PAUSADO**, not `TS_NOT_VALIDATED`. No resume was performed.

## Cu3N

23.7 was not run, as directed. No Cu3N entry discovery/hash diagnostic, reference timing, TS reduction classification, single-column probe, or “Failures in HubbardFlow code” result was collected. This summary does not infer those results from planning goldens.

## Publication and CI

The final docs-only stop record and summary are being published on `fdebq/r7-task23-ts`. No PR will be opened and no merge will be performed. CI status and run links are included in the completion report.
