# AGENTS.md — HubbardFlow

Instructions for coding agents (Codex and others) working in this repository.
Read this file completely before changing anything.

## 1. What this project is

HubbardFlow orchestrates, analyses and certifies first-principles linear-response
Hubbard parameters computed with SIESTA by finite differences:

    chi_IJ = d n_I / d alpha_J at alpha = 0      (BARE chi0 and SCREENED chi)
    U = inv(chi0) - inv(chi)

Package: `src/hubbardflow/` (import `hubbardflow`, CLI `hubbardflow`).
Active branch lineage: `codex/hubbardflow-rename`.

Layering (respect it strictly):

- `domain/` — mathematics, policies, decisions. Pure: no file I/O, no subprocess,
  no clock, no randomness, no SIESTA knowledge.
- `siesta_backend/` — everything that interprets SIESTA inputs/outputs.
- `execution/` — DAG, runner, scheduling, persistence. Calls `domain/`; never
  re-implements scientific decisions.
- `reporting/` — rendering only.

## 2. Things you must never do

1. Never modify the frozen scientific baseline: tag `scientific-v6-final`
   (commit `45cb53c5a98d9d55a163c05ca3b815a8ff9cfb7f`) or any path listed in
   `docs/history/SCIENTIFIC_BASELINE_V6.sha256`. This includes
   `FINAL_SIESTA_VALIDATION_REPORT_V6.md`, `validation_observables_v6/`,
   `results/stage-ub-v6-observables/`, `FEO_SCF_DIAGNOSTIC_EXPORT_20261001/`,
   `benchmarks/lr_u/`, `campaigns/nio_pbe_p5_20260928/results/`,
   `production_benchmarks_v6.zip*`. Read them; never write, move, reformat or delete them.
2. Never change the definitions of chi0, chi or U, the direct-inversion policy,
   or `domain/u_certification.py`.
3. Never introduce a pseudoinverse, regularization, or silent fallback for a
   singular matrix.
4. Never select alpha, a window, an estimator or a stopping rule using the value
   of U, the stability of U between rounds, agreement with experiment/literature,
   or to improve a condition number.
5. Never infer site equivalences from element, label, coordination or chemical similarity, nor from the
   similarity of U values. Equivalences may be used to reduce perturbations only through a
   `CoverageQualification` produced by `domain/coverage.py`: operations satisfying F1–F8
   (`docs/fdebq/HUBBARDFLOW_PERTURBATION_PLANNING_REVIEW.md` §F) with declared tolerance bands, a mandatory shadow
   column per reduced class, and fallback to explicit perturbation of the whole class on any failure.
   User-declared equivalences may only restrict a reduction, never add one.
5b. Features listed as 'disabled by flag' in `docs/fdebq/CODEX_TASKS_PHASE2.md` (spin-flip ε=−1, rotations,
   automatic species splitting, calibrated α grid, optional shadow) must stay disabled by default and may be enabled
   only by an explicit policy value that is recorded in the plan digest.
6. Never invent numerical thresholds. Every tolerance lives in a versioned,
   explicit policy/protocol object and enters its digest. No hidden defaults.
7. Never introduce `File.DM.Init`; the restart route is `DM.UseSaveDM true`
   with the parent DM identity preserved.
8. Never "fix" pre-existing test failures caused by missing historical fixtures
   or the legacy `siestaflow_hubbard` namespace (see
   `docs/architecture/SCIENTIFIC_DECOUPLING_VERIFICATION.md`). Report them; don't touch them.
9. Never change existing behaviour of the FIXED_PROTOCOL_GRID path (V6
   reproduction) unless a task explicitly says so.
10. `tests/unit/test_import_architecture.py` must pass; its allowlists may only shrink.
11. Never import a private name (leading underscore) from another module, never call a
    private method of another class; existing cases are allowlisted for Phase 3.

## 3. Code style

- Python 3.12, NumPy `<2` as declared in `pyproject.toml`.
- Results and policies are `@dataclass(frozen=True)`. Decisions, statuses and
  reason codes are `Enum` (`class X(str, Enum)`), never free strings.
  Serialize with an explicit `to_mapping()` / `from_mapping()` pair.
- New public functions return typed dataclasses, not `dict[str, Any]`.
- Units in names: `alpha_ev`, `occupation_e`, `slope_e_per_ev`, `u_ev`.
- Fail closed: validate inputs, reject NaN/inf (also in JSON), raise a
  module-specific `...Error(ValueError)` with an actionable message.
- Determinism: iterate over sets/dicts in sorted key order; results must not
  depend on input order. Tie-breaks are explicit and documented.
- Distinguish error kinds explicitly: rigorous `BOUND` (print quantization) vs
  a-posteriori `ESTIMATE` (e.g. SCF ladder) vs `DIAGNOSTIC`. Bounds are added,
  never combined in quadrature.
- Shared validators go in `domain/validation.py`; do not copy
  `_positive_finite`-style helpers into new modules.
- Docstrings explain the scientific reason, assumptions and scope, not only the API.
- Keep new modules small (< ~400 lines). Do not add logic to
  `execution/campaign_runner.py` beyond calling domain functions.
- New modules must pass `ruff check`, `ruff format --check` and `mypy --strict`
  (configuration in `pyproject.toml`; legacy modules are excluded for now).

## 4. Tests

- Every new module gets tests under `tests/unit/`.
- Required test families for scientific code:
  1. synthetic ground truth (known chi, known higher-order terms, known noise);
  2. property tests (`hypothesis`): input-order invariance, rejection of
     non-finite data, bounds cover truth in well-specified cases;
  3. regression on frozen data, read-only.
- Focused commands (use these, not the full historical suite, as the gate):

```bash
python -m pytest -q tests/unit/test_<module>.py
python -m pytest -q tests/unit/test_lr_analysis_v2.py tests/unit/test_matrix_lr.py \
  tests/unit/test_quantized_response.py tests/unit/test_u_certification.py
ruff check <new files> && ruff format --check <new files>
mypy --strict <new files>
```

- V6 integrity gate (must stay clean before every commit):

```bash
bash tools/check_v6_integrity.sh      # prints "V6 GATE OK" and exits 0
```

The manifest `docs/history/SCIENTIFIC_BASELINE_V6.sha256` still lists
`src/siestaflow_hubbard/execution/u_certification_node.py`, which the namespace
migration moved to `src/hubbardflow/...`. That one known absence is the only
tolerated difference (documented in
`docs/architecture/SCIENTIFIC_DECOUPLING_VERIFICATION.md`). Any other mismatch or
missing file fails the gate. Do not edit the manifest to make it pass.

## 5. Scientific reference for the response-calibration work

The methodology being implemented is FD-EBQ (Finite-Difference Error-Budget
Qualification), specified in `docs/fdebq/HUBBARDFLOW_FDRC_INDEPENDENT_REVIEW.md`
(sections I, J, K, M, O). When code and that document disagree, stop and ask;
do not improvise science. Implementation tasks are in `docs/fdebq/CODEX_TASKS.md`.

## 6. Working agreement

- One task = one small PR. State in the PR description: what changed, what did
  not change, commands run and their output, and any open question.
- If a task requires a scientific choice not specified in the reference
  document, stop and write the question in the PR instead of choosing.
- Do not clean up unrelated files in the same PR.

## 7. Delegation (subagents)

The agent roles are defined in `.codex/agents/*.toml`; this section says when to use them.
The main agent is the orchestrator: it plans, delegates, integrates and reports. Subagent output is
a claim, not evidence — the orchestrator re-runs the gate commands itself and pastes their output.

| Work | Agent |
|---|---|
| FD-EBQ TASK 0, 1, 3, 4 (mechanical, closed spec) | `implementador_luna` |
| FD-EBQ TASK 2 and everything in phase 2 (error-bound mathematics) | `implementador_sol` |
| Read-only questions about code, outputs, docs | `explorador_luna` |
| Run tests / inspect a diff without changing it | `verificador_luna` |
| Independent scientific audit | `auditor_cientifico` |

Rules:
1. Only one implementer writes at a time (`implementador_luna` and `implementador_sol` never run in
   parallel). The sandbox does not enforce this; it is a rule. Read-only agents may run in parallel.
2. Every diff is checked by `verificador_luna` before the PR is opened.
3. `auditor_cientifico` is requested for TASK 2 and for any phase-2 change before the PR is opened
   (this section is the explicit authorization). Otherwise only when the user asks.
4. If `implementador_luna` fails the same invariant test twice, stop and ask the user to rerun with
   `implementador_sol`. Never weaken or delete a test to make it pass.
5. Never delegate a scientific choice (thresholds, estimator rules, decision logic). Those come from
   the review document or from the user.
6. Subagents do not open PRs, push, or run SIESTA campaigns; the orchestrator does, after the gates pass.
