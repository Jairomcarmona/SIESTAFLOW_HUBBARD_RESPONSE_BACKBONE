from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from hubbardflow.siesta_backend.fdf_builder import materialize_split_species_fdf
from hubbardflow.siesta_backend.fdf_model import parse_effective_fdf
from hubbardflow.siesta_backend.semantic_ion_identity import (
    IonIdentityError,
    canonical_ion_bytes,
    relabel_ion_bytes,
)
from hubbardflow.siesta_backend.semantic_species_split import (
    materialize_semantic_split_species_fdf,
    verify_semantic_split_identities,
)
from hubbardflow.siesta_backend.semantic_split_models import (
    SemanticSpeciesIdentityEvidence,
    SemanticSpeciesSplitError,
    SemanticSpeciesSplitPolicy,
    SemanticSpeciesSplitResult,
    SemanticSplitCode,
    SemanticSplitStatus,
)

ROOT = Path(__file__).resolve().parents[2]
ENABLED = SemanticSpeciesSplitPolicy(auto_split_species=True)


def _ion(label: str, number: int) -> bytes:
    return (
        f"<basis_specs>\n{label:<21}Z= {number} Mass= 10.000\n"
        "rcs: 2.12345 3.23456\n</basis_specs>\n"
        f"{label:<30}# Label\n<radial>0.123456 0.234567</radial>\n"
    ).encode()


def _source(directory: Path, label: str = "Co", number: int = 27) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    fdf = directory / "reference.fdf"
    fdf.write_text(
        f"""NumberOfAtoms 3
NumberOfSpecies 2
LatticeConstant 4.2 Ang
%block LatticeVectors
1 0 0
0 1 0
0 0 1
%endblock LatticeVectors
%block ChemicalSpeciesLabel
1 {number} {label}
2 8 O
%endblock ChemicalSpeciesLabel
AtomicCoordinatesFormat Fractional
%block AtomicCoordinatesAndAtomicSpecies
 0.0 0.0 0.0 1 {label} keep extra # magnetic atom A
 0.5 0.0 0.0 1 {label} another token # magnetic atom B
 0.25 0.5 0.5 2 O unchanged # ligand
%endblock AtomicCoordinatesAndAtomicSpecies
%block DM.InitSpin
1 3.000
2 -2.500
3 0.010
%endblock DM.InitSpin
Spin polarized
DFTU.Method 2
DFTU.PotentialShift true
%block DFTU.Proj
{label} 1
3 2
0.123 0.045
3.000 0.050
%endblock DFTU.Proj
PAO.BasisSize DZP
PAO.BasisType split
PAO.EnergyShift 0.005 Ry
PAO.SplitNorm 0.15
%block PAO.Basis
{label} 3 # original header options
n=3 0 2 E 40 5
2.12345 3.23456
O 2
n=2 0 2 E 30 4
%endblock PAO.Basis
""",
        encoding="utf-8",
    )
    for suffix in (".psml", ".psf", ".vps"):
        (directory / f"{label}{suffix}").write_bytes(b"identical pseudopotential payload")
    (directory / f"{label}.ion").write_bytes(_ion(label, number))
    return fdf


def _materialize(source: Path, destination: Path) -> SemanticSpeciesSplitResult:
    return materialize_semantic_split_species_fdf(
        source, "Co", "CoLR", destination, (source.parent,), policy=ENABLED
    )


@pytest.mark.parametrize(("label", "number"), [("Co", 27), ("Ni", 28), ("Mn", 25)])
def test_split_preserves_physics_and_explicit_pending_status(tmp_path: Path, label: str, number: int) -> None:
    source = _source(tmp_path / "source", label, number)
    original = parse_effective_fdf(source)
    result = materialize_semantic_split_species_fdf(
        source, label, f"{label}LR", tmp_path / "out", (source.parent,), policy=ENABLED
    )
    split = parse_effective_fdf(tmp_path / "out/split-species.fdf")
    assert result.status == SemanticSplitStatus.STAGED_PENDING_GENERATED_IDENTITY
    assert split.dm_init_spin == original.dm_init_spin
    assert split.lattice_vectors_angstrom == original.lattice_vectors_angstrom
    assert tuple(atom.source_coordinates for atom in split.atoms) == tuple(
        atom.source_coordinates for atom in original.atoms
    )
    assert tuple(atom.trailing_label for atom in split.atoms) == tuple(
        atom.trailing_label for atom in original.atoms
    )
    assert " 0.25 0.5 0.5 3 O unchanged # ligand" in result.content
    assert "keep extra # magnetic atom A" in result.content
    assert tuple(record.label for record in split.dftu_records) == result.labels
    assert label not in dict(split.pao_basis_blocks)
    assert [record.canonical_text.splitlines()[1:] for record in split.dftu_records] == [
        original.dftu_records[0].canonical_text.splitlines()[1:]
    ] * 2
    assert {digest for _, digest in result.split_identity_digests} == {result.source_identity_digest}
    assert result.policy_digest == ENABLED.digest
    assert SemanticSpeciesSplitResult.from_mapping(result.to_mapping()) == result
    for alias in result.labels:
        for suffix in (".psml", ".psf", ".vps"):
            assert (tmp_path / "out" / f"{alias}{suffix}").read_bytes() == (
                source.parent / f"{label}{suffix}"
            ).read_bytes()
        assert canonical_ion_bytes(
            (tmp_path / "out" / f"{alias}.ion").read_bytes(), alias
        ) == canonical_ion_bytes((source.parent / f"{label}.ion").read_bytes(), label)


def test_flag_off_is_explicit_and_writes_nothing(tmp_path: Path) -> None:
    source = _source(tmp_path / "source")
    with pytest.raises(SemanticSpeciesSplitError) as error:
        materialize_semantic_split_species_fdf(source, "Co", "X", tmp_path / "out", (source.parent,))
    assert error.value.code == SemanticSplitCode.SHARED_LABEL_NEEDS_SPLIT
    assert not (tmp_path / "out").exists()
    assert (
        SemanticSpeciesSplitPolicy.from_mapping(SemanticSpeciesSplitPolicy().to_mapping())
        == SemanticSpeciesSplitPolicy()
    )
    assert ENABLED.digest != SemanticSpeciesSplitPolicy().digest


@pytest.mark.parametrize("missing", ["pseudo", "basis", "ion"])
def test_missing_source_identity_fails_before_output(tmp_path: Path, missing: str) -> None:
    source = _source(tmp_path / "source")
    if missing == "pseudo":
        for suffix in (".psml", ".psf", ".vps"):
            (source.parent / f"Co{suffix}").unlink()
    elif missing == "ion":
        (source.parent / "Co.ion").unlink()
    else:
        text = source.read_text()
        source.write_text(text[: text.index("%block PAO.Basis")])
    with pytest.raises(SemanticSpeciesSplitError, match="SPECIES_IDENTITY_NOT_ESTABLISHED"):
        _materialize(source, tmp_path / "out")
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize(
    "change", ["ion", "basis", "header", "options", "pseudo", "projector", "secondary_pseudo"]
)
def test_postgeneration_verifier_rejects_physical_changes(tmp_path: Path, change: str) -> None:
    source = _source(tmp_path / "source")
    result = _materialize(source, tmp_path / "out")
    generated_fdf = tmp_path / "out/split-species.fdf"
    if change == "ion":
        path = tmp_path / "out/CoLR0.ion"
        path.write_bytes(path.read_bytes().replace(b"0.123456", b"0.123457"))
    elif change == "pseudo":
        (tmp_path / "out/CoLR0.psml").write_bytes(b"different PP")
    elif change == "secondary_pseudo":
        (tmp_path / "out/CoLR0.psf").write_bytes(b"different PP")
    else:
        before, after = {
            "basis": ("2.12345", "2.12346"),
            "header": ("CoLR0 3", "CoLR0 4"),
            "options": ("PAO.BasisSize DZP", "PAO.BasisSize SZ"),
            "projector": ("0.123 0.045", "0.124 0.045"),
        }[change]
        generated_fdf.write_text(generated_fdf.read_text().replace(before, after))
    with pytest.raises(SemanticSpeciesSplitError, match="SPECIES_IDENTITY_NOT_ESTABLISHED"):
        verify_semantic_split_identities(
            generated_fdf, result.labels, source, "Co", (tmp_path / "out",), (source.parent,)
        )


@pytest.mark.parametrize(
    "control",
    [
        "%block AtomicMass\n1 55\n%endblock AtomicMass\n",
        "PAO.BasisType Co split\n",
        "%block PAO.BasisSizes\nCo SZ\n%endblock PAO.BasisSizes\n",
    ],
)
def test_unmodeled_species_controls_fail_closed(tmp_path: Path, control: str) -> None:
    source = _source(tmp_path / "source")
    # Replace the existing scalar to avoid an unrelated duplicate-key rejection.
    source.write_text(source.read_text().replace("PAO.BasisType split\n", "") + control)
    with pytest.raises(SemanticSpeciesSplitError, match="INVALID_SPLIT_INPUT"):
        _materialize(source, tmp_path / "out")
    assert not (tmp_path / "out").exists()


def test_wrapper_legacy_compatibility_and_optin_typed_result(tmp_path: Path) -> None:
    source = _source(tmp_path / "source")
    content = parse_effective_fdf(source).effective_text
    legacy = materialize_split_species_fdf(content, "Co", "CoLR")
    assert isinstance(legacy, tuple) and legacy[1] == ["CoLR0", "CoLR1"]
    assert "Co 1\n3 2\n0.123 0.045" in legacy[0]  # Existing legacy behavior retained.
    with pytest.raises(SemanticSpeciesSplitError, match="SHARED_LABEL_NEEDS_SPLIT"):
        materialize_split_species_fdf(content, "Co", "CoLR", semantic_policy=SemanticSpeciesSplitPolicy())
    opted_in = materialize_split_species_fdf(
        content,
        "Co",
        "CoLR",
        semantic_policy=ENABLED,
        source_fdf_path=str(source),
        search_dirs=(str(source.parent),),
        output_directory=str(tmp_path / "out"),
    )
    assert isinstance(opted_in, SemanticSpeciesSplitResult)
    assert opted_in.status == SemanticSplitStatus.STAGED_PENDING_GENERATED_IDENTITY


def test_archive_identity_failure_is_read_only(tmp_path: Path) -> None:
    for relative, label in [
        ("benchmarks/lr_u/CoO/reference.fdf", "CoLR0"),
        ("benchmarks/lr_u/stage_u_b/materials/NiO/reference.fdf", "NiLR0"),
        ("benchmarks/lr_u/MnO/reference.fdf", "MnLR0"),
    ]:
        source = ROOT / relative
        before = hashlib.sha256(source.read_bytes()).hexdigest()
        # Archives are already split and use implicit basis generation. They
        # cannot demonstrate the new helper's shared-label source identity.
        with pytest.raises(SemanticSpeciesSplitError):
            materialize_semantic_split_species_fdf(
                source, label, "X", tmp_path / label, (source.parent,), policy=ENABLED
            )
        assert hashlib.sha256(source.read_bytes()).hexdigest() == before


@given(st.integers(min_value=0, max_value=1000000))
def test_ion_label_normalization_preserves_every_physical_byte(index: int) -> None:
    source = _ion("Co", 27)
    alias = f"X{index}"
    renamed = relabel_ion_bytes(source, "Co", alias)
    assert canonical_ion_bytes(source, "Co") == canonical_ion_bytes(renamed, alias)
    assert relabel_ion_bytes(renamed, alias, "Co") == source


def test_real_ion_two_label_fields_and_unknown_layout() -> None:
    source = (ROOT / "examples/Mn.ion").read_bytes()
    renamed = relabel_ion_bytes(source, "Mn", "MnLR0")
    assert canonical_ion_bytes(source, "Mn") == canonical_ion_bytes(renamed, "MnLR0")
    assert relabel_ion_bytes(renamed, "MnLR0", "Mn") == source
    with pytest.raises(IonIdentityError):
        canonical_ion_bytes(b"unknown format", "Mn")


def test_invalid_serialized_values_fail_closed(tmp_path: Path) -> None:
    result = _materialize(_source(tmp_path / "source"), tmp_path / "out")
    for key, invalid in [
        ("content", float("nan")),
        ("status", "READY"),
        ("labels", [float("inf")]),
        ("split_identity_digests", [["X"]]),
    ]:
        mapping = result.to_mapping()
        mapping[key] = invalid
        with pytest.raises(SemanticSpeciesSplitError):
            SemanticSpeciesSplitResult.from_mapping(mapping)


def test_comparison_evidence_and_search_directory_order_are_deterministic(tmp_path: Path) -> None:
    source = _source(tmp_path / "source")
    duplicate = tmp_path / "duplicate"
    duplicate.mkdir()
    for path in source.parent.glob("Co.*"):
        (duplicate / path.name).write_bytes(path.read_bytes())
    first = materialize_semantic_split_species_fdf(
        source, "Co", "X", tmp_path / "one", (source.parent, duplicate), policy=ENABLED
    )
    second = materialize_semantic_split_species_fdf(
        source, "Co", "X", tmp_path / "two", (duplicate, source.parent), policy=ENABLED
    )
    assert first == second
    evidence = verify_semantic_split_identities(
        tmp_path / "one/split-species.fdf", first.labels, source, "Co", (tmp_path / "one",), (source.parent,)
    )
    assert SemanticSpeciesIdentityEvidence.from_mapping(evidence.to_mapping()) == evidence
