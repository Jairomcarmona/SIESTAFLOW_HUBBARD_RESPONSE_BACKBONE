# FD-EBQ — Codex task list, phase 1

Scientific reference: `docs/fdebq/HUBBARDFLOW_FDRC_INDEPENDENT_REVIEW.md`.
Repository rules: `AGENTS.md`.

Phase 1 is **diagnostic only**. Nothing in this phase changes how any existing
campaign selects alpha, fits responses, computes U or certifies it. Every task
below is one PR. Do them in order; each assumes the previous is merged.

Each task block is written so it can be pasted directly into Codex as the prompt.

---

## TASK 0 — Tooling and shared validators (no behaviour change)

**Goal.** Add lint/type tooling scoped to new code and a single home for
validation helpers.

**Do.**
1. In `pyproject.toml`:
   - add `hypothesis` and `ruff`, `mypy` to the `test` optional dependencies
     (do not change runtime dependencies or the NumPy constraint);
   - add `[tool.ruff]` with `line-length = 110`, `target-version = "py312"`,
     and `extend-exclude` listing every existing module except the new ones
     (simplest: `include = ["src/hubbardflow/domain/validation.py",
     "src/hubbardflow/domain/response_*.py", "tests/unit/test_response_*.py",
     "tests/unit/test_validation.py", "tools/fdebq_*.py"]`);
   - add `[tool.mypy]` with `strict = true` and `files` limited to the same new paths.
2. Create `src/hubbardflow/domain/validation.py` with:
   ```python
   class ValidationError(ValueError): ...
   def require_finite(value: object, label: str) -> float
   def require_positive_finite(value: object, label: str) -> float
   def require_nonnegative_finite(value: object, label: str) -> float
   def require_int(value: object, label: str, *, minimum: int) -> int
   def require_sha256(value: object, label: str) -> str   # lowercase 64-hex
   def require_fdf_representable_ev(value: float, label: str, *, decimals: int = 4) -> float
   ```
   Booleans must be rejected where numbers are expected (as existing code does).
3. Tests `tests/unit/test_validation.py` (include hypothesis tests for NaN/inf/bool rejection).

**Do not.** Refactor existing modules to use the new helpers in this PR.

**Done when.** New tests pass; `ruff check`, `ruff format --check`, `mypy --strict`
pass on the new files; the V6 integrity gate in `AGENTS.md` is clean.

---

## TASK 1 — `ResolvedResponseProtocol` (data model only)

**Goal.** Introduce the object that crosses the boundary between perturbation
strategy and production analysis (review §M.2). It must express per-(site, mode)
amplitudes and estimator, which the current global `alpha_grid_ev` cannot.

**Create** `src/hubbardflow/domain/response_protocol.py`:

```python
class PerturbationStrategy(str, Enum):
    FIXED_PROTOCOL_GRID = "FIXED_PROTOCOL_GRID"
    USER_EXPLICIT_GRID = "USER_EXPLICIT_GRID"
    CALIBRATED = "CALIBRATED"            # declared but not executable in phase 1

class ResponseMode(str, Enum):           # reuse domain.symmetry_reduction.ResponseMode if
    BARE = "BARE"                        # it has exactly these members; do not duplicate
    SCREENED = "SCREENED"

class EstimatorKind(str, Enum):
    CENTRAL = "CENTRAL"
    RICHARDSON_2 = "RICHARDSON_2"
    POLYNOMIAL_LSQ = "POLYNOMIAL_LSQ"    # V6 production: degree 3
    LINEAR_LSQ = "LINEAR_LSQ"

@dataclass(frozen=True)
class EstimatorSpec:
    kind: EstimatorKind
    polynomial_degree: int | None        # required for POLYNOMIAL_LSQ only
    amplitudes_ev: tuple[float, ...]     # positive magnitudes actually used, sorted
    def weights(self) -> tuple[tuple[float, float], ...]:
        """(alpha_ev, weight) pairs such that chi_hat = sum w * n(alpha)."""

@dataclass(frozen=True)
class ColumnPlan:
    site_id: str
    mode: ResponseMode
    amplitudes_ev: tuple[float, ...]     # positive magnitudes; +/- both executed
    estimator: EstimatorSpec
    scf_level_id: str

@dataclass(frozen=True)
class ResolvedResponseProtocol:
    schema: str                          # "hubbardflow.resolved_response_protocol.v1"
    strategy: PerturbationStrategy
    protocol_version: str
    reference_node_id: str
    observable_id: str                   # e.g. "siesta_occupations_total"
    columns: tuple[ColumnPlan, ...]      # sorted by (site_id, mode)
    def is_common_grid(self) -> bool
    def digest(self) -> str              # sha256 of canonical JSON of to_mapping()
    def to_mapping(self) -> dict[str, object]
    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> "ResolvedResponseProtocol"

def protocol_from_fixed_grid(
    site_ids: Sequence[str], alpha_grid_ev: Sequence[float], *,
    estimator: EstimatorKind, polynomial_degree: int | None,
    scf_level_id: str, reference_node_id: str, observable_id: str,
    strategy: PerturbationStrategy = PerturbationStrategy.FIXED_PROTOCOL_GRID,
    protocol_version: str,
) -> ResolvedResponseProtocol
```

**Rules.**
- Validate: symmetric magnitudes, FDF-representable, distinct, every declared
  site has exactly one BARE and one SCREENED column, estimator has enough
  amplitudes for its kind/degree, `POLYNOMIAL_LSQ` weights computed exactly as
  `domain/matrix_lr.py::fit_polynomial_response` would (same scaling, same
  design including or excluding alpha=0 as that function does — read it first).
- `weights()` must reproduce, for the V6 grid {±0.02, ±0.04, ±0.06}: sum|w| = 21.43/eV
  for LINEAR_LSQ and 58.33/eV for POLYNOMIAL_LSQ degree 3 (review §C.2).
- `digest()` is invariant to the order in which columns are supplied.

**Tests** (`tests/unit/test_response_protocol.py`): round-trip mapping; digest order
invariance; rejection of asymmetric/unrepresentable grids; V6 weight sums above;
for the polynomial estimator, `sum(w * n(alpha))` equals `fit_polynomial_response(...)`
slope on random data to 1e-12.

**Do not.** Wire this into `campaign_v2.py`, `lr_dag.py` or the runner yet.

---

## TASK 2 — `response_error_budget.py` (pure diagnostic mathematics)

**Goal.** Implement review §I.1–§I.4 as pure functions. No decisions about
PASS/FAIL beyond reporting admissibility of candidates.

**Create** `src/hubbardflow/domain/response_error_budget.py`:

```python
class BoundKind(str, Enum):
    BOUND = "BOUND"          # print quantization (rigorous)
    ESTIMATE = "ESTIMATE"    # SCF ladder (a-posteriori) — not produced in phase 1
    DIAGNOSTIC = "DIAGNOSTIC"

class OrderStatus(str, Enum):
    VERIFIED_2 = "VERIFIED_2"
    VERIFIED_1 = "VERIFIED_1"
    UNRESOLVED = "UNRESOLVED"       # drifts within noise
    INCONSISTENT = "INCONSISTENT"

@dataclass(frozen=True)
class PointObservation:              # one printed occupation
    alpha_ev: float
    occupation_e: float
    half_width_e: float              # print half-step from occupation_precision.py

@dataclass(frozen=True)
class ElementSeries:                 # one (perturbed J, mode, observed I)
    site_perturbed: str
    mode: ResponseMode
    site_observed: str
    reference_occupation_e: float
    reference_half_width_e: float
    points: tuple[PointObservation, ...]

@dataclass(frozen=True)
class NoiseModel:
    eps_abs_e: float = 0.0           # phase 1: zero, kind BOUND only (print);
    eps_rel: float = 0.0             # filled by the SCF ladder in phase 2
    kind: BoundKind = BoundKind.BOUND

@dataclass(frozen=True)
class OddEvenDecomposition:
    amplitudes_ev: tuple[float, ...]
    odd_e: tuple[float, ...]
    slopes_e_per_ev: tuple[float, ...]
    slope_noise_e_per_ev: tuple[float, ...]
    even_e: tuple[float, ...]
    even_fit: tuple[float, float, float] | None   # (delta0, c2, c4) when >= 3 amplitudes

@dataclass(frozen=True)
class CandidateBudget:
    estimator: EstimatorSpec
    estimate_e_per_ev: float
    noise_e_per_ev: float
    truncation_e_per_ev: float
    order_status: OrderStatus
    admissible: bool
    reasons: tuple[str, ...]          # stable reason codes
    @property
    def total_e_per_ev(self) -> float

@dataclass(frozen=True)
class ElementBudgetReport:
    series_key: tuple[str, ResponseMode, str]
    decomposition: OddEvenDecomposition
    drift_ratios: tuple[float | None, ...]
    candidates: tuple[CandidateBudget, ...]
    best: CandidateBudget | None      # argmin total among admissible; deterministic tie-break

def decompose(series: ElementSeries, noise: NoiseModel) -> OddEvenDecomposition
def verify_order(dec: OddEvenDecomposition) -> tuple[OrderStatus, ...]   # per drift pair
def candidate_budgets(dec: OddEvenDecomposition, orders: Sequence[OrderStatus],
                      *, protocol_estimator: EstimatorSpec | None,
                      kappa: float) -> tuple[CandidateBudget, ...]
def element_report(series: ElementSeries, noise: NoiseModel, *,
                   protocol_estimator: EstimatorSpec | None, kappa: float) -> ElementBudgetReport

@dataclass(frozen=True)
class ReciprocityResidual:
    pair: tuple[str, str]
    mode: ResponseMode
    residual_e_per_ev: float
    allowed_e_per_ev: float
    consistent: bool

def reciprocity(reports: Sequence[ElementBudgetReport], *, kappa: float) -> tuple[ReciprocityResidual, ...]

def u_influence(chi0: np.ndarray, chi: np.ndarray) -> tuple[np.ndarray, np.ndarray]
    """dU_KK/dchi0_IJ and dU_KK/dchi_IJ, shape (N, N, N)."""
```

**Formulas.** Exactly those of review §I.2 (order verification with the general
ratio rho_p = (a_{k+2}^p - a_{k+1}^p)/(a_{k+1}^p - a_k^p)), §I.3 (central,
Richardson only when order 2 verified, protocol estimator via its weights) and
§I.4 (neighbour consistency with `kappa`). `kappa` is a required argument with
no default. Use the reference prototype `docs/fdebq/fdrc_review_numerics.py`
(function `qualify`) only as a cross-check, not as the implementation.

**Invariants to test** (`tests/unit/test_response_error_budget.py`):
1. Adding any even function (constant, c2·a², c4·a⁴, reference offset) to the
   data changes no slope, no candidate estimate, no truncation bound.
2. Permuting `points` changes nothing.
3. Synthetic analytic data with print quantization only: the true chi lies
   inside `best.total_e_per_ev` for ≥ 99% of 400 seeded trials (BARE-like and
   SCREENED-like parameter sets from review Appendix 2).
4. Odd non-analytic term `k*a*|a|`: order never reported as VERIFIED_2;
   coverage still holds.
5. Non-finite input, asymmetric amplitudes, missing ±a partner → `ResponseBudgetError`.
6. Frozen-data regression (read-only): load
   `results/stage-ub-v6-observables/coo-u-b-campaigns/stageubv6-coo-a0/lr_u_analysis.v3.json`
   and assert, within 1e-9: BARE chi0[0,0] central slopes
   (-1.351575, -1.340237, -1.321592); drift ratio 1.645 ± 0.001;
   BARE even-fit delta0 = 1.92e-5 ± 1e-8 for (J=0, I=0); SCREENED cross reciprocity
   residual at a=0.02 equal to 0 within print bound. If the file is missing,
   `pytest.skip` with the reason — never fabricate the fixture.

**Do not.** Compute or report U; produce PASS/FAIL statuses; touch existing modules.

---

## TASK 3 — Read-only sidecar diagnostic tool

**Goal.** Let a human run FD-EBQ diagnostics on any existing analysis without
touching campaign folders.

**Create** `tools/fdebq_diagnose.py`:

```
python tools/fdebq_diagnose.py <lr_u_analysis.v3.json> --out <directory> --kappa <value>
```

- Builds `ElementSeries` from `response_observation_dataset.rows`
  (occupations and `occupation_half_widths_electron`), builds the protocol
  estimator from `estimator_policy` + `alpha_grid_eV` via TASK 1, runs TASK 2.
- Writes `fdebq_diagnostic.v1.json` and a short `FDEBQ_DIAGNOSTIC.md` into `--out`.
- **Refuses** to run if `--out` resolves inside `results/`, `benchmarks/`,
  `validation_observables_v6/`, `campaigns/*/results/`, or any directory
  containing the input file. Refuses if `--out` exists and is non-empty.
- Records the input file SHA-256, the protocol digest, `kappa`, package version
  and git commit (if available) in the output.
- Report wording: "diagnostic, print-quantization bounds only; SCF component
  not assessed". Never words like "certified", "accepted", "qualified".

**Tests** (`tests/unit/test_fdebq_diagnose_tool.py`): refusal paths; output
schema; byte-identical output for identical input (determinism; exclude
timestamps — do not write timestamps).

---

## TASK 4 — Deprecation notices (no behaviour change)

**Goal.** Make the overlapping alpha mechanisms visible as legacy.

**Do.**
- Add a module docstring paragraph and a `DeprecationWarning` on import-time use
  of public functions in `domain/alpha_selection.py` and `domain/adaptive_alpha.py`,
  pointing to the review §M.1. Keep behaviour identical; existing tests must pass
  (filter the warning in those tests if needed).
- Rename nothing yet. In `docs/fdebq/LEGACY_ALPHA_MECHANISMS.md`, document the
  two `AdaptiveAlphaPolicy` classes, where each is used
  (`execution/campaign_runner.py::_execute_adaptive_gate` → `decide_round`;
  `tools/*` → `authorize_alpha_window`), and that `decide_round`'s
  `STOP_STABLE` uses U stability (review finding 9).

**Do not.** Change `adaptive_alpha_control.py` logic or the runner. That is phase 2
and requires explicit scientific sign-off.

---

## Phase 2 (do not start without explicit instruction)

For awareness only: SCF tolerance ladder nodes and `scf_tolerance_ladder.py`;
`response_state_gate.py`; `response_qualification.py` (decision f(E, P) and next
round g(E, P)); replacing the `decide_round` call in the runner; per-mode
data model wired into `lr_analysis_v2`; `perturbation_strategy` in
`campaign_v2.validate_lr_config`. These depend on validation results (review §L).
