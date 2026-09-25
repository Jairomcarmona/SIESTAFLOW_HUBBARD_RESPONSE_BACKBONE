#!/usr/bin/env python3
"""Create a disposable, fail-closed local LR-U smoke campaign.

This helper is deliberately *not* a production launcher.  It is intended for
one-machine integration checks of the scientific gates before a campaign is
submitted to an HPC scheduler.  It materializes the mandatory centred
seven-point grid and, optionally, runs only the supplied reference FDF.

No response calculation is authorised by this tool: a SIESTA-version-specific
adapter must first provide positive evidence for the BARE electronic-state
semantics.  Treating a successful executable invocation or a copied DM as
that evidence would make the LR result scientifically ambiguous.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path
import shutil
import shlex
import subprocess
import sys
from typing import Iterable

from siestaflow_hubbard.domain.alpha_selection import AlphaSelectionPolicy, select_common_alpha_window
from siestaflow_hubbard.siesta_backend.fdf_builder import LegacyBareMaterializationDisabledError


GRID_FACTORS = (-2.0, -1.0, -0.5, 0.0, 0.5, 1.0, 2.0)


def sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def centred_alphas(step_ev: float) -> tuple[float, ...]:
    if step_ev <= 0.0:
        raise ValueError("alpha step must be positive")
    return tuple(step_ev * factor for factor in GRID_FACTORS)


def materialize_response_plan(
    source_fdf: Path,
    workdir: Path,
    *,
    alpha_step_ev: float,
    species: str,
    n: int,
    l: int,
    rc_bohr: float,
    omega: float,
) -> list[dict[str, object]]:
    """Reject legacy BARE/SCREENED plan materialization outside admission."""

    del source_fdf, workdir, alpha_step_ev, species, n, l, rc_bohr, omega
    raise LegacyBareMaterializationDisabledError(
        "local response-plan materialization is disabled; use an admitted SIESTA runtime"
    )


def alpha_gate_self_check(alpha_step_ev: float) -> dict[str, object]:
    """Exercise the analysis gate with explicitly synthetic, linear data.

    The result proves only the analysis contract, never a physical response.
    """

    alphas = centred_alphas(alpha_step_ev)
    occupations = [[4.0 - 0.20 * alpha, 4.0 - 0.10 * alpha] for alpha in alphas]
    moments = [[[0.0, 0.0, 0.0]] for _ in alphas]
    return select_common_alpha_window(
        alphas, occupations, moments, alpha_step_ev,
        AlphaSelectionPolicy(occupation_noise=1e-7),
    )


def run_reference(
    reference_fdf: Path,
    reference_dm: Path | None,
    workdir: Path,
    pseudos: Iterable[Path],
    command: list[str],
) -> dict[str, object]:
    """Run a supplied reference in a new directory and record only technical facts."""

    reference_dir = workdir / "reference"
    reference_dir.mkdir()
    staged_fdf = reference_dir / "siesta.fdf"
    shutil.copy2(reference_fdf, staged_fdf)
    if reference_dm is not None:
        shutil.copy2(reference_dm, reference_dir / reference_dm.name)
    for pseudo in pseudos:
        shutil.copy2(pseudo, reference_dir / pseudo.name)
    completed = subprocess.run(command, cwd=reference_dir, input=staged_fdf.read_bytes(), capture_output=True)
    # Some SIESTA builds honour SystemLabel and write their native transcript
    # beside the FDF rather than to stdout.  Preserve it under a stable smoke
    # name without discarding captured MPI diagnostics.
    native_outputs = sorted(
        path for path in reference_dir.glob("*.out") if path.name != "siesta.out"
    )
    native_output = native_outputs[0].read_bytes() if native_outputs else b""
    (reference_dir / "siesta.out").write_bytes(native_output + completed.stdout)
    (reference_dir / "siesta.err").write_bytes(completed.stderr)
    # Version 5.4.2 closes a normal transcript with ``>> End of run``;
    # other supported SIESTA builds commonly use ``normal completion``.
    # This is a technical terminal marker only, never SCF/BARE semantics.
    transcript = (native_output + completed.stdout).lower()
    normal = b"normal completion" in transcript or b">> end of run" in transcript
    return {
        "return_code": completed.returncode,
        "normal_completion_text": normal,
        "output_sha256": sha256_file(reference_dir / "siesta.out"),
        "error_sha256": sha256_file(reference_dir / "siesta.err"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-fdf", type=Path, required=True)
    parser.add_argument("--reference-dm", type=Path)
    parser.add_argument("--pseudo", type=Path, action="append", default=[])
    parser.add_argument("--workdir", type=Path, required=True)
    parser.add_argument("--alpha-step-ev", type=float, default=0.05)
    parser.add_argument("--species", default="Mn")
    parser.add_argument("--n", type=int, default=3)
    parser.add_argument("--l", type=int, default=2)
    parser.add_argument("--rc-bohr", type=float, default=3.0)
    parser.add_argument("--omega", type=float, default=0.05)
    parser.add_argument(
        "--run-reference", metavar="CMD",
        help="quoted executable command, e.g. 'mpirun -np 4 /path/to/siesta'",
    )
    args = parser.parse_args()

    if args.workdir.exists():
        raise SystemExit("refusing to reuse an existing --workdir")
    if (
        not args.reference_fdf.is_file()
        or (args.reference_dm is not None and not args.reference_dm.is_file())
        or any(not pseudo.is_file() for pseudo in args.pseudo)
    ):
        raise SystemExit("reference FDF or pseudopotential does not exist")

    args.workdir.mkdir(parents=True)
    response_records = materialize_response_plan(
        args.reference_fdf, args.workdir, alpha_step_ev=args.alpha_step_ev,
        species=args.species, n=args.n, l=args.l, rc_bohr=args.rc_bohr, omega=args.omega,
    )
    report: dict[str, object] = {
        "status": "PASS_FAIL_CLOSED",
        "scope": "local_smoke_only",
        "reference_fdf_sha256": sha256_file(args.reference_fdf),
        "pseudopotentials": {pseudo.name: sha256_file(pseudo) for pseudo in sorted(args.pseudo)},
        "response_plan": response_records,
        "alpha_analysis_self_check": alpha_gate_self_check(args.alpha_step_ev),
        "response_launch_authorized": False,
        "response_launch_blocker": "bare_semantics_evidence_adapter_not_configured",
        "scientific_result": None,
    }
    if args.run_reference:
        report["reference_execution"] = run_reference(
            args.reference_fdf, args.reference_dm, args.workdir, args.pseudo, shlex.split(args.run_reference),
        )

    report_path = args.workdir / "local_lr_gate_smoke.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(report_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
