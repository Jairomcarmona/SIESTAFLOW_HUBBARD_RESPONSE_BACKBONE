"""POSIX reference-only product run and archived NiO P5 follow-up planning."""

from __future__ import annotations

import hashlib
import json
import lzma
import os
import sys
from pathlib import Path

import pytest

from hubbardflow.cli import main
from hubbardflow.siesta_backend.siesta542_bare_profile import Siesta542PotentialShiftHamiltonianProfile

ROOT = Path(__file__).resolve().parents[2]
INPUTS = ROOT / "tests/fixtures/real_nio_p5_rerun/inputs"
REPLAY = ROOT / "tests/fixtures/replay_nio_p5"
DM_SHA256 = "f7fca191f941bbda5ee38eb361096aa8a802dfd410e12aaa680f39f3cf2193ef"


@pytest.mark.skipif(os.name == "nt", reason="reference replay requires POSIX fcntl and executables")
def test_nio_reference_product_archives_validated_output_and_parent_dm(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    fake = REPLAY / "siesta"
    launcher = REPLAY / "mpirun.openmpi"
    assert fake.stat().st_mode & 0o111
    assert launcher.stat().st_mode & 0o111
    backend_profile = Siesta542PotentialShiftHamiltonianProfile()
    registry = tmp_path / "backend_compatibility.json"
    registry.write_text(
        json.dumps(
            {
                "schema": "backend_compatibility_v1",
                "records": [
                    {
                        "backend": {
                            "backend_id": "siesta",
                            "version": "5.4.2",
                            "executable_sha256": hashlib.sha256(fake.read_bytes()).hexdigest(),
                        },
                        "profile": {
                            "profile_id": backend_profile.profile_id,
                            "version": backend_profile.profile_version,
                            "metadata": {"source_revision": backend_profile.source_revision},
                        },
                        "state": "compatible",
                        "reason": "hash-verified NiO replay executable",
                    }
                ],
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    config = json.loads((INPUTS / "source_lr_config.json").read_text(encoding="utf-8"))
    config["pseudopotentials"] = {
        label: str(INPUTS / "pseudopotentials" / f"{label}.psml") for label in ("NiLR0", "NiLR1", "O")
    }
    config["compatibility_registry"] = str(registry)
    config["version_text_source"] = str(INPUTS / "software/siesta_version.txt")
    config["reference_dm_name"] = "NIO_PBE_REFERENCE.DM"
    config_path = tmp_path / "lr_config.json"
    config_path.write_text(json.dumps(config, sort_keys=True), encoding="utf-8")
    profile_path = tmp_path / "execution_profile.json"
    profile_path.write_text(
        json.dumps(
            {
                "target": "local_wsl",
                "evidence": "VALIDATED_RUNTIME",
                "wsl": {
                    "distribution": "Ubuntu",
                    "python_executable": sys.executable,
                    "workspace_root": str(tmp_path / "campaigns"),
                },
                "allocation": {
                    "nodes": 1,
                    "total_cpus": 1,
                    "memory": "1G",
                    "walltime": "01:00:00",
                    "max_parallel_steps": 1,
                    "shutdown_margin_seconds": 60,
                    "termination_grace_seconds": 30,
                },
                "runtime": {
                    "module_commands": [],
                    "siesta_executable": str(fake),
                    "exclusive": True,
                    "environment": {},
                    "launcher": {
                        "kind": "openmpi",
                        "command": [str(launcher)],
                        "bootstrap": "local",
                        "processes_per_node": 1,
                    },
                },
                "task_policy": {"max_attempts": 1, "require_scf_converged": True},
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    output_dir = tmp_path / "nio-reference-product"
    reference_fdf = INPUTS / "reference.fdf"
    command = [
        "reference",
        str(reference_fdf),
        "--lr-config",
        str(config_path),
        "--profile",
        str(profile_path),
        "--name",
        "nio-reference-only",
        "--output-dir",
        str(output_dir),
    ]
    assert main(command) == 0
    console = capsys.readouterr().out
    assert "Follow-up run: hubbardflow run" in console

    reference_dir = output_dir / "planning_reference"
    archived_output = reference_dir / "reference.out"
    archived_dm = reference_dir / "NIO_PBE_REFERENCE.DM"
    receipt = json.loads((reference_dir / "receipt.json").read_text(encoding="utf-8"))
    assert hashlib.sha256(archived_dm.read_bytes()).hexdigest() == DM_SHA256
    assert receipt["reference_dm_sha256"] == DM_SHA256
    assert receipt["input_fdf_sha256"] == hashlib.sha256(reference_fdf.read_bytes()).hexdigest()
    assert receipt["node_id"] == "reference"
    assert receipt["campaign_manifest_path"].endswith("campaign.v2.json")
    assert receipt["command_argv"]

    fixture_manifest = json.loads((REPLAY / "manifest.json").read_text(encoding="utf-8"))
    reference_run = next(row for row in fixture_manifest["runs"] if row["site_id"] == "reference")
    expected_output = lzma.decompress((REPLAY / reference_run["out_file"]).read_bytes())
    assert archived_output.read_bytes() == expected_output
    worker_state = json.loads(
        (tmp_path / "campaigns/nio-reference-only/.siestaflow/worker-state.json").read_text(encoding="utf-8")
    )
    assert worker_state["status"] == "STOPPED"
    assert worker_state["stop_reason"] == "reference_only"
    assert (tmp_path / "campaigns/nio-reference-only/.siestaflow/replay-run-count").read_text() == "1"

    plan_dir = tmp_path / "nio-ts-plan"
    assert (
        main(
            [
                "plan",
                str(reference_fdf),
                "--lr-config",
                str(config_path),
                "--reference-output",
                str(archived_output),
                "--reference-dm",
                str(archived_dm),
                "--coverage",
                "TRANSLATION_SHADOWED",
                "--output-dir",
                str(plan_dir),
            ]
        )
        == 0
    )
    capsys.readouterr()
    plan = json.loads((plan_dir / "resolved_perturbation_plan.json").read_text(encoding="utf-8"))
    assert plan["reference"]["status"] == "ADMISSIBLE"
    assert plan["reference"]["parent_dm_sha256"] == DM_SHA256
