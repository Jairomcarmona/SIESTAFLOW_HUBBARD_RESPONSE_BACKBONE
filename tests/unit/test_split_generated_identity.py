from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from hubbardflow.siesta_backend.semantic_ion_identity import relabel_ion_bytes
from hubbardflow.siesta_backend.split_generated_identity import (
    GeneratedSplitIdentity,
    SplitIdentityError,
    SplitIdentityReason,
    SplitIdentityStatus,
    verify_generated_split_identity,
)
from tests.unit.test_semantic_species_split import ROOT, _ion
from tools.hubbardflow_verify_split_identity import main


def _run(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    source = _ion("Mn", 25)
    (directory / "Mn.ion").write_bytes(source)
    for label in ("MnLR0", "MnLR1"):
        (directory / f"{label}.ion").write_bytes(relabel_ion_bytes(source, "Mn", label))


def test_exact_receipt_roundtrip_and_cli(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _run(tmp_path)
    receipt = verify_generated_split_identity(tmp_path, "Mn", ["MnLR1", "MnLR0"])
    assert receipt.status is SplitIdentityStatus.MATCH
    assert receipt.reasons == ()
    assert all(item.raw_sha256 != receipt.original.raw_sha256 for item in receipt.aliases)
    assert all(item.differing_lines == (2, 5) for item in receipt.aliases)
    assert GeneratedSplitIdentity.from_mapping(receipt.to_mapping()) == receipt
    assert main([str(tmp_path), "--original-label", "Mn", "--aliases", "MnLR0", "MnLR1"]) == 0
    row = json.loads(capsys.readouterr().out)
    assert row["receipt_sha256"] == receipt.digest
    assert "READY" not in row.values()


@pytest.mark.parametrize("failure", ["original_missing", "alias_missing", "duplicate", "physical_change"])
def test_missing_duplicate_and_mismatch_fail_closed(tmp_path: Path, failure: str) -> None:
    _run(tmp_path)
    reason = SplitIdentityReason.ION_MISSING
    if failure == "original_missing":
        (tmp_path / "Mn.ion").unlink()
    elif failure == "alias_missing":
        (tmp_path / "MnLR0.ion").unlink()
    elif failure == "duplicate":
        child = tmp_path / "second"
        _run(child)
        reason = SplitIdentityReason.ION_DUPLICATE
    else:
        alias = relabel_ion_bytes(_ion("Mn", 25), "Mn", "MnLR0")
        (tmp_path / "MnLR0.ion").write_bytes(alias.replace(b"0.123456", b"0.123457"))
        reason = SplitIdentityReason.ION_BYTES_DIFFER
    receipt = verify_generated_split_identity(tmp_path, "Mn", ["MnLR0", "MnLR1"])
    expected_status = (
        SplitIdentityStatus.MISMATCH
        if failure == "physical_change"
        else SplitIdentityStatus.SPECIES_IDENTITY_NOT_ESTABLISHED
    )
    assert receipt.status is expected_status
    assert reason in receipt.reasons
    if failure == "physical_change":
        assert receipt.aliases[0].differing_lines == (2, 5, 6)
    assert main([str(tmp_path), "--original-label", "Mn", "--aliases", "MnLR0", "MnLR1"]) == 2


def test_real_archive_label_only_difference_matches(tmp_path: Path) -> None:
    archive = ROOT / "FEO_SCF_DIAGNOSTIC_EXPORT_20261001/feo_lru_fullU_PopTol1e-5_MixerWeight0.05"
    original = tmp_path / "original"
    aliases = tmp_path / "aliases"
    original.mkdir()
    aliases.mkdir()
    (original / "FeLR0.ion").write_bytes((archive / "FeLR0.ion").read_bytes())
    (aliases / "FeLR1.ion").write_bytes((archive / "FeLR1.ion").read_bytes())
    receipt = verify_generated_split_identity(aliases, "FeLR0", ["FeLR1"], reference_directory=original)
    assert receipt.status is SplitIdentityStatus.MATCH
    assert receipt.reasons == ()
    assert {item.diagnostic_canonical_sha256 for item in receipt.aliases} == {
        receipt.original.diagnostic_canonical_sha256
    }
    assert receipt.aliases[0].differing_lines == (5, 79)
    assert (archive / "FeLR0.ion").exists() and (archive / "FeLR1.ion").exists()


def test_raw_identical_ion_with_wrong_alias_header_is_mismatch(tmp_path: Path) -> None:
    source = _ion("Mn", 25)
    (tmp_path / "Mn.ion").write_bytes(source)
    (tmp_path / "MnLR0.ion").write_bytes(source)
    receipt = verify_generated_split_identity(tmp_path, "Mn", ["MnLR0"])
    assert receipt.status is SplitIdentityStatus.MISMATCH
    assert receipt.aliases[0].differing_lines == ()
    assert receipt.reasons == (SplitIdentityReason.ION_LABEL_MISMATCH,)


def test_symbol_line_difference_is_mismatch_and_lists_line(tmp_path: Path) -> None:
    source = (
        ROOT / "FEO_SCF_DIAGNOSTIC_EXPORT_20261001/feo_lru_fullU_PopTol1e-5_MixerWeight0.05/FeLR0.ion"
    ).read_bytes()
    alias = relabel_ion_bytes(source, "FeLR0", "FeLR1")
    alias = alias.replace(
        b"Fe                            # Symbol", b"Co                            # Symbol"
    )
    (tmp_path / "FeLR0.ion").write_bytes(source)
    (tmp_path / "FeLR1.ion").write_bytes(alias)
    receipt = verify_generated_split_identity(tmp_path, "FeLR0", ["FeLR1"])
    assert receipt.status is SplitIdentityStatus.MISMATCH
    assert receipt.aliases[0].differing_lines == (5, 78, 79)
    assert SplitIdentityReason.ION_BYTES_DIFFER in receipt.reasons


@pytest.mark.parametrize("labels", [[], ["MnLR0", "MnLR0"], ["Mn"], ["../Mn"], [float("nan")]])
def test_invalid_alias_requests_are_rejected(tmp_path: Path, labels: list[str]) -> None:
    with pytest.raises(SplitIdentityError):
        verify_generated_split_identity(tmp_path, "Mn", labels)


def test_raw_sha256_is_diagnostic_and_does_not_change_verdict(tmp_path: Path) -> None:
    _run(tmp_path)
    receipt = verify_generated_split_identity(tmp_path, "Mn", ["MnLR0"])
    changed = replace(receipt.aliases[0], raw_sha256="1" * 64)
    assert replace(receipt, aliases=(changed,)).status is SplitIdentityStatus.MATCH


def test_receipt_cannot_claim_relabel_match_with_different_canonical_digest(tmp_path: Path) -> None:
    _run(tmp_path)
    receipt = verify_generated_split_identity(tmp_path, "Mn", ["MnLR0"])
    mapping = receipt.to_mapping()
    aliases = mapping["aliases"]
    assert isinstance(aliases, list)
    alias = aliases[0]
    assert isinstance(alias, dict)
    alias["diagnostic_canonical_sha256"] = "1" * 64
    with pytest.raises(SplitIdentityError, match="equal canonical ion digests"):
        GeneratedSplitIdentity.from_mapping(mapping)
    row = receipt.to_mapping()
    row["original"] = {"label": float("nan")}
    with pytest.raises(SplitIdentityError):
        GeneratedSplitIdentity.from_mapping(row)


@pytest.mark.parametrize("invalid", [float("nan"), float("inf"), "invalid"])
def test_invalid_digest_uses_module_error(tmp_path: Path, invalid: str) -> None:
    _run(tmp_path)
    receipt = verify_generated_split_identity(tmp_path, "Mn", ["MnLR0"])
    with pytest.raises(SplitIdentityError):
        replace(receipt.original, raw_sha256=invalid)


def test_cli_invalid_labels_fails_closed(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main([str(tmp_path), "--original-label", "Mn", "--aliases", "MnLR0", "MnLR0"]) == 2
    row = json.loads(capsys.readouterr().out)
    assert row["status"] == SplitIdentityStatus.SPECIES_IDENTITY_NOT_ESTABLISHED.value


@given(st.permutations(("MnLR0", "MnLR1")))
def test_alias_order_is_irrelevant(labels: list[str]) -> None:
    absent = ROOT / "tests/fixtures/no_generated_ions"
    assert verify_generated_split_identity(absent, "Mn", labels) == verify_generated_split_identity(
        absent, "Mn", tuple(reversed(labels))
    )
