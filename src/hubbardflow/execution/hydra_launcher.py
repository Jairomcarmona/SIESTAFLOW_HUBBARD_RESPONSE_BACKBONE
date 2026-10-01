"""Safe construction of site-declared MPI commands; does not execute them."""
from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from .execution_profile import HydraLauncher, ProfileValidationError


@dataclass(frozen=True)
class HydraLaunch:
    argv: tuple[str, ...]
    uuid: str


def build_hydra_launch(launcher: HydraLauncher, hosts: list[str], ranks: int, executable: str, arguments: list[str] | None = None) -> HydraLaunch:
    if launcher.kind != "hydra":
        raise ProfileValidationError("Hydra command construction requires launcher kind 'hydra'")
    if not hosts or len(set(hosts)) != len(hosts):
        raise ProfileValidationError("Hydra requires unique resolved hosts")
    if ranks != len(hosts) * launcher.processes_per_node:
        raise ProfileValidationError("ranks must equal host count × processes_per_node")
    if ranks <= 0 or not executable:
        raise ProfileValidationError("invalid Hydra ranks or executable")
    run_uuid = str(uuid4())
    argv = (*launcher.command, "-bootstrap", launcher.bootstrap, "-hosts", ",".join(hosts), "-np", str(ranks), "-ppn", str(launcher.processes_per_node), "-genv", "FI_PSM3_UUID", run_uuid, executable, *(arguments or []))
    return HydraLaunch(argv, run_uuid)


def build_mpi_launch(launcher: HydraLauncher, hosts: list[str], ranks: int, executable: str, arguments: list[str] | None = None) -> HydraLaunch:
    """Build an argv vector for an explicitly selected MPI implementation."""
    if launcher.kind == "hydra":
        return build_hydra_launch(launcher, hosts, ranks, executable, arguments)
    if launcher.kind != "openmpi":
        raise ProfileValidationError("unsupported MPI launcher kind")
    if not hosts or len(set(hosts)) != len(hosts):
        raise ProfileValidationError("Open MPI requires unique resolved hosts")
    if ranks != len(hosts) * launcher.processes_per_node:
        raise ProfileValidationError("ranks must equal host count × processes_per_node")
    if ranks <= 0 or not executable:
        raise ProfileValidationError("invalid Open MPI ranks or executable")
    run_uuid = str(uuid4())
    slotted_hosts = ",".join(
        f"{host}:{launcher.processes_per_node}" for host in hosts
    )
    argv = (
        *launcher.command,
        "--host", slotted_hosts,
        "--map-by", f"ppr:{launcher.processes_per_node}:node",
        "-np", str(ranks),
        executable,
        *(arguments or []),
    )
    return HydraLaunch(argv, run_uuid)
