from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from hubbardflow.domain.perturbation_plan import PlanStatus
from hubbardflow.execution.campaign_split import (
    CampaignSplitStaging,
    stage_campaign_split,
    verify_campaign_split_staging,
)
from hubbardflow.execution.campaign_v2 import CampaignV2Error, load_campaign_v2
from hubbardflow.execution.product_models import ProductCommand, ProductError, ProductReason
from hubbardflow.execution.product_plan import (
    ProductRequest,
    freeze_product_snapshot,
    load_product_snapshot,
    product_execution_boundary,
    resolve_product_snapshot,
)
from hubbardflow.execution.wsl_campaign_init import initialize_campaign
from hubbardflow.siesta_backend.fdf_model import parse_effective_fdf
from hubbardflow.siesta_backend.semantic_species_split import verify_semantic_split_identities
from hubbardflow.siesta_backend.semantic_split_models import SemanticSpeciesSplitError, SemanticSplitStatus
from tests.unit.test_campaign_plan import inputs, normalized
from tests.unit.test_semantic_species_split import _source


def shared_inputs(tmp_path: Path) -> tuple[Path, dict[str, Any], Path]:
    source = _source(tmp_path)
    text = (
        source.read_text()
        .replace("0.123 0.045", "0 0")
        .replace("DFTU.Method 2", "DFTU.Method 2\nDFTU.ProjectorGenerationMethod 2")
        + "\nXC.functional GGA\nXC.authors PBE\n"
    )
    return inputs(tmp_path, text)


def request(fdf: Path, raw: dict[str, Any]) -> ProductRequest:
    config = fdf.parent / "lr-config.json"
    config.write_text(json.dumps(raw))
    return ProductRequest(str(fdf), str(config), None, None, None, None, (str(fdf.parent),), None, None)


def test_off_reports_shared_label_without_mutation(tmp_path: Path) -> None:
    fdf, raw, _ = shared_inputs(tmp_path / "source")
    before = {path.name: path.read_bytes() for path in fdf.parent.iterdir() if path.is_file()}
    assert stage_campaign_split(fdf, raw, tmp_path / "out") is None
    assert not (tmp_path / "out").exists()
    assert before == {path.name: path.read_bytes() for path in fdf.parent.iterdir() if path.is_file()}
    with pytest.raises(CampaignV2Error, match="SHARED_LABEL_NEEDS_SPLIT"):
        normalized(fdf, raw)
    snapshot = resolve_product_snapshot(request(fdf, raw))
    assert snapshot.reasons == (ProductReason.SHARED_LABEL_NEEDS_SPLIT,)
    assert snapshot.split_staging is None
    assert "split_staging" not in snapshot.to_mapping()


def test_campaign_init_stages_without_executable_manifest(tmp_path: Path) -> None:
    fdf, raw, profile = shared_inputs(tmp_path / "source")
    raw["auto_split_species"] = True
    config = fdf.parent / "lr-config.json"
    config.write_text(json.dumps(raw))
    result = initialize_campaign(
        fdf_path=str(fdf),
        lr_config_path=str(config),
        profile_path=str(profile),
        name="pending",
        campaign_root=str(tmp_path),
    )
    assert result["status"] == SemanticSplitStatus.STAGED_PENDING_GENERATED_IDENTITY.value
    assert not (tmp_path / "pending/campaign.v2.json").exists()
    assert not (tmp_path / "pending/campaign.lock").exists()
    with pytest.raises(CampaignV2Error):
        load_campaign_v2(Path(result["staging_manifest_path"]))
    staging = CampaignSplitStaging.from_mapping(json.loads(Path(result["staging_manifest_path"]).read_text()))
    assert staging.policy.auto_split_species is True
    assert staging.digest == result["staging_digest"]
    verify_campaign_split_staging(tmp_path / "pending", staging)
    final = parse_effective_fdf(tmp_path / "pending/species_split/reference.fdf")
    original = parse_effective_fdf(fdf)
    assert final.dm_init_spin == original.dm_init_spin
    assert tuple(record.label for record in final.dftu_records) == ("CoLR0", "CoLR1")
    assert tuple(atom.source_coordinates for atom in final.atoms) == tuple(
        atom.source_coordinates for atom in original.atoms
    )
    for label in ("CoLR0", "CoLR1"):
        assert (tmp_path / f"pending/species_split/{label}.psml").read_bytes() == (
            fdf.parent / "Co.psml"
        ).read_bytes()


def test_product_pending_identity_is_frozen_and_override_cannot_execute(tmp_path: Path) -> None:
    fdf, raw, _ = shared_inputs(tmp_path / "source")
    raw["auto_split_species"] = True
    snapshot = resolve_product_snapshot(request(fdf, raw))
    assert snapshot.status is PlanStatus.NOT_ESTABLISHED
    assert snapshot.planning is None
    assert snapshot.reasons == (ProductReason.STAGED_PENDING_GENERATED_IDENTITY,)
    assert snapshot.split_staging is not None
    root = tmp_path / "product"
    freeze_product_snapshot(root, snapshot)
    assert load_product_snapshot(root) == snapshot
    assert not (root / "resolved_perturbation_plan.json").exists()
    receipt = product_execution_boundary(
        root, snapshot, ProductCommand.RUN, override_reason="review", partition=None, account=None
    )
    assert receipt.to_mapping()["status"] == PlanStatus.NOT_ESTABLISHED.value
    assert ProductReason.STAGED_PENDING_GENERATED_IDENTITY in receipt.reasons
    assert (
        snapshot.campaign_identity
        != resolve_product_snapshot(request(fdf, {**raw, "auto_split_species": False})).campaign_identity
    )
    # Restore the opted-in source config before checking staged-byte tampering.
    request(fdf, raw)
    (root / "species_split/CoLR0.psml").write_bytes(b"changed")
    with pytest.raises(ProductError, match="staged input bytes changed"):
        load_product_snapshot(root)


@pytest.mark.parametrize("missing", ["basis", "pseudo", "ion"])
def test_optin_identity_preflight_fails_without_partial_staging(tmp_path: Path, missing: str) -> None:
    fdf, raw, _ = shared_inputs(tmp_path / "source")
    raw["auto_split_species"] = True
    if missing == "basis":
        text = fdf.read_text()
        fdf.write_text(text[: text.index("%block PAO.Basis")])
    elif missing == "pseudo":
        for suffix in (".psml", ".psf", ".vps"):
            (fdf.parent / f"Co{suffix}").unlink()
    else:
        (fdf.parent / "Co.ion").unlink()
    with pytest.raises((SemanticSpeciesSplitError, OSError)):
        stage_campaign_split(fdf, raw, tmp_path / "out")
    assert not (tmp_path / "out/species_split").exists()


def test_orphan_dftu_entry_is_rejected_by_identity_verifier(tmp_path: Path) -> None:
    fdf, raw, _ = shared_inputs(tmp_path / "source")
    staged = stage_campaign_split(fdf, {**raw, "auto_split_species": True}, tmp_path / "out")
    assert staged is not None
    final = tmp_path / "out/species_split/reference.fdf"
    original_record = parse_effective_fdf(fdf).dftu_records[0].canonical_text
    final.write_text(
        final.read_text().replace("%endblock DFTU.Proj", original_record + "\n%endblock DFTU.Proj")
    )
    with pytest.raises(SemanticSpeciesSplitError):
        verify_semantic_split_identities(final, ("CoLR0", "CoLR1"), fdf, "Co", (final.parent,), (fdf.parent,))


def test_pending_mapping_cannot_claim_ready(tmp_path: Path) -> None:
    fdf, raw, _ = shared_inputs(tmp_path / "source")
    snapshot = resolve_product_snapshot(request(fdf, {**raw, "auto_split_species": True}))
    with pytest.raises(ProductError, match="cannot supply an executable plan"):
        replace(snapshot, status=PlanStatus.READY)


def test_two_shared_species_stage_together_and_preserve_spin(tmp_path: Path) -> None:
    fdf, raw, _ = shared_inputs(tmp_path / "source")
    text = fdf.read_text().replace("NumberOfAtoms 3", "NumberOfAtoms 4")
    text = text.replace("2 8 O", "2 28 Ni")
    text = text.replace(" 0.25 0.5 0.5 2 O unchanged # ligand", " 0.25 0.5 0.5 2 Ni\n 0.75 0.5 0.5 2 Ni")
    text = text.replace("3 0.010", "3 0.010\n4 -0.010")
    text = text.replace("O 2\nn=2 0 2 E 30 4", "Ni 2\nn=2 0 2 E 30 4")
    text = text.replace("%endblock DFTU.Proj", "Ni 1\n3 2\n0 0\n3.000 0.050\n%endblock DFTU.Proj")
    fdf.write_text(text)
    (fdf.parent / "Ni.psml").write_bytes(b"Ni pseudopotential")
    from tests.unit.test_semantic_species_split import _ion

    (fdf.parent / "Ni.ion").write_bytes(_ion("Ni", 28))
    raw["pseudopotentials"] = {"Co": str(fdf.parent / "Co.psml"), "Ni": str(fdf.parent / "Ni.psml")}
    raw["auto_split_species"] = True
    first = stage_campaign_split(fdf, raw, tmp_path / "first")
    second = stage_campaign_split(fdf, raw, tmp_path / "second", identity_dirs=(fdf.parent,))
    assert first == second
    assert first is not None
    assert tuple(label for label, _ in first.splits) == ("Co", "Ni")
    final = parse_effective_fdf(tmp_path / "first/species_split/reference.fdf")
    assert {record.label for record in final.dftu_records} == {"CoLR0", "CoLR1", "NiLR0", "NiLR1"}
    assert final.dm_init_spin == parse_effective_fdf(fdf).dm_init_spin
    verify_campaign_split_staging(tmp_path / "first", first)


def test_staging_refuses_frozen_destination_without_writing(tmp_path: Path) -> None:
    from tests.unit.test_semantic_species_split import ROOT

    fdf, raw, _ = shared_inputs(tmp_path / "source")
    target = ROOT / "benchmarks/lr_u/task15-forbidden"
    with pytest.raises(ProductError, match="frozen V6"):
        stage_campaign_split(fdf, {**raw, "auto_split_species": True}, target)
    assert not target.exists()


@pytest.mark.parametrize("invalid", [float("nan"), float("inf"), float("-inf")])
def test_nonfinite_config_fails_before_staging(tmp_path: Path, invalid: float) -> None:
    fdf, raw, _ = shared_inputs(tmp_path / "source")
    with pytest.raises(SemanticSpeciesSplitError, match="finite JSON"):
        stage_campaign_split(
            fdf, {**raw, "auto_split_species": True, "alpha_grid_ev": [invalid]}, tmp_path / "out"
        )
    assert not (tmp_path / "out/species_split").exists()
