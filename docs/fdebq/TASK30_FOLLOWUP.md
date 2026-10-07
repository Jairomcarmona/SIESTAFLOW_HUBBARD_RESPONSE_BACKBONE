# TASK 30 follow-up evidence

## LR-06 fixture regeneration

`tests/fixtures/lr06_siesta542_yoltla_extract.txt` contains three verbatim ranges
from the supplied full SIESTA output. Regenerate or verify it with:

```powershell
python tools/extract_lr06_trace.py C:\Users\Jairo\Downloads\LR06_FULL_siesta542_bare_4x4.out.gz --check
```

The tool accepts the original `.out.gz` or the decompressed `.out`. It checks the
full output SHA-256 (`f28dbe35ff17734f9291676dccf9592e4cc0d09049d6192237be82ea4786eb20`)
and its 5,871-line count before extracting native lines 4337, 4483–4514, and
4515–4579. The fixture records a SHA-256 for each extracted section, calculated
over UTF-8 text with LF line endings and a final LF. The full output is not part
of the repository.

## Five skipped tests in the LR-06 focused run

Command:

```powershell
python -m pytest -q -rs tests/unit/test_lr06_trace_excerpt.py tests/unit/test_siesta542_bare_profile.py tests/adversarial/test_observation_selection.py
```

Result: 9 passed, 5 skipped. All five skips are in
`tests/adversarial/test_observation_selection.py` and share the reason that
legacy ordinal/context-only BARE selection is disabled; production BARE
selection must use the admitted SIESTA 5.4.2 native-output profile and
validator.

- `test_OBS_A_fake_event_before_bare` (line 40)
- `test_OBS_C_wrong_scf_iteration_for_bare` (line 65)
- `test_reject_ambiguous_bare` (line 101)
- `test_bare_cannot_be_promoted_without_native_semantic_evidence` (line 111)
- `test_bare_promotion_requires_trace_and_explicit_hxc_exclusion` (line 119)

The LR-06 excerpt test and the SIESTA 5.4.2 profile tests are not skipped.

## RECORD_ONLY and an undeclared Fermi tolerance

With `tol_fermi_ev` absent, the Fermi difference is recorded and
`fermi_equivalence` is `RECORDED_NOT_ASSESSED`; no Fermi threshold is inferred.
For `ParentReproduction.RECORD_ONLY`, the occupation status is also
`NOT_ASSESSED` even when the measured occupation differences lie within their
declared tolerance, because this criterion does not grant an equivalence
verdict. In that case the reason is `EQUIVALENCE_NOT_ASSESSED` and
`rejects_reduction` is false. `CampaignRunner` expands a reduced class only when
`rejects_reduction` is true, so an unassessed Fermi value alone does not prevent
TS reduction. A measured occupation difference outside tolerance or incomplete
atom/projector identity still rejects/falls back for the affected scope.

The regression `test_record_only_without_fermi_tolerance_records_fermi_without_rejecting`
checks a 0.9 eV Fermi difference, identical occupations within the configured
occupation tolerance, no declared Fermi tolerance, and no reduction rejection.
This verifies the parent-reproduction decision only; other campaign gates remain
independent.
