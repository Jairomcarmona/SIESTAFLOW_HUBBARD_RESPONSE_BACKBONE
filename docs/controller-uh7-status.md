# U-H7 installed controller: partial implementation

Specification: DFT Lab ADR-017 including Adendas 1 and 2, main `9710b9e`.
This branch is a draft. It does not qualify HF-1 or authorize scientific reuse.

The installed `hubbardflow-controller` console script receives the native
reservation and explicit prior-ledger paths. The complete native campaign root
is inside `paths.state_dir`. Hosts, ranks, launcher and deadlines come from the
descriptor. Inner launches remain in the supervisor's process tree; SIGTERM
requests cooperative stop. Attempt books append and fsync native events,
including settlement only after the complete native step and checkpoint.

Retries measure the frozen baseline and call the existing public `check_resume`
with no responses. The B.3 evaluator matches all 21 normative resume vectors;
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

## Pending gates and acceptance

- [DFT #59](https://github.com/Jairomcarmona/dftlab-suite/issues/59): B.3 rule 2
  conflicts with schema minItems for IDENTITY_MISMATCH/FAIL with changed empty.
  That path raises an explicit design-gate error before producing a verdict;
  it is not claimed as a completed exit-75 contract. No placeholder, alternate
  reason or schema-validation bypass is introduced.
- Complete installed synthetic campaigns through baseline, `check_resume`,
  runner and exit 75, including changed plan, pseudo, parent DM and policy,
  interruption and recovery. Pure vectors and adapter tests do not replace it.
- QRAFT integration and [DFT #57](https://github.com/Jairomcarmona/dftlab-suite/issues/57)
  remain separate gates. Both engines must be completed, tested and fixed in
  the platform lock before HF-1 can be enabled and qualified on WSL.

HF-1 stays disabled and its capability at most CONTRACT_TESTED. No engine pin
or operational environment is updated by this draft.
