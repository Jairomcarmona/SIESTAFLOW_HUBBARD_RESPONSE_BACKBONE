# MnO: Audit of the Correspondence Between Linear Response and the DFT+U Functional

Date: 2026-09-23. Static audit of the code, SIESTA 5.4.2 source, and saved
results. SIESTA was not run and no campaign was started.

## Main finding: calculated U is not, in general, the applied U−J

`tools/run_mno_afmii_response_quantized_v1.py` selects only
`precision[atom.atom_index].total` in `_occupations` (lines 142–160). From this
total, $n_I=n_{I\uparrow}+n_{I\downarrow}$, it fits BARE and SCREENED response
matrices, and `src/siestaflow_hubbard/domain/quantized_response.py` (lines
93–111) computes

\[
U_I^{\rm charge}=\left[\chi_0^{-1}-\chi^{-1}\right]_{II}.
\]

The formula and matrix evaluation are correct **for the scalar charge
response defined this way**. Current evidence gives 11.5320557 eV; the BARE /
SCREENED difference is in the native occupations and does not arise from an
accidental sign change or inversion.

However, the validation FDFs (for example,
`campaigns/mno_afmii_strict_lr_v3r2/results/u1153_minimal_afmii_relaxation/siesta.fdf`,
lines 49–57) pass `11.53 0.00` to `DFTU.Proj` with
`DFTU.PotentialShift false`. In
`third_party/siesta-5.4.2-source-audit/Src/dftu.F` (lines 682–713), the normal
branch explicitly uses `Ueff = U - J` and constructs a Dudarev-type potential
that depends on the occupation matrix for *each spin*. That functional has
intra-spin quadratic terms and no mixed correction term
$n_\uparrow n_\downarrow$. The parameter obtained by perturbing and observing
both spins together generally includes the cross-spin response. Therefore,
automatically identifying $U^{\rm charge}=U_{\rm eff}^{\rm Dudarev}$ for
magnetic MnO is unjustified.

Linscott et al., *Phys. Rev. B* **98**, 235157 (2018),
[full text](https://harvest.aps.org/v2/journals/articles/10.1103/PhysRevB.98.235157/fulltext),
Sec. II B and Eqs. 27–28, demonstrate equivalence between scalar response and
a spin-resolved combination that includes inter-spin interactions. On page 5
they explicitly explain that this result **does not correspond** to the
single-spin interaction $U_{\rm eff}=U-J$ of the conventional correction.
This is a published methodological result, not a conjecture based on the
number appearing high. The paper itself shows, for MnO with a different code,
projectors, and definition of $\chi_0$, that different spin treatments give
different values; its numbers are not directly interchangeable numerical
references for this campaign.

## Verifiable consequence for the software

The analysis output `REPORTABLE_NUMERICAL_U_INTERVAL` certifies at most a
rounding interval for **scalar charge U**. It does not certify equivalence to
the coefficient of the later-applied functional or physical predictions for
MnO. The `.out` files retain up/down occupations, but the campaign applied the
same shift to both spins; those perturbations do not determine the full
matrix $\partial n_{I\sigma}/\partial\alpha_{J\sigma'}$ separately. Refitting
the same data or reducing rounding error does not resolve that identification.

This correspondence failure could explain why a numerically stable U does
not reproduce observables. **It does not, by itself, prove that 11.53 eV is an
incorrect scalar U or quantify how much of the physical anomaly arises from
this issue**. Documented projector sensitivity and the material's other
approximations remain separate causes. Do not replace 11.53 with another
value before defining which parameter the applied functional is meant to
receive.

## Additional check on existing outputs

Printed spin-resolved totals were extracted from the same selected events,
and each component was fit against the seven saved alpha values. For site A,
BARE up/down slopes are −0.063203/−0.083502 electrons per eV; SCREENED slopes
are −0.018350/−0.035788. Site B swaps those two components due to AFM
orientation. Both spin slopes have the same sign, so **there is no
inter-spin cancellation that could artificially explain the high value of
11.53 eV**. Total SCREENED response is approximately −0.05414 versus
−0.14670 BARE; this reduction is the immediate numerical source of high U for
this model. This check only rereads existing outputs.

The product correction is to name the result `U_scalar_charge`, retain its
provenance, and block automatic promotion to `Ueff_Dudarev` in spin-polarized
calculations unless an explicit derivation and validation of that
correspondence exists. Merely changing the U number or the FDF J field does
not repair the issue: the examined implementation uses the difference
`U-J` for the same Dudarev term.
