# Projector scan and plateau executable specification

This document turns `PROJECTOR_SCAN_POLICY.md` and `PLATEAU_DETECTION_POLICY.md`
into a typed input and result contract. It is a specification skeleton: it does
not generate FDF files, schedule jobs, run SIESTA, calculate U, or evaluate the
numeric plateau thresholds.

## Scientific invariants

- A reported U belongs to the exact projector parameter and generation method
  that produced it. Results from distinct projectors remain separate; they are
  never averaged (LR-19/LR-20).
- A scan uses `DFTU.ProjectorGenerationMethod 2` and probes one representative
  site. Each candidate uses the same FDF except for its one projector line.
- Each candidate probe is one direct column: twelve response runs and one
  reference run. The response count is fixed by the probe contract, not inferred
  from the number of projector candidates.
- A `CutoffNorm` scan is invalid when explicit `rc` projector records are
  present. A candidate with any non-projector FDF change is rejected.
- Missing user-declared plateau criteria yield `PROJECTOR_NOT_ASSESSED`; no
  numeric criterion has a default. A computed U remains reportable in every
  status, but a projector candidate cannot advance to lock without
  `PROJECTOR_PLATEAU_CONFIRMED`. Plateau confirmation does not certify final U.
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
nonzero explicit `rc` row. Explicit-rc candidates may change only the `rc` row
in the effective method-2 projector block. Unsupported block syntax fails
closed. Included-file resolution and full SIESTA precedence remain the
responsibility of the eventual input-generation caller before passing effective
FDF text to this validator.

## Stage and result contract

The prescribed order is:

1. `COARSE_SCAN`
2. `REFINEMENT`
3. `EVALUATION`
4. `PLATEAU_DETECTION`
5. `LOCK`
6. `FULL_RESPONSE`

The assessment is a result state, not a calculation stop gate:

| Status | Meaning | U accepted? |
|---|---|---:|
| `PROJECTOR_PLATEAU_CONFIRMED` | All declared criteria and required evidence were assessed and passed. | Candidate may advance to `LOCK` / `FULL_RESPONSE`; this does not accept or certify final U. |
| `PROJECTOR_NOT_ASSESSED` | Criteria or required evidence are missing. | No. |
| `PROJECTOR_NO_PLATEAU` | At least one required plateau gate failed. | No. |

Required plateau evidence covers result stability, response linearity,
electronic state continuity, magnetic stability, matrix conditioning, local
sensitivity stability, and all non-failed blocking gates. The typed skeleton
accepts externally assessed gate states; it does not implement these analyses.
`LOCK` records a candidate projector configuration and advances to
`FULL_RESPONSE`; it does not certify U by itself.

## Production-value internal control

`ProductionControl` records the exact projector, probe U, full-campaign site U,
and `abs(probe U - full-campaign site U)`. The projector must be the production
projector. This control difference is retained as evidence for review. Its
interpretation is not assigned a threshold in this specification.

`ProjectorUResult` stores each reported U alongside its exact `ProjectorValue`.
There is no aggregate or averaging API over candidates; a report must preserve
one U row per projector identity.

## Serialization

The dataclasses provide explicit `to_mapping()` / `from_mapping()` pairs. The
pure domain serialization records candidate projector identities; FDF
validation remains a separate backend operation. No digest is used as a
projector equivalence or plateau decision.
