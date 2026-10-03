from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from hubbardflow.domain.state_evidence import (
    CorrelatedSubspaceLike,
    EvidenceStatus,
    OccupationSpectraStatus,
    StateEvidenceReason,
    spectrum_difference,
)
from hubbardflow.siesta_backend.fdf_model import parse_effective_fdf
from hubbardflow.siesta_backend.reference_state_evidence import build_reference_state_evidence

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "examples/tmo_campaigns"


@dataclass(frozen=True)
class _Subspace:
    site_id: str
    atom_index: int


def _subspaces(fdf_path: Path) -> tuple[CorrelatedSubspaceLike, ...]:
    model = parse_effective_fdf(fdf_path)
    labels = {record.label for record in model.dftu_records}
    return tuple(
        _Subspace(f"{atom.species_label}@{atom.atom_index}", atom.atom_index)
        for atom in model.atoms
        if atom.species_label in labels
    )


@pytest.mark.parametrize("system", ["CoO", "NiO", "Cu3N", "FeO"])
def test_archived_reference_examples_provide_hash_bound_local_spectra(system: str) -> None:
    fdf = EXAMPLES / f"{system}_ref.fdf"
    output = EXAMPLES / f"{system}_ref.out"
    evidence = build_reference_state_evidence(fdf, output, _subspaces(fdf))

    assert evidence.input_fdf_sha256 == parse_effective_fdf(fdf).effective_fdf_sha256
    assert len(evidence.siesta_output_sha256) == 64
    assert evidence.normal_completion_verified
    assert evidence.scf_converged
    assert evidence.mesh_divisions is not None
    assert evidence.k_mesh is not None
    assert not evidence.moments_by_atom
    assert StateEvidenceReason.MOMENTS_MISSING in evidence.reason_codes
    assert evidence.occupation_spectra_status is OccupationSpectraStatus.AVAILABLE
    assert evidence.status is EvidenceStatus.REFERENCE_NOT_ADMISSIBLE
    assert evidence.occupation_spectra_by_subspace
    first = evidence.occupation_spectra_by_subspace[0].spectra[0]
    assert first.eigenvalues_e
    assert len(first.matrix_half_widths_e) == len(first.eigenvalues_e)


def test_mno_v3r2_reference_output_provides_local_spectra() -> None:
    folder = (
        ROOT
        / "campaigns/mno_afmii_strict_lr_v3r2/results/response-matrix-foreground-recovery-v4/00_REFERENCE"
    )
    fdf, output = folder / "siesta.fdf", folder / "siesta.out"
    evidence = build_reference_state_evidence(fdf, output, _subspaces(fdf))
    assert evidence.occupation_spectra_status is OccupationSpectraStatus.AVAILABLE
    assert evidence.status is EvidenceStatus.ADMISSIBLE


def test_v6_coo_reference_keeps_partial_evidence_but_never_invents_spectra() -> None:
    folder = ROOT / "validation_observables_v6/coo/pbe_lru"
    fdf, output = folder / "input.fdf", folder / "siesta.out"
    evidence = build_reference_state_evidence(fdf, output, _subspaces(fdf))
    assert evidence.normal_completion_verified
    assert evidence.scf_converged
    assert evidence.moments_by_atom
    assert evidence.mesh_divisions is not None
    assert evidence.k_mesh is not None
    assert evidence.occupation_spectra_status is OccupationSpectraStatus.NOT_AVAILABLE
    assert not evidence.occupation_spectra_by_subspace
    assert StateEvidenceReason.OCCUPATION_SPECTRA_NOT_AVAILABLE in evidence.reason_codes
    assert evidence.status is EvidenceStatus.REFERENCE_NOT_ADMISSIBLE


def test_v6_mno_reference_keeps_partial_evidence_but_never_invents_spectra() -> None:
    folder = ROOT / "validation_observables_v6/mno/lru_central"
    fdf, output = folder / "input.fdf", folder / "siesta.out"
    evidence = build_reference_state_evidence(fdf, output, _subspaces(fdf))
    assert evidence.normal_completion_verified
    assert evidence.scf_converged
    assert evidence.moments_by_atom
    assert evidence.mesh_divisions is not None
    assert evidence.k_mesh is not None
    assert evidence.occupation_spectra_status is OccupationSpectraStatus.NOT_AVAILABLE
    assert StateEvidenceReason.OCCUPATION_SPECTRA_NOT_AVAILABLE in evidence.reason_codes
    assert evidence.status is EvidenceStatus.REFERENCE_NOT_ADMISSIBLE


def test_feo_diagnostic_output_retains_observables_and_marks_missing_state_data() -> None:
    folder = ROOT / "FEO_SCF_DIAGNOSTIC_EXPORT_20261001/feo_pbe/seedDM_converged"
    fdf, output = folder / "input.fdf", folder / "siesta.out"
    evidence = build_reference_state_evidence(fdf, output, _subspaces(fdf))
    assert evidence.moments_by_atom
    assert evidence.mesh_divisions is not None
    assert evidence.k_mesh is not None
    assert evidence.scf_converged
    assert evidence.occupation_spectra_status is OccupationSpectraStatus.NOT_AVAILABLE
    assert evidence.status is EvidenceStatus.REFERENCE_NOT_ADMISSIBLE


def test_feo_archived_spectrum_is_visible_but_has_only_one_site() -> None:
    fdf, output = EXAMPLES / "FeO_ref.fdf", EXAMPLES / "FeO_ref.out"
    evidence = build_reference_state_evidence(fdf, output, _subspaces(fdf))
    subspaces = evidence.occupation_spectra_by_subspace
    assert len(subspaces) == 1
    assert subspaces[0].spectra
    assert {spectrum.spin for spectrum in subspaces[0].spectra} == {"up", "down"}


def test_truncated_output_is_not_admissible_and_has_explicit_reason(tmp_path: Path) -> None:
    fdf = EXAMPLES / "CoO_ref.fdf"
    output = tmp_path / "truncated.out"
    text = (EXAMPLES / "CoO_ref.out").read_text(encoding="utf-8")
    output.write_text(text.rsplit("Job completed", 1)[0], encoding="utf-8")
    evidence = build_reference_state_evidence(fdf, output, _subspaces(fdf))
    assert evidence.status is EvidenceStatus.REFERENCE_NOT_ADMISSIBLE
    assert not evidence.normal_completion_verified
    assert StateEvidenceReason.NORMAL_COMPLETION_MISSING in evidence.reason_codes


def test_spectrum_difference_swaps_spin_channels_for_global_flip() -> None:
    from hubbardflow.domain.state_evidence import OccupationSpectrum, SubspaceOccupationEvidence

    a = SubspaceOccupationEvidence(
        "a",
        0,
        (
            OccupationSpectrum("up", (0.2, 0.8), ((0.01, 0.01), (0.01, 0.01))),
            OccupationSpectrum("down", (0.1, 0.9), ((0.01, 0.01), (0.01, 0.01))),
        ),
    )
    b = SubspaceOccupationEvidence(
        "b",
        1,
        (
            OccupationSpectrum("up", (0.1, 0.9), ((0.01, 0.01), (0.01, 0.01))),
            OccupationSpectrum("down", (0.2, 0.8), ((0.01, 0.01), (0.01, 0.01))),
        ),
    )
    assert spectrum_difference(a, b, flip=False) == pytest.approx(0.1)
    assert spectrum_difference(a, b, flip=True) == pytest.approx(0.0)


def test_missing_spectrum_cannot_be_classified_equal() -> None:
    from hubbardflow.domain.state_evidence import SubspaceOccupationEvidence

    available = SubspaceOccupationEvidence("site-a", 0, ())
    no_spectra = SubspaceOccupationEvidence("site-b", 1, ())
    assert spectrum_difference(available, no_spectra, flip=False) is None
