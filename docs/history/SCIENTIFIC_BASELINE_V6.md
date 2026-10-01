# Scientific baseline V6 freeze

## Freeze identity and scope

This document freezes the Stage U-B V6 scientific validation state as recovered in the dedicated `codex/hubbardflow-v6-freeze` worktree. It preserves the reports, run records, certificates, calculations, inputs, and derived artifacts as historical evidence. It does not rerun SIESTA, regenerate scientific results, change qualification semantics, begin consolidation, or begin PBE decoupling.

The freeze is created now as a dedicated commit with message `freeze: scientific validation baseline V6`, followed by the annotated tag `scientific-v6-final`. The new tag identifies this frozen commit only. Its exact target is recorded after creation in [`HUBBARDFLOW_RENAME_VERIFICATION.md`](HUBBARDFLOW_RENAME_VERIFICATION.md). This identity does not replace any Git identity recorded in older V6 artifacts.

The Stage U-B V6 tag `stage-ub-v6-20260930` remains untouched and points to `03ccd5913abdc6dd0e9a2cb59c0bc7637562c267`. The source baseline authorized for this clean recovery began at `7dafe8c828d0c5155a15bd595ce6779bdfe9c133`; Stage U-B implementation history was transferred by cherry-pick into this isolated worktree. That recovery procedure does not assert that a cherry-picked commit is byte-identical to its source commit.

## Scientific terminal state

The canonical final report is [`FINAL_SIESTA_VALIDATION_REPORT_V6.md`](../../FINAL_SIESTA_VALIDATION_REPORT_V6.md), and the machine-readable terminal table is [`observable_validation_v6.json`](../../validation_observables_v6/observable_validation_v6.json). Their recorded terminal state is:

```text
NiO = COMPLETE
FeO = COMPLETE
CoO = REVIEW
MnO = PROTOCOL_REVIEW_REQUIRED
PENDING_SIESTA_VALIDATIONS = 0
SIESTA_VALIDATION_PHASE = CLOSED
READY_FOR_CONSOLIDATION_REVIEW = YES
```

The observable-validation closure and the U qualification are separate axes. In particular, NiO observable validation is `COMPLETE`; the archived v3 response analysis says `NUMERICAL_CANDIDATE_UNASSESSED` / `physical_acceptance=NOT_ESTABLISHED`, while the V6 summary's `u_qualification=ACCEPTED` and the certificate's `CERTIFIED` describe their own recorded classifications. These records are preserved as authored. This freeze does not reinterpret one status as another or claim a physical acceptance threshold that the analysis did not establish.

All reported SCF-mesh and Seekpath gaps are sampled values. Neither establishes a mathematical global gap over the continuous Brillouin zone. FeO's earlier apparent LR-U Fermi crossings were caused by subtracting the Fermi energy twice in postprocessing; corrected derived artifacts use eigenvalues already expressed relative to EF. No SIESTA recalculation was needed for that correction.

## Historical provenance gaps

### Certificate generator source unavailable

```text
HISTORICAL_PROVENANCE_GAP:
  artifact:
    CoO_u_certificate.superseding.v2.json
    MnO_u_certificate.superseding.v2.json
  recorded_source_sha256:
    611c8ff2b42349bfd4c6a16b56a265bb22553be64489a1f3edcecc227abf1184
  historical_source_available:
    NO
  current_source_sha256:
    C991E0C95CAC2687237A7636E9F4F76B9ABC386F3CE91DDFDA1606FD2461DA9F
  interpretation:
    The certificates are preserved as authoritative historical V6 artifacts,
    but the exact source-code snapshot identified by their recorded source
    hash is not presently available. The current source file must not be
    represented as the generating implementation.
```

The certificates are preserved byte-for-byte. The current tracked [`u_certification_node.py`](../../src/siestaflow_hubbard/execution/u_certification_node.py) is included only as the current repository implementation, not as historical generator evidence. Recorded certificate SHA-256 values are CoO `C1EF6CBA648C0EC64619D018D7957428C710EF77BAE7BCBA125291A1041A1252` and MnO `14133690A65FD3CED84594C95B4BED8AADAB48C398B0AEEEDD5F5D40F2F17265`.

### Historical Git commit identity mismatch

```text
HISTORICAL_PROVENANCE_GAP:
  kind: GIT_COMMIT_IDENTITY_MISMATCH
  recorded_git_sha:
    03ccd5913abdc6dd0e9e2cb59c0bc7637562c267
  recorded_git_sha_present_in_repository:
    NO
  related_existing_tag:
    stage-ub-v6-20260930
  tag_target_sha:
    03ccd5913abdc6dd0e9a2cb59c0bc7637562c267
  equivalence_established:
    NO
  interpretation:
    Existing V6 scientific artifacts record a Git commit identifier that
    is not present in the repository. A nearby existing commit is referenced
    by the historical stage-ub-v6-20260930 tag, but the freeze does not
    assume or assert that the two identifiers are equivalent.
```

The historical recorded identity, existing tag target, and new freeze identity are distinct:

```text
HISTORICAL_RECORDED_GIT_IDENTITY
  sha = 03ccd5913abdc6dd0e9e2cb59c0bc7637562c267
  repository_object_available = NO

EXISTING_STAGE_TAG_TARGET
  tag = stage-ub-v6-20260930
  sha = 03ccd5913abdc6dd0e9a2cb59c0bc7637562c267
  equivalence_to_historical_record = NOT_ESTABLISHED

NEW_FREEZE_IDENTITY
  tag = scientific-v6-final
  sha = the verified target recorded in HUBBARDFLOW_RENAME_VERIFICATION.md
```

All 18 files identified with the absent historical SHA are listed in [`V6_ARTIFACT_INVENTORY.md`](V6_ARTIFACT_INVENTORY.md). They are not edited to replace that SHA.

### Other limits on reproducibility claims

Some V6 NiO run records point to original calculation locations under `/home/jmc/.local/state/siestaflow/stage-u-b-v6-20260930/observables/`. This recovered Windows worktree preserves the transferred V6 reports, records, inputs, and available derived evidence; it does not claim that the external original paths or every original raw SIESTA primary output are available here. The transferred record is an artifact-preservation freeze, not a claim of full historical rerun capability.

Accordingly, the V6 baseline is **not fully historical-source-reconstructable**. Both provenance gaps remain visible and unresolved by design.

## Verification and artifact inventory

The selected scientific payload is enumerated in [`V6_ARTIFACT_INVENTORY.md`](V6_ARTIFACT_INVENTORY.md) and covered by [`SCIENTIFIC_BASELINE_V6.sha256`](SCIENTIFIC_BASELINE_V6.sha256). The manifest covers the transferred V6 reports, data, campaign evidence, certificates, run records, inputs, schemas, and band-postprocessor regression test. It intentionally excludes transient caches and this self-describing documentation. The inventory records the preserved historical Git SHA and lists every affected artifact located during the scoped scan.

No SIESTA process was launched during this freeze. No PBE decoupling or unrelated architectural work was performed.
