# Typed analysis acceptance in the scientific DAG — 2026-09-24

## Contract

Gate 4 now records an explicit analysis verdict in `results/analysis-verdict.json` and in `results/scientific_dag_state.json`. It keeps the native `source_status`, campaign `analysis_state`, `gate_decision`, and `physical_acceptance` as separate fields. The native analysis result is never rewritten.

The default installed contract is `{"schema_version": 1, "kind": "generic_full_rank"}`. It retains the prior generic rule: native `status` must be `PASS`, and `matrix_dimension`, `rank_chi0`, and `rank_chi` must be positive integers and all equal. Boolean, missing, zero, and non-integer dimensions/ranks fail closed. The resulting `gate_decision=ACCEPTED` means only that this generic algebra contract passed; its `physical_acceptance` is `NOT_ASSESSED`.

A campaign can opt in to a pinned validator with:

```text
python tools/install_scientific_dag.py --campaign-root CAMPAIGN \
  --analysis-validator scripts/validate_analysis.py --campaign-id CAMPAIGN_ID
```

The installer records the validator's SHA-256 and campaign ID. The hook is invoked as `python scripts/validate_analysis.py --result PATH`; it must write one JSON object to stdout with `schema_version: 1`, the exact `campaign_id` and native `source_status`, a non-empty `analysis_state`, a `gate_decision` (`ACCEPTED`, `RECORDED_ONLY`, or `REJECTED`), a `physical_acceptance` (`ACCEPTED`, `REJECTED`, `NOT_ESTABLISHED`, `NOT_ASSESSED`, or `NOT_APPLICABLE`), and a non-empty list of `evidence` entries containing campaign-relative `path` and `sha256`. Each evidence hash is recalculated before Gate 4 is recorded.

The helper rejects a `FAIL` source status unless the decision is `REJECTED`. It treats `REPORTABLE_NUMERICAL_U_INTERVAL` only as `RECORDED_ONLY` with `physical_acceptance=NOT_ESTABLISHED`; it cannot be represented as physical acceptance. Any physical `ACCEPTED` claim also requires the same explicit field in the native result and an `ACCEPTED` hook decision.

The verdict binds hashes of the native result, complete DAG config, analysis script, installed verdict validator, pinned campaign hook, and hook-declared evidence files. Gate 4 is `VALIDATED` only for `gate_decision=ACCEPTED`; otherwise its terminal analysis record is `RECORDED`. Gate 5 is always `RECORDED` and its evidence report explicitly says it does not itself assert physical validation.

At the start of a valid Slurm run, prior `ANALYSIS` and `EVIDENCE` ledger entries are invalidated. Gate 4 re-runs the analysis contract. The `is-complete ANALYSIS --analysis-verdict PATH` API also compares the recorded verdict hash and recomputes every bound source-file hash, so an edited result, config, analysis script, hook, or evidence file cannot reuse a stale acceptance.

## Verification and limits

In WSL, `bash -n templates/slurm/submit_scientific_lru_dag.slurm` passed. The focused test command covering the adversarial contract, gate ledger, and installer completed with **33 passed**:

```bash
PYTHONPATH=tools python3 -m pytest -p no:cacheprovider \
  tests/adversarial/test_scientific_dag_analysis_contract.py \
  tests/unit/test_scientific_dag_gate.py \
  tests/unit/test_install_scientific_dag_profiles.py
```

The verifier and generic installer were checked without launching SIESTA or a campaign. Coverage includes full-rank generic acceptance, malformed ranks, campaign state preservation, numerical-only versus physical acceptance, hook/evidence hash mismatch, stale verdict inputs, and ledger invalidation. This interface does not supply a MnO v3r2 hook, does not adapt its archived outputs, and does not establish that a campaign is physically valid. The separate MnO admission audit remains in force; its archived campaign is not staged by this change. Windows pytest was constrained by an ACL `WinError 5` while using its temporary-directory cleanup; the final focused suite was run successfully in WSL.
