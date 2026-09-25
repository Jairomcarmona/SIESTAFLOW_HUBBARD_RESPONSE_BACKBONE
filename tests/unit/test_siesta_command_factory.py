from pathlib import Path

import pytest

from siestaflow_hubbard.execution.execution_profile import ExecutionProfile
from siestaflow_hubbard.siesta_backend.command_factory import SiestaCampaignLayout, SiestaCommandFactory


def _profile(executable: Path) -> ExecutionProfile:
    return ExecutionProfile.from_mapping({
        "target": "slurm", "evidence": "VALIDATED_RUNTIME",
        "slurm": {"partition": "private", "account": None, "qos": None},
        "allocation": {"nodes": 1, "total_cpus": 2, "memory": "private", "walltime": "private",
                       "max_parallel_steps": 1, "shutdown_margin_seconds": 60, "termination_grace_seconds": 30},
        "runtime": {"module_commands": [], "siesta_executable": str(executable), "exclusive": True,
                    "environment": {}, "launcher": {"kind": "hydra", "command": [str(executable)],
                    "bootstrap": "ssh", "processes_per_node": 2}},
        "task_policy": {"max_attempts": 1, "require_scf_converged": True},
    })


def _layout(tmp_path: Path) -> SiestaCampaignLayout:
    fdf = tmp_path / "reference.fdf"; fdf.write_text("SystemLabel reference\n", encoding="utf-8")
    dm = tmp_path / "reference.DM"; dm.write_bytes(b"dm")
    return SiestaCampaignLayout(fdf, tmp_path / "runs", dm, "reference.DM")


def test_direct_factory_construction_requires_an_admission(tmp_path: Path):
    executable = tmp_path / "siesta"; executable.write_bytes(b"binary")
    with pytest.raises(TypeError):
        SiestaCommandFactory(_profile(executable), ["host-a"], _layout(tmp_path), {})


def test_factory_layout_no_longer_exposes_legacy_bare_sidecars(tmp_path: Path):
    _layout(tmp_path)
    sidecar = tmp_path / "bare.json"; sidecar.write_text("{}", encoding="utf-8")
    fdf = tmp_path / "other.fdf"; fdf.write_text("SystemLabel other\n", encoding="utf-8")
    dm = tmp_path / "other.DM"; dm.write_bytes(b"dm")
    with pytest.raises(TypeError):
        SiestaCampaignLayout(fdf, tmp_path / "other-runs", dm, "other.DM", bare_sidecars={"bare": sidecar})
