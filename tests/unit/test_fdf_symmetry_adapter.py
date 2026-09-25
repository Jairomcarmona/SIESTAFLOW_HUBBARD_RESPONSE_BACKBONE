import json
from pathlib import Path

import pytest

from siestaflow_hubbard.siesta_backend.fdf_symmetry_adapter import (
    FdfSymmetryError,
    audit_fdf_symmetry,
    plan_fdf_symmetry_reduction,
    parse_fdf_symmetry_input,
)
from siestaflow_hubbard.domain.symmetry_reduction import ReductionState, SymmetryReductionPolicy


ROOT = Path(__file__).resolve().parents[2]
REAL_FDFS = {
    "NiO": ROOT / "NIO_PBE_LRU_SC222_V1/runs/00_REFERENCE/siesta.fdf",
    "MnO": ROOT / "MNO_PBE_LRU_SC222_VALIDATION_V1_1/runs/00_REFERENCE/siesta.fdf",
    "FeO": ROOT / "FEO_PBE_LRU_SC222_VALIDATION_V1/runs/00_REFERENCE/siesta.fdf",
    "Cu3N": ROOT / "CU3N_PBE_LRU_SC222_RC3p0_V1/runs/00_REFERENCE/siesta.fdf",
}


@pytest.mark.parametrize("name", REAL_FDFS)
def test_real_campaign_fdf_parses_but_never_uses_initial_spin_as_evidence(name):
    parsed = parse_fdf_symmetry_input(REAL_FDFS[name])
    assert len(parsed.atom_ids) == len(parsed.fractional_coordinates)
    assert parsed.correlated_atom_ids
    # Campaigns assign unique NiLR/MnLR/etc. identifiers.  They must not become
    # physical classes, otherwise an artificial naming convention kills every
    # valid translation candidate.
    correlated_classes = [parsed.equivalence_classes[parsed.atom_ids.index(atom)]
                            for atom in parsed.correlated_atom_ids]
    assert len(set(correlated_classes)) == 1
    audit = audit_fdf_symmetry(REAL_FDFS[name])
    assert audit.geometric_candidate_count >= 1
    assert audit.reduction_enabled is False
    assert audit.certificate is None
    assert "reference_magnetic_evidence_missing" in audit.reasons


def test_evidence_must_bind_hash_and_cover_every_atom(monkeypatch):
    fdf = REAL_FDFS["NiO"]
    parsed = parse_fdf_symmetry_input(fdf)
    bad_payload = json.dumps({"schema_version": 1, "input_fdf_sha256": "0" * 64,
                              "moments_by_atom_index": {"1": [0, 0, 0]}})
    monkeypatch.setattr(Path, "read_text", lambda self, **kwargs: bad_payload)
    with pytest.raises(FdfSymmetryError, match="ligada"):
        audit_fdf_symmetry(fdf, "bad.json")

    incomplete_payload = json.dumps({"schema_version": 1, "input_fdf_sha256": parsed.fdf_sha256,
                                     "moments_by_atom_index": {"1": [0, 0, 0]}})
    monkeypatch.setattr(Path, "read_text", lambda self, **kwargs: incomplete_payload)
    with pytest.raises(FdfSymmetryError, match="cubrir"):
        audit_fdf_symmetry(fdf, "incomplete.json")


def test_missing_magnetic_evidence_materializes_explicit_site_neutral_plan():
    audit, plan = plan_fdf_symmetry_reduction(
        REAL_FDFS["Cu3N"], None, SymmetryReductionPolicy(alpha_ev=0.05)
    )
    assert audit.reduction_enabled is False
    assert plan.state is ReductionState.EXPLICIT_REQUIRED
    assert len(plan.perturbations) == 4 * len(audit.input.correlated_atom_ids)
    assert {spec.purpose for spec in plan.perturbations} == {"explicit_fallback"}
