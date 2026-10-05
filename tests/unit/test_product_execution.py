"""Exercise product-to-legacy initialization without launching SIESTA."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, cast

import pytest

from hubbardflow.domain.lr_campaign_contract import LinearResponseBareCampaignContract
from hubbardflow.domain.symmetry_reduction import PerturbationSpec, ResponseMode
from hubbardflow.execution.campaign_plan import CampaignCoverage
from hubbardflow.execution.campaign_v2 import load_campaign_v2
from hubbardflow.execution.product_admission import (
    ExecutionAdmissionStatus,
    execution_admission,
)
from hubbardflow.execution.product_models import ProductError, json_object
from hubbardflow.execution.product_plan import (
    ProductRequest,
    freeze_product_snapshot,
    load_product_snapshot,
    resolve_product_snapshot,
)
from hubbardflow.execution.wsl_campaign_init import initialize_campaign
from hubbardflow.product_cli import _execute_product_campaign
from hubbardflow.siesta_backend.backend_admission_plugin import admit_siesta542_from_campaign_contract
from hubbardflow.siesta_backend.siesta542_bare_profile import Siesta542PotentialShiftHamiltonianProfile
from hubbardflow.siesta_backend.symmetry_materializer import materialize_response_fdf
from tests.unit.test_campaign_plan import inputs, normalized


def _profile_with_test_backend(profile_path: Path, executable: Path) -> Path:
    launcher = executable.parent / "mpiexec.hydra"
    launcher.write_bytes(b"test launcher; never executed")
    payload = json.loads(profile_path.read_text(encoding="utf-8"))
    payload["runtime"]["siesta_executable"] = str(executable)
    payload["runtime"]["launcher"]["command"] = [str(launcher)]
    profile_path.write_text(json.dumps(payload), encoding="utf-8")
    return profile_path


def _bind_test_backend(registry_path: Path, executable: Path) -> None:
    profile = Siesta542PotentialShiftHamiltonianProfile()
    digest = hashlib.sha256(executable.read_bytes()).hexdigest()
    registry_path.write_text(
        json.dumps(
            {
                "schema": "backend_compatibility_v1",
                "records": [
                    {
                        "backend": {
                            "backend_id": "siesta",
                            "version": "5.4.2",
                            "executable_sha256": digest,
                        },
                        "profile": {
                            "profile_id": profile.profile_id,
                            "version": profile.profile_version,
                            "metadata": {"source_revision": profile.source_revision},
                        },
                        "state": "compatible",
                        "reason": "unit materialization identity fixture",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def _run_specs(campaign: dict[str, Any]) -> list[dict[str, object]]:
    path = Path(str(campaign["_campaign_root"])) / str(campaign["resolved_perturbation_plan_file"])
    return cast(list[dict[str, object]], json.loads(path.read_text(encoding="utf-8"))["run_specs"])


def _materialized_bytes(campaign: dict[str, Any], executable: Path) -> dict[str, bytes]:
    root = Path(str(campaign["_campaign_root"]))
    contract = LinearResponseBareCampaignContract.from_json(
        (root / str(campaign["contract_file"])).read_text(encoding="utf-8")
    )
    admission = admit_siesta542_from_campaign_contract(
        campaign_root=root,
        contract=contract,
        executable_path=executable,
    )
    profile = Siesta542PotentialShiftHamiltonianProfile()
    plan = json.loads((root / str(campaign["resolved_perturbation_plan_file"])).read_text(encoding="utf-8"))
    subspaces = plan["inventory"]["subspaces"]
    site_labels = {row["site_id"]: row["species_label"] for row in subspaces}
    site_index = {row["site_id"]: index for index, row in enumerate(subspaces)}
    contents: dict[str, bytes] = {}
    for row in plan["run_specs"]:
        site_id = str(row["site_id"])
        alpha = float(row["alpha_ev"])
        mode = ResponseMode(str(row["mode"]))
        alpha_token = ("p" if alpha > 0 else "m") + f"{abs(alpha):.12g}".replace(".", "p")
        run_id = f"lr_s{site_index[site_id]:03d}_{alpha_token}_{mode.value.lower()}"
        spec = PerturbationSpec(
            run_id,
            site_id,
            site_index[site_id],
            str(site_labels[site_id]),
            mode,
            alpha,
            "explicit_fixed_grid",
        )
        rendered = materialize_response_fdf(
            root / str(campaign["reference_fdf"]),
            spec,
            bare_profile=profile,
            admission=admission,
        )
        contents[run_id] = rendered.content.encode("utf-8")
    return contents


def test_product_direct_grid_links_legacy_campaign_without_running_siesta(
    tmp_path: Path, monkeypatch: Any
) -> None:
    executable = tmp_path / "siesta"
    executable.write_bytes(b"test backend identity; never executed")
    fdf, raw_config, profile = inputs(tmp_path / "inputs")
    _profile_with_test_backend(profile, executable)
    _bind_test_backend(Path(raw_config["compatibility_registry"]), executable)
    raw_config["coverage"] = "DISABLED"
    raw_config["sites"] = normalized(fdf, raw_config)["sites"]
    config_path = fdf.parent / "lr.json"
    config_path.write_text(json.dumps(raw_config), encoding="utf-8")
    request = ProductRequest(
        str(fdf.resolve()),
        str(config_path.resolve()),
        None,
        None,
        CampaignCoverage.DISABLED,
        None,
        (str(fdf.parent.resolve()),),
        None,
        None,
    )
    snapshot = resolve_product_snapshot(request)
    assert snapshot.frozen_lr_config_sha256 is not None
    assert snapshot.frozen_lr_config_json is not None
    frozen_config = json_object(snapshot.frozen_lr_config_json)
    frozen_grid = cast(list[float], frozen_config["alpha_grid_ev"])
    assert frozen_grid == sorted(frozen_grid)
    admission = execution_admission(snapshot, frozen_config)
    assert admission.status is ExecutionAdmissionStatus.ADMISSIBLE_LEGACY_EQUIVALENT, admission.reasons

    product_root = tmp_path / "product"
    freeze_product_snapshot(product_root, snapshot)
    frozen_snapshot = load_product_snapshot(product_root)
    worker_calls: list[tuple[str, str]] = []

    def fake_worker(manifest: Path, mode: str) -> int:
        worker_calls.append((str(manifest), mode))
        return 0

    monkeypatch.setattr("hubbardflow.execution.campaign_runner.run_campaign_worker", fake_worker)
    assert (
        _execute_product_campaign(
            product_root,
            frozen_snapshot,
            profile_path=profile,
            name="product-run",
            campaign_root=tmp_path / "product-campaigns",
        )
        == 0
    )
    assert len(worker_calls) == 1 and worker_calls[0][1] == "run"
    product_manifest = Path(worker_calls[0][0])
    product_campaign = load_campaign_v2(product_manifest)

    legacy = initialize_campaign(
        fdf_path=str(fdf),
        lr_config_path=str(config_path),
        profile_path=str(profile),
        name="legacy-run",
        campaign_root=str(tmp_path / "legacy-campaigns"),
    )
    legacy_campaign = load_campaign_v2(str(legacy["manifest_path"]))
    assert sorted(_run_specs(product_campaign), key=lambda row: json.dumps(row, sort_keys=True)) == sorted(
        _run_specs(legacy_campaign), key=lambda row: json.dumps(row, sort_keys=True)
    )
    assert _materialized_bytes(product_campaign, executable) == _materialized_bytes(
        legacy_campaign, executable
    )
    link = json.loads((product_root / "execution_link.json").read_text(encoding="utf-8"))
    assert link["campaign_path"] == str(product_manifest)
    assert link["manifest_sha256"] == hashlib.sha256(product_manifest.read_bytes()).hexdigest()
    assert not any(tmp_path.rglob("*.out"))


def test_single_manganese_pseudopotential_map_matches_staged_inventory_digest(tmp_path: Path) -> None:
    source = Path(__file__).resolve().parents[2] / (
        "campaigns/mno_afmii_strict_lr_v3r2/results/response-matrix-foreground-recovery-v4/00_REFERENCE/siesta.fdf"
    )
    fdf, raw_config, profile = inputs(tmp_path / "inputs", source.read_text(encoding="utf-8"))
    executable = tmp_path / "siesta"
    executable.write_bytes(b"test backend identity; never executed")
    _profile_with_test_backend(profile, executable)
    _bind_test_backend(Path(raw_config["compatibility_registry"]), executable)
    root = Path(__file__).resolve().parents[2]
    manganese_pseudo = root / "campaigns/mno_afmii_strict_lr_v3r2/pseudopotentials/Mn.psml"
    oxygen_pseudo = root / "campaigns/mno_afmii_strict_lr_v3r2/pseudopotentials/O.psml"
    raw_config["coverage"] = "DISABLED"
    raw_config["pseudopotentials"] = {
        **{f"MnLR{index:02d}": str(manganese_pseudo) for index in range(16)},
        "O": str(oxygen_pseudo),
    }
    raw_config["sites"] = normalized(fdf, raw_config)["sites"]
    config_path = fdf.parent / "lr.json"
    config_path.write_text(json.dumps(raw_config), encoding="utf-8")
    request = ProductRequest(
        str(fdf.resolve()),
        str(config_path.resolve()),
        None,
        None,
        CampaignCoverage.DISABLED,
        None,
        (str(fdf.parent.resolve()),),
        None,
        None,
    )
    snapshot = resolve_product_snapshot(request)
    product_root = tmp_path / "product"
    freeze_product_snapshot(product_root, snapshot)
    initialized = initialize_campaign(
        fdf_path=str(fdf),
        lr_config_path=str(config_path),
        profile_path=str(profile),
        name="mno-identity-map",
        campaign_root=str(tmp_path / "campaigns"),
    )
    campaign_root = Path(str(initialized["manifest_path"])).parent
    from hubbardflow.execution.campaign_plan import campaign_inventory

    staged_inventory = campaign_inventory(
        campaign_root / "reference.fdf", (campaign_root / "pseudopotentials",)
    )
    frozen_plan = json.loads((campaign_root / "resolved_perturbation_plan.json").read_text(encoding="utf-8"))
    assert snapshot.planning is not None
    assert snapshot.planning.plan.inventory.digest == staged_inventory.digest
    assert frozen_plan["inventory"]["digest"] == staged_inventory.digest


def test_local_wsl_product_campaign_uses_workspace_and_pointer(tmp_path: Path, monkeypatch: Any) -> None:
    executable = tmp_path / "siesta"
    executable.write_bytes(b"test backend identity; never executed")
    fdf, raw_config, profile = inputs(tmp_path / "inputs")
    _profile_with_test_backend(profile, executable)
    _bind_test_backend(Path(raw_config["compatibility_registry"]), executable)
    profile_data = json.loads(profile.read_text(encoding="utf-8"))
    profile_data["target"] = "local_wsl"
    profile_data.pop("slurm")
    workspace = tmp_path / "wsl-workspace"
    workspace_root = workspace.as_posix()
    if len(workspace_root) >= 3 and workspace_root[1:3] == ":/":
        workspace_root = workspace_root[2:]
    profile_data["wsl"] = {
        "distribution": "Ubuntu",
        "python_executable": "/usr/bin/python3",
        "workspace_root": workspace_root,
    }
    profile_data["allocation"]["total_cpus"] = 1
    profile_data["runtime"]["launcher"] = {
        "kind": "openmpi",
        "command": ["mpirun.openmpi"],
        "bootstrap": "local",
        "processes_per_node": 1,
    }
    profile.write_text(json.dumps(profile_data), encoding="utf-8")
    raw_config["coverage"] = "DISABLED"
    raw_config["sites"] = normalized(fdf, raw_config)["sites"]
    config_path = fdf.parent / "lr.json"
    config_path.write_text(json.dumps(raw_config), encoding="utf-8")
    request = ProductRequest(
        str(fdf.resolve()),
        str(config_path.resolve()),
        None,
        None,
        CampaignCoverage.DISABLED,
        None,
        (str(fdf.parent.resolve()),),
        None,
        None,
    )
    snapshot = resolve_product_snapshot(request)
    product_root = tmp_path / "product"
    freeze_product_snapshot(product_root, snapshot)
    frozen_snapshot = load_product_snapshot(product_root)
    worker_calls: list[tuple[str, str]] = []

    def fake_worker(manifest: Path, mode: str) -> int:
        worker_calls.append((str(manifest), mode))
        return 0

    monkeypatch.setattr("hubbardflow.execution.campaign_runner.run_campaign_worker", fake_worker)
    with pytest.raises(ProductError, match="workspace_root"):
        _execute_product_campaign(
            product_root,
            frozen_snapshot,
            profile_path=profile,
            name="product-run",
            campaign_root=tmp_path / "different-campaign-root",
        )
    assert worker_calls == []

    assert (
        _execute_product_campaign(
            product_root,
            frozen_snapshot,
            profile_path=profile,
            name="product-run",
            campaign_root=None,
        )
        == 0
    )
    assert len(worker_calls) == 1 and worker_calls[0][1] == "run"
    manifest_path = Path(worker_calls[0][0]).resolve()
    assert manifest_path == (workspace / "product-run" / "campaign.v2.json").resolve()
    pointer_path = product_root / "campaign.pointer.json"
    pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
    assert Path(pointer["manifest_path"]).resolve() == manifest_path


@pytest.mark.parametrize("changed_input", ["fdf", "pseudopotential"])
def test_source_change_after_admission_stops_before_worker(
    tmp_path: Path, monkeypatch: Any, changed_input: str
) -> None:
    executable = tmp_path / "siesta"
    executable.write_bytes(b"test backend identity; never executed")
    fdf, raw_config, profile = inputs(tmp_path / "inputs")
    _profile_with_test_backend(profile, executable)
    _bind_test_backend(Path(raw_config["compatibility_registry"]), executable)
    raw_config["coverage"] = "DISABLED"
    raw_config["sites"] = normalized(fdf, raw_config)["sites"]
    config_path = fdf.parent / "lr.json"
    config_path.write_text(json.dumps(raw_config), encoding="utf-8")
    request = ProductRequest(
        str(fdf.resolve()),
        str(config_path.resolve()),
        None,
        None,
        CampaignCoverage.DISABLED,
        None,
        (str(fdf.parent.resolve()),),
        None,
        None,
    )
    snapshot = resolve_product_snapshot(request)
    assert snapshot.frozen_lr_config_json is not None
    frozen_config = json_object(snapshot.frozen_lr_config_json)
    assert execution_admission(snapshot, frozen_config).status is (
        ExecutionAdmissionStatus.ADMISSIBLE_LEGACY_EQUIVALENT
    )
    product_root = tmp_path / "product"
    freeze_product_snapshot(product_root, snapshot)
    frozen_snapshot = load_product_snapshot(product_root)

    if changed_input == "fdf":
        fdf.write_bytes(fdf.read_bytes() + b"\n# changed after product admission\n")
    else:
        potential = Path(next(iter(cast(dict[str, str], raw_config["pseudopotentials"]).values())))
        potential.write_bytes(potential.read_bytes() + b"\n ")

    worker_calls: list[tuple[str, str]] = []

    def fake_worker(manifest: Path, mode: str) -> int:
        worker_calls.append((str(manifest), mode))
        return 0

    monkeypatch.setattr("hubbardflow.execution.campaign_runner.run_campaign_worker", fake_worker)
    with pytest.raises(ProductError, match="campaign input hash disagrees with frozen source evidence"):
        _execute_product_campaign(
            product_root,
            frozen_snapshot,
            profile_path=profile,
            name="changed-input-run",
            campaign_root=tmp_path / "product-campaigns",
        )
    assert worker_calls == []
    assert not (product_root / "execution_link.json").exists()
    assert list((tmp_path / "product-campaigns").rglob("campaign.v2.json"))
