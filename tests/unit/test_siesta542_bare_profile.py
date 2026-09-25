from pathlib import Path
import re

import pytest

from siestaflow_hubbard.siesta_backend.siesta542_bare_profile import (
    Siesta542BareProfileError,
    Siesta542PotentialShiftHamiltonianProfile,
)


EXAMPLE = Path(__file__).resolve().parents[2] / "examples" / "MnO_BARE_+0.05.out"


def test_materialized_profile_is_explicit_and_valid():
    profile = Siesta542PotentialShiftHamiltonianProfile()
    text = profile.materialize("SystemName MnO\nSCF.Mix density\nMaxSCFIterations 7\n")

    assert "DFTU.PotentialShift true" in text
    assert "DFTU.FirstIteration true" in text
    assert "DM.UseSaveDM true" in text
    assert "SCF.Mix hamiltonian" in text
    assert "MaxSCFIterations 1" in text
    assert "SCF.MustConverge false" in text
    profile.validate_fdf(text)


def test_rejects_density_mixing_or_conflicting_definition():
    profile = Siesta542PotentialShiftHamiltonianProfile()
    with pytest.raises(Siesta542BareProfileError, match="SCF.Mix"):
        profile.validate_fdf("\n".join(
            [
                "DFTU.PotentialShift true",
                "DFTU.FirstIteration true",
                "DM.UseSaveDM true",
                "SCF.Mix density",
                "MaxSCFIterations 1",
                "SCF.MustConverge false",
            ]
        ))


def test_rejects_duplicate_critical_fdf_key_even_when_value_is_identical():
    profile = Siesta542PotentialShiftHamiltonianProfile()
    fdf = "\n".join(
        [
            "DFTU.PotentialShift true",
            "DFTU.FirstIteration true",
            "DM.UseSaveDM true",
            "SCF.Mix Hamiltonian",
            "MaxSCFIterations 1",
            "SCF.MustConverge false",
            "SCF.MustConverge false",
        ]
    )
    with pytest.raises(Siesta542BareProfileError, match="Duplicate definitions"):
        profile.validate_fdf(fdf)


def test_selects_source_audited_response_from_real_siesta_output():
    profile = Siesta542PotentialShiftHamiltonianProfile()
    selection = profile.select_response(EXAMPLE.read_text(encoding="utf-8"))

    assert selection.pre_perturbation_event.occurrence_index == 0
    assert selection.response_event.occurrence_index == 1
    assert selection.response_event.dftu_population_iteration == 1
    assert selection.response_event.scf_iteration == 1
    assert selection.stepf_line < selection.response_event.source_start_line
    assert selection.response_event.source_end_line < selection.first_scf_line


def test_rejects_missing_or_ambiguous_structural_markers():
    profile = Siesta542PotentialShiftHamiltonianProfile()
    output = EXAMPLE.read_text(encoding="utf-8")
    with pytest.raises(Siesta542BareProfileError, match="stepf"):
        profile.select_response(output.replace("stepf: Fermi-Dirac step function", "stepf omitted", 1))
    with pytest.raises(Siesta542BareProfileError, match="SCF mix quantity"):
        profile.select_response(re.sub(
            r"SCF mix quantity\s*=\s*Hamiltonian",
            "SCF mix quantity = density",
            output,
            flags=re.I,
        ))
