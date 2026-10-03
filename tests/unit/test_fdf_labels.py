"""TASK 20.2 label identity, fail-closed writer spelling and census regressions."""

from __future__ import annotations

from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from hubbardflow.siesta_backend.coverage_reference import _canonical, _perturbed
from hubbardflow.siesta_backend.fdf_labels import canonical_fdf_label
from hubbardflow.siesta_backend.fdf_model import (
    FdfErrorCode,
    FdfModelError,
    _blocks,
    _one,
    parse_effective_fdf,
)

from .test_fdf_model import _fdf


@given(st.text(), st.sampled_from(("-", "_", ".")))
def test_canonical_label_ignores_only_declared_punctuation(text: str, punctuation: str) -> None:
    assert canonical_fdf_label(punctuation.join(text)) == canonical_fdf_label(text)
    assert canonical_fdf_label(canonical_fdf_label(text)) == canonical_fdf_label(text)


def test_unmanaged_long_output_is_read_generically() -> None:
    assert _one("Long_Output true # supported alias\n", "LongOutput") == "true"
    assert _blocks("%block Long_Output\nvalue\n%endblock long.output\n") == {"longoutput": ("value",)}


@pytest.mark.parametrize(
    ("source", "expected"),
    (
        ("Chemical_Species_Label", "ChemicalSpeciesLabel"),
        ("DFTU_PotentialShift", "DFTU.PotentialShift"),
        ("Spin_Orbit", "SpinOrbit"),
        ("spin.orbit", "SpinOrbit"),
        ("Non-Collinear-Spin", "NonCollinearSpin"),
        ("scf_dm_tolerance", "SCF.DM.Tolerance"),
    ),
)
def test_managed_alias_is_recognized_then_rejected(tmp_path: Path, source: str, expected: str) -> None:
    text = _fdf()
    if expected == "ChemicalSpeciesLabel":
        text = text.replace(expected, source)
    else:
        text += f"{source} T\n"
    path = tmp_path / "alias.fdf"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(FdfModelError) as error:
        parse_effective_fdf(path)
    assert error.value.code is FdfErrorCode.NONCANONICAL_MANAGED_LABEL
    assert expected in str(error.value)


def test_dftu_case_difference_is_accepted(tmp_path: Path) -> None:
    path = tmp_path / "case.fdf"
    path.write_text(_fdf().replace("DFTU.Proj", "DFTU.pRoJ"), encoding="utf-8")
    assert parse_effective_fdf(path).dftu_records[0].label == "Co"


@pytest.mark.parametrize("reverse", (False, True))
@pytest.mark.parametrize(
    "pair",
    (
        ("DM.Tolerance 0.01\n", "dm_tolerance 0.02\n"),
        ("LongOutput true\n", "long.output false\n"),
        ("%block LongOutput\n1\n%endblock\n", "%block long_output\n2\n%endblock\n"),
        ("%block DM.InitSpin\n1 0\n%endblock\n", "%block dm_initspin\n1 1\n%endblock\n"),
    ),
)
def test_duplicate_precedes_managed_spelling_independent_of_order(
    tmp_path: Path, pair: tuple[str, str], reverse: bool
) -> None:
    ordered = pair[::-1] if reverse else pair
    path = tmp_path / "duplicate.fdf"
    # The unrelated bad spelling appears first to check whole-input precedence.
    path.write_text("DFTU_PotentialShift T\n" + _fdf() + "".join(ordered), encoding="utf-8")
    with pytest.raises(FdfModelError) as error:
        parse_effective_fdf(path)
    assert error.value.code is FdfErrorCode.UNSUPPORTED_SYNTAX
    assert "duplicate" in str(error.value)


def test_block_payload_is_not_interpreted_as_directives(tmp_path: Path) -> None:
    path = tmp_path / "payload.fdf"
    path.write_text(
        _fdf() + "%block Long_Output\nDM.Tolerance 1\ndm_tolerance 2\n%endblock Long_Output\n",
        encoding="utf-8",
    )
    assert parse_effective_fdf(path).number_of_atoms == 1
    assert _one(path.read_text(encoding="utf-8"), "DM.Tolerance") is None


def test_coverage_recognizes_punctuation_without_normalizing_exact_echo() -> None:
    text = "DFTU_PotentialShift T\n%block dftu_proj\nCo 1\n3 2\n0.02 0\n3 0.05\n%endblock\n"
    assert _perturbed(text)
    assert _canonical(text) != _canonical(text.replace("DFTU_PotentialShift", "DFTU.PotentialShift"))
    unshifted = text.replace("0.02 0", "0 0")
    assert not _perturbed(unshifted)
