# V1 retrospective reconstruction

Development evidence only. No production qualification.

Print BOUNDs are added componentwise using TASK2; SCF ESTIMATE is NOT_AVAILABLE.

| System | Mode | α (eV) | max shadow difference (e/eV) | α × difference (e) | print BOUND | Pass |
|---|---|---:|---:|---:|---:|---|
| CoO | BARE | 0.020 | 0.000000e+00 | 0.000000e+00 | 5.000000e-05 | True |
| CoO | BARE | 0.040 | 1.250000e-05 | 5.000000e-07 | 2.500000e-05 | True |
| CoO | BARE | 0.060 | 8.333333e-06 | 5.000000e-07 | 1.666667e-05 | True |
| CoO | SCREENED | 0.020 | 0.000000e+00 | 0.000000e+00 | 5.000000e-05 | True |
| CoO | SCREENED | 0.040 | 1.250000e-05 | 5.000000e-07 | 2.500000e-05 | True |
| CoO | SCREENED | 0.060 | 4.166667e-05 | 2.500000e-06 | 1.666667e-05 | False |
| NiO | BARE | 0.020 | 0.000000e+00 | 0.000000e+00 | 5.000000e-05 | True |
| NiO | BARE | 0.040 | 1.250000e-05 | 5.000000e-07 | 2.500000e-05 | True |
| NiO | BARE | 0.060 | 8.333333e-06 | 5.000000e-07 | 1.666667e-05 | True |
| NiO | SCREENED | 0.020 | 0.000000e+00 | 0.000000e+00 | 5.000000e-05 | True |
| NiO | SCREENED | 0.040 | 0.000000e+00 | 0.000000e+00 | 2.500000e-05 | True |
| NiO | SCREENED | 0.060 | 0.000000e+00 | 0.000000e+00 | 1.666667e-05 | True |
| MnO | BARE | 0.025 | 6.000000e-04 | 1.500000e-05 | 4.000000e-03 | True |
| MnO | BARE | 0.050 | 3.000000e-04 | 1.500000e-05 | 2.000000e-03 | True |
| MnO | BARE | 0.100 | 1.500000e-04 | 1.500000e-05 | 1.000000e-03 | True |
| MnO | SCREENED | 0.025 | 8.000000e-04 | 2.000000e-05 | 4.000000e-03 | True |
| MnO | SCREENED | 0.050 | 4.000000e-04 | 2.000000e-05 | 2.000000e-03 | True |
| MnO | SCREENED | 0.100 | 1.500000e-04 | 1.500000e-05 | 1.000000e-03 | True |

MnO receipt occupations are sums of ten printed matrix diagonal entries (5 decimals).
Each occupation has BOUND 5e-5 e, giving 1e-4/α for direct plus reconstructed central slopes.
The reference script's 1e-5/α comparison is retained in JSON as a legacy diagnostic; it is smaller by ×10.
MnO α × discrepancy is around 1.5e-5 e: an absolute occupation-scale discrepancy, consistent with 1/α slope scaling.
This scaling does not identify an SCF cause or establish an SCF ESTIMATE.

Cu3N has X/Y/Z representative columns and reconstructed matrices; independent translated shadows are absent (21 in SC222, 78 in SC333).
Compact Cu3N evidence omits printed tokens; no rounding budget is guessed. Historical BARE selection is reported.
MnO historical permutation uses only Mn positions and assumes oxygen mapping; no F1–F8 qualification is implied.
CoO/NiO exchange and spin-flip comparisons are candidates; flags remain disabled.

Raw observations, reconstructed and symmetrized data, correction norms and source digests are retained in JSON.
