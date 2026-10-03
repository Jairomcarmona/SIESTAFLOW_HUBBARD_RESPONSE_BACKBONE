# TASK15: staged aliases and generated ion identity

`lr-config.auto_split_species` is a boolean, default `false`. OFF reports
`SHARED_LABEL_NEEDS_SPLIT` for a shared correlated label and creates no aliases.
Explicit `true` permits input staging only. It never grants `READY` or starts
SIESTA. This implements AMENDMENTS_2 D6; the complete production state gate
remains a separate dependency.

## Stage the preserved inputs

Supply the authoritative FDF, pseudopotentials, explicit per-label `PAO.Basis`,
and the original reference `.ion` files. Declare their directories using
`--identity-dir` and/or `static_artifacts` in the config. A missing PP, basis or
original ion fails preflight. Unsupported species-indexed controls also fail.

```bash
hubbardflow plan system.fdf --lr-config lr-config.json \
  --identity-dir reference-run --output-dir split-plan
```

The product plan has `NOT_ESTABLISHED`, reason
`STAGED_PENDING_GENERATED_IDENTITY`, and a typed `split_staging` record. It binds
the versioned opt-in, effective source FDF, alias identities, and every staged
input SHA256 in the frozen campaign identity. The directory
`split-plan/species_split/` contains `reference.fdf`, the alias pseudopotentials
and staged reference ion copies, plus `species_split_staging.json`.

The existing campaign initializer also stages a shared label on this config
flag and returns `staging_manifest_path`, `staging_digest`, and the pending
status. It creates no executable `campaign.v2.json` or production plan lock.
Neither a normal `run` nor an override can execute the pending aliases.

For every split label, the helper duplicates all projector fields, the full
explicit basis record, and every available PP format under each new label.
It preserves global basis options, geometry, coordinate tokens and per-atom
`DM.InitSpin`. The original projector entry is removed; an orphan is rejected.
Staged ion normalization changes only the two previously audited label fields.
Its semantic equality check proves input preservation, not generated identity.

## Generate ions on the user's SIESTA machine

1. Preserve the original reference-run directory and its `.ion` files read-only.
2. Copy the staged inputs to a fresh, separate real-run directory. Keep the
   frozen `split-plan` intact: changing its bytes invalidates resume.
3. Remove the **copied alias `.ion` files from this fresh directory** before
   the run, so they cannot be mistaken for newly generated outputs. Inspect
   any read-ion/restart settings explicitly before running. Use the user's
   chosen SIESTA executable, machine and launcher. This repository tool does
   not run the generation calculation.
4. Record the actual command, SIESTA version/bin hash, effective FDF and output
   digest separately. Ensure normal completion and confirm each alias `.ion`
   was produced by that run. Filename identity alone cannot prove generation.
5. Verify the real output files:

```bash
python tools/hubbardflow_verify_split_identity.py real-alias-run \
  --original-label Co --aliases CoLR0 CoLR1 \
  --reference-directory original-reference-run > split-identity-receipt.json
```

Run once per original split label. Without `--reference-directory`, the tool
looks for the original `.ion` inside `real-alias-run`. It searches recursively;
exactly one file per requested label is required. Even identical duplicates
are ambiguous and fail. The tool reads only; save the JSON outside frozen V6
paths and outside the frozen staging directory.

## Interpret the receipt

Exit 0 / `EXACT_ION_BYTES_MATCH` means every alias **raw file SHA256** equals
the original raw file SHA256. Exit 2 / `SPECIES_IDENTITY_NOT_ESTABLISHED`
records missing, duplicate, unreadable or byte-different ions. Invalid or
duplicate label arguments also exit 2. The typed receipt serializes all file
digests, paths, reason codes, version and its canonical receipt digest.

The optional `diagnostic_canonical_sha256` normalizes the two audited species
label fields. It is diagnostic only and cannot produce a positive verdict.
Ordinary renamed `.ion` files can therefore have matching canonical hashes
and different raw hashes: they **fail** exact identity. Do not edit output
bytes, strip labels or substitute staged copies to force a passing verdict.
Report the mismatch and its receipt for scientific review.

Even exact equality does not prove generation, SCF convergence, reference
state consistency or production admission. This task has no configuration
field that consumes the receipt to unlock execution. The prepared campaign
remains pending until actual generated identity and the other production
dependencies are admitted through an explicitly reviewed contract. No real
generation or positive real-data identity is claimed by synthetic tests.
