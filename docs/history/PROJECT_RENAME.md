# Project identity migration

## Identity change

The development identity `SIESTAFLOW_HUBBARD_RESPONSE_BACKBONE` / `siestaflow_hubbard` / `siestaflow` is being replaced by the project name **HubbardFlow**, distribution and import namespace `hubbardflow`, and CLI `hubbardflow`.

The reason is to avoid implying ownership, maintenance, or official affiliation with the SIESTA project. The README states that HubbardFlow is an independent research software project and that its current implementation uses SIESTA as the electronic-structure engine. The software is not presented as backend independent.

## Scientific identity

The immutable pre-rename scientific baseline is tagged `scientific-v6-final`. Its verified freeze commit is `45cb53c5a98d9d55a163c05ca3b815a8ff9cfb7f`. The identity and provenance limits are recorded in [`SCIENTIFIC_BASELINE_V6.md`](SCIENTIFIC_BASELINE_V6.md) and [`V6_ARTIFACT_INVENTORY.md`](V6_ARTIFACT_INVENTORY.md).

This is a project/package/CLI namespace migration only. It does not alter scientific formulas, thresholds, U values, certified intervals, inputs, certificates, qualification labels, or observable results. Historical artifacts may retain the former identifiers where those values are part of their preserved provenance or versioned data formats.

## Preserved history and compatibility

Git history is intentionally preserved. The repository itself, GitHub remote, historical tags, reports, run records, and locked campaign artifacts are not renamed or rewritten. Versioned campaign schema IDs such as `siestaflow.campaign.v2` and the existing `.siestaflow.json` pointer suffix remain stable because they identify persisted data contracts. Frozen software locks that name a legacy distribution or source path continue to resolve through that exact locked distribution; the current application does not import the old namespace as an active alias.

The CoO/MnO certificate generator source gap and the V6 recorded-Git-SHA mismatch remain explicitly documented. No historical identifier has been inferred or substituted.
