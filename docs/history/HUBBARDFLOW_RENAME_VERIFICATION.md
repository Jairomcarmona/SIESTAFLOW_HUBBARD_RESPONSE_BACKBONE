# HubbardFlow freeze and rename verification

## Scope and safety

This report tracks the V6 scientific freeze and the authorized repository/package rename in the dedicated `codex/hubbardflow-v6-freeze` worktree. The original dirty checkout was not modified. No SIESTA calculation was run, no PBE decoupling was started, and no unrelated architectural work was included.

The scientific freeze preserves existing V6 records and results. The subsequent rename changes project, distribution, import, and CLI branding only where compatible with the existing contracts. It does not change scientific outputs, U values, certificate metadata, qualification semantics, or historical identifiers.

## Provenance decisions carried through the rename

The freeze preserves both documented historical provenance gaps:

1. The CoO/MnO superseding V2 certificates record historical generator SHA-256 `611c8ff2b42349bfd4c6a16b56a265bb22553be64489a1f3edcecc227abf1184`, whose source is unavailable. The current tracked `u_certification_node.py` SHA-256 is `C991E0C95CAC2687237A7636E9F4F76B9ABC386F3CE91DDFDA1606FD2461DA9F`; it is not attributed as their generator.
2. V6 artifacts record Git SHA `03ccd5913abdc6dd0e9e2cb59c0bc7637562c267`, which is absent. Existing tag `stage-ub-v6-20260930` points to `03ccd5913abdc6dd0e9a2cb59c0bc7637562c267`; equivalence is not established. Neither the tag nor historical records were rewritten.

The full 18-file list and certificate hashes are in [`V6_ARTIFACT_INVENTORY.md`](V6_ARTIFACT_INVENTORY.md). Provenance coverage is partial, and the baseline is not fully historical-source-reconstructable.

## Freeze identity

```text
NEW_FREEZE_IDENTITY
  branch = codex/hubbardflow-v6-freeze
  commit_subject = freeze: scientific validation baseline V6
  tag = scientific-v6-final (annotated)
  verified_commit_sha = PENDING_FREEZE_COMMIT
  tag_target_sha = PENDING_FREEZE_COMMIT
```

Replace the two `PENDING_FREEZE_COMMIT` values with the verified SHA only after creating and resolving the annotated tag. The new identity describes this frozen state; it does not retroactively identify older records.

## Validation record

Pending freeze hash verification, scientific terminal-table comparison, package/import/CLI and distribution tests, legacy-branding audit, and a final clean-tree audit for `codex/hubbardflow-rename`. Results and exact commands will be recorded here after execution. The isolated scientific baseline preparation passed the canonical CI backend-contract subset plus the FeO postprocessor regression: 94 tests passed and 4 subtests passed. A broader unfiltered pytest discovery attempt was not canonical and failed during collection on repository-root scratch scripts, an outdated root test API, a missing archived NiO analysis script, and a missing optional module; no SIESTA was run.
