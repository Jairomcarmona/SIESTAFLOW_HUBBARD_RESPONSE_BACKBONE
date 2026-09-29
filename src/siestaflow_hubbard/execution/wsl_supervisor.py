"""PowerShell-to-WSL control and durable detached-worker supervision.

The supervisor persists independently of the PowerShell process. WSL shutdown
or a Windows reboot can stop it; the campaign checkpoint remains available to
``resume``. Every process signal is guarded by PID, Linux start ticks and argv.
"""
from __future__ import annotations

import json
import os
from pathlib import Path, PurePosixPath
import signal
import subprocess
import sys
import time
from typing import Any, Mapping, Sequence


class WslSupervisorError(RuntimeError):
    """The WSL campaign supervisor could not safely complete an operation."""


def _wsl_argv(distribution: str, argv: Sequence[str]) -> list[str]:
    return ["wsl.exe", "--distribution", distribution, "--exec", *argv]


def wsl_command(distribution: str, argv: Sequence[str], *, input_text: str | None = None) -> str:
    try:
        completed = subprocess.run(
            _wsl_argv(distribution, argv), input=input_text, capture_output=True,
            text=True, encoding="utf-8", errors="replace", check=False, shell=False,
        )
    except OSError as exc:
        raise WslSupervisorError(f"cannot start WSL: {exc}") from exc
    if completed.returncode:
        detail = (completed.stderr or completed.stdout).strip()
        raise WslSupervisorError(detail or f"WSL command failed with exit code {completed.returncode}")
    return completed.stdout.strip()


def windows_to_wsl_path(distribution: str, path: str | Path) -> str:
    converted = wsl_command(distribution, ["wslpath", "-u", str(Path(path).resolve())])
    if not converted.startswith("/"):
        raise WslSupervisorError(f"wslpath returned a non-absolute path: {converted!r}")
    return converted


def write_wsl_text(distribution: str, python_executable: str, target: str, text: str) -> None:
    script = (
        "import pathlib,sys; p=pathlib.Path(sys.argv[1]); "
        "p.parent.mkdir(parents=True,exist_ok=True); "
        "p.write_text(sys.stdin.read(),encoding='utf-8')"
    )
    wsl_command(distribution, [python_executable, "-c", script, target], input_text=text)


def copy_to_wsl(distribution: str, source: str | Path, target: str) -> None:
    source_wsl = windows_to_wsl_path(distribution, source)
    parent = str(PurePosixPath(target).parent)
    wsl_command(distribution, ["mkdir", "-p", parent])
    wsl_command(distribution, ["cp", "--", source_wsl, target])


def start_worker(*, distribution: str, python_executable: str, manifest_path: str, mode: str) -> dict[str, Any]:
    if mode not in {"run", "resume"}:
        raise WslSupervisorError("worker mode must be run or resume")
    raw = wsl_command(distribution, [
        python_executable, "-m", "siestaflow_hubbard.cli", "_daemon-launch", manifest_path, mode,
    ])
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise WslSupervisorError("WSL worker launcher returned invalid status data") from exc
    if not isinstance(value, dict) or not value.get("pid"):
        raise WslSupervisorError("WSL worker launcher did not return a process ID")
    return value


def read_worker_status(*, distribution: str, python_executable: str, manifest_path: str) -> dict[str, Any]:
    raw = wsl_command(distribution, [python_executable, "-m", "siestaflow_hubbard.cli", "_status", manifest_path])
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise WslSupervisorError("WSL status command returned invalid JSON") from exc
    if not isinstance(value, dict):
        raise WslSupervisorError("WSL status command returned an invalid object")
    return value


def stop_worker(*, distribution: str, python_executable: str, manifest_path: str) -> dict[str, Any]:
    raw = wsl_command(distribution, [python_executable, "-m", "siestaflow_hubbard.cli", "_stop", manifest_path])
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise WslSupervisorError("WSL stop command returned invalid JSON") from exc
    if not isinstance(value, dict):
        raise WslSupervisorError("WSL stop command returned an invalid object")
    return value


def _pid_start_time(pid: int) -> str | None:
    try:
        stat = Path(f"/proc/{pid}/stat").read_text(encoding="ascii")
        fields = stat[stat.rfind(")") + 2:].split()
        return fields[19]
    except (OSError, IndexError):
        return None


def _pid_matches_campaign(record: Mapping[str, Any], manifest_path: str) -> bool:
    pid = record.get("pid")
    if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 1:
        return False
    if _pid_start_time(pid) != str(record.get("start_time_ticks", "")):
        return False
    try:
        argv = Path(f"/proc/{pid}/cmdline").read_bytes().decode("utf-8", errors="replace").split("\0")
    except OSError:
        return False
    return "siestaflow_hubbard.cli" in argv and "_worker" in argv and str(Path(manifest_path)) in argv


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def daemon_launch(manifest_path: str, mode: str) -> dict[str, Any]:
    """Start one detached worker and return as soon as its identity is stored."""
    import fcntl
    if mode not in {"run", "resume"}:
        raise WslSupervisorError("worker mode must be run or resume")
    manifest = Path(manifest_path).resolve(strict=True)
    root, control = manifest.parent, manifest.parent / ".siestaflow"
    control.mkdir(parents=True, exist_ok=True)
    with (control / "launch.lock").open("a+b") as launch_lock:
        try:
            fcntl.flock(launch_lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise WslSupervisorError("a campaign start/resume request is already being processed") from exc
        record_path = control / "supervisor.json"
        try:
            prior = json.loads(record_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            prior = {}
        if isinstance(prior, dict) and _pid_matches_campaign(prior, str(manifest)):
            raise WslSupervisorError(f"campaign worker is already running with PID {prior['pid']}")

        log_path = control / "worker.log"
        command = [sys.executable, "-m", "siestaflow_hubbard.cli", "_worker", str(manifest), mode]
        child: subprocess.Popen[bytes] | None = None
        with log_path.open("ab", buffering=0) as log:
            try:
                child = subprocess.Popen(
                    command, cwd=root, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                    close_fds=True, shell=False, start_new_session=True,
                )
            except OSError as exc:
                raise WslSupervisorError(f"cannot start detached campaign worker: {exc}") from exc
            try:
                deadline = time.monotonic() + 3.0
                start_ticks: str | None = None
                while time.monotonic() < deadline:
                    start_ticks = _pid_start_time(child.pid)
                    if start_ticks is not None:
                        break
                    if child.poll() is not None:
                        break
                    time.sleep(0.05)
                if start_ticks is None:
                    raise WslSupervisorError("worker started but its Linux process identity cannot be verified")
                _atomic_json(record_path, {
                    "pid": child.pid, "start_time_ticks": start_ticks,
                    "manifest_path": str(manifest), "mode": mode, "process_group": child.pid,
                })
            except Exception:
                # Never leave an unregistered process behind if persistence fails.
                try:
                    os.killpg(child.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                try:
                    child.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    try:
                        os.killpg(child.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    child.wait(timeout=2)
                raise
        return {"pid": child.pid, "mode": mode, "state": "STARTING", "log": str(log_path)}


def daemon_status(manifest_path: str) -> dict[str, Any]:
    manifest = Path(manifest_path).resolve(strict=True)
    control = manifest.parent / ".siestaflow"
    try:
        state = json.loads((control / "worker-state.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        state = {"status": "NOT_STARTED"}
    try:
        record = json.loads((control / "supervisor.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        record = {}
    try:
        adaptive = json.loads((control / "adaptive-alpha-state.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        adaptive = None

    def add_adaptive(payload: dict[str, Any]) -> dict[str, Any]:
        if isinstance(adaptive, dict):
            rounds = adaptive.get("rounds", [])
            current = rounds[-1] if isinstance(rounds, list) and rounds else {}
            decisions = adaptive.get("decisions", [])
            payload["adaptive_alpha"] = {
                "campaign_status": adaptive.get("campaign_status"),
                "candidate_status": adaptive.get("candidate_status"),
                "current_round": current.get("round_index") if isinstance(current, dict) else None,
                "round_status": current.get("status") if isinstance(current, dict) else None,
                "refinement_decision": decisions[-1] if isinstance(decisions, list) and decisions else None,
                "budget": adaptive.get("budget"),
            }
        return payload
    if isinstance(record, dict) and _pid_matches_campaign(record, str(manifest)):
        worker_state = state.get("status", "STARTING") if isinstance(state, dict) else "STARTING"
        terminal = {"COMPLETED", "FAILED", "INTERRUPTED"}
        status = worker_state if worker_state in {"RUNNING", "STOP_REQUESTED", *terminal} else "RUNNING"
        heartbeat = state.get("heartbeat_epoch") if isinstance(state, dict) else None
        interval = state.get("heartbeat_interval_seconds", 15) if isinstance(state, dict) else 15
        if status == "RUNNING" and isinstance(heartbeat, (int, float)):
            if time.time() - heartbeat > max(45.0, float(interval) * 3.0):
                status = "STALE_HEARTBEAT"
        return add_adaptive({**state, "status": status, "pid": record["pid"], "log": str(control / "worker.log")})
    if isinstance(state, dict) and state.get("status") in {"RUNNING", "STOP_REQUESTED"}:
        return add_adaptive({**state, "status": "INTERRUPTED", "pid": None, "log": str(control / "worker.log")})
    return add_adaptive({**state, "pid": None, "log": str(control / "worker.log")})


def daemon_stop(manifest_path: str) -> dict[str, Any]:
    manifest = Path(manifest_path).resolve(strict=True)
    control = manifest.parent / ".siestaflow"
    record_path, state_path = control / "supervisor.json", control / "worker-state.json"
    try:
        record = json.loads(record_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise WslSupervisorError("campaign has no readable supervisor record") from exc
    if not isinstance(record, dict) or not _pid_matches_campaign(record, str(manifest)):
        return {"status": "NOT_RUNNING", "pid": None}
    state = {}
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        pass
    if isinstance(state, dict):
        state.update({"status": "STOP_REQUESTED", "stop_requested_epoch": time.time()})
        _atomic_json(state_path, state)
    pid = int(record["pid"])
    try:
        os.killpg(pid, signal.SIGTERM)
    except ProcessLookupError:
        return {"status": "NOT_RUNNING", "pid": None}
    return {"status": "STOP_REQUESTED", "pid": pid}


__all__ = [
    "WslSupervisorError", "copy_to_wsl", "read_worker_status", "start_worker", "stop_worker",
    "windows_to_wsl_path", "write_wsl_text", "wsl_command", "daemon_launch", "daemon_status", "daemon_stop",
]
