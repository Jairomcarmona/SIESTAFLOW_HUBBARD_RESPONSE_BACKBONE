import pytest

from siestaflow_hubbard.siesta_backend.adapter import (
    LegacySiestaExecutionDisabledError,
    SiestaLRAdapter,
)


@pytest.mark.parametrize(
    ("method", "args"),
    [
        ("prepare_input", ("reference.fdf", 0.05, "BARE")),
        ("run_simulation", ("input.fdf", "output.out", 4)),
        ("run_siesta_mpi_local", ("input.fdf", "output.out", ".", 4, 1)),
        ("run_siesta_wsl", ("input.fdf", "output.out", ".")),
        ("run_siesta_slurm", ("input.fdf", "output.out")),
        ("extract_occupations", ("output.out", "BARE", 0.05)),
        ("parse_converged_hubbard_occupations", ("native output",)),
    ],
)
def test_retired_adapter_entries_fail_before_launch_or_extraction(method, args):
    with pytest.raises(LegacySiestaExecutionDisabledError):
        getattr(SiestaLRAdapter(), method)(*args)
