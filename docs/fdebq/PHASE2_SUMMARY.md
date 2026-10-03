# FD-EBQ Phase 2 implementation summary

This records the resumed task sequence requested for Phase 2. Each task was
implemented on its own stacked branch in this order: 10, 12, 13, 14, 16, 17,
18, 19, 15. `AMENDMENTS_2.md` was committed first (`9a60d78`) before the task
branches. No pull requests were opened and no SIESTA campaigns were run.

| Task | Branch | Implementation commit | Status and verification |
|---|---|---|---|
| 10 — coverage qualification | `fdebq/r2-task10-coverage` | `1bba765` | Implemented D1/D2 diagnostic qualification and golden contracts. Cu3N archive cannot be a positive reference because input and output disagree; MnO semantic species identity is incomplete. 27 focused and 70 scientific regression tests passed; Ruff, format, mypy and V6 gate passed. |
| 12 — resolved plan | `fdebq/r2-task12-plan` | `6f970bb` | Frozen typed plan and digest; fixed-grid identities retained; calibrated strategy remains disabled here. 27 focused and 70 scientific regression tests passed; Ruff, format, mypy and V6 gate passed. |
| 13 — campaign v2 | `fdebq/r2-task13-campaign-v2` | `b66e370` | Inventory/config/lock integration implemented and checked against complete frozen fields. Operational pilot-reuse producer/source remains OPEN / NOT_ESTABLISHED. 81 focused and 70 scientific regression tests passed; Ruff, format, mypy and V6 gate passed. |
| 14 — translation shadow | `fdebq/r2-task14-shadow` | `5038065` | Additive shadow budget, expansion, resume and raw response evidence implemented. Production I.5 state producer remains absent; production classes conservatively expand and cannot become PROVEN. 320 focused and 70 scientific regression tests passed; Ruff, format, mypy and V6 gate passed. |
| 16 — calibrated rounds | `fdebq/r2-task16-calibrated-rounds` | `8e44282` | Deterministic minimax estimators, first-order refinement selection and elementwise MatrixBox qualification implemented with unchanged certification. Runtime state and prospective T0–T4 evidence remain OPEN. 136 focused and 70 scientific regression tests passed; Ruff, format, mypy and V6 gate passed. |
| 17 — SCF ladder | `fdebq/r2-task17-scf-ladder` | `e2a7a88` | D5 ladder/envelope, BOUND vs ESTIMATE separation, validator/materializer and user runbook implemented. Production I.5 and prospective T0–T4 evidence remain OPEN. 119 focused and 70 scientific regression tests passed; Ruff, format, mypy and V6 gate passed. |
| 18 — spin and rotations | `fdebq/r2-task18-spin-rotations` | `81b5f85` | D7 flags are explicit, default-off, digest-bound and conservative. Prospective V2/V3/V4 evidence and runtime I.5 remain OPEN. 264 focused and 70 scientific regression tests passed; Ruff, format, mypy and V6 gate passed. |
| 19 — product CLI | `fdebq/r2-task19-product-cli` | `74ea767` | Product plan/run/submit boundary, frozen snapshot verification and protected output paths implemented. Commands stop before execution while upstream pilot, runtime-state, calibrated-validation and generated identity evidence are absent. 63 focused and 70 scientific regression tests passed; Ruff, format, mypy and V6 gate passed. |
| 15 — species split | `fdebq/r2-task15-species-split` | `f79ef42` | D6 staging is opt-in/default-off, identity-bound and NOT_ESTABLISHED; no executable campaign or READY state is created. Typed generated-ion receipt requires exact raw SHA256 equality and never unlocks execution. Independent review found no P1/P2. 53 focused, 270 campaign/product integration and 70 scientific regression tests passed; Ruff, format, mypy and V6 gate passed. |

## Remaining production evidence

- TASK 13 operational pilot reuse remains `NOT_ESTABLISHED` because no
  production source/producer supplies the complete identity-bound receipt.
- The runtime producer for FDRC I.5 (occupied subspace/spectra, gap/Fermi and
  smoothness) is still absent. This prevents translation classes from being
  proven and blocks calibrated/product execution admission.
- Prospective T0–T4 validation and real V2/V3/V4 evidence have not been
  generated. Synthetic models and archived read-only checks do not replace
  these artifacts.
- TASK 15 has not run SIESTA or generated real alias ions. Its runbook describes
  the user-run exact-byte comparison; a receipt by itself cannot grant READY.
- TASK 19 reports downstream scientific outputs as `NOT_ASSESSED` while these
  dependencies are missing. No U certificate or production result is claimed.

The focused checks above were re-run by the orchestrator along with Ruff,
`ruff format --check`, strict mypy and `bash tools/check_v6_integrity.sh` on
each task's final diff before commit. The expanded historical suite retains the
known missing-fixture limitation documented in `BLOCKERS.md`; no historical
test or data were changed.
