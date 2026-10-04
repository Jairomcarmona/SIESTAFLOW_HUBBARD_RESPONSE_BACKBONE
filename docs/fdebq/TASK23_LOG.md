# TASK 23 execution log

## Preparation

- Read the complete repository `AGENTS.md` before editing.
- `git fetch origin` completed. `git diff --quiet a1b3c31 origin/codex/hubbardflow-rename` returned 0 with no output; the TASK 22 merge was present.
- Created `fdebq/r7-task23-ts` from `origin/codex/hubbardflow-rename`.
- The supplied `CODEX_TASK23_TS.md` was copied byte for byte (source and destination SHA-256 `3b34b6670dff30601cbab6e47ed4d02308ff8db00bc64a4d40a4b6e1717246bf`). D14a–D14e were appended under `TASK 23` in `AMENDMENTS_2.md`. The docs-only commit is `632725e`.
- The docs-only diff was checked by `verificador_luna`. Post-commit gates: WSL NiO P5 replay 7 passed; golden 20.9 4 passed; product tests 110 passed; scientific regressions 70 passed; architecture 8 passed; `ruff check .` passed; `ruff format --check .` reported 91 files already formatted; `MYPYPATH=src mypy` succeeded on 91 files; V6 gate printed `V6 GATE OK`; full suite reported 1395 passed, 27 skipped, 20 xfailed, 4 subtests passed, 2 warnings.

## 23.1 — species identity from the global basis

### Premises checked before implementation

| Premise | Real command/evidence | Result |
|---|---|---|
| Identity required a known pseudo and an explicit `PAO.Basis` record. | `Get-Content src/hubbardflow/siesta_backend/fdf_model.py` around `species_identity`; the original status expression required both `pseudo_digest` and `basis_digest`. | Confirmed. |
| No repository FDF declares a `%block PAO.Basis`; repository block names match the audited set. | `rg -n -i '^\\s*%block\\s+pao\\.basis\\b' --glob '*.fdf'` had no matches. A repository-wide `rg` enumeration found only `atomiccoordinatesandatomicspecies`, `bandlines`, `bandpoints`, `chemicalspecieslabel`, `dftu.hubbard`, `dftu.proj`, `dftu.projector`, `dm.initspin`, `kgrid_monkhorst_pack`, and `latticevectors`. | Confirmed. |
| MnO source is the expected unperturbed reference FDF. | `Get-FileHash campaigns/mno_afmii_strict_lr_v3r2/results/response-matrix-foreground-recovery-v4/00_REFERENCE/siesta.fdf -Algorithm SHA256` | `3c86abab6daf4c0c00a10da6a7e060470e54bcc5364f70a0e2932285c24941e6`. |
| Old PAO parser dropped all fields on the first row after the label. | Read `parse_effective_fdf` around its `pao_basis_blocks` construction. | Confirmed: initialized each PAO entry with an empty row list. |
| Planning callers ignored the explicit lr-config map; runtime inventory must remain unchanged. | `rg -n 'species_identity\\(' src/hubbardflow/...` and source reads of `product_plan.py`, `campaign_plan.py`, and `campaign_inventory`. | Confirmed: product/campaign planning passed only parent directories; runtime `campaign_inventory` passes staged directories. |
| Archived MnO currently cannot establish identities; planning with a single Mn pseudo should make the translation plan usable. | Added regression using the archived FDF, explicit map for the 16 Mn labels plus O, and the archived `siesta.out`; it passes with 17 established identities, two 8-member classes, shadows MnLR02/MnLR03, 4 computed columns, 48 run specs, and `REVIEW/SHADOW_PENDING`. | Confirmed by `tests/unit/test_product_cli.py::test_mno_translation_shadow_product_plan_uses_single_file_species_map`. |
| Baseline focused parser/planner tests were clean. | `python -m pytest tests/unit/test_fdf_model.py tests/unit/test_campaign_plan.py -q` | 40 passed. |

No premise was false.

### Independent review and conservative choice

`auditor_cientifico` confirmed D14a is compatible with the coverage evidence contract and found no scientific choice blocking implementation. The read-only check also showed fallback pseudopotential selection depended on the caller's directory order when duplicate files disagreed. The implementation sorts search directories and treats conflicting copies of the selected suffix as `NOT_ESTABLISHED`; this is recorded as **decisión del implementador (conservadora)**. Explicit map entries remain authoritative, and a missing mapped file does not fall back to directory search.

### Changes and authorized tests

- `species_identity` now accepts the optional explicit pseudopotential map, evaluates the audited neutral-block/global-basis rule, recognizes basis headers in identity digests, and fails closed for an incomplete PAO block set or enabled/unknown `User.Basis` controls.
- The product and campaign planning callers pass the lr-config map; runtime inventory callers remain unchanged.
- Bumped `CAMPAIGN_PLANNER_VERSION` to `campaign-planner-v4`.
- Follow-up audit confirmed an empty `%block PAO.Basis` contains no species records; the implementation therefore tests parsed records (`bool(basis_by_label)`), not merely block presence.
- Tests added/updated: FDF identity cases in `test_fdf_model.py`; the authorized CoO identity expectation plus missing-O control in `test_symmetry_operations.py`; planner v4 literals/name in `test_campaign_plan.py`; MnO TS product-plan golden in `test_product_cli.py`; shared-pseudopotential staged inventory digest in `test_product_execution.py`.
- No test assertion outside these item-authorized behaviors was changed.

### Golden updates

- `docs/fdebq/task10_reports/{CoO,NiO,FeO,Cu3N}.json`: each changed only `reasons[]`, removing `SPECIES_IDENTITY_NOT_ESTABLISHED`. No strategy or `would_reduce_to` field changed.
  - CoO: `abb0d72429bddc3c79e2d6e128b3e6133225c3d24ed294c7b9d3d483171a219f` → `8d4a1c976fda9e0f5dd2c6ffa91dd9060e3025e8c85e9c11a0ce1755704517a6`.
  - NiO: `025eb503d31cdc579afc3d9a4ae5bec6e968369684c7ea55c392965d1155f8a5` → `50336a4aeb3769109c3a68825758fb55e27577546d44101723040441d3f02449`.
  - FeO: `e59300867a624a406b4d7ad7198fbdd8c730f788f3804aeae36a0867e675cab7` → `3f1f8d3cba95ad3a32ea6010befc10049d75894996dbb8860be4c12ae624c158`.
  - Cu3N: `5c435dbe3196a16538ee2f866761cfea1ea180eb44297fafb17d705b78513b8e` → `af3bd903e7a02e82e16db73527e77a97ac5a60145022ef31544b58eb9e21c600`.
- WSL replay manifest differences were exactly the three authorized paths: `campaign.lock`, `campaign.v2.json`, and `resolved_perturbation_plan.json`. Only identity/F2-derived content and hashes changed; analysis equivalence, Part A U and I.5 assertions remained unchanged. The separate JSON snapshot is diagnostic and was regenerated.
  - Manifest file SHA-256: `7644a7f7abda043e851a1bc1cd30e19ad3edffffe35ca77b080bd29e8ca656a9` → `af86fdfa99c330548b9729ccc4f7533f60f594068dbd0dcd61c17e9906e55cbf`.
  - Snapshot file SHA-256: `a3825081551d2fb1bf18d459c65ea0688b60cbcfcb7dabf1224676538a7b167b` → `5fa071aef8590afb309a2e1c1ddadcc5a53fafbd2656f08aba24860e5501a758`.
  - Manifest entries: `campaign.lock` `468dfbc57ffb5952a9713dd1a8289e8d3ebd0ca9b1c9ee3b0bb2979ef9c9d892` → `d86108fbcf1d6e5d3206b98b512209e7c300368469c9fcbf750bb123d7588951`; `campaign.v2.json` `b018826f0fecffb5355db50eb81f44271ba76b950f3e2a8b072988ea7e3a4367` → `561fb80c765aaa58c2c938710688b853ca2f5a091d824f6697f9c06020265f08`; plan `3d201d120b6257f41982bded0f5ac3518a4aa4d246e74bbc89a0b925630acd3a` → `96ed7660e4f951114e8b9dcd292ea822e10619dd962d2ad257e5ae5fa3893726`.

### Verification so far

- Focused parser/planner/symmetry/product modules: 151 passed, 2 warnings. The final added absent-mapped-file case was separately run in the 19-test FDF module, which passed.
- NiO P5 replay in WSL after the authorized golden update: 7 passed, 2 existing deprecation warnings.
- Coverage and 20.9 golden tests: 52 passed, 2 warnings.
- Legacy resume plus campaign planning tests: 29 passed, 2 warnings.
- `verificador_luna` approved the final scope, including the tested conservative conflict handling; `auditor_cientifico` found no scientific blocker.

### Post-commit gates for 23.1 (`7bf8ac6`)

- WSL NiO P5 replay: 7 passed; golden 20.9: 4 passed; product group: 112 passed; scientific regressions: 70 passed; architecture: 8 passed.
- `ruff check .`: passed; `ruff format --check .`: 91 files already formatted; `MYPYPATH=src mypy`: success on 91 files; V6 gate: `V6 GATE OK`.
- Full suite: 1404 passed, 27 skipped, 20 xfailed, 4 subtests passed, 2 warnings.
- No post-commit failures or additional edits were needed.

## 23.2 I.5 shadow state gate

### Premise checks

- `rg -n "def _complete_state_gate|_complete_state_gate\\(|state_gate_mapping\\(" src/hubbardflow tests/unit/test_campaign_shadow.py` confirmed that the production gate returned `False`, `_outcomes` and `analysis_data` called it without a runner, and the synthetic test oracle was `lambda: True`.
- `rg -n "covered=not adaptive|def state_gate_mapping|class StateGateReason" src/hubbardflow` confirmed that the direct-analysis caller excluded TS (`covered=False`), the mapping had no column-index filter, and the reason enum had no reconstructed-column code.
- Independent `auditor_cientifico` read-only checks on archived MnO A/B × both modes × all six signed α found 4/4 PASS verdicts; point checks were G1 PASS=24, G2 PASS=768, G3a PASS=768, G4 NOT_AVAILABLE=24. This confirms that D14b must block the archived points absent `.EIG` for a production shadow proof.
- The same audit checked real NiO fixtures with and without `.EIG`: with `.EIG`, all four pairs and their point checks pass; without it, all four diagnostic verdicts still PASS while G4 is NOT_AVAILABLE=24. `tests/fixtures/replay_nio_p5/replay_i5_state_gate.json` has the latter structure. A 16-column replay mapping also confirmed that unfiltered reconstructed columns appear as failures due to absent validated nodes.
- The auditor verified index correspondence at `campaign_runner.py` by mapping `plan.inventory.subspaces` to runner sites by index, while plan `site_id` and runner labels intentionally differ. No premise was false. The existing `_response_node` alpha locator tolerance (`1e-14`) was noted as pre-existing and outside this item.

### Conservative decisions and edits

- Keep `site_indices=None` behavior unchanged. With a filter, mark excluded columns as `NOT_ESTABLISHED/RECONSTRUCTED_FROM_REPRESENTATIVE` without evaluating their nodes.
- The shadow gate requires both modes for every computed/expanded runner label, verdict `PASS`, at least one amplitude and both signed point records, and rejects point checks `FAIL`, `NOT_AVAILABLE`, or `NOT_ESTABLISHED`. `NOT_DEFINED` and `NOT_APPLICABLE` remain allowed. Reject malformed and duplicate pairs. Exclude the separate G3 smoothness result as D14b directs.
- 23.2 test edits: added `tests/unit/test_shadow_state_gate.py` for synthetic all-pass, G4 unavailable, failure, missing pair, allowed NOT_DEFINED, duplicates, real NiO `.EIG` fixtures passing the gate, actual NiO replay golden rejection, and reconstructed index filtering; adapted only the authorized R5 oracle signature in `test_campaign_shadow.py` from `lambda: True` to `lambda *_: True`. No golden files changed.
- Production changes are limited to `state_gate_results.py`, `state_gate_step.py`, `campaign_shadow.py`, and `campaign_runner.py`: wire index filtering into the TS diagnostic, compute the gate from current runner evidence, and expose its result in `translation_shadow.complete_state_gate`.
- Focused checks: `python -m pytest -q tests/unit/test_shadow_state_gate.py tests/unit/test_campaign_shadow.py` → 30 passed, 2 pre-existing deprecation warnings; `ruff check` on the new test and state-gate modules passed; `ruff format --check` on the five non-legacy touched Python files passed; `MYPYPATH=src mypy --strict` on `state_gate_results.py`, `state_gate_step.py`, and `campaign_shadow.py` passed; `git diff --check` passed.
- POSIX replay in WSL: `PYTHONPATH=src python3 -m pytest -q tests/integration/test_runner_replay_nio_p5.py` → 7 passed, 2 pre-existing deprecation warnings. Its manifest/golden remained unchanged.
- `verificador_luna` reviewed the diff twice. The first pass requested the explicit real NiO `.EIG` satisfiability case; that test was added and passed. The second pass approved the scope and found no functional blocker. The full legacy `campaign_runner.py` has existing Ruff formatting and strict-mypy findings outside this item’s hunk; no broad formatting/type edits were made.

### Post-commit gates for 23.2 (`36b7796`)

- WSL NiO replay: 7 passed; 20.9 golden: 4 passed; product group: 112 passed; scientific gates (`test_matrix_lr.py`, `test_quantized_response.py`, `test_u_certification.py`): 54 passed; architecture: 8 passed.
- `ruff check .`: passed; `ruff format --check .`: 91 files already formatted; `MYPYPATH=src mypy`: success on 91 files; V6 gate: `V6 GATE OK`.
- Full suite: 1412 passed, 27 skipped, 20 xfailed, 2 warnings in 338.62s. No test failures.
- Golden files remained unchanged.
