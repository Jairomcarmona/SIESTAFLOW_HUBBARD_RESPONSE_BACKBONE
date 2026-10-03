"""V3 synthetic adversaries: zero false reductions for either flag setting.

These known constructions are software controls, never real V3 result files.
Band displacements are derived from the declared policy, not new tolerances.
"""

from __future__ import annotations

from dataclasses import replace
from hashlib import sha256

import pytest

from hubbardflow.domain.coverage import UserCoveragePolicy, qualify_coverage
from hubbardflow.domain.coverage_models import CoverageStrategy
from hubbardflow.domain.state_evidence import MomentEvidence
from hubbardflow.domain.symmetry_operation_models import (
    IDENTITY,
    Operation,
    SymmetryAtom,
    coverage_policy_v1,
)
from hubbardflow.domain.symmetry_operations import CandidateOperations
from tests.unit.test_coverage import DIGEST, _toy


@pytest.mark.parametrize("spin_flip", [False, True])
@pytest.mark.parametrize("rotations", [False, True])
@pytest.mark.parametrize(
    "control",
    [
        "ferrimagnet",
        "orbital_order",
        "slab",
        "defect",
        "near_symmetric",
        "different_basis",
        "soc",
        "noncollinear",
        "different_environment",
    ],
)
def test_zero_false_acceptances(
    monkeypatch: pytest.MonkeyPatch, control: str, spin_flip: bool, rotations: bool
) -> None:
    inventory, evidence, model = _toy(4, antiferromagnet=True)
    policy = replace(coverage_policy_v1(), allow_spin_flip=spin_flip, allow_rotations=rotations)
    if control == "ferrimagnet":
        evidence = replace(
            evidence,
            state=replace(
                evidence.state,
                moments_by_atom=tuple(
                    MomentEvidence(i, m, 5e-7) for i, m in enumerate((0.8, -0.4, 0.6, -0.2))
                ),
            ),
        )
    elif control == "orbital_order":
        evidence = replace(
            evidence,
            state=replace(
                evidence.state,
                occupation_spectra_by_subspace=tuple(
                    replace(
                        row,
                        spectra=tuple(
                            replace(s, eigenvalues_e=(s.eigenvalues_e[0] + i * 0.01,)) for s in row.spectra
                        ),
                    )
                    for i, row in enumerate(evidence.state.occupation_spectra_by_subspace)
                ),
            ),
        )
    elif control == "different_basis":
        model = replace(
            model,
            atoms=tuple(
                replace(a, identity_digest=sha256(f"basis-{a.atom_index}".encode()).hexdigest())
                for a in model.atoms
            ),
        )
        inventory = replace(
            inventory,
            subspaces=tuple(
                replace(s, identity_digest=model.atoms[s.atom_index].identity_digest or "")
                for s in inventory.subspaces
            ),
        )
        assert len({s.species_label for s in inventory.subspaces}) == 1
    elif control in ("slab", "defect", "different_environment"):
        # Equal |m|, equal projectors, but all-atom geometry lacks translation.
        model = replace(
            model,
            atoms=(
                *model.atoms,
                SymmetryAtom(4, (0.13, 0.21, 0.0 if control == "slab" else 0.37), DIGEST, False),
            ),
        )
    elif control == "near_symmetric":
        gray = (policy.geometry.tau_eq + policy.geometry.tau_neq) / 2
        model = replace(
            model,
            atoms=tuple(
                replace(
                    a,
                    coordinates_fractional=(
                        a.coordinates_fractional[0] + (gray if a.atom_index == 1 else 0),
                        0,
                        0,
                    ),
                )
                for a in model.atoms
            ),
        )
    elif control == "soc":
        model = replace(model, spin_orbit=True)
    else:
        model = replace(model, collinear=False)
    # Deliberately offer the tempting mappings even for broken geometries.
    # Classification must reject them; the candidate search cannot hide a fail.
    operations = []
    for shift in range(4):
        for reflection in (False, True):
            rotation = ((-1, 0, 0), (0, 1, 0), (0, 0, 1)) if reflection else IDENTITY
            correlated = tuple(((-i if reflection else i) + shift) % 4 for i in range(4))
            atoms = (*correlated, 4) if len(model.atoms) == 5 else correlated
            for eps in (1, -1):
                operations.append(Operation(rotation, (shift / 4, 0, 0), eps, atoms, correlated, model))
    monkeypatch.setattr(
        "hubbardflow.domain.coverage.candidate_operations",
        lambda *_: CandidateOperations(tuple(operations), ()),
    )
    result = qualify_coverage(
        inventory, evidence, model, policy, UserCoveragePolicy("synthetic-v3-v1", True, ())
    )
    assert result.strategy is CoverageStrategy.ALL_SUBSPACES
    assert result.computed_columns == ("s0", "s1", "s2", "s3")
    assert all(not c.reduced for c in result.classes)
    assert all(
        not c.accepted for c in result.operations if c.operation.correlated_permutation != (0, 1, 2, 3)
    )
