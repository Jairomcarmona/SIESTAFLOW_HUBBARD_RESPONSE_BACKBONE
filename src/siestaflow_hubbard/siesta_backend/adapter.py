"""Retired compatibility surface for the former direct SIESTA adapter.

Production SIESTA execution is deliberately composed only by
``build_admitted_siesta542_runtime``. This module keeps the old import path
from silently becoming an execution bypass while callers migrate.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from shutil import copy2
from typing import List

from siestaflow_hubbard.domain.interfaces import BaseBackendAdapter


class LegacySiestaExecutionDisabledError(RuntimeError):
    """Raised by retired direct execution and evidence-extraction methods."""


def prepare_canonical_dm(
    reference_dm_path: str,
    child_dm_path: str,
    reference_sha256: str,
) -> str:
    """Copy a declared parent DM and verify its bytes.

    This is an integrity helper only. It does not authorize a calculation or
    create a scientific receipt.
    """
    source, destination = Path(reference_dm_path), Path(child_dm_path)
    copy2(source, destination)
    digest = sha256(destination.read_bytes()).hexdigest()
    if digest != reference_sha256:
        raise RuntimeError("Parent DM identity mismatch after copy")
    return digest


class SiestaLRAdapter(BaseBackendAdapter):
    """Deprecated non-production adapter retained solely for clear failures."""

    def __init__(self, *args: object, **kwargs: object):
        # Do not retain a default executable path: accepting one would imply a
        # deployment choice outside the admission route.
        del args, kwargs

    @staticmethod
    def _disabled() -> None:
        raise LegacySiestaExecutionDisabledError(
            "direct SIESTA execution and occupation extraction are disabled; "
            "use build_admitted_siesta542_runtime"
        )

    def prepare_input(self, fdf_template: str, alpha: float, mode: str) -> str:
        del fdf_template, alpha, mode
        self._disabled()

    def run_simulation(self, fdf_filename: str, out_filename: str, n_procs: int) -> None:
        del fdf_filename, out_filename, n_procs
        self._disabled()

    def extract_occupations(self, out_filename: str, *args: object, **kwargs: object) -> List[float]:
        del out_filename, args, kwargs
        self._disabled()

    # These names previously constructed shell commands or selected outputs.
    # Keep explicit fail-closed methods so existing callers cannot fall back to
    # scheduler/PATH discovery during migration.
    def run_siesta_mpi_local(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        self._disabled()

    def run_siesta_wsl(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        self._disabled()

    def run_siesta_slurm(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        self._disabled()

    def parse_converged_hubbard_occupations(self, *args: object, **kwargs: object) -> List[float]:
        del args, kwargs
        self._disabled()
