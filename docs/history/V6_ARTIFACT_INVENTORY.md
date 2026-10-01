# V6 scientific artifact inventory and provenance coverage

This inventory is part of the `scientific-v6-final` freeze. The 484-entry file-level SHA-256 manifest is retained as a tracked audit companion in the subsequent HubbardFlow rename commit: the generic `*.sha256` ignore rule omitted the manifest from the immutable freeze tag, although the manifest itself was verified before that commit. Every entry has now been checked against the corresponding blob in `scientific-v6-final`; all 484 are present and match. The manifest represents only the listed V6 evidence scope, not the entire repository. The follow-up does not rewrite the freeze commit or tag.

## Included inventory scopes

- `FINAL_SIESTA_VALIDATION_REPORT_V6.md`
- `validation_observables_v6/` (excluding transient caches)
- `results/stage-ub-v6-observables/` (including inputs, run records, route and full-BZ derived data)
- `FEO_SCF_DIAGNOSTIC_EXPORT_20261001/` (excluding transient caches)
- `benchmarks/lr_u/{CoO,FeO,MnO,NiO}/`
- `benchmarks/lr_u/forensic_audit/`
- `campaigns/nio_pbe_p5_20260928/results/`
- `schemas/u_certificate.v1.schema.json`
- `schemas/response_tokens.v1.schema.json`
- `tests/unit/test_feo_band_postprocessor.py`
- `src/siestaflow_hubbard/execution/u_certification_node.py` as the current tracked implementation only

The inventory preserves the bytes of all transferred historical reports, run records, and certificates. The two superseding V2 certificates retain these SHA-256 values:

| Artifact | SHA-256 |
|---|---|
| `benchmarks/lr_u/forensic_audit/CoO_u_certificate.superseding.v2.json` | `C1EF6CBA648C0EC64619D018D7957428C710EF77BAE7BCBA125291A1041A1252` |
| `benchmarks/lr_u/forensic_audit/MnO_u_certificate.superseding.v2.json` | `14133690A65FD3CED84594C95B4BED8AADAB48C398B0AEEEDD5F5D40F2F17265` |

## Historical provenance gaps

### Certificate generator source

```text
HISTORICAL_PROVENANCE_GAP:
  artifacts:
    CoO_u_certificate.superseding.v2.json
    MnO_u_certificate.superseding.v2.json
  recorded_source_sha256:
    611c8ff2b42349bfd4c6a16b56a265bb22553be64489a1f3edcecc227abf1184
  historical_source_available: NO
  current_source_sha256:
    C991E0C95CAC2687237A7636E9F4F76B9ABC386F3CE91DDFDA1606FD2461DA9F
  interpretation:
    Current u_certification_node.py is the current tracked implementation,
    not established evidence of the historical certificate generator.
```

The current implementation SHA-256 is retained only to identify the present source file. It is not substituted for the historical hash, and the missing source was not searched for, reconstructed, synthesized, or reverse-engineered.

### Recorded Git identity

```text
HISTORICAL_PROVENANCE_GAP:
  kind: GIT_COMMIT_IDENTITY_MISMATCH
  recorded_git_sha:
    03ccd5913abdc6dd0e9e2cb59c0bc7637562c267
  recorded_git_sha_present_in_repository: NO
  related_existing_tag: stage-ub-v6-20260930
  tag_target_sha:
    03ccd5913abdc6dd0e9a2cb59c0bc7637562c267
  equivalence_established: NO
```

### Files containing the absent historical Git SHA

The following 18 artifacts contain `03ccd5913abdc6dd0e9e2cb59c0bc7637562c267`. Their bytes and recorded identity are preserved unchanged:

1. `FINAL_SIESTA_VALIDATION_REPORT_V6.md`
2. `FEO_SCF_DIAGNOSTIC_EXPORT_20261001/FDF_PARAMETER_COMPARISON.md`
3. `FEO_SCF_DIAGNOSTIC_EXPORT_20261001/feo_lru_mix001/run_record.json`
4. `FEO_SCF_DIAGNOSTIC_EXPORT_20261001/feo_lru_seedDM/run_record.json`
5. `FEO_SCF_DIAGNOSTIC_EXPORT_20261001/README.md`
6. `FEO_SCF_DIAGNOSTIC_EXPORT_20261001/nio_lru_control/run_record.json`
7. `FEO_SCF_DIAGNOSTIC_EXPORT_20261001/feo_pbe/seedDM_converged/run_record.json`
8. `FEO_SCF_DIAGNOSTIC_EXPORT_20261001/feo_pbe/mix001_both_DM_source/run_record.json`
9. `results/stage-ub-v6-observables/run-records/nio-dft_lru.json`
10. `results/stage-ub-v6-observables/run-records/nio-dft.json`
11. `FEO_SCF_DIAGNOSTIC_EXPORT_20261001/feo_lru_original/run_record.json`
12. `results/stage-ub-v6-observables/run-records/feo-dft_lru-seedDM.json`
13. `results/stage-ub-v6-observables/run-records/feo-dft_lru-seedDM/run_record.json`
14. `results/stage-ub-v6-observables/run-records/feo-dft_lru-mix001-both/run_record.json`
15. `results/stage-ub-v6-observables/run-records/feo-dft_lru/run_record.json`
16. `results/stage-ub-v6-observables/run-records/feo-dft-seedDM.json`
17. `results/stage-ub-v6-observables/nio-full-bz-gap-search/NIO_FULL_BZ_GAP_SEARCH.md`
18. `results/stage-ub-v6-observables/OBSERVABLE_VALIDATION_STAGE_UB_V6.md`

The V6 final report, NiO full-BZ gap-search report, observable report, and affected run records are all explicitly included. Any additional occurrence discovered by a later scoped scan must be appended here and to the rename verification report without editing the historical artifact.

## Coverage interpretation

`COMPLETE` in the observable table records the terminal observable-validation workflow state. It does not mean every raw output referenced by an external historical path is present in this checkout, nor that the exact historical certificate generator source or recorded Git commit object is available. `CERTIFIED`, `ACCEPTED`, `REVIEW`, `PROTOCOL_REVIEW_REQUIRED`, and `NOT_ESTABLISHED` retain the meanings recorded by their respective certificate, analysis, and V6 summary artifacts; this inventory does not reconcile them by rewriting evidence.

Provenance coverage: **PARTIAL — HISTORICAL_PROVENANCE_GAPS_RECORDED**. The baseline is not classified as fully source-reproducible or fully historical-source-reconstructable.
