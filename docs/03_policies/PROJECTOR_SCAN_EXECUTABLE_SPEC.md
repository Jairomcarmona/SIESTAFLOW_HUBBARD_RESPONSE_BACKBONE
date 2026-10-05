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

## Provisional M1 CutoffNorm fixture

The current fixture contains four provisional values only:

| CutoffNorm | U (eV) |
|---:|---:|
| 0.80 | 13.0972 |
| 0.90 | 10.6622 |
| 0.95 | 8.2302 |
| 0.98 | 6.2659 |

These points do not form a plateau over this sampled range. This is a statement
about these four provisional records only, not a general conclusion about the
projector curve. Additional planned records at 0.50, 0.60, 0.70, 0.85, and 0.99
will extend the fixture when available.

Required plateau evidence covers result stability, response linearity,
electronic state continuity, magnetic stability, matrix conditioning, local
sensitivity stability, and all non-failed blocking gates. The typed skeleton
accepts externally assessed gate states; it does not implement these analyses.
`LOCK` records a candidate projector configuration and advances to
`FULL_RESPONSE`; it does not certify U by itself.

## Production-value internal control

`ProductionControl` records the exact projector, probe U, full-campaign site U,
and `abs(probe U - full-campaign site U)`. The projector must be the production
projector. For the current M1 control, the probe value is 10.6622 eV and the
full-campaign value is 10.658 eV, for a difference of 0.0042 eV. This is
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
For M1 at CutoffNorm 0.90, the recorded support is 2.44 bohr and half the
Mn–Mn distance is 2.69 bohr, so the support does not exceed half the distance.
The typed record does not parse projector files; interpreting SIESTA output
remains a future backend responsibility.

## Serialization

The dataclasses provide explicit `to_mapping()` / `from_mapping()` pairs. The
pure domain serialization records candidate projector identities; FDF
validation remains a separate backend operation. No digest is used as a
projector equivalence or plateau decision.
