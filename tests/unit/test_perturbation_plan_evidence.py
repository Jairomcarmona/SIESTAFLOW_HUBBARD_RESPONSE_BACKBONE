"""Complete projector and immutable inventory snapshot contracts."""

from dataclasses import replace

import pytest
from hypothesis import given
from hypothesis import strategies as st

from hubbardflow.domain.perturbation_plan_evidence import (
    PerturbationPlanError,
    ProjectorEvidence,
    freeze_inventory,
    inventory_from_mapping,
    inventory_mapping,
)
from tests.unit.test_coverage import RECORD, _toy


def test_snapshot_retains_every_projector_field_and_canonical_atom_order() -> None:
    original, _, _ = _toy(4)
    frozen = freeze_inventory(replace(original, subspaces=tuple(reversed(original.subspaces))))
    assert [s.atom_index for s in frozen.subspaces] == [0, 1, 2, 3]
    assert isinstance(frozen.subspaces[0].dftu_record, ProjectorEvidence)
    assert inventory_from_mapping(inventory_mapping(frozen)) == frozen
    assert frozen.subspaces[0].dftu_record.n == original.subspaces[0].dftu_record.n


def test_duplicate_atom_cannot_silently_define_another_column() -> None:
    original, _, _ = _toy(4)
    duplicate = replace(original.subspaces[1], atom_index=0)
    with pytest.raises(PerturbationPlanError, match="one correlated subspace"):
        freeze_inventory(replace(original, subspaces=(original.subspaces[0], duplicate)))


@given(st.sampled_from((float("nan"), float("inf"), -float("inf"))))
def test_nonfinite_projector_fails_with_plan_error(bad: float) -> None:
    original, _, _ = _toy(4)
    record = replace(RECORD, u_ref_ev=bad)
    changed = replace(original, subspaces=tuple(replace(s, dftu_record=record) for s in original.subspaces))
    with pytest.raises(PerturbationPlanError, match="u_ref_ev must be finite"):
        freeze_inventory(changed)
