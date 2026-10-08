"""POSIX replay of the production MnO translation-shadow path with fake SIESTA."""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

import numpy as np
import pytest

from hubbardflow.execution.campaign_runner import campaign_status, run_campaign_worker
from hubbardflow.execution.campaign_v2 import CONFIG_SCHEMA
from hubbardflow.execution.wsl_campaign_init import initialize_campaign
from hubbardflow.siesta_backend.siesta542_bare_profile import Siesta542PotentialShiftHamiltonianProfile

ROOT = Path(__file__).resolve().parents[2]
ARCHIVE = ROOT / "campaigns/mno_afmii_strict_lr_v3r2/results/response-matrix-foreground-recovery-v4"
FDF = ARCHIVE / "00_REFERENCE/siesta.fdf"


@pytest.mark.skipif(os.name == "nt", reason="POSIX campaign replay requires fcntl and executable fixtures")
@pytest.mark.parametrize("reference_dm_varies", [False, True])
def test_mno_translation_shadowed_replay_proves_shadows_and_reconstructs(
    tmp_path: Path,
    reference_dm_varies: bool,
) -> None:
    """Exercise the real gate and shadow DAG against archived MnO response outputs."""
    dm_bytes = b"synthetic replay parent DM\n"
    planning_dm = tmp_path / "reference.DM"
    planning_dm.write_bytes(dm_bytes)
    settings_path = tmp_path / "replay-settings.json"
    call_log = tmp_path / "calls.log"
    fake = tmp_path / "siesta"
    fake.write_text(_fake_siesta_source(), encoding="utf-8")
    fake.chmod(0o755)
    launcher = tmp_path / "mpirun.openmpi"
    launcher.write_text('#!/bin/sh\nset -eu\nshift 6\nexec "$@"\n', encoding="utf-8")
    launcher.chmod(0o755)
    settings_path.write_text(
        json.dumps(
            {
                "archive": str(ARCHIVE),
                "dm": str(planning_dm),
                "calls": str(call_log),
                "fdf": str(FDF),
                "reference_dm_varies": reference_dm_varies,
            }
        ),
        encoding="utf-8",
    )

    profile = Siesta542PotentialShiftHamiltonianProfile()
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
                            "profile_id": profile.profile_id,
                            "version": profile.profile_version,
                            "metadata": {"source_revision": profile.source_revision},
                        },
                        "state": "compatible",
                        "reason": "hash-verified fake SIESTA replay",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    raw_config = {
        "schema": CONFIG_SCHEMA,
        "functional": "PBE",
        "pseudopotentials": {
            label: str(ROOT / "campaigns/mno_afmii_strict_lr_v3r2/pseudopotentials/Mn.psml")
            for label in (f"MnLR{index:02d}" for index in range(16))
        }
        | {"O": str(ROOT / "campaigns/mno_afmii_strict_lr_v3r2/pseudopotentials/O.psml")},
        "alpha_grid_ev": [-0.1, -0.05, -0.025, 0.025, 0.05, 0.1],
        "compatibility_registry": str(registry),
        "version_text_source": str(
            ROOT / "tests/fixtures/real_nio_p5_rerun/inputs/software/siesta_version.txt"
        ),
        "declared_executable": "siesta",
        "analysis_policy": {"estimator": "polynomial", "polynomial_degree": 3},
        # This is the declared I.5 continuity tolerance used by the task's MnO config.
        "magnetic_moment_tolerance_muB": 0.1,
        "coverage": "TRANSLATION_SHADOWED",
        "planning_reference_output": str(ARCHIVE / "00_REFERENCE/siesta.out"),
        "planning_reference_dm": str(planning_dm),
        "reference_dm_name": "00_REFERENCE.DM",
        "shadow_rejection_policy": "STOP",
        # Explicit fixture policy: identical printed occupations use the FDF
        # SCF tolerance; Fermi is recorded without an energy tolerance.
        "parent_reproduction_factor": 1.0,
    }
    config_path = tmp_path / "lr_config.json"
    config_path.write_text(json.dumps(raw_config, sort_keys=True), encoding="utf-8")
    profile_path = tmp_path / "execution_profile.json"
    profile_path.write_text(
        json.dumps(
            {
                "target": "local_wsl",
                "evidence": "VALIDATED_RUNTIME",
                "wsl": {
                    "distribution": "Ubuntu",
                    "python_executable": sys.executable,
                    "workspace_root": str(tmp_path),
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
                    "environment": {"HUBBARDFLOW_MNO_REPLAY_SETTINGS": str(settings_path)},
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

    initialized = initialize_campaign(
        fdf_path=str(FDF),
        lr_config_path=str(config_path),
        profile_path=str(profile_path),
        name="mno_translation_shadowed_replay",
        pointer_path=str(tmp_path / "campaign.pointer.json"),
    )
    manifest = Path(initialized["manifest_path"])
    assert run_campaign_worker(manifest, "run") == 0
    status = campaign_status(manifest)
    assert status["status"] == "COMPLETED"
    assert len(call_log.read_text(encoding="utf-8").splitlines()) == 49

    analysis = json.loads(
        (manifest.parent / "results/data/lr_u_analysis.v3.json").read_text(encoding="utf-8")
    )
    dataset = analysis["response_observation_dataset"]
    evidence = json.loads((manifest.parent / ".siestaflow/node-evidence.json").read_text(encoding="utf-8"))
    reproduction = evidence["nodes"]["reference"]["reference_reproduction"]
    assert reproduction["criterion"] == "PRINT_EQUIVALENT"
    assert reproduction["equivalent"] is True
    assert reproduction["occupation_equivalence"] == "EQUIVALENT"
    assert reproduction["fermi_equivalence"] == "RECORDED_NOT_ASSESSED"
    assert reproduction == dataset["reference_reproduction"]
    assert reproduction["planning_parent_dm_sha256"] == hashlib.sha256(dm_bytes).hexdigest()
    assert (
        reproduction["planning_parent_dm_sha256"] != reproduction["campaign_parent_dm_sha256"]
    ) is reference_dm_varies
    report = (manifest.parent / "results/HUBBARDFLOW.out").read_text(encoding="ascii")
    assert reproduction["planning_parent_dm_sha256"] in report
    assert reproduction["campaign_parent_dm_sha256"] in report
    assert dataset["reference_source"]["dm_sha256"] == reproduction["campaign_parent_dm_sha256"]
    shadow = dataset["translation_shadow"]
    assert len(shadow["outcomes"]) == 2
    assert all(outcome["status"] == "PROVEN" for outcome in shadow["outcomes"])
    assert shadow["complete_state_gate"] == "PROVEN"
    reconstructed = shadow["reconstructed_raw_matrices"]
    primary = analysis["primary"]
    for key in ("chi0_raw", "chi_raw"):
        np.testing.assert_allclose(reconstructed[key], primary[key], atol=1e-12, rtol=0.0)
    plan = json.loads((manifest.parent / "resolved_perturbation_plan.json").read_text(encoding="utf-8"))
    classes = plan["coverage"]["classes"]
    u_by_site = primary["U_by_site_eV"]
    for group in classes:
        class_sites = [member.split("@", 1)[0] for member in group["members"]]
        indices = dataset["site_id_to_matrix_index"]
        values = [float(u_by_site[str(indices[site])]) for site in class_sites]
        assert max(values) - min(values) <= 1e-9


def _fake_siesta_source() -> str:
    return r"""#!/usr/bin/env python3
import json, os, re, sys
from pathlib import Path
settings = json.loads(Path(os.environ["HUBBARDFLOW_MNO_REPLAY_SETTINGS"]).read_text())
archive, cwd = Path(settings["archive"]), Path.cwd()
fdf = (cwd / "siesta.fdf").read_text()
label = re.search(r"(?im)^\s*SystemLabel\s+(\S+)", fdf).group(1)
with Path(settings["calls"]).open("a") as stream: stream.write(label + "\n")
if label == "00_REFERENCE":
    dm = Path(settings["dm"]).read_bytes()
    if settings.get("reference_dm_varies"): dm += str(cwd).encode()
    (cwd / "00_REFERENCE.DM").write_bytes(dm)
    text = (archive / "00_REFERENCE/siesta.out").read_text()
else:
    match = re.fullmatch(r"lr_s(\d{3})_([mp])0p(\d+)_(bare|screened)", label)
    if not match: raise SystemExit("unexpected SIESTA label: " + label)
    index, sign, fraction, mode = int(match.group(1)), match.group(2), match.group(3), match.group(4).upper()
    tag = f"{sign}0d{int(round(float('0.' + fraction) * 1000)):03d}"
    sublattice = "A" if index % 2 == 0 else "B"
    text = (archive / f"{sublattice}_{mode}_{tag}/siesta.out").read_text()
    coords_text = fdf.split("%block AtomicCoordinatesAndAtomicSpecies")[1].split("%endblock")[0].strip()
    rows = [line for line in coords_text.splitlines() if line.strip()]
    positions = [tuple(float(value) for value in row.split()[:3]) for row in rows]
    correlated = [n for n, row in enumerate(rows, 1) if re.search(r"MnLR\d+", row)]
    representative = correlated[0 if sublattice == "A" else 1]
    target = correlated[index]
    shift = tuple((positions[target-1][k] - positions[representative-1][k]) % 1.0 for k in range(3))
    def image(atom):
        wanted = tuple((positions[atom-1][k] + shift[k]) % 1.0 for k in range(3))
        for candidate in range(1, len(positions)+1):
            if all(abs(((positions[candidate-1][k] - wanted[k] + .5) % 1.0) - .5) < 1e-8 for k in range(3)):
                return candidate
        raise SystemExit("translation has no atom image")
    permutation = {atom: image(atom) for atom in correlated}
    if any(permutation[atom] != atom for atom in correlated):
        lines = text.split("\n")
        starts = [i for i, line in enumerate(lines) if line.strip() == "hubbard_term: projector occupations"]
        blocks = []
        for start in starts:
            end = next(i for i in range(start, len(lines)) if lines[i].startswith("Occupations:"))
            atom = int(lines[start+1].split()[-2]); blocks.append((start, end, atom))
        transformed = list(lines)
        inverse = {value: key for key, value in permutation.items()}
        for offset in range(0, len(blocks), len(correlated)):
            group = blocks[offset:offset+len(correlated)]
            content = {atom: lines[start+2:end+1] for start, end, atom in group}
            for start, end, atom in group:
                replacement = content[inverse[atom]]
                if len(replacement) != end-start-1: raise SystemExit("occupation block sizes differ")
                transformed[start+2:end+1] = replacement
        text = "\n".join(transformed)
sys.stdout.write(text)
fermi = re.findall(r"(?im)siesta:\s+Fermi\s*=\s*([-+0-9.eE]+)", text)[-1]
all_fermi = []
for path in archive.glob("*/siesta.out"):
    found = re.findall(r"(?im)siesta:\s+Fermi\s*=\s*([-+0-9.eE]+)", path.read_text(errors="replace"))
    if found: all_fermi.extend(float(value) for value in found)
low, high = min(all_fermi)-2.0, max(all_fermi)+2.0
(cwd / f"{label}.EIG").write_text(f"{fermi}\n2 1 1\n1 {low:.10f} {high:.10f}\n")
"""
