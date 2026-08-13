# Automatic symmetry reduction contract for LR-U campaigns

This contract defines the safe route from a CIF or SIESTA FDF to symmetry-
reduced Hubbard perturbations. It is intentionally separate from the frozen
NiO, MnO and Cu3N campaigns.

## 1. Canonical structure

The CIF is an external structural source. The materialized FDF is the actual
SIESTA input. Both are parsed into the same canonical record:

```text
(cell, fractional_positions, atomic_numbers, spin/state labels, Hubbard shell labels)
```

The comparison is performed after periodic wrapping and a declared length
tolerance. Atom order is not used as an identity. A mismatch in cell,
species, coordinates or magnetic labels is a hard failure; the CIF must never
silently overwrite the FDF.

For a campaign generated without a CIF, the FDF remains the sole canonical
input and the provenance record must say `CIF_NOT_SUPPLIED`.

## 2. Symmetry detection

The canonical record is passed to `spglib.get_symmetry_dataset` with explicit
`symprec`, `angle_tolerance` and magnetic moments when magnetic symmetry is
supported by the selected version. The result is recorded, not inferred:

- space-group number and international symbol;
- every accepted rotation/translation operation;
- atom permutations induced by each operation;
- tolerance values and `spglib` version;
- Hubbard-site equivalence classes.

Chemical equivalence alone is insufficient. Two sites are equivalent only if
the operation preserves species, magnetic state, correlated shell, projector
definition and the campaign's perturbation semantics.

## 3. Representative generation

For each equivalence class, one representative is selected deterministically.
The generator writes a manifest containing the class members and the exact
operation mapping. It then materializes one pair of BARE and one pair of
SCREENED FDFs per representative and injects the perturbation only into the
representative's projector block.

The generated FDF is validated against the canonical record before execution:
atom count, species, coordinates, projectors, alpha sign and all unperturbed
projector fields must match byte-for-byte at the semantic level.

## 4. Response-equivalence gate

Symmetry reduction is accepted only after an explicit control calculation.
For each class, at least one non-representative member is perturbed and its
response is compared after applying the predicted permutation:

```text
max_abs(n_explicit - P_g n_representative) <= response_tolerance
```

The gate is applied independently to BARE and SCREENED responses. A failed
class is expanded to explicit perturbations; it is never averaged into
agreement. The output states `SYMMETRY_ACCEPTED` or `SYMMETRY_REJECTED`.

## 5. Matrix construction

Only after the response-equivalence gate passes are the omitted columns
reconstructed with the recorded permutations. Raw matrices are retained,
then any declared symmetrization is applied and its norm is reported. Rank,
condition number and direct-inversion residuals remain mandatory gates.

## 6. CIF/FDF and reinjection tests

The implementation must test, before a production submission:

1. CIF and FDF produce the same canonical structure;
2. atom reordering produces the same canonical structure and site classes;
3. periodic wrapping at cell boundaries is invariant;
4. a known translation maps the expected Hubbard labels;
5. a magnetic sign reversal breaks equivalence when it should;
6. generated FDFs contain exactly one intended alpha shift;
7. a perturbed non-representative response is rejected when it violates the
   symmetry tolerance;
8. a valid transformed response reconstructs the same matrix;
9. missing `spglib`, ambiguous symmetry, or mismatched CIF/FDF fails closed.

These are semantic tests, not string-only tests. They protect the physical
assumption that makes reduction legal.

## 7. Relation to `hp.x`

This reproduces the *symmetry-selection* logic conceptually, but not the
DFPT response algorithm of `hp.x`. SIESTA finite differences still determine
the occupations and susceptibilities. Equivalence must therefore be checked
against calculated responses, not only against geometry.

No existing campaign may be silently converted to this mode. A campaign is
eligible only when its symmetry manifest, parser versions, tolerances and
control responses are archived with the results.
