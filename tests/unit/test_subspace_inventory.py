from __future__ import annotations

from pathlib import Path

from hubbardflow.domain.subspace_inventory import (
    InventoryReason,
    InventoryStatus,
    build_inventory,
)
from hubbardflow.siesta_backend.fdf_model import (
    FdfModel,
    SpeciesIdentity,
    parse_effective_fdf,
    species_identity,
)


def _source(
    *, shared: bool = False, orphan: bool = False, spin: str = "Spin polarized", soc: str = ""
) -> str:
    labels = "1 27 Co\n2 8 O" + ("\n3 27 Co2" if orphan else "")
    coordinate_rows = "0 0 0 1\n0.5 0.5 0.5 1" if shared else "0 0 0 1"
    if not shared:
        coordinate_rows += "\n0.5 0.5 0.5 2"
    if orphan:
        coordinate_rows += "\n0.25 0.25 0.25 2"
    records = "Co 1\n3 2\n0 0\n3 0.05"
    if orphan:
        records += "\nCo2 1\n3 2\n0 0\n3 0.05"
    basis_co2 = "Co2\nn=3 0 2 E 40 5" if orphan else ""
    return f"""NumberOfAtoms {len(coordinate_rows.splitlines())}
NumberOfSpecies {3 if orphan else 2}
%block ChemicalSpeciesLabel
{labels}
%endblock ChemicalSpeciesLabel
LatticeConstant 4 Ang
%block LatticeVectors
1 0 0
0 1 0
0 0 1
%endblock LatticeVectors
AtomicCoordinatesFormat Fractional
%block AtomicCoordinatesAndAtomicSpecies
{coordinate_rows}
%endblock AtomicCoordinatesAndAtomicSpecies
DFTU.ProjectorGenerationMethod 2
{spin}
{soc}
%block DFTU.Proj
{records}
%endblock DFTU.Proj
%block PAO.Basis
Co
n=3 0 2 E 40 5
O
n=2 0 2 E 40 5
{basis_co2}
%endblock PAO.Basis
"""


def _model(
    tmp_path: Path,
    *,
    shared: bool = False,
    orphan: bool = False,
    spin: str = "Spin polarized",
    soc: str = "",
) -> tuple[FdfModel, dict[str, SpeciesIdentity]]:
    fdf = tmp_path / "case.fdf"
    fdf.write_text(_source(shared=shared, orphan=orphan, spin=spin, soc=soc), encoding="utf-8")
    model = parse_effective_fdf(fdf)
    for label in ("Co", "Co2", "O"):
        pseudo = tmp_path / f"{label}.psml"
        if label in {species.label for species in model.chemical_species_labels}:
            pseudo.write_text(f"{label} pseudopotential", encoding="utf-8")
    return model, species_identity(model, [tmp_path])


def test_inventory_order_is_atom_order_and_input_digest_is_bound(tmp_path: Path) -> None:
    model, identities = _model(tmp_path)
    inventory = build_inventory(model, identities)
    assert inventory.status is InventoryStatus.OK
    assert [site.atom_index for site in inventory.subspaces] == [0]
    assert inventory.subspaces[0].species_label == "Co"
    assert inventory.effective_fdf_sha256 == model.effective_fdf_sha256
    assert inventory.digest


def test_reordered_atomic_rows_change_the_canonical_atom_index(tmp_path: Path) -> None:
    source = _source().replace("0 0 0 1\n0.5 0.5 0.5 2", "0.5 0.5 0.5 2\n0 0 0 1")
    fdf = tmp_path / "reordered.fdf"
    fdf.write_text(source, encoding="utf-8")
    model = parse_effective_fdf(fdf)
    for label in ("Co", "O"):
        (tmp_path / f"{label}.psml").write_text(f"{label} pseudo", encoding="utf-8")
    inventory = build_inventory(model, species_identity(model, [tmp_path]))
    assert [(item.atom_index, item.species_label) for item in inventory.subspaces] == [(1, "Co")]


def test_shared_dftu_label_is_explicitly_reported(tmp_path: Path) -> None:
    model, identities = _model(tmp_path, shared=True)
    inventory = build_inventory(model, identities)
    assert inventory.status is InventoryStatus.SHARED_LABEL_NEEDS_SPLIT
    assert InventoryReason.DFTU_LABEL_MULTIPLE_ATOMS in inventory.reason_codes
    assert [item.atom_index for item in inventory.subspaces] == [0, 1]


def test_dftu_label_without_atom_is_mapping_not_established(tmp_path: Path) -> None:
    model, identities = _model(tmp_path, orphan=True)
    inventory = build_inventory(model, identities)
    assert inventory.status is InventoryStatus.SUBSPACE_MAPPING_NOT_ESTABLISHED
    assert InventoryReason.DFTU_LABEL_NO_ATOM in inventory.reason_codes


def test_missing_pseudopotential_blocks_inventory_reduction(tmp_path: Path) -> None:
    fdf = tmp_path / "case.fdf"
    fdf.write_text(_source(), encoding="utf-8")
    model = parse_effective_fdf(fdf)
    identities = species_identity(model, [tmp_path])
    inventory = build_inventory(model, identities)
    assert inventory.status is InventoryStatus.SUBSPACE_MAPPING_NOT_ESTABLISHED
    assert InventoryReason.SPECIES_IDENTITY_NOT_ESTABLISHED in inventory.reason_codes


def test_noncollinear_spin_and_soc_are_not_supported(tmp_path: Path) -> None:
    for index in range(2):
        folder = tmp_path / str(index)
        folder.mkdir()
        model, identities = _model(
            folder,
            spin="Spin noncollinear" if index == 0 else "Spin polarized",
            soc="SpinOrbit true" if index == 1 else "",
        )
        inventory = build_inventory(model, identities)
        assert inventory.status is InventoryStatus.NOT_SUPPORTED
        assert InventoryReason.NONCOLLINEAR_OR_SOC_NOT_SUPPORTED in inventory.reason_codes
