# Context Report: Bottleneck in Obtaining and Reporting U with SIESTAFLOW

**Date:** 2026-09-29
**Purpose:** provide another assistant with a sufficiently complete technical status to reason about investigation paths, challenge current hypotheses, and propose the next step that would add the most information.
**Scope of this report:** synthesis and analysis of existing evidence. It does not authorize a new campaign, SIESTA execution, changes to SIESTA code, changes to historical data, or tolerance changes.

**Terminal state of the P0–P6 closeout recorded on 2026-09-28:** `PRODUCT_BLOCKED`.
Operational gates P0–P6 passed and wheel 0.1.2 was built, but P5 remained
`NUMERICAL_CANDIDATE_UNASSESSED` / `NOT_ESTABLISHED`. According to the
[final execution log](P0_EXECUTION_20260928.md), this does not meet the
scientific objective the user requires to consider the product ready. This
report seeks a way to resolve that block; it does not reclassify the terminal
state.

**Repository availability:** implementation 0.1.2, several v3 modules, tests,
and closeout documents are on published branch
`codex/sync-product-20260929` y en el
[PR borrador #4](https://github.com/Jairomcarmona/SIESTAFLOW_HUBBARD_RESPONSE_BACKBONE/pull/4).
Branch `main` retains an earlier version. See the
[synchronization inventory](ESTADO_REPOSITORIO_Y_PUBLICACION_20260929.md)
before attributing this record's status to the remote branch.

---

## 1. Executive summary

The problem to solve is not simply “make the report say U is useful” or “get more decimals.” The core need is for SIESTAFLOW to produce a Hubbard U response that is **numerically useful, reproducible under an explicit protocol, and presented with an honest interpretation**, using supported SIESTA installations without modifying them.

The completed P0–P6 closeout delivered the operational workflow and a 25-node
P5 campaign, but ended as **`PRODUCT_BLOCKED`** because the scientific U goal
remains unresolved. `0.1.2` identifies the built and tested package; it must
not be
interpreted as a declaration of `PRODUCT_READY`.

There is a fundamental difference between two questions:

1. **Does the software work as a tool?** It can receive a structure/configuration, prepare and run the supported protocol, record provenance, analyze the response, and generate reproducible results or an informative terminal state.
2. **Is numerical or physical acceptance established for a particular NiO U?** That requires additional criteria and evidence. A numerical candidate can be useful without physical acceptance being established.

The current adaptive NiO campaign report gives `NUMERICAL_CANDIDATE_UNASSESSED` and `NOT_ESTABLISHED` for physical acceptance because no sensitivity tolerance was declared before that campaign. `STOP_STABLE` means its adaptive-refinement stopping rule was met; **it does not** by itself turn that rule into a guarantee of physical accuracy.

The operational target the user later selected is ±0.02 eV per site for `U_scalar_charge`. It is an engineering/numerical-acceptance target to investigate, not a universal physical constant or a threshold automatically recognized by all methods. A conservative deterministic bound exceeding 0.02 eV means **the current procedure does not certify that target under that bound**. It does not prove that actual U error exceeds 0.02 eV, that U is useless, or that the linear-response method failed.

The primary cubic bound in the adaptive result is **0.03436273105 eV**. The value **0.01353711826 eV** is from a diagnostic linear fit. They must not be interchanged: they use different estimators. For the separate fixed-mesh P5 campaign, the reported v3 deterministic printing bound is approximately **0.01183306193 eV** per site. These magnitudes differ because propagation depends on the mesh, observations used, and estimator.

Evidence already rules out a simple attribution of the between-campaign difference to SCF noise: rereading with the same v3 analyzer gives a P5–adaptive distance around 10.22 meV per site, within the deterministic printing bounds for both. By contrast, applying v2 and v3 to the same adaptive files shifts U by approximately 30.5–31.6 meV, showing that changing occupation source/semantics and analyzer can move the result more than the between-campaign difference. This historical incompatibility is identified and must not be conflated with SCF repeatability.

Public comparison with other codes provides context, not an acceptance criterion: Quantum ESPRESSO shows diagonal U to four decimal places in normal output and matrices to six decimals in more detailed output; its documentation sets convergence thresholds separately. A developers' email describes a 15-decimal matrix format and a field-width adjustment to prevent adjacent negative numbers from running together. VASP shows occupations to three decimals in a tutorial. None of these decimal counts proves U accuracy by itself, and their algorithms/observables may not be comparable to SIESTAFLOW.

Therefore, promising paths must not assume that `f12.6` is the bottleneck, that ±0.02 is physically mandatory, or that the current analysis is necessarily too strict. First identify which component consumes the margin and which claim should be guaranteed: print resolution, estimator robustness, SCF repeatability, protocol stability, or agreement with an independent physical value. These are different claims and require different tests.

---

## 2. What the project is and what it should deliver

`siestaflow_hubbard` is a standalone utility for calculating and reporting the charge response associated with local Hubbard-type perturbations in SIESTA. It automates the campaign protocol and preserves the relationship between inputs, nodes, outputs, and analysis, rather than requiring a person to coordinate each calculation manually and reconstruct provenance afterward.

The intended user workflow is generally:

```text
configure inputs and sites
        ↓
init → run / status / resume → report
        ↓
traceable campaign → per-site response → versioned JSON + Markdown report
```

The CLI includes commands `init`, `run`, `status`, `resume`, `report`, and `stop`. The target operation includes PowerShell→WSL and Linux execution; there is also a path for using an already granted Slurm allocation. The tool must not depend on a private SIESTA rebuild: portability to supported SIESTA installations is part of the product's value.

The current product charter is [`docs/EJE_RECTOR_CIERRE_PRODUCTO.md`](EJE_RECTOR_CIERRE_PRODUCTO.md). It defines the standalone utility as the product and distinguishes product closeout from physical acceptance for each material. The plan documents scope limits, gates, investigation paths, and terminal states. It does not itself authorize another campaign.

### 2.1 Reported observable

The method estimates the unscreened and screened response matrices:

\[
\chi^0_{IJ}=\left.\frac{\partial n_I^{\mathrm{BARE}}}{\partial\alpha_J}\right|_{0},\qquad
\chi_{IJ}=\left.\frac{\partial n_I^{\mathrm{SCREENED}}}{\partial\alpha_J}\right|_{0}.
\]

The quantity implemented as `U_scalar_charge` is:

\[
U_I=\left[(\chi^0)^{-1}-\chi^{-1}\right]_{II}.
\]

Here, `I` identifies the site and `J` the perturbed site. Projected occupation depends on the orbital/projector definition and how it is extracted from output. `U_scalar_charge` is not automatically `Ueff_Dudarev`; SIESTA applies a `U-J` combination in its collinear Dudarev implementation, and equivalence would require a separate physical contract. Nor should an off-diagonal element automatically be labeled as parameter V from another functional.

### 2.2 Scientific/technical scope

The version's certified scope centers on SIESTA 5.4.2 and spin modes with tested protocols and parsers. It does not promise a universal material U or automatic support for SOC, non-collinear spin, or separately calculated J. Tool acceptance is not determined by comparing U with literature, gaps, lattice parameters, or an expected NiO value. Such comparisons may be described as external context, but not used to select alpha, window, estimator, or U.

---

## 3. Case behind the bottleneck: NiO

The central case is type-II antiferromagnetic NiO with PBE and two inequivalent correlated sites in the response model, reported as `NiLR0` and `NiLR1`. The method applies local alpha perturbations, runs BARE and SCREENED calculations according to protocol, and reconstructs responses to calculate U per site.

There is more than one campaign and analysis generation. They must not be treated as a homogeneous series:

| Item | Context | Meaning |
|---|---|---|
| Historical/adaptive v2 campaign | 41 nodes total: 1 reference, 20 BARE, and 20 SCREENED across adaptive rounds | Recorded the adaptive protocol and initial analysis; part of the result is tied to v2 occupation source/semantics. |
| Reanalysis of the same adaptive OUT files with v3 | Uses the same generated material, but current selector/parser/analysis | Allows a controlled comparison of extraction method; it is not a new SIESTA campaign. |
| Fixed P5/v3 closeout | Fixed mesh of 25 nodes documented for the previous closeout | Result from another protocol/mesh; not a certified replicate of the adaptive campaign. |
| Possible future calibration | Separate contract proposes three full replicas and one preregistered primary | Prospective design of up to 100 nodes (25 + 3×25); a proposal, not an authorization or automatically pending execution. |

The previous P5 path had a campaign limit of up to 25 nodes for the selected NiO alternative. This limit must not be confused with the prospective 100-node calibration design: these are different goals and contracts. There is no current authorization to start another campaign.

### 3.1 Current adaptive values and reports

The v3 adaptive report associated with campaign UUID `99d5ee67-d9cf-41f1-9f8f-39315c6e81fd` identifies material `NiO-AFMII-PBE`, SIESTA 5.4.2, analyzer v0.1.2, and schema v3. It reports approximately:

| Quantity | NiLR0 | NiLR1 |
|---|---:|---:|
| `U_scalar_charge` in adaptive v3 analysis | 6.86706412 eV | 6.86623404 eV |
| Estimator-sensitivity diagnostic | 0.00604 eV | 0.00534 eV |
| Window-sensitivity diagnostic | 0.004777 eV | 0.004359 eV |
| χ⁰ condition | rank 2/2; condition ≈1.745 | rank 2/2; condition ≈1.745 |
| χ condition | rank 2/2; condition ≈1.024 | rank 2/2; condition ≈1.024 |

Sensitivity figures are empirical diagnostics across considered analysis choices; they are not automatically standard errors, confidence intervals, or bounds on true error. Condition values suggest these report matrices are not severely ill-conditioned in the usual numerical sense. This makes an obvious singularity as the sole bottleneck less plausible, but does not replace a complete perturbation-propagation inspection or prove the projector's physical quality.

The adaptive algorithm recorded refinement decisions in earlier rounds and ended with `STOP_STABLE` after two consecutive equivalent comparisons passed its internal rule. The reported active window and final alpha set are part of the analyzed protocol. `STOP_STABLE` expresses stability relative to that rule; it does not mean “physical sensitivity is below ±0.02 eV,” because `sensitivity_tolerance_eV` was not configured for that campaign.

### 3.2 Non-equivalent campaigns: quantitative comparison

The precision contract records a comparable v3 reconstruction from two existing sources:

| Analysis source/method | NiLR0 (eV) | NiLR1 (eV) |
|---|---:|---:|
| Adaptive round-00, historical v2 analysis | 6.8845915692 | 6.8857890044 |
| Same adaptive files, re-extracted and analyzed with v3 | 6.8540481204 | 6.8541678955 |
| P5, v3 analysis | 6.8642677000 | 6.8643874752 |

Comparing P5 and adaptive with the same v3 treatment gives a difference of about **10.2196 meV per site**, essentially equal at both sites. The v3 deterministic printing bounds cited for these reconstructions are approximately **11.8331 meV** and **11.8342 meV**. Thus this difference falls within the considered printing bounds and cannot by itself isolate an SCF/reproducibility contribution.

By contrast, v2 versus v3 applied to the same adaptive OUT files shifts U by approximately **30.5434 meV** for NiLR0 and **31.6211 meV** for NiLR1. This is associated with the change in occupation source/interpretation (`matrix_trace` in historical v2 versus `siesta_occupations_total` in v3), along with analysis version/selector. **This is not SIESTA execution noise**, because the output files are the same. The historical 20–21 meV campaign difference must not be attributed to SCF before correcting for this semantic difference.

Receipts for 25/25 nodes in each compared campaign were validated for FDF/OUT/DM, with distinct campaign, node, and execution identifiers. They share the reference DM SHA and some metadata; both declare SIESTA 5.4.2, the same path, and the same version text. However, no executable content hash was archived. This supports diagnostic reanalysis but is not formal calibration of reproducibility between binaries.

---

## 4. What the current states mean

The latest relevant result is classified as:

```text
NUMERICAL_CANDIDATE_UNASSESSED
physical_acceptance: NOT_ESTABLISHED
```

The correct reading is that a numerical candidate with reproducible analysis was produced, but the protocol does not support claiming acceptance under a sensitivity/precision criterion declared before the campaign, and physical acceptance remains unestablished. It does not mean “U is useless,” “the calculation failed,” or “the tool does not work.”

Do not reverse the error and claim that U is guaranteed within ±0.02 eV either. Current evidence does not demonstrate that claim.

Conceptually, the closeout plan allows a utility to work even if a particular
material ends as a sensitive candidate or without physical acceptance. The
final decision for the executed workflow was stricter: the user considered the
main scientific objective unresolved, and the terminal log set
`PRODUCT_BLOCKED`. Therefore, package delivery and product status must be
communicated separately. Resolving the block requires a useful, supported
claim about U, not merely changing the result label.

---

## 5. ±0.02 eV target: status and limits

Document [`docs/U_PRECISION_ACCEPTANCE_CONTRACT_20260928.md`](U_PRECISION_ACCEPTANCE_CONTRACT_20260928.md) sets ±0.02 eV per site for `U_scalar_charge` as the future operational target selected by the user. The contract notes that:

- It is not a universal physical tolerance;
- Alpha, projectors, windows, SCF thresholds, estimator, or criteria must not be changed after seeing U to force a pass;
- The target must be preregistered for prospective evaluation;
- An empirical envelope supports only a claim conditional on the observed protocol;
- Even a conditional numerical pass does not imply physical acceptance;
- `total_numerical_U_interval` may remain `NOT_ESTABLISHED` even if the protocol shows conditional reproducibility.

For P5, the contract calculates a conservative partial sum under the combined model of rounding, estimator sensitivity, and window sensitivity. Even setting the observed replica spread to zero, that sum is approximately:

| Site | Partial sum under the current conservative formula |
|---|---:|
| NiLR0 | 0.0275105 eV |
| NiLR1 | 0.0279243 eV |

Both exceed ±0.02 eV. The exact consequence is: **the current contract, with this conservative composition, cannot certify ±0.02 eV for P5**. It does not logically follow that actual error exceeds 0.02 eV. The bound is deterministic with respect to quantization intervals and may be conservative; sensitivities are diagnostics, not necessarily independent uncertainties that should be summed linearly as error components.

Separately, the primary adaptive cubic bound in the closeout report is **0.03436273105 eV**. The diagnostic linear fit gives **0.01353711826 eV**. The linear result being below 0.02 eV does not authorize choosing it after seeing the result. Preferring an estimator requires a predeclared methodological reason, suitable validation, or a contract explaining the desired estimand. The larger number also does not prove the actual value is wrong: it indicates that the conservative propagation associated with the cubic fit does not meet the operational criterion in that analysis.

### Essential distinction: five different concepts

1. **Printed decimals:** program text format. It determines the resolution of input observed by the parser, not physical accuracy.
2. **Deterministic rounding bound:** propagation of rounding intervals through fitting and matrix inversion under explicit assumptions. It is a possibility envelope, not a probability distribution.
3. **Estimator/window sensitivity:** observed change when varying defined models or subsets. It is not automatically error or statistical uncertainty.
4. **SCF variability/reproducibility:** observed difference between runs under a comparable protocol. This requires separating rounding, inputs, binary, magnetic branches, and convergence criterion.
5. **True physical error/acceptance:** how far the result is from the physical quantity being described. It is not inferred solely from the preceding four concepts or from agreement with literature.

The contract must not combine these concepts without demonstrating independence, distribution assumptions, or coverage. In particular, a linear sum of bounds may be deliberately conservative, but is not a typical error estimate when contributions are correlated or describe different diagnostic variations.

---

## 6. What do decimal places in other codes tell us?

Official or first-hand technical sources were consulted. The comparison helps question what display precision is reasonable, but does not determine how many decimal places SIESTAFLOW should accept.

### Quantum ESPRESSO / `hp.x`

- Official QE 7.5 source, `HP/src/hp_postproc.f90`, writes diagonal Hubbard U values in normal output using format `f10.4`, four decimal places. At higher verbosity it writes Hubbard matrices and responses using `f11.6`, six decimal places. [Source: QE 7.5 `hp_postproc.f90`](https://gitlab.com/QEF/q-e/-/raw/qe-7.5/HP/src/hp_postproc.f90).
- `hp.x` documentation separately defines `conv_thr_chi` (response-convergence threshold, documented default `1.D-5`) and `ethr_nscf` (`1.D-11`). An internal iteration threshold is distinct from the decimal places used to print U or χ. [Source: `INPUT_HP` documentation](https://www.quantum-espresso.org/Doc/INPUT_HP.html).
- A response on the official developer list for QE 6.7 says `hp_write_chi_full.f90` wrote matrices using `f19.15`; the suggestion to change to `f20.15` was made to add a space and prevent adjacent negative values from running together, not to certify accuracy to 15 decimals. [Source: QE developers list](https://lists.quantum-espresso.org/pipermail/developers/2021-July/002428.html).

### VASP

The VASP linear-response tutorial shows occupations to three decimal places and an example of linear U analysis from one perturbation and a fit with multiple perturbations, yielding different values (about 6.33 eV and 5.58 eV in that example). This illustrates that perturbation/fit design can move U more than the number of decimals displayed in a table; it does not allow direct comparison of those numbers with NiO/SIESTA. [Source: VASP Wiki, Calculate U](https://vasp.at/wiki/index.php/Calculate_U_for_LSDA%2BU).

### Cautious conclusion from the comparison

Some codes display U with fewer decimals and matrices with more; this is common because formatting serves readability, debugging, and postprocessing. These sources provide no universal physical rule such as “U is validated to N decimal places” or “a 0.02 eV tolerance is mandatory.” Nor can one conclude that QE's four published decimals mean its U uncertainty is 0.0001 eV, or that 15 internal decimals are 15 physically reliable significant digits.

The useful question is not only “how many decimals do other codes print,” but “what quantitative claim does SIESTAFLOW make, what evidence supports it, and what display precision avoids implying more knowledge than is available?” Reporting U to hundredths may be a display convention; it does not automatically demonstrate a ±0.01 eV bound.

---

## 7. Open hypotheses about the bottleneck

The following hypotheses are alternative explanations to discriminate; none is accepted in advance.

### H1. Quantization propagation is conservative, but its worst case is physically implausible

`Occupations:` is printed to six decimal places on the v3 path. The reader derives a quantization interval per observation and propagates its endpoints to the result. On matrix inversion, combinations of endpoints can be very conservative, especially if treated as independent even when they come from linked quantities or correlated rounding.

**For:** printing bounds exceed the observed change between P5 and the v3 adaptive re-extraction; current bound analysis is not an experiment measuring actual errors.
**Not demonstrated:** that the bound is excessively conservative for this particular problem; that there is sufficient favorable correlation; or that likely rounding error is <0.02 eV.

### H2. Alpha range, window, or fit degree dominates variation

Reported adaptive sensitivity to estimator and window is several meV per site, and the primary cubic bound is larger than the diagnostic linear-fit bound. The result depends on how the derivative at α=0 is approximated and which points are included.

**For:** the model/window comparisons themselves change U measurably.
**Not demonstrated:** which estimator best represents the linear-response limit, or that a narrower or wider window should be selected to meet a particular target. Choosing it based on U would be post hoc bias.

### H3. SCF, magnetic branch, or between-run reproducibility consumes the margin

SCREENED outputs report TDM thresholds `1e-5` and `1e-4 eV`. A post hoc diagnostic of U drift between terminal and last state was calculated at around 8.224 meV/site. This value is not an error bound. There are no full replicas admitted by the calibrator and no independent SCF/reproducibility envelope has been established.

**For:** SCF is a plausible source and the drift diagnostic is nonzero.
**Not demonstrated:** that it is the dominant factor or that a repeat would reduce the total below 0.02 eV. The current campaign comparison cannot isolate it.

### H4. Matrix conditioning

The matrix response affects U through inversion. The adaptive report shows full rank 2/2 and condition numbers of about 1.745 for χ⁰ and 1.024 for χ.

**For:** it is a potentially sensitive transformation.
**Against it being the only obvious problem here:** the reported matrices do not appear ill-conditioned by these indicators.
**Pending:** local sensitivity of U to each entry and observation interval, including dependencies/covariances. Good conditioning does not remove rounding or validate the projector.

### H5. Occupation definition/extraction and analysis versions caused historical differences

The v2→v3 change on the same OUT files shifts U by about 31 meV/site. Current v3 uses the `Occupations:` total (`siesta_occupations_total`); historical v2 analysis used the matrix-trace sum. The historical product charter described `trace_total` as the primary path and `Occupations:` as pending verification; later implementation and reports fixed a different semantics.

**Status:** the historical discrepancy is identified and explains why the raw campaign comparison was misleading. The exact meaning must be documented as the current contract and kept consistent when comparing. Do not attribute that shift to SCF again.

### H6. The problem may be defining a useful product claim, not guaranteeing ±0.02

The practical obstacle may have been amplified by asking for a stronger guarantee than the experimental data/protocol needs, or by mixing physical accuracy with numerical reproducibility. The opposite may also be true: the application may genuinely need ≤0.02 eV to distinguish downstream decisions. The threshold must not be raised or lowered to get a “pass”; justify it by downstream use or report it as a conditional engineering target.

The user recognizes that the tool needs to deliver a useful numerical U rather than remain in permanent refusal. The outstanding work is to propose a useful, supported, testable claim, not defend `NOT_ESTABLISHED` as the final answer to everything.

---

## 8. What was explored and what was ruled out

### Already explored with existing evidence

1. **Reanalyze historical results without rerunning SIESTA.** Adaptive OUT files were reconstructed with v3 extraction and compared with P5 under equivalent analysis.
2. **Separate analysis differences from execution differences.** The v2→v3 change was observed on the same OUT files and shifts U by ~30.5–31.6 meV; therefore, it is not SCF variation.
3. **Check whether the P5–adaptive gap demonstrates SCF noise.** Its v3 difference of ~10.22 meV is within propagated rounding bounds; by itself, it does not support that conclusion.
4. **Review adaptive stopping and sensitivity.** The campaign ended `STOP_STABLE`, but no physical/numerical sensitivity tolerance was declared; this state is not an acceptance guarantee.
5. **Quantify the printing bound with more than one estimator.** The primary adaptive cubic bound is 0.03436273105 eV; the diagnostic linear result is 0.01353711826 eV. The linear value was not substituted because it falls below the target.
6. **Compare other codes' formats and thresholds.** Official examples print U to 4 decimals and matrices to 6 or 15; sources distinguish convergence from formatting.
7. **Investigate whether resolution requires modifying SIESTA.** The portability goal rules out modifying the source or requiring a private rebuild as a product solution.

### Ruled out as a product path

During investigation, a temporary SIESTA 5.4.2 copy with `f20.12` formatting was prepared under `build/siesta542-f20.12-offline/` to explore whether more textual resolution would change the bound. The original audited source `third_party/siesta-5.4.2-source-audit/Src/dftu.F` remained intact. Staging and build logs are a research experiment, not the product backend. **The binary was not run and no campaign was launched with it**, and a complete build receipt for admission was not confirmed. After the user clarified that the tool must be portable to supported SIESTA installations, this path is ruled out as a deployable solution.

This does not show that print resolution is irrelevant; it means the solution cannot require modifying SIESTA. A future improvement must read standard artifacts from a supported installation, or demonstrate with data that the current format is sufficient for the desired claim.

### Must not be presented as fact

- “U is invalid because the conservative bound exceeds ±0.02 eV.” This does not follow from the bound.
- “U is guaranteed because the printed numbers have six decimal places.” This also does not follow.
- “QE prints four decimals, so ±0.02 eV is too strict.” Formatting does not demonstrate accuracy.
- “The campaign discrepancy is 20 meV of SCF noise.” This mixes analysis versions/occupation sources.
- “`STOP_STABLE` means the physical tolerance was met.” No tolerance was configured.
- “A replica campaign is the only possible path.” It may be necessary for a defined repeatability claim, but first rigorously use existing data and clarify what question the experiment must resolve.

---

## 9. Neutral paths forward

Choose steps based on their ability to distinguish hypotheses, cost, and compatibility with standard SIESTA. The suggested order does not assume the primary cause.

### Path A — Settle semantics and quantization using existing files

**Question:** What exact datum is being fitted, at what resolution, and how does that resolution propagate to U?

1. Freeze in the technical report the meaning of the event and `siesta_occupations_total` for reference, BARE, and SCREENED under the supported output version.
2. For existing observations, reconstruct occupation bounds per printed token and derive how each perturbation affects χ⁰, χ, and per-site U.
3. Separate a “deterministic worst case” from explorations of plausible combinations. If a probabilistic interpretation of rounding is proposed, declare the distribution and dependencies before presenting probabilities; Monte Carlo with uniform inputs is not a guarantee without justification of uniformity/independence.
4. Identify which observations contribute to the bound (reference, BARE, SCREENED; site; alpha) and whether one or a few rows dominate. This may reveal which measurement needs better resolution or which equation amplifies the interval.

**Expected result:** determine whether 0.03436 eV is distributed across the protocol, dominated by a specific observation, or whether the endpoint method produces a highly pessimistic envelope. Do not change the acceptance criterion.

### Path B — Distinguish estimation error from model sensitivity

**Question:** Is the cubic fit estimating real curvature/nonlinearity, or does the ±0.02 interval depend on a particular model?

Use existing analyses to document, per site, each occupation–alpha curve, residuals, alpha domain, number of points, degrees of freedom, and linear/cubic coefficient. Review whether the rule for selecting cubic/linear was fixed for scientific reasons before viewing U and whether adaptive points are comparable. If other models are needed, predefine them and treat them as sensitivity; do not choose the smallest U or bound.

**Expected result:** determine what quantity the algorithm reports: a local derivative under a given alpha set, a polynomial derivative over the declared window, or a diagnostic fit. Choose the primary output based on the estimand and a declared rule, not on passing ±0.02.

### Path C — Check accessible resolution without modifying SIESTA

**Question:** Is a more precise standard representation already generated by SIESTA or recoverable from native output of a supported run?

Review SIESTA 5.4.2 documentation and available artifacts to determine whether `Occupations:` and the printed matrix are the only sources, or whether a standard file (for example, DM/HSX or another compatible native product) allows the same projected occupation to be calculated at higher resolution through already supported interfaces. Do not assume DM/HSX contains the same projectors/occupations or that postprocessing can reproduce them without changing the observable. Validate equivalence on existing results before adoption.

**Expected result:** a verifiable “yes/no” answer about a portable precision path. If none exists, the design must treat standard text as the data resolution and report its limitation, not modify the executable.

### Path D — Isolate SCF/reproducibility only if it is the decisive uncertainty

**Question:** Does a repeat run under the same protocol change U by more than the available margin?

Current data are not formal replicas: adaptive and P5 differ in campaign/mesh and analysis history and have no executable content hash; there is also no preregistered protocol for the original campaign's sensitivity tolerance. If, after Paths A–C, SCF remains the dominant term preventing a decision, define a minimal prospective protocol: what to repeat (an informative subset or a full mesh), what remains identical, how to identify the installed executable without modifying it, how to verify the same magnetic branch, how to avoid double-counting rounding, and what decision the result would change.

The current future contract proposes one primary plus three full-mesh replicas (25 nodes each: 100 total with a new primary). This is a conservative option for evaluating conditional reproducibility, not a demonstrated necessity as the first next step. It requires campaign authorization and budget; this report does not authorize it.

**Expected result:** choose between a focused test and the full design, with criteria allowing the path to be abandoned if the data would not change the conclusion.

### Path E — Justify tolerance level based on its use

**Question:** Which downstream decision requires U to be stable to ±0.02 eV?

The threshold could be a legitimate product requirement or a conservative engineering target. To distinguish these, describe downstream use: is U used for a quantitative report, comparing sites, selecting a configuration, feeding a DFT+U calculation, or making a decision that changes at a 20 meV scale? If downstream use does not resolve that scale, the interface could express a different claim level (e.g., reported figures plus a stability category) without pretending to provide a guarantee. If it does resolve that scale, the target remains relevant.

**Limit:** do not change ±0.02 retrospectively merely because the current result fails. Any new policy must be justified by use and applied prospectively or clearly labeled as exploratory reanalysis.

---

## 10. Proposed framework for a useful decision

The next decision should not be “does the bound pass or fail?” in the abstract, but one of these explicit claims:

| Claim level | What must be supported | What it does not imply |
|---|---|---|
| Reproducible result from existing artifacts | Same input/analysis versions produce the same matrices, fits, and U | Does not demonstrate physical accuracy or stability across distinct SIESTA runs |
| Stable under declared model/window | U range across preregistered models/windows is reported and conditionally bounded | Does not demonstrate statistical/true error below that range |
| Sufficient print resolution | Quantization of standard inputs is propagated and compared with the target | Does not guarantee SCF or projector accuracy |
| Conditional execution repeatability | Comparable protocol, controlled branch, and defined replicas produce an observed envelope | Does not guarantee results outside sampled conditions/machine/protocol |
| Physical acceptance | Physical definition of observable, model/projector validity, and a properly justified physical criterion | Not obtained from more decimals or agreement with literature alone |

A useful tool can report several layers rather than collapsing them into one “useful/not useful” result: estimated U; interval from print quantization; spread across models/windows; SCF/reproducibility diagnostic; rank and condition warnings; and the level of claim that is actually supported. This allows delivering a result without hiding limits or calling a calculation “physically invalid” merely because it has not passed a guarantee test that has not yet been designed.

---

## 11. Constraints that must survive any path

1. **Do not edit or rebuild SIESTA as a product solution.** SIESTAFLOW must remain portable to supported installations.
2. **Do not alter historical campaigns, data, or reports.** Save reanalysis separately and link it to the source.
3. **Do not tune alpha, SCF tolerances, projectors, windows, polynomial degree, or criteria to reach a desired U or force a pass.** Method changes require prior justification and freezing.
4. **Do not use agreement with literature as an acceptance criterion** or select a result because it is close to an expected value.
5. **Do not treat output decimals as certified significant figures.** Formatting and accuracy are different.
6. **Do not call a worst-case bound an observed error**, or call an empirical range between two fits a bound.
7. **Do not call the current adaptive/P5 comparison a formal replica.** It is a diagnostic of existing files/history.
8. **Do not start another campaign without authorization and its required gate.** A calibration of up to 100 nodes is documented as a possibility, not authorized.
9. **Communicate product status accurately.** Operational gates finished, but current closeout is `PRODUCT_BLOCKED` due to the user's scientific objective. Distinguish this block from CLI execution failure and from proof that the numerical value is wrong.

---

## 12. Local package serving as primary evidence

Review these local sources for exact definitions, output details, and cited values:

- [`docs/EJE_RECTOR_CIERRE_PRODUCTO.md`](EJE_RECTOR_CIERRE_PRODUCTO.md): current closeout plan, product status, R1/R2 paths, and campaign limits.
- [`docs/P0_EXECUTION_20260928.md`](P0_EXECUTION_20260928.md): final P0–P6 gates log, Sol audit, P5 campaign, wheel, and terminal state `PRODUCT_BLOCKED` (the initial addendum supersedes lower historical sections).
- [`docs/ESTADO_REPOSITORIO_Y_PUBLICACION_20260929.md`](ESTADO_REPOSITORIO_Y_PUBLICACION_20260929.md): pre-publication inventory, local commit selection, and GitHub publication status.
- [`docs/U_PRECISION_ACCEPTANCE_CONTRACT_20260928.md`](U_PRECISION_ACCEPTANCE_CONTRACT_20260928.md): ±0.02 eV target, P5/adaptive review, bounds, and proposed replica protocol.
- [`README.md`](../README.md): purpose, CLI, SIESTA scope, and states.
- JSON/Markdown report and manifest/receipts for the adaptive NiO campaign cited above: v3 values, terminal state, mesh, rounds, and provenance.
- P5 report and receipts: fixed reconstruction, occupations, and printing bounds.
- `src/siestaflow_hubbard/siesta_backend/occupation_precision.py`: interpretation of printed decimals and half-widths.
- `src/siestaflow_hubbard/lr_analysis_v2.py`: analysis policy, tolerances, and response context.

Absolute campaign-artifact paths may depend on Windows/WSL and user paths; resolve evidence from roots recorded in receipts instead of assuming a fixed portable path.

---

## 13. Concrete questions for the next analysis

A useful external analysis should answer, with evidence rather than prior preference:

1. Which bottleneck contributes most to the inability to support a ±0.02 eV claim today: quantization, model/window, SCF/reproducibility, observable definition, or mixed versions?
2. Which parts are demonstrated by existing data, and which are only plausible hypotheses?
3. Is the conservative sum `B_round + E_estimator + E_window + E_SCF/repro` mathematically appropriate for the desired claim? What dependencies or double-counting are present? If another rule is proposed, what coverage/guarantee does it have and under which explicit assumptions?
4. Can a more informative quantization diagnostic be calculated from the same results without assigning an unjustified probability to rounding?
5. What portable option based on native SIESTA outputs could provide higher resolution without changing the observable or rebuilding the program, and what equivalence test would falsify it?
6. What minimal prospective experiment would change the decision, if one is essential? Explicitly compare the value of a focused test with the 100-node full-replica campaign. Do not run anything.
7. What product claim would let the user obtain a useful U without presenting untested physical accuracy as guaranteed?
8. What evidence would refute each proposed explanation? Avoid a single dominant narrative when the data do not distinguish one.

---

## 14. Neutral prompt to include with this report

> Read this report as an evidence record, not as an instruction to defend the
> existing criterion. Analyze SIESTAFLOW's bottleneck in obtaining a useful,
> supported numerical U while preserving portability to standard SIESTA 5.4.2
> installations. Explicitly distinguish observed facts, inferences, and
> unresolved questions. Try to falsify hypotheses H1–H6: do not assume
> `f12.6` is the cause, ±0.02 eV is a physical law, the conservative bound is
> the actual error, or the current analysis is right merely because it fails
> the gate. Do not retrospectively lower the target to get approval either.
> Use existing evidence and linked sources first. Compare quantization,
> estimator/window, SCF/reproducibility, conditioning, and observable
> semantics. Propose the smallest next action that discriminates hypotheses
> and explain what result would change the decision. Do not modify files or
> parameters, run SIESTA, start a campaign, or use agreement with literature
> as an acceptance criterion. Return: (1) prioritized diagnosis with
> confidence, (2) evidence for and against, (3) minimum next action, (4) cost/
> nodes if applicable, clearly as an unauthorized proposal, and (5) the U
> claim that would be legitimate to communicate after that action.

If you only have GitHub access, review
[draft PR #4](https://github.com/Jairomcarmona/SIESTAFLOW_HUBBARD_RESPONSE_BACKBONE/pull/4)
and its branch to compare the code, tests, and 0.1.2 documents. State which
claims still depend on WSL artifacts not included in GitHub; do not infer
them from the PR summary alone.

---

## 15. External sources consulted

- Quantum ESPRESSO, official QE 7.5 code: [`HP/src/hp_postproc.f90`](https://gitlab.com/QEF/q-e/-/raw/qe-7.5/HP/src/hp_postproc.f90).
- Quantum ESPRESSO, official [`INPUT_HP`](https://www.quantum-espresso.org/Doc/INPUT_HP.html) documentation.
- Quantum ESPRESSO Developers mailing list, note on `hp_write_chi_full.f90`, `f19.15`/`f20.15` formatting, and matrix output: [July 2021 message](https://lists.quantum-espresso.org/pipermail/developers/2021-July/002428.html).
- VASP Wiki, linear-response U tutorial: [`Calculate U for LSDA+U`](https://vasp.at/wiki/index.php/Calculate_U_for_LSDA%2BU).

These sources are cited to describe formats, thresholds, and methodological examples from other codes. They are **not** used to validate NiO U or set SIESTAFLOW's acceptance criterion.
