from pathlib import Path
import json

import numpy as np
import pytest

from siestaflow_hubbard.siesta_backend.fdf_symmetry_adapter import audit_fdf_symmetry
from siestaflow_hubbard.siesta_backend.reference_magnetic_evidence import (
    ReferenceMagneticEvidenceError,
    build_reference_magnetic_evidence,
    parse_final_collinear_mulliken_sz,
    reference_moments_from_fdf_and_output,
)


ROOT = Path(__file__).resolve().parents[2]
FDF = ROOT / "docs/audits/representative_nio_afm_mpi_input.fdf"
OUT = ROOT / "docs/audits/representative_nio_afm_mpi_output.out"


def test_parses_last_complete_real_siesta_542_mulliken_table():
    moments = parse_final_collinear_mulliken_sz(OUT.read_text(encoding="utf-8"), 4)
    assert np.allclose(moments[:, 2], [1.295705, -1.295209, -0.000242, -0.000242])


def test_explicit_nonpolarized_mode_allows_zero_moments_without_mulliken_table():
    fdf = "NumberOfAtoms 2\nSpin non-polarized\n"
    output = """redata: Spin configuration = none
redata: Number of spin components = 1
redata: Time-Reversal Symmetry = T
siesta: normal completion
"""
    moments, parser_name = reference_moments_from_fdf_and_output(fdf, output)
    assert parser_name == "siesta_5_4_explicit_nonpolarized_v1"
    assert np.array_equal(moments, np.zeros((2, 3)))


def test_spin_none_output_without_nonpolarized_fdf_is_rejected():
    fdf = "NumberOfAtoms 1\nSpin polarized\n"
    output = """redata: Spin configuration = none
redata: Number of spin components = 1
redata: Time-Reversal Symmetry = T
siesta: normal completion
"""
    with pytest.raises(ReferenceMagneticEvidenceError, match="Mulliken"):
        reference_moments_from_fdf_and_output(fdf, output)


def test_builds_hash_bound_evidence_and_audits_real_afm_output(monkeypatch):
    evidence = build_reference_magnetic_evidence(FDF, OUT)
    assert evidence["normal_completion_verified"] is True
    assert evidence["atom_count"] == 4
    monkeypatch.setattr(Path, "read_text", lambda self, **kwargs: json.dumps(evidence))
    audit = audit_fdf_symmetry(FDF, "reference_moments.json")
    assert audit.certificate is not None
    # The actual AFM moments reject the apparent geometric sublattice swap.
    assert audit.reduction_enabled is False


@pytest.mark.parametrize("mutator, message", [
    (lambda text: text.replace("Job completed", "job not completed"), "terminación normal"),
    (lambda text: text + "\nSCF_NOT_CONV: SCF did not converge\n", "SCF no convergida"),
])
def test_rejects_incomplete_or_nonconverged_output(mutator, message):
    with pytest.raises(ReferenceMagneticEvidenceError, match=message):
        parse_final_collinear_mulliken_sz(mutator(OUT.read_text(encoding="utf-8")), 4)
