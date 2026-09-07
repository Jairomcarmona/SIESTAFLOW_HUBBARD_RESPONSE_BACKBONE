"""Materialize a SIESTA Method-2 ``.dftu_proj`` without completing SCF.

Run this only on a machine where the selected SIESTA executable and MPI stack
are configured.  It works in a fresh temporary directory and copies only the
projector and ion files requested for the subsequent audit.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import subprocess
import tempfile
import time
import xml.etree.ElementTree as ET
from pathlib import Path


def parse_mapping(text: str) -> tuple[str, Path]:
    try:
        label, source = text.split("=", 1)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("pseudo mapping must be LABEL=PATH") from exc
    source_path = Path(source)
    if not source_path.is_file():
        raise argparse.ArgumentTypeError(f"pseudopotential does not exist: {source_path}")
    return label, source_path


def atomic_number_from_psml(path: Path) -> int:
    root = ET.parse(path).getroot()
    atom = next((node for node in root.iter() if node.tag.rsplit("}", 1)[-1] == "pseudo-atom-spec"), None)
    if atom is None or atom.get("atomic-number") is None:
        raise ValueError(f"cannot read atomic number from {path}")
    return int(atom.get("atomic-number"))


def fdf_species(path: Path) -> dict[str, int]:
    import re
    text = path.read_text(encoding="utf-8")
    match = re.search(r"%block\s+ChemicalSpeciesLabel\s*(.*?)%endblock\s+ChemicalSpeciesLabel", text, re.I | re.S)
    if not match:
        raise ValueError("missing ChemicalSpeciesLabel block")
    return {line.split()[2]: int(line.split()[1]) for line in match.group(1).splitlines() if line.split() and not line.lstrip().startswith("#")}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fdf", type=Path, required=True)
    parser.add_argument("--central-label", required=True)
    parser.add_argument("--pseudo", type=parse_mapping, action="append", help="Repeat LABEL=source.psml for every FDF species label")
    parser.add_argument("--pseudo-source", type=Path, action="append", help="PSML source; aliases are inferred by matching its atomic number to FDF species")
    parser.add_argument("--siesta", type=Path, required=True)
    parser.add_argument("--mpi-launcher", default="mpiexec")
    parser.add_argument("--ranks", type=int, default=1)
    parser.add_argument("--timeout-seconds", type=int, default=90)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if not args.fdf.is_file() or not args.siesta.is_file():
        raise SystemExit("FDF or SIESTA executable does not exist")
    if not args.pseudo and not args.pseudo_source:
        raise SystemExit("provide --pseudo LABEL=PATH or one or more --pseudo-source PATH")
    if args.ranks < 1:
        raise SystemExit("--ranks must be positive")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    projector_name = f"{args.central_label}.dftu_proj"
    mappings = list(args.pseudo or [])
    if args.pseudo_source:
        sources = {atomic_number_from_psml(path): path for path in args.pseudo_source}
        for label, atomic_number in fdf_species(args.fdf).items():
            if atomic_number not in sources:
                raise SystemExit(f"no --pseudo-source with atomic number {atomic_number} for FDF label {label}")
            mappings.append((label, sources[atomic_number]))
    with tempfile.TemporaryDirectory(prefix="siestaflow-method2-") as temporary:
        workdir = Path(temporary)
        shutil.copy2(args.fdf, workdir / "siesta.fdf")
        for label, source in mappings:
            shutil.copy2(source, workdir / f"{label}.psml")
        command = [args.mpi_launcher, "-n", str(args.ranks), str(args.siesta)]
        with (workdir / "siesta.fdf").open("rb") as stdin, (workdir / "siesta.out").open("wb") as stdout, (workdir / "siesta.err").open("wb") as stderr:
            process = subprocess.Popen(command, cwd=workdir, stdin=stdin, stdout=stdout, stderr=stderr, start_new_session=True)
            deadline = time.monotonic() + args.timeout_seconds
            while time.monotonic() < deadline and not (workdir / projector_name).is_file():
                if process.poll() is not None:
                    break
                time.sleep(0.5)
            materialized = (workdir / projector_name).is_file()
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
        copied = []
        for name in (projector_name, f"{args.central_label}.ion", f"{args.central_label}.ion.xml", "siesta.out", "siesta.err"):
            source = workdir / name
            if source.is_file():
                shutil.copy2(source, args.output_dir / name)
                copied.append(name)
    status = {"status": "PROJECTOR_MATERIALIZED_ONLY" if materialized else "PROJECTOR_NOT_MATERIALIZED", "projector": projector_name, "files": copied}
    (args.output_dir / "materialization.json").write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(status, indent=2))
    if not materialized:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
