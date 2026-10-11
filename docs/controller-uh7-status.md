# U-H7 installed controller: partial implementation

Specification: DFT Lab ADR-017 including Adendas 1–3, main `880cca4`.
This branch is a draft. It does not qualify HF-1 or authorize scientific reuse.

The installed `hubbardflow-controller` console script receives the native
reservation and explicit prior-ledger paths. The complete native campaign root
is inside `paths.state_dir`. Hosts, ranks, launcher and deadlines come from the
descriptor. Inner launches remain in the supervisor's process tree; SIGTERM
requests cooperative stop. Attempt books append and fsync native events,
including settlement only after the complete native step and checkpoint.

Retries measure the frozen baseline and call the existing public `check_resume`
with no responses. The B.3 evaluator matches all 23 normative resume vectors;
scientific effect remains NONE. Terminal recovery precedes rule 6, derived
warnings preserve native recomputation, and history reconciliation checks full
launch identities. The real `prepare_controller_attempt` route rejects a
settlement detached from its finished trace. A new intent clears stale observer
completion before a same-key shadow fallback. Frozen request DTOs change no
wire fields. Four native schemas are bundled byte-identically, alongside all
three existing public API schemas.

Windows11 / CPython3.12.10 / uv0.11.14: the controller, campaign, architecture
and four frozen scientific regression families give 104 passed, 1 skipped
(3.34 s). Ruff check and format pass; strict mypy passes seven source modules;
the V6 integrity gate passes. The earlier complete local suite gave 1796 passed,
32 skipped, 22 xfailed and seven failures also reproduced at the base pin:
four coverage goldens, execution geometry identity and two phase-2 goldens.
No golden, known-failure allowlist, formula, gate or tolerance was changed.

The public consumer workflow additionally installs the built wheel in a fresh
environment using locked hashed dependencies, runs copied controller tests via
`python -I` outside the checkout, checks the declared installed entrypoint and
all four schema hashes, and exercises synthetic child-process lifecycle. This
is not the full installed synthetic campaign acceptance in ADR B.5, nor a real
SIESTA/Slurm qualification. Published-commit Windows/WSL evidence and CI results
must still be recorded after rebuilding from a clean source snapshot.

## Early retry admission correction

B.3 rules1–3 now run under the native worker lock before loading the campaign
or performing scientific admission. The original baseline must be a complete
public check_resume request and preserve B.2's literal expected/observed
equality; refreshing evidence cannot repair a truncated or inconsistent baseline.
Early refusal writes the unchanged verdict with checkpoint_identity null and
returns75. A neutral result still passes all native campaign, checkpoint and
artifact validations. Missing retry manifests reach the same refusal path.

Stop received before an inner launch is cooperative, emits no intent and closes
already opened handles. Windows11/Python3.12.10: focused controller and architecture
tests45PASS/2SKIP; Ruff global199files and strict mypy221files PASS. The native
flock exclusion test requires POSIX. Source CI and the external installed-wheel
consumer both include the new preflight suite; its public synthetic plan helpers
are copied without running their unrelated golden tests. A source snapshot with
this correction produced an isolated wheel consumer result of37PASS/2SKIP on
Windows and39PASS on WSL (Python3.12.10, hashed locked dependencies, `-I`, no
PYTHONPATH, installed module and schema-hash checks). Commit18d6163 subsequently
passed all seven CI checks, including the complete Linux suite (1839 passed,
20 skipped, 22 xfailed). At that revision, schemas and scientific policies
were unchanged; the former #59 route is resolved by Adenda 3 below.

## Installed synthetic native campaigns

The wheel qualifier additionally runs seven POSIX campaign cases through the
installed console script and native initialization, runner, checkpoint and
resume API. A synthetic reference produces a native validated receipt without
running SIESTA or accepting scientific evidence. A neutral retry launches a
pending node and does not relaunch reference. Changed valid plan, policy,
pseudopotential and parent DM each return75, with no current intent and no
increase in the executable launch counter. Cooperative SIGTERM during the
next synthetic node records abandonment and does not settle that node.

Recovery preserves the native checkpoint and finished trace, omitting only the
final settlement row in a separate synthetic prior book. The next attempt
records SETTLEMENT_RECOVERED before its pending launch. This models one crash
window deterministically; it is not a process crash or a real SCF recovery.
Synthetic children have a finite lifetime, and timeout cleanup targets only
the test's own controller process. No process group or foreign PID is killed.

The qualifier installs locked hashed dependencies and a wheel into an external
temporary environment and runs these tests with `-I`, without PYTHONPATH or
checkout imports. Windows exercises platform rejection and skips seven POSIX
cases. The optional qualifier `--wheel` selects an explicit artifact; it adds
no controller argument or contract field. ROOT clean-source Windows regressions
and architecture:117 passed,9 skipped. Ruff and strict mypy pass; V6 is intact.
Published-commit wheel results and fresh Windows/Linux CI remain to be recorded.

## Adenda 3: inconsistent native identity result

- ADR-017 C.2 assigns `IDENTITY_MISMATCH` with `changed: []` to rule 1. The
  evaluator emits `REFUSE / RESUME_EVIDENCE_INVALID`, retains the five native
  fields literally, and sets `blocking: []`, `continuation: null`. An already
  loaded checkpoint retains its identity in the pure evaluator; preflight uses
  null because it rejects before loading. The controller preflight writes this verdict and
  returns 75 under the native worker lock before campaign admission, checkpoint
  loading, settlement recovery, or child creation.
- The installed consumer checks the copied 23 resume vectors and the updated
  resume-verdict schema. The 21 earlier vectors are unchanged; the two new
  vectors cover the inconsistent result both with a loaded checkpoint and with
  a checkpoint that cannot load. The previous 3 API schemas and the reservation
  and ledger schemas remain byte-identical.
- The normative resource hashes are schema
  `d825a369a57712a11ff346d2b9333bb5956a3a21efb75eabb3d3086748c25fd5` and
  23-vector fixture
  `8775f90fdfed832f5890d25566cf8e4e00682a37482b27ac2fa32e15507f2175`.
- Temporary installed-wheel consumers built from this working tree passed on
  WSL (`50 passed`, CPython 3.12.10) and Windows (`40 passed, 10 skipped`,
  CPython 3.12.10). Both used `-I`, locked dependencies, the installed console
  entrypoint, and all 23 vectors. These are local checks, not published-commit
  CI results or HF-1 scientific qualification. WSL wheel SHA-256:
  `e15decbd8321565a25c9f420b866a93d5a9b8b90e13f4ffc35584ca72453c1ed`;
  Windows wheel SHA-256:
  `275a579c3b479c58ee0ee7bfa7ecac1a45b11b1cadef6804dcbffcbdb53f3310`.

## Remaining acceptance gates

- The synthetic consumer cases do not prove real SIESTA cancellation/recovery,
  containment ownership, scientific reuse, or full HF-1 qualification.
- QRAFT integration and the published engine/runtime CI remain separate gates.
  HF-1 stays disabled until both engines are completed and verified against the
  fixed platform lock and the requested WSL qualification is complete.

HF-1 stays disabled and its capability at most CONTRACT_TESTED. No engine pin
or operational environment is updated by this draft.
