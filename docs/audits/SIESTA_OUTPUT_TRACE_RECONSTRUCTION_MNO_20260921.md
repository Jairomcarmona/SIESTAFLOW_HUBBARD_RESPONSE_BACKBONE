# SIESTA output trace reconstruction — MnO, 2026-09-21

Inspected result set: `campaigns\mno_afmii_strict_lr_v3r2\results\response-matrix-foreground-recovery-v4`. Twenty-nine runs were reconstructed: 1 reference, 14 BARE, and 14 SCREENED. Only existing files were read; SIESTA/Slurm was not launched and its code was not modified.

## Trace conclusion

- All 14/14 BARE outputs have a complete block of 16 populations between `stepf` and `scf: 1`; this is the candidate event from the first diagonalization. In every BARE response, the event is on lines `5370–5835`; `stepf` is on line 5369 and `scf: 1` on line 5863.
- All 14/14 SCREENED outputs converge in 3 to 12 iterations and retain a final block of 16 populations after the convergence marker and use of `DM_out`; this is the SCREENED event to follow.
- All 29 outputs end with `Job completed` and have the external marker `0_NORMAL_EXIT`. The 28 `.out` hashes recorded in `response-receipt.json` match the existing files; all 28 parent hashes in the receipt match reference DM `65d418d1a21b4b4052d41d68554639fc4bc4682566bb780c0d072fd4cfe5eb47`.
- The reference FDF and 28 response FDFs use SIESTA 5.4.2, Hamiltonian mixing, DFTU PotentialShift, projector method 2, and the same Mn-3d manifold (16 sites; n=3, l=2, CutoffNorm=0.90, omega=0.05 Bohr). Each nonzero perturbation activates a single site and sign; alpha=0 is identified from the manifest/receipt because the FDF block has U=0 at every site.
- The sequence supports which population is treated as candidate BARE and which as converged SCREENED in these outputs. The `.out` does not literally print a “frozen Hxc” flag; the semantic BARE interpretation relies on the call order audited for 5.4.2 and executable identity.
- The parent-DM identity is declared and bound by the receipt, and each output confirms a successful read. However, the pre-run DM file was not preserved separately: the current `.DM` in each directory is the post-run artifact. Therefore, the exact hash of each copy read cannot be recalculated retrospectively from the final directories.
- This does not produce an accepted U. `analysis-result.json` reports `status=FAIL`, `U_Mn_eV=null`; the signal gate rejects all three windows (`0.025`, `0.05`, `0.1 eV`) with `signal_unresolved`. The trace confirms event selection and control, not the physical/numerical validity of U.

## Reconstructed sequence

The following trace gives inclusive ranges for the `hubbard_term: recalculating local occupations` blocks; each block contains 16 atom headers and 16 `Occupations:` summaries. The original files are the `.out` and `.fdf` files in the directory specified by `result_set` in the attached JSON.

| Mode | Run | Site | α (eV) | Population events (inclusive lines) | SCF/convergence |
|---|---|---|---:|---|---|
| REF | `00_REFERENCE` | — | 0 | E1 4898–5363; E2 5367–5832; E3 5863–6328; E4 6332–6797; E5 6801–7266; E6 7270–7735; E7 7739–8204; E8 8208–8673; E9 8677–9142; E10 9145–9610; E11 9614–10079; E12 10082–10547; E13 10550–11015; E14 11018–11483; E15 11486–11951; E16 11954–12419; E17 12432–12897 | converged in 15 iterations, line 12428; E17 is post-convergence |
| BARE | `A_BARE_m0d025` | MnLR00 | -0.025 | E1 4901–5366; E2 5370–5835; E3 5871–6336 | 1 step; SCF_NOT_CONV line 5866 |
| BARE | `A_BARE_m0d050` | MnLR00 | -0.050 | E1 4901–5366; E2 5370–5835; E3 5871–6336 | 1 step; SCF_NOT_CONV line 5866 |
| BARE | `A_BARE_m0d100` | MnLR00 | -0.100 | E1 4901–5366; E2 5370–5835; E3 5871–6336 | 1 step; SCF_NOT_CONV line 5866 |
| BARE | `A_BARE_p0d000` | MnLR00 | +0.000 | E1 4901–5366; E2 5370–5835; E3 5876–6341 | 1 step; converged (α=0) |
| BARE | `A_BARE_p0d025` | MnLR00 | +0.025 | E1 4901–5366; E2 5370–5835; E3 5871–6336 | 1 step; SCF_NOT_CONV line 5866 |
| BARE | `A_BARE_p0d050` | MnLR00 | +0.050 | E1 4901–5366; E2 5370–5835; E3 5871–6336 | 1 step; SCF_NOT_CONV line 5866 |
| BARE | `A_BARE_p0d100` | MnLR00 | +0.100 | E1 4901–5366; E2 5370–5835; E3 5871–6336 | 1 step; SCF_NOT_CONV line 5866 |
| SCREENED | `A_SCREENED_m0d025` | MnLR00 | -0.025 | E1 4906–5371; E2 5375–5840; E3 5871–6336; E4 6339–6804; E5 6807–7272; E6 7275–7740; E7 7743–8208; E8 8211–8676; E9 8679–9144; E10 9147–9612; E11 9625–10090 | converged in 9 steps, line 9621; final event E11 |
| SCREENED | `A_SCREENED_m0d050` | MnLR00 | -0.050 | E1 4906–5371; E2 5375–5840; E3 5871–6336; E4 6339–6804; E5 6807–7272; E6 7275–7740; E7 7743–8208; E8 8211–8676; E9 8679–9144; E10 9147–9612; E11 9615–10080; E12 10083–10548; E13 10551–11016; E14 11029–11494 | converged in 12 steps, line 11025; final event E14 |
| SCREENED | `A_SCREENED_m0d100` | MnLR00 | -0.100 | E1 4906–5371; E2 5375–5840; E3 5871–6336; E4 6339–6804; E5 6808–7273; E6 7276–7741; E7 7744–8209; E8 8212–8677; E9 8680–9145; E10 9148–9613; E11 9616–10081; E12 10084–10549; E13 10552–11017; E14 11030–11495 | converged in 12 steps, line 11026; final event E14 |
| SCREENED | `A_SCREENED_p0d000` | MnLR00 | +0.000 | E1 4906–5371; E2 5375–5840; E3 5871–6336; E4 6339–6804; E5 6817–7282 | converged in 3 steps, line 6813; final event E5 |
| SCREENED | `A_SCREENED_p0d025` | MnLR00 | +0.025 | E1 4906–5371; E2 5375–5840; E3 5871–6336; E4 6339–6804; E5 6807–7272; E6 7275–7740; E7 7743–8208; E8 8211–8676; E9 8679–9144; E10 9157–9622 | converged in 8 steps, line 9153; final event E10 |
| SCREENED | `A_SCREENED_p0d050` | MnLR00 | +0.050 | E1 4906–5371; E2 5375–5840; E3 5871–6336; E4 6339–6804; E5 6807–7272; E6 7275–7740; E7 7743–8208; E8 8211–8676; E9 8679–9144; E10 9147–9612; E11 9615–10080; E12 10093–10558 | converged in 10 steps, line 10089; final event E12 |
| SCREENED | `A_SCREENED_p0d100` | MnLR00 | +0.100 | E1 4906–5371; E2 5375–5840; E3 5871–6336; E4 6339–6804; E5 6808–7273; E6 7276–7741; E7 7744–8209; E8 8212–8677; E9 8680–9145; E10 9148–9613; E11 9616–10081; E12 10084–10549; E13 10562–11027 | converged in 11 steps, line 10558; final event E13 |
| BARE | `B_BARE_m0d025` | MnLR01 | -0.025 | E1 4901–5366; E2 5370–5835; E3 5871–6336 | 1 step; SCF_NOT_CONV line 5866 |
| BARE | `B_BARE_m0d050` | MnLR01 | -0.050 | E1 4901–5366; E2 5370–5835; E3 5871–6336 | 1 step; SCF_NOT_CONV line 5866 |
| BARE | `B_BARE_m0d100` | MnLR01 | -0.100 | E1 4901–5366; E2 5370–5835; E3 5871–6336 | 1 step; SCF_NOT_CONV line 5866 |
| BARE | `B_BARE_p0d000` | MnLR01 | +0.000 | E1 4901–5366; E2 5370–5835; E3 5876–6341 | 1 step; converged (α=0) |
| BARE | `B_BARE_p0d025` | MnLR01 | +0.025 | E1 4901–5366; E2 5370–5835; E3 5871–6336 | 1 step; SCF_NOT_CONV line 5866 |
| BARE | `B_BARE_p0d050` | MnLR01 | +0.050 | E1 4901–5366; E2 5370–5835; E3 5871–6336 | 1 step; SCF_NOT_CONV line 5866 |
| BARE | `B_BARE_p0d100` | MnLR01 | +0.100 | E1 4901–5366; E2 5370–5835; E3 5871–6336 | 1 step; SCF_NOT_CONV line 5866 |
| SCREENED | `B_SCREENED_m0d025` | MnLR01 | -0.025 | E1 4906–5371; E2 5375–5840; E3 5871–6336; E4 6339–6804; E5 6807–7272; E6 7275–7740; E7 7743–8208; E8 8211–8676; E9 8679–9144; E10 9147–9612; E11 9625–10090 | converged in 9 steps, line 9621; final event E11 |
| SCREENED | `B_SCREENED_m0d050` | MnLR01 | -0.050 | E1 4906–5371; E2 5375–5840; E3 5871–6336; E4 6339–6804; E5 6807–7272; E6 7275–7740; E7 7743–8208; E8 8211–8676; E9 8679–9144; E10 9147–9612; E11 9615–10080; E12 10083–10548; E13 10551–11016; E14 11029–11494 | converged in 12 steps, line 11025; final event E14 |
| SCREENED | `B_SCREENED_m0d100` | MnLR01 | -0.100 | E1 4906–5371; E2 5375–5840; E3 5871–6336; E4 6339–6804; E5 6808–7273; E6 7276–7741; E7 7744–8209; E8 8212–8677; E9 8680–9145; E10 9148–9613; E11 9616–10081; E12 10084–10549; E13 10552–11017; E14 11030–11495 | converged in 12 steps, line 11026; final event E14 |
| SCREENED | `B_SCREENED_p0d000` | MnLR01 | +0.000 | E1 4906–5371; E2 5375–5840; E3 5871–6336; E4 6339–6804; E5 6817–7282 | converged in 3 steps, line 6813; final event E5 |
| SCREENED | `B_SCREENED_p0d025` | MnLR01 | +0.025 | E1 4906–5371; E2 5375–5840; E3 5871–6336; E4 6339–6804; E5 6807–7272; E6 7275–7740; E7 7743–8208; E8 8211–8676; E9 8679–9144; E10 9157–9622 | converged in 8 steps, line 9153; final event E10 |
| SCREENED | `B_SCREENED_p0d050` | MnLR01 | +0.050 | E1 4906–5371; E2 5375–5840; E3 5871–6336; E4 6339–6804; E5 6807–7272; E6 7275–7740; E7 7743–8208; E8 8211–8676; E9 8679–9144; E10 9147–9612; E11 9615–10080; E12 10093–10558 | converged in 10 steps, line 10089; final event E12 |
| SCREENED | `B_SCREENED_p0d100` | MnLR01 | +0.100 | E1 4906–5371; E2 5375–5840; E3 5871–6336; E4 6339–6804; E5 6808–7273; E6 7276–7741; E7 7744–8209; E8 8212–8677; E9 8680–9145; E10 9148–9613; E11 9616–10081; E12 10084–10549; E13 10562–11027 | converged in 11 steps, line 10558; final event E13 |

## Configuration and checks

- Reference DM SHA-256: `65d418d1a21b4b4052d41d68554639fc4bc4682566bb780c0d072fd4cfe5eb47`.
- Response receipt: `da0363ebeaa4705063917dfb32c53db8501b02c743ce11167849bac63431b7c6`; Slurm job `333`.
- SHA-256 of the SIESTA executable declared in the receipt: `aaa9a2e45a41b12f3aad52ca4fca7c25b1cc6afd3aff2a0c7fe145b1bd9f18ce`; MPI: `e3a009cd4ab8b41ef23019df3a1388944294b330b7c51ad17be18a0120b36daa`.
- Reference FDF settings: `DFTU.PotentialShift true`, `DFTU.FirstIteration false`, `SCF.Mix Hamiltonian`, `SCF.MustConverge T`, `MaxSCFIterations 300`, `DM.UseSaveDM false`.
- BARE FDF settings: `DFTU.PotentialShift true`, `DFTU.FirstIteration true`, `SCF.Mix Hamiltonian`, `SCF.MustConverge F`, `MaxSCFIterations 1`, `DM.UseSaveDM true`.
- SCREENED FDF settings: `DFTU.PotentialShift true`, `DFTU.FirstIteration true`, `SCF.Mix Hamiltonian`, `SCF.MustConverge T`, `MaxSCFIterations 300`, `DM.UseSaveDM true`, `SCF.DM.Converge T`, `SCF.H.Converge T`.
- Semantic source compared: `docs/audits/SIESTA_542_BARE_SOURCE_AUDIT_20260909.md` (commit SIESTA `e486d12067b96ff688179f0496d0ec21b6fae0ab`).
- Machine-readable per-run details, FDF/OUT/DM hashes, markers, and the 16 sites in each event: the attached JSON.
