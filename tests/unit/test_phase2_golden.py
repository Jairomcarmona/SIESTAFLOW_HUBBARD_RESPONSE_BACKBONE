"""NiO P5 current initialization versus independently archived R10 evidence."""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
from typing import Any, cast

import pytest

from hubbardflow.domain.lr_campaign_contract import LinearResponseBareCampaignContract
from hubbardflow.execution.campaign_runner import _build_dag
from hubbardflow.execution.campaign_v2 import load_campaign_v2
from hubbardflow.execution.wsl_campaign_init import initialize_campaign
from hubbardflow.siesta_backend.backend_admission_plugin import admit_siesta542_from_campaign_contract
from hubbardflow.siesta_backend.siesta542_bare_profile import Siesta542PotentialShiftHamiltonianProfile
from hubbardflow.siesta_backend.symmetry_materializer import materialize_response_fdf
from tools.dev.generate_phase2_golden import _archive_golden

ROOT = Path(__file__).resolve().parents[2]
ARCHIVE = ROOT / "campaigns/nio_pbe_p5_20260928"
MATERIAL = ROOT / "benchmarks/lr_u/stage_u_b/materials/NiO"
FIXTURE = ROOT / "tests/fixtures/phase2_golden/nio_p5.json"


def _json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def _archived_config_file(tmp_path: Path) -> Path:
    config = tmp_path / "archived_lr_config.json"
    config.write_bytes(_json(FIXTURE)["archived_lr_config_source_text"].encode("utf-8"))
    return config


def test_nio_p5_golden_is_exact_archived_evidence(tmp_path: Path) -> None:
    assert _json(FIXTURE) == _archive_golden(
        ARCHIVE / "campaign.v2.json",
        ARCHIVE / ".siestaflow/node-evidence.json",
        _archived_config_file(tmp_path),
    )


def test_golden_generator_does_not_fabricate_missing_archive_nodes(tmp_path: Path) -> None:
    evidence = _json(ARCHIVE / ".siestaflow/node-evidence.json")
    node = next(key for key in sorted(evidence["nodes"]) if key.startswith("response:"))
    del evidence["nodes"][node]
    incomplete = tmp_path / "node-evidence.json"
    incomplete.write_text(json.dumps(evidence), encoding="utf-8")
    with pytest.raises(ValueError, match="does not exactly cover"):
        _archive_golden(ARCHIVE / "campaign.v2.json", incomplete, _archived_config_file(tmp_path))


def test_golden_generator_rejects_unbound_archived_config(tmp_path: Path) -> None:
    config = _archived_config_file(tmp_path)
    config.write_bytes(config.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="lr-config SHA256 differs"):
        _archive_golden(ARCHIVE / "campaign.v2.json", ARCHIVE / ".siestaflow/node-evidence.json", config)


def test_nio_p5_disabled_coverage_reproduces_archived_identities_and_fdfs(tmp_path: Path) -> None:
    golden = _json(FIXTURE)
    expected_inputs = golden["archive"]["input_files_sha256"]
    fdf = MATERIAL / "reference.fdf"
    assert sha256(fdf.read_bytes()).hexdigest() == expected_inputs[golden["archive"]["reference_fdf"]]
    relocated = _json(ARCHIVE / "lr-config.json")
    raw = golden["archived_lr_config"]
    # The repository archive relocated lr_config.json as lr-config.json and
    # rewrote only these three local asset paths. Every other mapping value,
    # including fields beyond the selected manifest scientific values, matches.
    path_fields = {"compatibility_registry", "pseudopotentials", "version_text_source"}
    assert {key: value for key, value in relocated.items() if key not in path_fields} == {
        key: value for key, value in raw.items() if key not in path_fields
    }
    assert set(relocated) == set(raw)
    assert set(relocated["pseudopotentials"]) == set(raw["pseudopotentials"])
    for field, value in golden["scientific_values"].items():
        assert raw[field] == value
    assert raw["sites"] == [{k: v for k, v in s.items() if k != "index"} for s in golden["sites"]]
    pseudo = {label: MATERIAL / "pseudopotentials" / f"{label}.psml" for label in raw["pseudopotentials"]}
    for label, path in pseudo.items():
        assert sha256(path.read_bytes()).hexdigest() == expected_inputs[f"pseudopotentials/{label}.psml"]

    # These artifacts authorize only in-memory materialization. The placeholder
    # executable is never run, and its registry identity is explicitly test-only.
    executable = tmp_path / "siesta"
    executable.write_bytes(b"test-only identity: never execute\n")
    version = tmp_path / "version.txt"
    version.write_text("SIESTA 5.4.2\n", encoding="utf-8")
    registry = tmp_path / "backend.json"
    profile_id = "siesta-5.4.2-potential-shift-hamiltonian-v1"
    registry.write_text(
        json.dumps(
            {
                "schema": "backend_compatibility_v1",
                "records": [
                    {
                        "backend": {
                            "backend_id": "siesta",
                            "version": "5.4.2",
                            "executable_sha256": sha256(executable.read_bytes()).hexdigest(),
                        },
                        "profile": {"profile_id": profile_id, "version": "1"},
                        "state": "compatible",
                        "reason": "test-only admission for rendering; no execution",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    profile = _json(ARCHIVE / "execution_profile.json")
    # Select a non-submitting portable profile so this test runs on Windows and
    # Linux alike. Allocation/SCF values are retained from the archived profile.
    profile["target"] = "slurm"
    del profile["wsl"]
    profile["slurm"] = {"partition": "test-only", "account": None, "qos": None}
    profile["runtime"]["siesta_executable"] = str(executable)
    profile["runtime"]["launcher"] = {
        "kind": "hydra",
        "command": ["test-only-mpiexec"],
        "bootstrap": "ssh",
        "processes_per_node": 4,
    }
    profile_path = tmp_path / "profile.json"
    profile_path.write_text(json.dumps(profile), encoding="utf-8")
    raw.update(
        {
            "coverage": "DISABLED",
            "pseudopotentials": {k: str(v) for k, v in pseudo.items()},
            "compatibility_registry": str(registry),
            "version_text_source": str(version),
        }
    )
    config = tmp_path / "lr-config.json"
    config.write_text(json.dumps(raw), encoding="utf-8")
    result = initialize_campaign(
        fdf_path=str(fdf),
        lr_config_path=str(config),
        profile_path=str(profile_path),
        name="nio-p5-golden",
        campaign_root=str(tmp_path / "campaigns"),
    )
    manifest = load_campaign_v2(result["manifest_path"])
    assert manifest["coverage"] == "DISABLED"
    assert manifest["sites"] == golden["sites"]
    for field, value in golden["scientific_values"].items():
        assert manifest[field] == value
    _, specs = _build_dag(manifest["sites"], manifest["alpha_grid_ev"])
    by_label = {s["site_id"]: s["atom_index"] for s in manifest["sites"]}
    identities = sorted(
        [
            {
                "label": spec.site_id,
                "atom_index": by_label[spec.site_id],
                "mode": spec.mode.value,
                "alpha_ev": spec.alpha_ev,
            }
            for spec in specs.values()
        ],
        key=lambda row: (row["label"], row["atom_index"], row["mode"], row["alpha_ev"]),
    )
    assert identities == golden["response_identities"]
    campaign = Path(manifest["_campaign_root"])
    contract = LinearResponseBareCampaignContract.from_dict(_json(campaign / manifest["contract_file"]))
    admission = admit_siesta542_from_campaign_contract(
        campaign_root=campaign, contract=contract, executable_path=executable
    )
    materialized = {"reference": sha256((campaign / "reference.fdf").read_bytes()).hexdigest()}
    for node_id, spec in specs.items():
        rendered = materialize_response_fdf(
            campaign / "reference.fdf",
            spec,
            bare_profile=Siesta542PotentialShiftHamiltonianProfile(),
            admission=admission,
        )
        materialized[node_id] = sha256(rendered.content.encode("utf-8")).hexdigest()
    assert materialized == golden["materialized_fdf_sha256"]
