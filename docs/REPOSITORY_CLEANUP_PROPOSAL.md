# Repository cleanup proposal

Status: proposal only. This document records an inventory and suggested structure. It does not authorize moving or deleting files.

## Inventory basis

The inventory was taken from the TASK 34d worktree at commit `07ef31f`. It found 73 tracked files directly in the repository root, including 30 zero-byte timestamped `fdf.*.log` files and 10 standalone Python scripts. The root also contains small scratch-looking files (`CLOCK`, `MESSAGES`, allocation markers, and `test_rc` / `test_ua` inputs and outputs), two pseudopotential files, and a nested versioned repository snapshot. Their current consumers and provenance have not been established, so they remain in place.

The root contains production benchmark archives `production_benchmarks_v1.zip` through `production_benchmarks_v6.zip`. The versioned set is historical evidence, not confirmed duplication. The V6 archive and other paths covered by the scientific-baseline instructions are protected and must not be moved or rewritten as part of cleanup.

`docs/` contains 199 files totaling about 8.98 MB. Its taxonomy mixes the numbered areas `00_governance` through `05_backend` with parallel `architecture`, `audits`, `evidence`, `fdebq`, `history`, and `schemas` directories, plus documents at the `docs/` root. Five separate subdirectories contain a `README.md`; these appear to be local indexes, so a repeated basename alone is not evidence of duplicate content. No content-level deduplication was performed.

The largest documentation items are:

| Area or file | Approximate size | Initial assessment |
|---|---:|---|
| `docs/fdebq/V1_RETROSPECTIVE_REPORT.json` | 2.77 MB | Generated historical report; candidate for an evidence or archive area after reference checks. |
| `docs/evidence/` | 4.10 MB | Evidence bundle; retain as source material. |
| `docs/audits/` | 634 KB | Audit records; retain, but separate current policy from historical audit snapshots. |
| `docs/fdebq/` | 3.50 MB | Active policy, runbooks, and task history are mixed; classify before any move. |

The repository also contains large validation and run data outside `docs/`: `results/` (~74.9 MB), `validation_observables_v6/` (~67.6 MB), `FEO_SCF_DIAGNOSTIC_EXPORT_20261001/` (~37.3 MB), and `campaigns/` (~20.9 MB). These are evidence-bearing or protected paths, not cleanup targets. In particular, no action may alter the frozen V6 baseline or its manifest.

## Cleanup candidates for owner review

1. **Root logs and markers.** Review the 30 empty timestamped FDF logs and zero-byte marker/allocation files. If they are reproducible runtime residue, move them to a clearly dated archive or remove them only after provenance and consumer checks.
2. **Standalone root scripts.** Review `add_imports.py`, `append_tests.py`, `fix_block.py`, the `fix_tests*.py` family, `patch_fdf.py`, `test_proj.py`, and `update_cli_tests.py`. Keep active maintenance utilities under `tools/maintenance/`; archive one-off scripts with their purpose and source commit; remove nothing without owner approval.
3. **Root test inputs and pseudopotentials.** Check `test_rc.*`, `test_ua.*`, `cu_test.alloc`, `test_ua.alloc`, `Ni.psml`, and `O.psml` against tests, examples, and campaign configuration. If still needed, place them in named fixtures or material inputs and update references atomically. Their role is currently unconfirmed.
4. **Versioned archives and embedded snapshot.** Determine whether the older production benchmark ZIPs and `SIESTAFLOW_HUBBARD_RESPONSE_BACKBONE_V0_1_0/` are release artifacts or active inputs. A future artifact archive could group old releases, but the V6 archive and protected baseline paths stay untouched.
5. **Documentation taxonomy.** Decide whether the numbered sections or the older thematic directories are canonical. Consolidate only after mapping every relative link and code reference; retain stable landing pages or redirects for existing links.
6. **Task and evidence history.** Keep decision records and scientific evidence, but separate them from current user guidance. The large retrospective JSON and dated task logs are archive candidates, not deletion candidates.

## Proposed target layout

Keep the repository root for project entry points and metadata (`README.md`, `AGENTS.md`, `CHANGELOG.md`, contribution and citation metadata, build configuration, and the source/test/tool directories). Put generated local scratch output outside the tracked root or under an ignored workspace directory.

Use one documentation taxonomy with a top-level index and stable categories:

```text
docs/
  README.md
  governance/
  science/
  architecture/
  policies/
  backend/
  validation/
  audits/
  evidence/
  history/
    tasks/
    baselines/       # immutable records; preserve V6 paths and hashes
  schemas/
  archive/
    retrospectives/
```

Keep executable maintenance tools in `tools/`, reproducible examples in `examples/`, small test data in `tests/fixtures/`, and validated run packages under an explicitly documented artifact area. Large evidence should remain versioned only when required for reproducibility; otherwise a future task can define external artifact storage and checksums. That decision is outside this proposal.

## Migration safeguards

Before any approved move, identify all path references, confirm ownership and whether the item is reproducible, record hashes for evidence, update links and manifests, and run the relevant tests. Move files in small reviewed changes with compatibility links where external users may rely on paths. Run the V6 integrity gate before and after changes. Do not alter protected scientific data, change scientific content, or remove historical task records as part of a cosmetic cleanup.

No files were moved, renamed, or deleted for this proposal. Any filesystem reorganization requires a separate explicit approval and implementation task.
