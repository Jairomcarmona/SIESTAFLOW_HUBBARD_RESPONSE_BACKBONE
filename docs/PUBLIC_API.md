# HubbardFlow public native API 1.0

Integration lineage: `codex/hubbardflow-rename`. Distribution `hubbardflow`
0.1.3, CPython `>=3.12,<3.13`, NumPy `>=1.26.4,<2`. The qualified target is
CPython 3.12.10 with NumPy 1.26.4 and jsonschema 4.23.0 on Windows and Linux/WSL.
`uv.lock` records the complete environment; uv 0.11.14 is used by CI.
The Linux full historical suite remains an independent mandatory check.
The worker still requires Linux/WSL `fcntl`; Windows supports transport and
analysis, not campaign execution. No SIESTA, MPI, SSH or SLURM is launched by
this API or its qualification tests.

Only `hubbardflow.api.__all__`, documented execution/backend interfaces and
the existing CLI are public. Consumers must not import `hubbardflow.domain`
or private names. The facade alone may call the existing domain functions.
`describe_capabilities()` describes installed interfaces, not scientific or
HF-1 runtime qualification; `runtime_qualified` is explicitly false. The
Hubbard layer belongs under QRAFT in operational integrations. Actual HF-1
allocation/cancellation/ownership integration follows in the adapter release;
HF-2 fragment export is not implemented or advertised here.

```python
from hubbardflow import api

descriptor = api.describe_capabilities().to_mapping()
receipt = api.resolve_plan(native_request)
native_plan = receipt.to_mapping()["payload"]
native_digest = receipt.native_digest
```

Every function returns a frozen `ApiResult`, with a fresh JSON copy from
`to_mapping()` and explicit `from_mapping()` round trip. Inputs are finite
JSON trees; nested native fields must be explicit. Unknown request keys,
missing policy fields, boolean/number coercion and NaN/Infinity are rejected.
No tolerance or physical evidence is injected by the facade. Printed decimal
tokens remain strings and are interpreted only by their existing domain gate.

| Operation | Request | Payload / native status |
|---|---|---|
| `describe_capabilities()` | No arguments | Versions, operations, strategies, targets, schemas, `U_scalar_charge`, runtime unqualified |
| `resolve_plan(request)` | Native inventory, coverage, response protocol; `source_fdf_sha256`, `alpha_strategy`, `planner_version`, `backend_identity`, explicit `tau_u_ev`; optional explicit sites/calibration protocol and qualification | Existing plan mapping; `READY`, `REVIEW`, `NOT_ESTABLISHED`, `FAIL` unchanged |
| `validate_observation(request)` | `observation` and `expected`: complete native Observation / RunIdentity JSON records | Validated observation hash; semantic validation, not hash equality alone |
| `evaluate_gate(request)` | Native PointState `reference`, `column_id`, `mode`, array of StateGatePoint `points` | Existing I.5 StateGateResult mapping and native verdict |
| `analyze(request)` | Array of native ResponseObservation `observations`; complete LRAnalysisPolicy `policy` including nulls | Existing v2/v3 native analysis, candidates and exact proof tokens; physical acceptance unchanged |
| `check_resume(request)` | Expected/observed complete native plans/policies, file hash observations, response identity pairs | Changed inputs and native reuse qualifications; no files touched, worker started or resume approved |
| `worker_status(request)` | `snapshot`: previously observed native worker-state JSON | Snapshot unchanged, execution status never interpreted as science |

Serializable analysis options mirror the native analyzer: `campaign`,
`scf_validated`, `active_window_ev`, `occupation_source`,
`occupation_noise_calibration`, `response_grid_reproducibility_calibration`.
Tuple-key maps use rows: `magnetic_state_labels` contains
`{alpha_ev, label}`; `trace_half_widths_electron` contains
`{perturbation_site, alpha_ev, mode, half_widths_electron}`. Duplicate identities
are rejected. Projector fingerprint object keys are canonical nonnegative
integer strings; the facade restores the native integer keys.

Resume `files` rows contain `{artifact_id, expected_sha256, observed_sha256}`
(`observed_sha256` may be null). `responses` contain
`{response_id, pilot, production}` with complete native ResponseRunIdentity
records. These are caller-supplied observations, not independent proof of
physical validity. Matching digests never establish physical equivalence:
the existing policy returns `NOT_ESTABLISHED`, even for identical records,
so `reusable_response_ids` is empty. A native identity mismatch, changed plan,
policy or file is visible, with direct recalculation required. The caller
remains responsible for observing worker termination and scheduler ownership.

`PublicApiError.kind == ApiErrorKind.TRANSPORT_INVALID` denotes malformed
transport. `ScientificEvidenceError.kind == ApiErrorKind.SCIENTIFIC_REJECTION`
preserves a rejection from native observation/gate/analysis evaluation;
adapters must record a scientific assessment, never turn it into an HTTP
transport failure or introduce a fallback. Such exceptions preserve the
native cause. Positive scientific decisions and non-establishment travel as
native result payloads/statuses. No new mathematical rule is introduced.

## Digests and schemas

`native_digest` is opaque native metadata, not a hash of the API envelope.
For `resolve_plan`, it is exactly `ResolvedPerturbationPlan.digest`: SHA-256
of the native mapping with compact separators, sorted keys, `allow_nan=False`,
and **ensure_ascii=True**. For `validate_observation`, it is the native
observation provenance hash, whose canonical JSON uses **ensure_ascii=False**.
Other operations do not invent a digest. Platform adapters must carry the
correct operation-specific algorithm and source contract; they must not
recalculate either digest using JCS or QRAFT's encoding.

Schemas are installed wheel resources available via
`api.get_schema(schema_id).to_mapping()`:

- `hubbardflow.api_result.v1`: immutable receipt, closed operation/version,
  open native status and conservative transport assessment.
- `hubbardflow.analysis_result.v1`: native v2/v3 analysis payload, explicitly
  `U_scalar_charge`, eV and `physical_acceptance: NOT_ESTABLISHED`.
- `hubbardflow.worker_status.v1`: existing native worker snapshot payload,
  with open execution status and preserved legacy fields.

Native analysis payloads and CLI status files are not rewritten to the new
envelope. The facade wraps them; schemas do not rename or recanonicalize them.
`NumericalStatus` names the five existing candidate/absence values plus
`NOT_ESTABLISHED`. Unknown future native statuses survive round trips and
project to `SafeAssessment.NOT_ESTABLISHED`, never `PASS`. `FAIL` and
`IDENTITY_MISMATCH` project to failure; ready/validated/completed/certified
tokens do not imply scientifically accepted U. Inverse `CERTIFIED` proves an
interval inversion, not physical acceptance of Hubbard U.

API/schema incompatible changes require a new major version and explicit
consumer migration; closed request/operation enum additions also require
compatibility review. Unknown native *result* values are safe by design.
Historical native schema and digest identities remain unchanged. Versions
identify contracts, not a claim of full scientific qualification.

## Reproducible checks

```text
uv sync --locked --extra test --python 3.12.10
uv run --locked --extra test python -m pytest -q tests/unit/test_public_api.py tests/unit/test_public_api_schemas.py
uv run --locked --extra test ruff check .
uv run --locked --extra test ruff format --check .
uv run --locked --extra test mypy
uv build --no-build-isolation --wheel
uv run --locked --extra test python tools/qualify_public_api.py
bash tools/check_v6_integrity.sh
```

The installed consumer creates a temporary environment outside the checkout,
installs locked hashed runtime dependencies and the built wheel, removes
PYTHONPATH/PYTHONHOME and executes Python `-I`. Six frozen synthetic consumer
cases compare facade payloads/digests with the original native entrypoints at
e508f47 (ready/review/non-established plan, observation, gate and analysis).
Analysis compares the native entrypoint and facade exactly within the same
numerical environment; no cross-OS BLAS byte identity or new tolerance is
asserted. The installed consumer checks analysis schema, statuses, policy,
units and semantics; the scientific regression suite checks the mathematics.
The fixtures are read-only after generation; see their provenance README.
No scientific baseline path, tolerance, policy implementation, inversion or
existing CLI behavior is modified. The former stale uv lock describing the
`siestaflow-hubbard` distribution is regenerated for the actual distribution.
