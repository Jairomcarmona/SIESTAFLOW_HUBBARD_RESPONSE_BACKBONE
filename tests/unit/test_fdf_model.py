from __future__ import annotations

import re
from fractions import Fraction
from pathlib import Path

import pytest

from hubbardflow.domain.symmetry_operation_models import bind_symmetry_model
from hubbardflow.execution.campaign_v2 import (
    CampaignV2Error,
    resolve_fdf_includes,
    validate_reference_fdf,
)
from hubbardflow.siesta_backend.fdf_model import (
    CoordinateFormat,
    FdfErrorCode,
    FdfModelError,
    SpeciesIdentityStatus,
    parse_effective_fdf,
    species_identity,
)

ROOT = Path(__file__).resolve().parents[2]


def _legacy_atom_map(text: str, site_ids: tuple[str, ...]) -> dict[str, tuple[int, ...]]:
    species_match = re.search(
        r"^\s*%block\s+ChemicalSpeciesLabel\s*$([\s\S]*?)^\s*%endblock(?:\s+ChemicalSpeciesLabel)?\s*$",
        text,
        re.IGNORECASE | re.MULTILINE,
    )
    coordinates_match = re.search(
        r"^\s*%block\s+AtomicCoordinatesAndAtomicSpecies\s*$([\s\S]*?)"
        r"^\s*%endblock(?:\s+AtomicCoordinatesAndAtomicSpecies)?\s*$",
        text,
        re.IGNORECASE | re.MULTILINE,
    )
    assert species_match is not None and coordinates_match is not None
    label_by_species: dict[int, str] = {}
    for raw in species_match.group(1).splitlines():
        fields = raw.split("#", 1)[0].split()
        if fields:
            label_by_species[int(fields[0])] = fields[2]
    indices_by_label: dict[str, list[int]] = {site_id: [] for site_id in site_ids}
    atom_index = 0
    for raw in coordinates_match.group(1).splitlines():
        fields = raw.split("#", 1)[0].split()
        if len(fields) >= 4:
            label = label_by_species[int(fields[3])]
            if label in indices_by_label:
                indices_by_label[label].append(atom_index)
            atom_index += 1
    return {label: tuple(indices) for label, indices in indices_by_label.items()}


def _fdf(
    *,
    coordinate_format: str = "Fractional",
    coordinates: str = "0 0 0 1 # Co label",
    lattice_parameters: str = "",
) -> str:
    return f"""NumberOfAtoms 1
NumberOfSpecies 1
{lattice_parameters}%block ChemicalSpeciesLabel
1 27 Co
%endblock ChemicalSpeciesLabel
LatticeConstant 2 Ang
%block LatticeVectors
1 0 0
0 1 0
0 0 1
%endblock LatticeVectors
AtomicCoordinatesFormat {coordinate_format}
%block AtomicCoordinatesAndAtomicSpecies
{coordinates}
%endblock AtomicCoordinatesAndAtomicSpecies
%block DFTU.Proj
Co 1
3 2
0.2 0.1 0.0
3.0 0.05 9.0
%endblock DFTU.Proj
DFTU.ProjectorGenerationMethod 2
Spin polarized
%block PAO.Basis
Co
n=3 0 2 E 40 5
%endblock PAO.Basis
"""


def test_repo_campaign_fdfs_and_campaign_validation_share_site_mapping() -> None:
    paths = [
        ROOT / "benchmarks/lr_u/CoO/reference.fdf",
        ROOT / "benchmarks/lr_u/stage_u_b/materials/NiO/reference.fdf",
        ROOT / "benchmarks/lr_u/MnO/reference.fdf",
        ROOT / "tests/fixtures/cu3n_reference_siesta.fdf",
        ROOT / "campaigns/mno_afmii_strict_lr_v3r2/geometry/supercell_222.fdf",
    ]
    for path in paths:
        model = parse_effective_fdf(path)
        _, species_by_label, sites = validate_reference_fdf(model.effective_text, "PBE")
        dftu_labels = [record.label for record in model.dftu_records]
        assert sites == dftu_labels
        assert all(label in species_by_label for label in dftu_labels)
        for label in dftu_labels:
            matching = [atom.atom_index for atom in model.atoms if atom.species_label == label]
            assert matching
            assert all(model.atoms[index].species_label == label for index in matching)


def test_every_campaign_fixture_accepted_by_campaign_validator_has_same_site_map() -> None:
    search_roots = (ROOT / "campaigns", ROOT / "benchmarks", ROOT / "tests/fixtures")
    paths = sorted({path for root in search_roots for path in root.rglob("*.fdf")})
    accepted = 0
    for path in paths:
        try:
            effective_text, _ = resolve_fdf_includes(path)
            _, _, sites = validate_reference_fdf(effective_text, "PBE")
        except CampaignV2Error:
            continue
        model = parse_effective_fdf(path)
        parsed_site_map = {
            label: tuple(atom.atom_index for atom in model.atoms if atom.species_label == label)
            for label in sites
        }
        assert parsed_site_map == _legacy_atom_map(model.effective_text, tuple(sites)), path
        assert tuple(record.label for record in model.dftu_records) == tuple(sites), path
        accepted += 1
    assert accepted >= 5


def test_all_supported_coordinate_formats_are_normalized_and_recorded(tmp_path: Path) -> None:
    cases = [
        ("Fractional", "0.25 0.5 0.75", (0.25, 0.5, 0.75)),
        ("Ang", "0.5 1 1.5", (0.25, 0.5, 0.75)),
        ("Bohr", "0.944863062706 1.889726125412 2.834589188118", (0.25, 0.5, 0.75)),
        ("ScaledCartesian", "0.25 0.5 0.75", (0.25, 0.5, 0.75)),
    ]
    for index, (fmt, coords, expected) in enumerate(cases):
        path = tmp_path / f"format-{index}.fdf"
        path.write_text(_fdf(coordinate_format=fmt, coordinates=f"{coords} 1"), encoding="utf-8")
        model = parse_effective_fdf(path)
        assert model.coordinate_format is CoordinateFormat(fmt)
        assert model.atoms[0].coordinates_fractional == pytest.approx(expected)


def test_decimal_coordinate_tokens_produce_exact_fractional_coordinates(tmp_path: Path) -> None:
    cases = [
        ("Fractional", "0.25 0.5 0.75", "LatticeConstant 2 Ang", ("1/4", "1/2", "3/4")),
        ("ScaledCartesian", "0.25 0.5 0.75", "LatticeConstant 2 Ang", ("1/4", "1/2", "3/4")),
        ("Ang", "0.5 1 1.5", "LatticeConstant 2 Ang", ("1/4", "1/2", "3/4")),
        ("Ang", "0.3 0.6 0.9", "LatticeConstant 3 Ang", ("1/10", "1/5", "3/10")),
        ("Bohr", "0.5 1 1.5", "LatticeConstant 2 Bohr", ("1/4", "1/2", "3/4")),
    ]
    for index, (fmt, coordinates, lattice_constant, expected) in enumerate(cases):
        path = tmp_path / f"exact-{index}.fdf"
        text = _fdf(coordinate_format=fmt, coordinates=f"{coordinates} 1").replace(
            "LatticeConstant 2 Ang", lattice_constant
        )
        path.write_text(text, encoding="utf-8")
        atom = parse_effective_fdf(path).atoms[0]
        assert atom.source_coordinate_tokens == tuple(coordinates.split())
        assert atom.coordinates_fractional_rational == expected
        assert atom.coordinates_fractional == pytest.approx(
            tuple(float(Fraction(value)) for value in expected)
        )
        bound = bind_symmetry_model(parse_effective_fdf(path), {})
        assert bound.atoms[0].rational_coordinates == tuple(Fraction(value) for value in expected)

    mixed = tmp_path / "mixed-units.fdf"
    mixed.write_text(
        _fdf(coordinate_format="Bohr", coordinates="0.944863062706 1.889726125412 2.834589188118 1"),
        encoding="utf-8",
    )
    assert parse_effective_fdf(mixed).atoms[0].coordinates_fractional_rational is None


def test_include_effective_digest_and_per_block_digest(tmp_path: Path) -> None:
    child = tmp_path / "geometry.fdf"
    child.write_text(
        """NumberOfAtoms 1
NumberOfSpecies 1
%block ChemicalSpeciesLabel
1 27 Co
%endblock ChemicalSpeciesLabel
LatticeConstant 2 Ang
%block LatticeVectors
1 0 0
0 1 0
0 0 1
%endblock LatticeVectors
AtomicCoordinatesFormat Fractional
%block AtomicCoordinatesAndAtomicSpecies
0 0 0 1
%endblock AtomicCoordinatesAndAtomicSpecies
%block DFTU.Proj
Co 1
3 2
0 0
3 0.05
%endblock DFTU.Proj
""",
        encoding="utf-8",
    )
    parent = tmp_path / "main.fdf"
    parent.write_text('%include "geometry.fdf"\n', encoding="utf-8")
    model = parse_effective_fdf(parent)
    assert model.effective_fdf_sha256
    assert dict(model.block_sha256)["dftu.proj"]


def test_lattice_parameters_is_explicitly_rejected(tmp_path: Path) -> None:
    path = tmp_path / "unsupported.fdf"
    path.write_text(
        _fdf(lattice_parameters="%block LatticeParameters\n1 1 1 90 90 90\n%endblock LatticeParameters\n"),
        encoding="utf-8",
    )
    with pytest.raises(FdfModelError) as error:
        parse_effective_fdf(path)
    assert error.value.code is FdfErrorCode.UNSUPPORTED_SYNTAX


def test_duplicate_dftu_label_is_explicitly_rejected(tmp_path: Path) -> None:
    path = tmp_path / "duplicate-dftu.fdf"
    source = _fdf().replace(
        "%endblock DFTU.Proj",
        "Co 1\n3 2\n0.2 0.1\n3.0 0.05\n%endblock DFTU.Proj",
    )
    path.write_text(source, encoding="utf-8")
    with pytest.raises(FdfModelError) as error:
        parse_effective_fdf(path)
    assert error.value.code is FdfErrorCode.AMBIGUOUS_DFTU_LABEL


def test_dftu_method_aliases_are_normalized_and_conflicts_rejected(tmp_path: Path) -> None:
    method_path = tmp_path / "method.fdf"
    method_path.write_text(
        _fdf().replace("DFTU.ProjectorGenerationMethod 2", "DFTU.Method 2"), encoding="utf-8"
    )
    assert parse_effective_fdf(method_path).dftu_method == 2

    matching_path = tmp_path / "matching-methods.fdf"
    matching_path.write_text(_fdf() + "DFTU.Method 2\n", encoding="utf-8")
    assert parse_effective_fdf(matching_path).dftu_method == 2

    conflicting_path = tmp_path / "conflicting-methods.fdf"
    conflicting_path.write_text(_fdf() + "DFTU.Method 1\n", encoding="utf-8")
    with pytest.raises(FdfModelError) as error:
        parse_effective_fdf(conflicting_path)
    assert error.value.code is FdfErrorCode.UNSUPPORTED_SYNTAX


def test_projector_header_value_is_retained_without_assuming_one(tmp_path: Path) -> None:
    path = tmp_path / "projector-header.fdf"
    path.write_text(_fdf().replace("Co 1\n", "Co 7\n"), encoding="utf-8")
    assert parse_effective_fdf(path).dftu_records[0].projector_header_value == "7"


def test_invalid_spin_and_spin_orbit_values_fail_closed(tmp_path: Path) -> None:
    cases = [
        _fdf().replace("Spin polarized", "Spin maybe"),
        _fdf() + "SpinPolarized maybe\n",
        _fdf() + "SpinOrbit maybe\n",
        _fdf() + "SpinOrbit yes\n",
        _fdf() + "SpinPolarized false\n",
    ]
    for index, source in enumerate(cases):
        path = tmp_path / f"invalid-spin-{index}.fdf"
        path.write_text(source, encoding="utf-8")
        with pytest.raises(FdfModelError) as error:
            parse_effective_fdf(path)
        assert error.value.code is FdfErrorCode.UNSUPPORTED_SYNTAX


def test_species_identity_hashes_files_and_missing_files_fail_closed(tmp_path: Path) -> None:
    fdf_path = tmp_path / "identity.fdf"
    fdf_path.write_text(_fdf(), encoding="utf-8")
    model = parse_effective_fdf(fdf_path)
    missing = species_identity(model, [tmp_path])["Co"]
    assert missing.status is SpeciesIdentityStatus.NOT_ESTABLISHED
    (tmp_path / "Co.psml").write_text("pseudo contents", encoding="utf-8")
    established = species_identity(model, [tmp_path])["Co"]
    assert established.status is SpeciesIdentityStatus.ESTABLISHED
    assert established.pseudopotential_sha256
    assert established.pao_basis_sha256
    assert established.digest != missing.digest


def test_unknown_coordinate_format_rejected(tmp_path: Path) -> None:
    path = tmp_path / "unsupported-coordinate.fdf"
    path.write_text(_fdf(coordinate_format="ZMatrix"), encoding="utf-8")
    with pytest.raises(FdfModelError) as error:
        parse_effective_fdf(path)
    assert error.value.code is FdfErrorCode.UNSUPPORTED_SYNTAX
