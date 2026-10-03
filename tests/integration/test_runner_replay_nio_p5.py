"""End-to-end POSIX replay of the real NiO P5 SIESTA response grid."""

from __future__ import annotations

import hashlib
import json
import re
import sys
import time
from pathlib import Path
from typing import Any

import pytest

from hubbardflow.execution import campaign_v2, wsl_campaign_init
from hubbardflow.execution.campaign_runner import campaign_status, run_campaign_worker
from hubbardflow.execution.wsl_campaign_init import initialize_campaign
from hubbardflow.siesta_backend.siesta542_bare_profile import Siesta542PotentialShiftHamiltonianProfile

ROOT = Path(__file__).resolve().parents[2]
REAL_FIXTURE = ROOT / "tests" / "fixtures" / "real_nio_p5_rerun"
REPLAY_FIXTURE = ROOT / "tests" / "fixtures" / "replay_nio_p5"
ANALYSIS = "lr_u_analysis.v3.json"
GOLDEN_MANIFEST = REPLAY_FIXTURE / "campaign_manifest.sha256.json"
_ATTEMPT = re.compile(r"attempt-\d+-[0-9a-f]{8}")
_ATTEMPT_BYTES = re.compile(rb"attempt-\d+-[0-9a-f]{8}")
_ATTEMPT_GROUP = re.compile(r"(?<=/attempts/)[0-9a-f]{20}")
_ATTEMPT_SUFFIX = re.compile(r"(?<=_)[0-9a-f]{12}(?=[/._]|$)")
_ATTEMPT_GROUP_BYTES = re.compile(rb"(?<=/attempts/)[0-9a-f]{20}")
_ATTEMPT_SUFFIX_BYTES = re.compile(rb"(?<=_)[0-9a-f]{12}(?=[/._]|$)")
_DYNAMIC_INPUT_HASH_ROW = re.compile(rb"(\| (?:execution_profile|lr_config) \| [^|]+ \| )[0-9a-f]{64}( \|)")
_EVIDENCE_DIGEST_ROW = re.compile(rb"(\| response:[^\n]*\| )[0-9a-f]{64}( \|)")
_SHA256_TOKEN = re.compile(rb"(?<![0-9a-f])[0-9a-f]{64}(?![0-9a-f])")


@pytest.mark.skipif(sys.platform == "win32", reason="campaign replay requires POSIX fcntl and executables")
def test_nio_p5_runner_replay_matches_part_a_and_resumes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Stable campaign identity and timestamps make the complete written-file
    # manifest reproducible; these patches affect only this isolated test.
    def fixed_campaign_id() -> str:
        return "00000000-0000-4000-8000-000000000021"

    monkeypatch.setattr(campaign_v2, "new_campaign_id", fixed_campaign_id)
    monkeypatch.setattr(wsl_campaign_init, "new_campaign_id", fixed_campaign_id)
    ticks = iter(range(1_791_100_000_000_000_000, 1_791_100_000_000_001_000))
    monkeypatch.setattr(time, "time", lambda: 1_791_100_000.0)
    monkeypatch.setattr(time, "time_ns", lambda: next(ticks))
    profile = Siesta542PotentialShiftHamiltonianProfile()
    executable = REPLAY_FIXTURE / "siesta"
    launcher = REPLAY_FIXTURE / "mpirun.openmpi"
    assert executable.stat().st_mode & 0o111, "replay SIESTA fixture must be executable on POSIX"
    assert launcher.stat().st_mode & 0o111, "replay MPI launcher fixture must be executable on POSIX"
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
                            "executable_sha256": hashlib.sha256(executable.read_bytes()).hexdigest(),
                        },
                        "profile": {
                            "profile_id": profile.profile_id,
                            "version": profile.profile_version,
                            "metadata": {"source_revision": profile.source_revision},
                        },
                        "state": "compatible",
                        "reason": "hash-verified test replay fixture",
                    }
                ],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    inputs = REAL_FIXTURE / "inputs"
    config = json.loads((inputs / "source_lr_config.json").read_text(encoding="utf-8"))
    config["pseudopotentials"] = {
        label: str(inputs / "pseudopotentials" / f"{label}.psml") for label in ("NiLR0", "NiLR1", "O")
    }
    config["compatibility_registry"] = str(registry)
    config["version_text_source"] = str(inputs / "software" / "siesta_version.txt")
    config_path = tmp_path / "lr_config.json"
    config_path.write_text(json.dumps(config, indent=2, sort_keys=True) + "\n", encoding="utf-8")

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
                    "siesta_executable": str(executable),
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
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    initialized = initialize_campaign(
        fdf_path=str(inputs / "reference.fdf"),
        lr_config_path=str(config_path),
        profile_path=str(profile_path),
        name="nio_p5_runner_replay",
        pointer_path=str(tmp_path / "nio_p5_runner_replay.pointer.json"),
    )
    manifest = Path(initialized["manifest_path"])

    run_exit_code = run_campaign_worker(manifest, "run")
    if run_exit_code != 0:
        control = manifest.parent / ".siestaflow"
        state_path = control / "worker-state.json"
        worker_state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.is_file() else {}
        working_directory = Path(str(worker_state.get("active_working_directory", "")))
        tails = {
            name: (working_directory / name).read_text(encoding="utf-8", errors="replace").splitlines()[-40:]
            for name in ("siesta.err", "siesta.out")
            if (working_directory / name).is_file()
        }
        worker_error_path = control / "worker-error.json"
        worker_error = (
            json.loads(worker_error_path.read_text(encoding="utf-8")) if worker_error_path.is_file() else None
        )
        raise AssertionError(
            json.dumps(
                {
                    "run_exit_code": run_exit_code,
                    "campaign_status": campaign_status(manifest),
                    "worker_state": worker_state,
                    "worker_error": worker_error,
                    "active_output_tails": tails,
                },
                sort_keys=True,
            )
        )
    stopped = campaign_status(manifest)
    assert stopped["status"] == "STOPPED"
    assert len(stopped["completed_nodes"]) >= 13

    assert run_campaign_worker(manifest, "resume") == 0
    completed = campaign_status(manifest)
    assert completed["status"] == "COMPLETED"
    assert len(completed["completed_nodes"]) == 27

    actual_analysis = json.loads((manifest.parent / "results" / ANALYSIS).read_text(encoding="utf-8"))
    part_a_analysis = json.loads((REAL_FIXTURE / ANALYSIS).read_text(encoding="utf-8"))
    removed: dict[str, str] = {}
    actual_view = _comparison_view(actual_analysis, removed, "$")
    expected_view = _comparison_view(part_a_analysis, removed, "$")
    assert _report_precision_view(actual_view) == _report_precision_view(expected_view)
    assert _report_precision_view(actual_analysis["primary"]["U_by_site_eV"]) == _report_precision_view(
        part_a_analysis["primary"]["U_by_site_eV"]
    )
    actual_manifest = _campaign_file_manifest(manifest.parent)
    expected_manifest = json.loads(GOLDEN_MANIFEST.read_text(encoding="utf-8"))
    if actual_manifest != expected_manifest:
        differences = {
            path: {"actual": actual_manifest.get(path), "expected": expected_manifest.get(path)}
            for path in sorted(set(actual_manifest) | set(expected_manifest))
            if actual_manifest.get(path) != expected_manifest.get(path)
        }
        raise AssertionError(f"replay campaign manifest differs: {json.dumps(differences, sort_keys=True)}")


def _comparison_view(value: Any, removed: dict[str, str], path: str) -> Any:
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if key == "input_files" and isinstance(child, list):
                dynamic_input_paths = {
                    "backend_contract.json",
                    "execution_profile.json",
                    "lr_config.json",
                    "provenance/source_lr_config.json",
                }
                normalized_files = []
                for index, record in enumerate(child):
                    if not isinstance(record, dict):
                        normalized_files.append(record)
                        continue
                    file_record = dict(record)
                    if file_record.get("path") in dynamic_input_paths:
                        file_record.pop("sha256", None)
                    normalized_files.append(_comparison_view(file_record, removed, f"{child_path}[{index}]"))
                result[key] = normalized_files
                continue
            category: str | None = None
            if key in {"campaign_id", "input_identity"} or key == "name" and path.endswith(".campaign"):
                category = "campaign identity"
            elif key.endswith(("_epoch", "_utc")) or key in {"epoch", "timestamp"}:
                category = "timestamps"
            elif key in {"evidence_digest", "evidence_sha256", "report_sha256"}:
                category = "runtime binding: evidence digest"
            elif key in {"runtime_executable", "python_executable", "package_version"}:
                category = "runtime binding"
            elif key == "sha256" and any(
                field in child_path
                for field in (
                    ".lr_config.",
                    ".execution_profile.",
                    ".campaign_contract.",
                    "lr_config.json",
                    "execution_profile.json",
                    "backend_contract.json",
                )
            ):
                category = "path-bound or campaign-bound input hash"
            if category is not None:
                removed[child_path] = category
                continue
            result[key] = _comparison_view(child, removed, child_path)
        return result
    if isinstance(value, list):
        return [_comparison_view(child, removed, f"{path}[{index}]") for index, child in enumerate(value)]
    if isinstance(value, str):
        return _normalize_attempt_path(value)
    return value


def _campaign_file_manifest(root: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = _normalize_attempt_path(path.relative_to(root).as_posix())
        raw = path.read_bytes()
        try:
            value = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError):
            normalized = raw.replace(str(root.parent).encode(), b"$CAMPAIGN_ROOT")
            normalized = normalized.replace(str(ROOT).encode(), b"$REPOSITORY_ROOT")
            normalized = _ATTEMPT_BYTES.sub(b"attempt-NORMALIZED", normalized)
            normalized = _ATTEMPT_GROUP_BYTES.sub(b"ATTEMPT-GROUP", normalized)
            normalized = _ATTEMPT_SUFFIX_BYTES.sub(b"ATTEMPT-SUFFIX", normalized)
            if path.name == "LR_U_REPORT.v3.md":
                normalized = _DYNAMIC_INPUT_HASH_ROW.sub(rb"\1DYNAMIC_INPUT_HASH\2", normalized)
                normalized = _EVIDENCE_DIGEST_ROW.sub(rb"\1DYNAMIC_EVIDENCE_DIGEST\2", normalized)
                # The report repeats hashes for artifacts that are checked as
                # separate manifest entries; canonicalize their rendered copies.
                normalized = _SHA256_TOKEN.sub(b"SHA256", normalized)
        else:
            removed: dict[str, str] = {}
            comparable = _comparison_view(value, removed, "$")
            comparable = _normalize_campaign_root(comparable, str(root.parent))
            comparable = _normalize_campaign_root(comparable, str(ROOT))
            normalized = (json.dumps(comparable, sort_keys=True, separators=(",", ":")) + "\n").encode()
        result[relative] = hashlib.sha256(normalized).hexdigest()
    return result


def _normalize_attempt_path(value: str) -> str:
    value = _ATTEMPT.sub("attempt-NORMALIZED", value)
    value = _ATTEMPT_GROUP.sub("ATTEMPT-GROUP", value)
    return _ATTEMPT_SUFFIX.sub("ATTEMPT-SUFFIX", value)


def _normalize_campaign_root(value: Any, root: str) -> Any:
    if isinstance(value, dict):
        return {key: _normalize_campaign_root(child, root) for key, child in value.items()}
    if isinstance(value, list):
        return [_normalize_campaign_root(child, root) for child in value]
    if isinstance(value, str):
        return value.replace(root, "$CAMPAIGN_ROOT")
    return value


def _report_precision_view(value: Any) -> Any:
    """Compare replay numbers at the report renderer's nine-significant-digit precision."""
    if isinstance(value, float):
        return format(value, ".9g")
    if isinstance(value, dict):
        return {key: _report_precision_view(child) for key, child in value.items()}
    if isinstance(value, list):
        return [_report_precision_view(child) for child in value]
    return value
