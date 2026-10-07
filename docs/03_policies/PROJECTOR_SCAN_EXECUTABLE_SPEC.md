# Projector scan and plateau executable specification

This document turns `PROJECTOR_SCAN_POLICY.md` and `PLATEAU_DETECTION_POLICY.md`
into a typed input and result contract. It is a specification skeleton: it does
not generate FDF files, schedule jobs, run SIESTA, calculate U, or evaluate the
numeric plateau thresholds.

## Scientific invariants

- A reported U belongs to the exact projector parameter and generation method
  that produced it. Results from distinct projectors remain separate; they are
  never averaged (LR-19/LR-20).
- U is acceptable only for the projector the user declares. A declared
  projector with its U(parameter) curve attached is
  `PROJECTOR_DECLARED_AND_CHARACTERIZED`; plateau evidence is optional.
- A scan uses `DFTU.ProjectorGenerationMethod 2` and probes one representative
  site. Each candidate uses the same FDF except for its one projector line.
- Each candidate probe is one direct column: twelve response runs and one
  reference run. The response count is fixed by the probe contract, not inferred
  from the number of projector candidates.
- A `CutoffNorm` scan is invalid when explicit `rc` projector records are
  present. A candidate with any non-projector FDF change is rejected.
- Missing declaration or scan/curve evidence yields
  `PROJECTOR_NOT_ASSESSED`. Missing user-declared plateau criteria leave only
  the optional plateau outcome unassessed; no numeric criterion has a default.
  A computed U remains reportable, and lack of a plateau never blocks using U
  for its declared projector. Plateau confirmation is additional evidence and
  does not certify final U.
- The production-value control compares the probe U at the projector already
  used in production with the corresponding site U from the full campaign. Its
  absolute difference is always recordable and is not converted into an
  undeclared threshold.

## Typed input

`hubbardflow.domain.projector_plateau.ProjectorScanSpec` contains the
representative site, parameter kind, production projector, candidate projector
values, and optional `PlateauCriteria`. The latter has three declared
parameters: maximum U variation in eV, minimum points in the connected window,
and refinement step in the scanned parameter. Every parameter is optional in
the schema; the assessment remains NOT_ASSESSED until all required values and
gate evidence are supplied. The schema does not choose their values.

FDF candidate validation lives in
`hubbardflow.siesta_backend.projector_scan_inputs`, because FDF syntax belongs
to the backend. It requires Method 2 in both inputs, the same line count,
byte-identical non-target lines, and exactly one changed projector line.
CutoffNorm candidates are rejected when the effective projector block has any
explicit `rc` row, including a row whose value is `0.0`. Explicit-rc candidates
may change only the `rc` row in the effective method-2 projector block.
Unsupported block syntax fails closed. Included-file resolution and full SIESTA
precedence remain the responsibility of the eventual input-generation caller
before passing effective FDF text to this validator.

## Stage and result contract

The prescribed order is:

1. `COARSE_SCAN`
2. `REFINEMENT`
3. `EVALUATION`
4. `PLATEAU_DETECTION`
5. `LOCK`
6. `FULL_RESPONSE`

The assessment is a result state, not a calculation stop gate:

| Characterization status | Meaning | U accepted for declared projector? |
|---|---|---:|
| `PROJECTOR_DECLARED_AND_CHARACTERIZED` | User declaration and a U(parameter) curve are attached; optional plateau is absent or unassessed. | Yes, for the declared projector only. |
| `PROJECTOR_PLATEAU_CONFIRMED` | The declaration/curve are present and all declared optional plateau criteria/evidence pass. | Yes, for the declared projector only. |
| `PROJECTOR_NOT_ASSESSED` | Declaration or characterization curve is missing. | No. |

The optional plateau outcome is recorded separately as
`PROJECTOR_PLATEAU_CONFIRMED`, `PROJECTOR_NO_PLATEAU`, or
`PROJECTOR_NOT_ASSESSED`. Failure to find a plateau leaves the characterization
status at `PROJECTOR_DECLARED_AND_CHARACTERIZED`; it does not reject the
projector-specific U. When no plateau is established, the report includes the
literal phrase `no plateau; U is projector-specific` and the adjacent secant
slopes `dU/d(norm)` from the observed curve. No averaging between projector
values is permitted.

## Measured M1 CutoffNorm fixture

The fixture `tests/fixtures/projector_curve_m1.json` records nine measured
Yoltla points for the one-column MnLR00 probe (Mn formal d3):

| CutoffNorm | U (eV) | n_ref (e) | Projector support (bohr) |
|---:|---:|---:|---:|
| 0.50 | 25.0833 | 2.6050 | 1.452035750261572 |
| 0.60 | 19.0979 | 3.0697 | 1.588122997468477 |
| 0.70 | 15.4146 | 3.5521 | 1.765052169941702 |
| 0.80 | 13.0972 | 4.0605 | 2.011479793011571 |
| 0.85 | 12.0211 | 4.3436 | 2.188619831130068 |
| 0.90 | 10.6622 | 4.6739 | 2.439367465832430 |
| 0.95 | 8.2302 | 5.1445 | 2.872995373814031 |
| 0.98 | 6.2659 | 5.6680 | 3.455406057237902 |
| 0.99 | 5.5708 | 5.8848 | 3.893329137527022 |

The recorded verification says the nine runs differed only in the
`DFTU.CutoffNorm` line and the Mn magnetic moment stayed between 2.9207 and
2.9183 muB. The fixture preserves these values as measurement metadata. The
observed least-steep adjacent interval is 0.80–0.85: U falls by 1.0761 eV over
0.05 in CutoffNorm (secant slope -21.522 eV per norm). No user plateau criteria
are declared in this fixture, so it does not establish a plateau. Any
no-plateau observation is limited to these nine sampled points and does not
generalize to unsampled projector values.

Required plateau evidence covers result stability, response linearity,
electronic state continuity, magnetic stability, matrix conditioning, local
sensitivity stability, and all non-failed blocking gates. The typed skeleton
accepts externally assessed gate states; it does not implement these analyses.
`LOCK` records a candidate projector configuration and advances to
`FULL_RESPONSE`; it does not certify U by itself.

## Production-value internal control

`ProductionControl` records the exact projector, probe U, full-campaign site U,
and `abs(probe U - full-campaign site U)`. The projector must be the production
projector. For the current M1 control, the one-column probe value is 10.6622 eV
and the 36x36 full-campaign value is in [10.6578, 10.6586] eV. The absolute
difference spans 0.0036–0.0044 eV; the recorded maximum is 0.0044 eV. This is
retained as evidence only; it has no acceptance threshold or gate.

`ProjectorUResult` stores each reported U alongside its exact `ProjectorValue`.
There is no aggregate or averaging API over candidates; a report must preserve
one U row per projector identity.

## Record-only support geometry

`ProjectorSupportGeometry` records the generated projector header values
(`npts`, `delta`, and `cutoff`) when available, the support radius in bohr, and
the minimum distance between Hubbard sites. The diagnostic compares support
radius with half that minimum distance and records whether support exceeds it.
This is an exact geometric observation only: it cannot reject a projector, a
scan, or U. No quantitative overlap metric or threshold is specified here.
For M1, Mn–Mn is 5.390 bohr (half-distance 2.695 bohr), Mn–O is 3.59 bohr,
and the basis PAO 3d radius is 4.502 bohr, identical across CutoffNorm values.
The generated projector support at CutoffNorm 0.90 is 2.439367465832430 bohr,
below half the Mn–Mn distance. At 0.95, 0.98, and 0.99 the recorded generated
support exceeds that half-distance. This comparison is record-only geometry;
it neither grants nor rejects physical equivalence, projector validity, or U.
The typed record does not parse projector files; interpreting SIESTA output
remains a future backend responsibility.

## Serialization

The dataclasses provide explicit `to_mapping()` / `from_mapping()` pairs. The
pure domain serialization records candidate projector identities; FDF
validation remains a separate backend operation. No digest is used as a
projector equivalence or plateau decision.
