# Projector diagnostics (record-only)

Campaign reports include a machine-readable `projector_diagnostics` object and
a matching Markdown section. These values describe the declared projector and
the calculated response; they never gate a campaign, select a model, accept U,
or change a result.

## Per-site electron-count references

An `lr-config` may declare values under `projector_diagnostic_references`,
keyed by an exact campaign `site_id`:

```json
{
  "projector_diagnostic_references": {
    "MnLR00": {
      "formal_d_electrons": 3,
      "free_atom_d_electrons": 5
    }
  }
}
```

Either field can be declared independently. Values must be finite and
nonnegative. The code never infers electron counts from an element, label, or
chemical environment. If the reference occupation or the corresponding
declared count is absent, that comparison is `NOT_ASSESSED`. When both values
exist, the report records the occupation minus the formal count separately
from the occupation minus the free-atom count. `CAPTURE_INDICATED` means the
reference projector occupation is greater than the declared free-atom d
occupation; this is a descriptive marker, not a physical acceptance rule.

## Response-regime indicator

For each site the report records

```text
U_scalar_charge × abs(chi0_ii)
```

where `U_scalar_charge` is the reported diagonal U in eV and `chi0_ii` is the
selected bare-response diagonal in eV⁻¹. The product is dimensionless and can
be approximately constant when screened and bare responses remain
proportional. The implementation sets no range or acceptance threshold. If
either input is unavailable, the indicator is `NOT_ASSESSED`.

## Permanent Method 2 warning

Production campaign validation requires
`DFTU.ProjectorGenerationMethod 2`. Every campaign report therefore includes
the machine-readable warning code
`SIESTA_METHOD_2_ATOMIC_NONORTHOGONALIZED_PROJECTOR`. It records that SIESTA
Method 2 uses atomic, non-orthogonalized projectors and its U is not comparable
to U from an orthogonalized projector scheme. Its decision role is
`RECORD_ONLY`.

## M1 nine-point record

The following values are the supplied Yoltla one-column M1 projector-scan
record, preserved in [`projector_curve_m1.json`](../../tests/fixtures/projector_curve_m1.json).
The site is `MnLR00`; its declared formal d count is 3 and the supplied
free-atom d count is 5. The `U × |chi0|` column is copied from that record and
is retained as a fixture datum for checking the report calculation; it is not
a threshold.

| CutoffNorm | U (eV) | Reference occupation (e) | U × |chi0| |
|---:|---:|---:|---:|
| 0.50 | 25.0833 | 2.6050 | 3.80 |
| 0.60 | 19.0979 | 3.0697 | 3.91 |
| 0.70 | 15.4146 | 3.5521 | 4.06 |
| 0.80 | 13.0972 | 4.0605 | 4.21 |
| 0.85 | 12.0211 | 4.3436 | 4.20 |
| 0.90 | 10.6622 | 4.6739 | 4.00 |
| 0.95 | 8.2302 | 5.1445 | 3.30 |
| 0.98 | 6.2659 | 5.6680 | 2.61 |
| 0.99 | 5.5708 | 5.8848 | 2.35 |

The supplied values cross the free-atom reference between CutoffNorm 0.90 and
0.95. No conclusion is generalized beyond these measured points.
