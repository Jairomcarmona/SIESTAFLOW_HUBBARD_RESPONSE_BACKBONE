# HubbardFlow freeze and rename verification

## Scope and safety

This report tracks the V6 scientific freeze and the authorized repository/package rename in the dedicated worktree. Preflight found the original checkout at `C:\Users\Jairo\Downloads\SIESTAFLOW_HUBBARD_RESPONSE_BACKBONE_V0_1_0`, branch `codex/sync-product-20260929`, HEAD `7dafe8c828d0c5155a15bd595ce6779bdfe9c133`; it was dirty and was not modified. No SIESTA calculation was run, no PBE decoupling was started, and no unrelated architectural work was included.

The scientific freeze preserves existing V6 records and results. The subsequent rename changes project, distribution, import, and CLI branding only where compatible with the existing contracts. It does not change scientific outputs, U values, certificate metadata, qualification semantics, or historical identifiers.

## Provenance decisions carried through the rename

The freeze preserves both documented historical provenance gaps:

1. The CoO/MnO superseding V2 certificates record historical generator SHA-256 `611c8ff2b42349bfd4c6a16b56a265bb22553be64489a1f3edcecc227abf1184`, whose source is unavailable. The current tracked `u_certification_node.py` SHA-256 is `C991E0C95CAC2687237A7636E9F4F76B9ABC386F3CE91DDFDA1606FD2461DA9F`; it is not attributed as their generator.
2. V6 artifacts record Git SHA `03ccd5913abdc6dd0e9e2cb59c0bc7637562c267`, which is absent. Existing tag `stage-ub-v6-20260930` points to `03ccd5913abdc6dd0e9a2cb59c0bc7637562c267`; equivalence is not established. Neither the tag nor historical records were rewritten.

The full 18-file list and certificate hashes are in [`V6_ARTIFACT_INVENTORY.md`](V6_ARTIFACT_INVENTORY.md). Provenance coverage is partial, and the baseline is not fully historical-source-reconstructable.

## Freeze identity

```text
NEW_FREEZE_IDENTITY
  freeze_branch = codex/hubbardflow-v6-freeze
  commit_subject = freeze: scientific validation baseline V6
  tag = scientific-v6-final (annotated)
  verified_commit_sha = 45cb53c5a98d9d55a163c05ca3b815a8ff9cfb7f
  tag_target_sha = 45cb53c5a98d9d55a163c05ca3b815a8ff9cfb7f
  rename_branch = codex/hubbardflow-rename
  rename_base = 45cb53c5a98d9d55a163c05ca3b815a8ff9cfb7f
```

The new identity describes the frozen state as it exists now; it does not retroactively identify older records.

## Pre-rename identity and persisted-data handling

```text
project = SIESTAFLOW_HUBBARD_RESPONSE_BACKBONE
distribution = siestaflow_hubbard (normalized by Python packaging as siestaflow-hubbard)
import = siestaflow_hubbard
CLI = siestaflow
```

Versioned persisted-data identifiers such as `siestaflow.campaign.v2`, `siestaflow.lr_config.v2`, `siestaflow-campaign-software-lock-v1`, and the `.siestaflow.json` pointer suffix remain stable. Frozen MnO campaign locks name the former distribution and source path; their exact old wheel and records remain unchanged. The current verifier resolves that path through the exact locked distribution without importing the old Python namespace as the active package. These identifiers are classified as `LEGACY_REFERENCE_ALLOWED` because they are stable persisted-format/provenance identities, not active project branding.

## Validation record

The 484-entry freeze manifest was verified against the staged payload before the freeze commit, but `*.sha256` is ignored and the manifest was therefore not included in the immutable tag tree. This was detected during final verification. The manifest is now retained as a tracked audit companion in this rename follow-up; a fresh blob-by-blob check against `scientific-v6-final` found 484 entries, zero missing blobs, and zero SHA-256 mismatches. All 18 artifacts carrying the absent historical Git SHA matched the original checkout byte-for-byte. The annotated `scientific-v6-final` tag resolves to the freeze commit above; the pre-existing `stage-ub-v6-20260930` tag remains at `03ccd5913abdc6dd0e9a2cb59c0bc7637562c267`. The manifest is not retroactively inserted into or used to rewrite the freeze tag.

The isolated scientific baseline preparation passed the canonical backend-contract test selection plus the FeO postprocessor regression: 94 tests passed and 4 subtests passed. A broader unfiltered pytest discovery attempt was not canonical and failed during collection on root scratch scripts, an outdated root test API, a missing archived NiO analysis script, and a missing optional module; this is a recorded unrelated collection issue. No SIESTA was run.

## Rename-phase verification

- Current active package imports and CLI calls use `hubbardflow`; a scoped search found zero active old-namespace imports or `siestaflow` CLI invocations in runtime code, tests, examples, tools, production benchmarks, and current user guides. Remaining runtime strings are stable serialized schema IDs, `.siestaflow` control/pointer paths, and explicit legacy-lock compatibility. The README retains its existing historical draft-PR URL because the GitHub remote/repository rename is outside scope. The historical Yoltla deployment guide and three source files named by frozen MnO locks remain explicitly historical/provenance inputs.
- The V6 manifest matches all 484 blobs in the immutable freeze tag. The current worktree has one expected manifest-path difference: the V6-freeze `u_certification_node.py` snapshot was moved from the legacy path to `src/hubbardflow` and its imports were namespace-migrated. The tag retains the exact old-path snapshot, whose SHA-256 was `C991E0C95CAC2687237A7636E9F4F76B9ABC386F3CE91DDFDA1606FD2461DA9F`; this is a pre-rename current-implementation hash, not historical certificate-generator evidence or the hash of the post-rename file.
- The canonical backend-contract selection, the software-lock compatibility tests, and the FeO postprocessor regression passed in the prior rename validation run: 97 tests and 4 subtests. A repeat in this continuation could not start because neither the system nor bundled Python runtime has `pytest` installed; the same runtimes also lack NumPy, so the package/CLI smoke could not be repeated here. The prior successful import and direct entry-point dispatch remain recorded; no dependencies were installed. A wheel/installed launcher check is `NOT_APPLICABLE`: `setuptools.build_meta` is unavailable and no cached build backend exists; no network install was attempted.
- No SIESTA process was run. The original dirty checkout remains untouched. The existing freeze and Stage U-B tags are unchanged.

The final rename commit identity and clean-tree state are verified after commit and reported with the completion summary.
