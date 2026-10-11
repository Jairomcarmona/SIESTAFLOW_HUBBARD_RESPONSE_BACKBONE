# Native public consumer fixture provenance

`native_consumer.json` records six deterministic synthetic cases constructed
with existing native entrypoints from `e508f47aff1c6243deabb12915063b6b9d899d65`.
The expected payloads come directly from `resolve_perturbation_plan`,
`validate_observation`, `qualify_state_gate` and `analyze_verified_lr`; the
public facade did not generate them. Scientific domain sources remain byte
identical to that commit. The existing synthetic planning helper uses
explicit versioned policies from `tests/unit/test_perturbation_plan.py`.
Only the qualified operations referenced by each synthetic class are injected
(four for the review case, none for disabled reduction); their indices are
remapped consistently. Other search diagnostics are irrelevant to these
transport cases and omitted. The native frozen qualification/planner validates
this declared input; no scientific source, policy or baseline is changed.

The plan's Unicode planner ID distinguishes ensure_ascii=True from the
observation hash's ensure_ascii=False profile. The scalar synthetic response
has bare slope -0.8 e/eV and screened slope -0.25 e/eV with declared cubic
terms, fitted by the explicit native polynomial policy. No acceptance
tolerance is inferred; the result remains NUMERICAL_CANDIDATE_UNASSESSED and
physical_acceptance NOT_ESTABLISHED. The fixed grid is not changed.

The resume request uses the same native plan/policy/file hashes and the
existing response-reuse synthetic identity. Even exact metadata equality
does not establish physical equivalence and cannot authorize reuse.

Tests run the installed public facade against these expected native results
on Windows and Linux. Planning/observation/gate payloads and digests compare
exactly against the fixture; scientific analysis compares the facade with
the native entrypoint in the same numerical environment in unit tests, also
exactly without a tolerance. The installed consumer checks the native
analysis schema, statuses, units, policy and semantics. Cross-OS BLAS
floating-point byte identity is not asserted. This establishes transport equivalence, not a real
SIESTA campaign, physical certification or HF-1 scheduler qualification.
