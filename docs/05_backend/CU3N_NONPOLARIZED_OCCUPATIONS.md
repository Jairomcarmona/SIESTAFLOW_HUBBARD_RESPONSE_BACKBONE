# Non-polarized Hubbard occupations

## Parsing convention

For the attached Cu3N SIESTA 5.4.2 BARE excerpt, the FDF and output attest a
non-polarized calculation: `Spin non-polarized`, `Spin configuration = none`,
one spin component, and time-reversal symmetry enabled. The projector matrix
prints one column. Its diagonal trace is a per-spin occupation, and the
`Occupations:` summary prints that same per-spin value twice.

HubbardFlow therefore forms the total shell occupation as twice the printed
per-spin value. That total is derived, not printed. It is the occupation used
for both chi0 and chi, matching the up-plus-down convention used for
polarized calculations. A one-column event is accepted only after both the
FDF and output spin markers are verified. Otherwise the parser fails closed.
Offline source-token re-extraction also requires the optional `fdf_path` in
the source-evidence manifest for one-column events; manifests without that
locator cannot certify non-polarized occupations.

The selected response summary is source line 6423, `4.792367 4.792367`; its
total is `9.584734 e`. The matrix diagonal trace is `4.79237` at five-decimal
matrix precision and is checked against the per-spin summary with the
existing `2.55e-5` tolerance. The summary at source line 6389 is before
`stepf`; the summary at line 6488 is after the indented `scf: 1` marker. Neither
is selected as the response event. `SCF_NOT_CONV` is expected for this
one-iteration probe and is not treated as an output failure by the BARE
response selector.

## Scientific controls

The total Cu d-shell occupation in this excerpt is about `9.6 e`, an
order-of-magnitude check consistent with Cu+ d10. This is a non-blocking
sanity check, not a numerical acceptance threshold.

A later absolute control is to apply this parser to the 13-run Cu3N probe and
compare its one-column U with the archived `12.6739 eV` result in
`docs/evidence/cu3n_mathematical_20260812`. The result should be near that
reference and not near twice its value. This repository change does not claim
that the 13-run comparison has been performed.

## Source record

- Fixture: `tests/fixtures/cu3n_nonpol_excerpt.txt` (124 physical lines).
- Fixture SHA-256: `ef365f3a8034bc946d97645bba6ab51d7b69429792c2b7cd0e93ee8a1828cda2`.
- Full source output SHA-256 (citation only):
  `6e0db88f89eccee3b8350c5349f3289629b9529656e0c1c827fe03d4ad582359`.
- The source output is not copied into the repository. No SIESTA campaign was
  run for this change.
- The excerpt begins inside the pre-`stepf` population context and omits the
  native `SCF mix quantity = Hamiltonian` signature. Its boundary test uses
  the real excerpt and source-line markers; the profile integration test wraps
  the selected real population block in the minimal required structure. Full
  profile selection on the unabridged Cu3N output remains unverified.
