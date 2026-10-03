"""Authoritative FDF perturbations cannot be relabelled by ladder metadata."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from hubbardflow.domain.scf_ladder_models import ScfLadderError
from hubbardflow.domain.symmetry_reduction import ResponseMode
from hubbardflow.siesta_backend.scf_ladder_inputs import bind_ladder_input
from hubbardflow.siesta_backend.siesta542_bare_profile import Siesta542PotentialShiftHamiltonianProfile
from tests.unit.test_scf_ladder import policy
from tools.fdebq_scf_ladder_campaign import LadderRunInput, build_ladder_runs


def source_text(alpha_ev: float) -> str:
    return f"""SystemLabel toy
NumberOfAtoms 1
NumberOfSpecies 1
LatticeConstant 1 Ang
%block LatticeVectors
1 0 0
0 1 0
0 0 1
%endblock LatticeVectors
%block ChemicalSpeciesLabel
1 1 toy
%endblock ChemicalSpeciesLabel
AtomicCoordinatesFormat Fractional
%block AtomicCoordinatesAndAtomicSpecies
0 0 0 1
%endblock AtomicCoordinatesAndAtomicSpecies
DFTU.ProjectorGenerationMethod 2
DFTU.PotentialShift true
DFTU.FirstIteration true
DM.UseSaveDM true
DM.Tolerance 0.001
MaxSCFIterations 300
SCF.MustConverge true
SCF.Mix Hamiltonian
%block DFTU.Proj
toy 1
1 0
{alpha_ev} 0
2 0.2
%endblock DFTU.Proj
"""


def test_noncanonical_file_dm_init_is_rejected_before_fdf_parsing(tmp_path: Path) -> None:
    source = tmp_path / "unsafe.fdf"
    source.write_text("file_dm_init parent.DM\n", encoding="utf-8")
    with pytest.raises(ScfLadderError, match="File.DM.Init"):
        bind_ladder_input(source, "toy", ResponseMode.SCREENED, 0.01)


def test_binding_checks_exact_label_alpha_and_screened_bare_modes(tmp_path: Path) -> None:
    source = tmp_path / "input.fdf"
    source.write_text(source_text(0.01), encoding="utf-8")
    binding = bind_ladder_input(source, "toy", ResponseMode.SCREENED, 0.01)
    assert binding.alpha_ev == 0.01 and binding.site_id == "toy" and binding.atom_index == 0
    assert type(binding).from_mapping(binding.to_mapping()) == binding
    for site, mode, alpha in (
        ("other", ResponseMode.SCREENED, 0.01),
        ("toy", ResponseMode.SCREENED, 0.02),
        ("toy", ResponseMode.SCREENED, -0.01),
        ("toy", ResponseMode.BARE, 0.01),
    ):
        with pytest.raises(ScfLadderError, match="NOT_ESTABLISHED"):
            bind_ladder_input(source, site, mode, alpha)
    source.write_text(
        Siesta542PotentialShiftHamiltonianProfile().materialize(source_text(0.01)), encoding="utf-8"
    )
    assert bind_ladder_input(source, "toy", ResponseMode.BARE, 0.01).mode is ResponseMode.BARE
    with pytest.raises(ScfLadderError, match="NOT_ESTABLISHED"):
        bind_ladder_input(source, "toy", ResponseMode.SCREENED, 0.01)


@pytest.mark.parametrize(
    "change",
    (
        ("SCF.MustConverge true", ""),
        ("DFTU.FirstIteration true", ""),
        ("DFTU.PotentialShift true", "DFTU.PotentialShift false"),
        ("MaxSCFIterations 300", "MaxSCFIterations 1"),
        ("SCF.Mix Hamiltonian", "SCF.Mix density"),
        ("SCF.MustConverge true", "SCF.MustConverge true\nSCF.MustConverge false"),
        ("0.01 0", "0.010001 0"),
        ("0.01 0", "0.01000000000000000000000000001 0"),
        ("0.01 0", "0.01 0.1"),
        ("0 0 0 1", "0 0 0 1\n0.5 0 0 1"),
    ),
)
def test_unsupported_ambiguous_or_unbound_inputs_fail_closed(tmp_path: Path, change: tuple[str, str]) -> None:
    source = tmp_path / "invalid.fdf"
    source.write_text(source_text(0.01).replace(*change), encoding="utf-8")
    with pytest.raises(ScfLadderError, match="NOT_ESTABLISHED"):
        bind_ladder_input(source, "toy", ResponseMode.SCREENED, 0.01)


@pytest.mark.parametrize("mismatch", ("alpha", "label", "mode"))
def test_materializer_rejects_mislabelled_sources_before_writing(tmp_path: Path, mismatch: str) -> None:
    parent = tmp_path / "toy.DM"
    parent.write_bytes(b"parent")
    inputs = []
    for index, a in enumerate((-0.08, -0.01, 0.01, 0.08)):
        source = tmp_path / f"source{index}.fdf"
        source.write_text(source_text(a), encoding="utf-8")
        inputs.append(LadderRunInput("toy", ResponseMode.SCREENED, a, str(source), str(parent), ()))
    if mismatch == "alpha":
        source = Path(inputs[0].source_fdf)
        source.write_text(source_text(-0.04), encoding="utf-8")
    elif mismatch == "label":
        inputs = [replace(item, site_id="wrong") for item in inputs]
    else:
        inputs = [replace(item, mode=ResponseMode.BARE) for item in inputs]
    target = tmp_path / "must-not-exist"
    with pytest.raises(ScfLadderError, match="NOT_ESTABLISHED"):
        build_ladder_runs(inputs, policy(), target)
    assert not target.exists()


def test_archived_reference_cannot_be_relabelled_as_perturbed_input() -> None:
    source = Path(__file__).resolve().parents[2] / "examples/tmo_campaigns/Cu3N_ref.fdf"
    with pytest.raises(ScfLadderError, match="NOT_ESTABLISHED"):
        bind_ladder_input(source, "Cu1", ResponseMode.SCREENED, 0.01)
