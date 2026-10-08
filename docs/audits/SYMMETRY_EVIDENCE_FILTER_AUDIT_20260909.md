# Symmetry evidence filter — Luna B proposal

## Scope

This proposal adds a strict path for authorizing perturbation reduction. The
existing geometric/magnetic certificate remains compatible with prior
behavior; the strict path additionally requires a
`SymmetryEvidenceBundle` linked by SHA-256 to the certificate, reference FDF,
its output, and magnetic evidence.

The bundle also contains an explicit local-subspace fingerprint for each
atom. A candidate magnetic operation passes the filter only if the atoms it
exchanges have the same subspace fingerprint. The filter does not infer
equivalence from site names or `DM.InitSpin`.

## Preserved safeguards

- Missing or incomplete evidence raises `SymmetryPlanError` on the strict path.
- Existing policy `translation_only=True` remains the only policy that can
  authorize reduction; rotations remain candidates.
- Authorization still requires direct shadow responses and their existing
  tolerances. This change alters no tolerance.
- No `spglib` dependency was added; FDFs, campaigns, launchers, Slurm, and site
  profiles were not modified.

## What the tests demonstrate

Synthetic tests verify that:

1. A correctly linked bundle retains only operations compatible with the
   declared subspace;
2. A different fingerprint removes non-trivial operations, retaining at most
   the identity;
3. An incorrect certificate hash blocks planning;
4. Incomplete magnetic evidence blocks the strict path;
5. Unknown formats or invalid hashes are rejected.

 Tests run:

```text
python -m pytest tests/unit/test_symmetry_evidence_contract.py \
  tests/unit/test_symmetry_reduction_plan.py \
  tests/unit/test_fdf_symmetry_adapter.py -q -p no:cacheprovider
15 passed
```

## Deliberate limits

This change does not implement general orbital operations, time reversal,
SOC, non-collinearity, or automatic magnetic symmetry. Nor does it generate
the bundle from `siesta.out`: the production adapter must create it from an
accepted reference and calculate its hashes. Until then, the strict path is a
verifiable contract, not a claim of production capability.
