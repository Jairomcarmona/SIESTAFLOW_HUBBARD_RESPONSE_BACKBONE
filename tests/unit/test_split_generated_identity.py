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
    # Exact-byte positive is deliberately synthetic: this makes no claim of
    # actual SIESTA generation, SCF convergence or production admissibility.
    for label in ("Mn", "MnLR0", "MnLR1"):
        (directory / f"{label}.ion").write_bytes(_ion("Mn", 25))


def test_exact_receipt_roundtrip_and_cli(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _run(tmp_path)
    receipt = verify_generated_split_identity(tmp_path, "Mn", ["MnLR1", "MnLR0"])
    assert receipt.status is SplitIdentityStatus.EXACT_ION_BYTES_MATCH
    assert receipt.reasons == ()
    assert {item.raw_sha256 for item in receipt.aliases} == {receipt.original.raw_sha256}
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
        (tmp_path / "MnLR0.ion").write_bytes(_ion("Mn", 25).replace(b"0.123456", b"0.123457"))
        reason = SplitIdentityReason.ION_BYTES_DIFFER
    receipt = verify_generated_split_identity(tmp_path, "Mn", ["MnLR0", "MnLR1"])
    assert receipt.status is SplitIdentityStatus.SPECIES_IDENTITY_NOT_ESTABLISHED
    assert reason in receipt.reasons
    assert main([str(tmp_path), "--original-label", "Mn", "--aliases", "MnLR0", "MnLR1"]) == 2


def test_real_archive_label_only_difference_is_never_a_positive(tmp_path: Path) -> None:
    data = (ROOT / "examples/Mn.ion").read_bytes()
    original = tmp_path / "original"
    aliases = tmp_path / "aliases"
    original.mkdir()
    aliases.mkdir()
    (original / "Mn.ion").write_bytes(data)
    for label in ("MnLR0", "MnLR1"):
        (aliases / f"{label}.ion").write_bytes(relabel_ion_bytes(data, "Mn", label))
    receipt = verify_generated_split_identity(aliases, "Mn", ["MnLR0", "MnLR1"], reference_directory=original)
    assert receipt.status is SplitIdentityStatus.SPECIES_IDENTITY_NOT_ESTABLISHED
    assert receipt.reasons == (SplitIdentityReason.ION_BYTES_DIFFER,)
    assert {item.diagnostic_canonical_sha256 for item in receipt.aliases} == {
        receipt.original.diagnostic_canonical_sha256
    }
    assert (ROOT / "examples/Mn.ion").read_bytes() == data


@pytest.mark.parametrize("labels", [[], ["MnLR0", "MnLR0"], ["Mn"], ["../Mn"], [float("nan")]])
def test_invalid_alias_requests_are_rejected(tmp_path: Path, labels: list[str]) -> None:
    with pytest.raises(SplitIdentityError):
        verify_generated_split_identity(tmp_path, "Mn", labels)


def test_invalid_receipt_cannot_claim_match(tmp_path: Path) -> None:
    _run(tmp_path)
    receipt = verify_generated_split_identity(tmp_path, "Mn", ["MnLR0"])
    changed = replace(receipt.aliases[0], raw_sha256="1" * 64)
    with pytest.raises(SplitIdentityError, match="reasons disagree"):
        replace(receipt, aliases=(changed,))
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
