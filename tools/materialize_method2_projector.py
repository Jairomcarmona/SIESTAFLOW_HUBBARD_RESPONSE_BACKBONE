"""Materialize complete SIESTA Method-2 ``.dftu_proj`` files without SCF."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import signal
import subprocess
import tempfile
import time
from pathlib import Path

from audit_method2_projector import parse_projector
from psml_selection import parse_fdf_species, resolve_explicit_psmls, select_psml_sources
from verify_method2_projector_identity import fdf_sha256, projector_configuration_fingerprint, projector_specs


def parse_mapping(text: str) -> tuple[str, Path]:
    try:
        label, source = text.split("=", 1)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("pseudo mapping must be LABEL=PATH") from exc
    source_path = Path(source)
    if not source_path.is_file():
        raise argparse.ArgumentTypeError(f"pseudopotential does not exist: {source_path}")
    return label, source_path


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _profile_is_complete(path: Path, expected_n: int, expected_l: int) -> None:
    l_value, n_value, _, _, _ = parse_projector(path)
    # SIESTA writes n as the projector sequence number in the profile header;
    # its FDF principal quantum number is part of the config fingerprint.
    if l_value != expected_l:
        raise ValueError(
            f"{path}: generated projector quantum numbers (n={n_value}, l={l_value}) "
            f"do not match the expected FDF angular momentum l={expected_l}"
        )


def _atomic_manifest(path: Path, data: dict) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fdf", type=Path, required=True)
    parser.add_argument("--central-label", required=True)
    pseudo_group = parser.add_mutually_exclusive_group(required=True)
    pseudo_group.add_argument("--pseudo", type=parse_mapping, action="append", help="Repeat LABEL=source.psml for every FDF species label")
    pseudo_group.add_argument("--pseudo-source", type=Path, action="append", help="PSML source candidates; exact labels are preferred")
    parser.add_argument("--siesta", type=Path, required=True)
    parser.add_argument("--mpi-launcher", default="mpiexec")
    parser.add_argument("--ranks", type=int, default=1)
    parser.add_argument("--timeout-seconds", type=int, default=90)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if not args.fdf.is_file() or not args.siesta.is_file():
        raise SystemExit("FDF or SIESTA executable does not exist")
    if args.ranks < 1 or args.timeout_seconds < 1:
        raise SystemExit("ranks and timeout-seconds must be positive")
    try:
        fdf_text = args.fdf.read_text(encoding="utf-8")
        species = parse_fdf_species(fdf_text, str(args.fdf))
        specs = projector_specs(args.fdf)
        if args.central_label not in specs:
            raise ValueError(f"central label {args.central_label} has no effective DFTU.Proj entry")
        if args.pseudo is not None:
            mappings = resolve_explicit_psmls(species, args.pseudo)
        else:
            mappings = select_psml_sources(species, list(args.pseudo_source or []))
    except (OSError, ValueError) as exc:
        raise SystemExit(f"unsupported/ambiguous Method-2 preflight input: {exc}") from exc

    args.output_dir.mkdir(parents=True, exist_ok=True)
    manifest: dict = {
        "schema_version": 2,
        "status": "PROJECTOR_NOT_MATERIALIZED",
        "projector": f"{args.central_label}.dftu_proj",
        "projected_labels": sorted(specs),
        "projector_files": [f"{label}.dftu_proj" for label in sorted(specs)],
        "fdf_sha256": fdf_sha256(args.fdf),
        "projector_configuration_sha256": projector_configuration_fingerprint(args.fdf),
        "pseudopotential_sha256": {label: _sha256(path) for label, path in sorted(mappings.items())},
        "files": [],
    }

    with tempfile.TemporaryDirectory(prefix="siestaflow-method2-") as temporary:
        workdir = Path(temporary)
        shutil.copy2(args.fdf, workdir / "siesta.fdf")
        for label, source in mappings.items():
            shutil.copy2(source, workdir / f"{label}.psml")

        command = [args.mpi_launcher, "-n", str(args.ranks), str(args.siesta)]
        stdout_path, stderr_path = workdir / "siesta.out", workdir / "siesta.err"
        with (workdir / "siesta.fdf").open("rb") as stdin, stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
            process = subprocess.Popen(command, cwd=workdir, stdin=stdin, stdout=stdout, stderr=stderr, start_new_session=True)
            deadline = time.monotonic() + args.timeout_seconds
            previous: dict[str, tuple[int, int, str]] = {}
            stable_counts = {label: 0 for label in specs}
            materialized = False
            while time.monotonic() < deadline:
                all_stable = True
                for label, spec in specs.items():
                    profile_path = workdir / f"{label}.dftu_proj"
                    if not profile_path.is_file() or profile_path.stat().st_size <= 0:
                        all_stable = False
                        continue
                    stat = profile_path.stat()
                    signature = (stat.st_size, stat.st_mtime_ns, _sha256(profile_path))
                    if signature == previous.get(label):
                        stable_counts[label] += 1
                    else:
                        previous[label] = signature
                        stable_counts[label] = 0
                    if stable_counts[label] < 2:
                        all_stable = False
                        continue
                    try:
                        _profile_is_complete(profile_path, spec["n"], spec["l"])
                    except (ValueError, OSError):
                        all_stable = False
                if all_stable:
                    materialized = True
                    break
                if process.poll() is not None and all((workdir / f"{label}.dftu_proj").is_file() for label in specs):
                    # SIESTA has stopped writing; malformed or incomplete files
                    # cannot become valid later in this work directory.
                    break
                time.sleep(0.5)
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()

        copied: list[str] = []
        if materialized:
            for label in sorted(specs):
                names = [f"{label}.dftu_proj", f"{label}.ion", f"{label}.ion.xml"]
                for name in names:
                    source = workdir / name
                    if source.is_file():
                        shutil.copy2(source, args.output_dir / name)
                        copied.append(name)
        for name in ("siesta.out", "siesta.err"):
            source = workdir / name
            if source.is_file():
                shutil.copy2(source, args.output_dir / name)
                copied.append(name)

    manifest["status"] = "PROJECTOR_MATERIALIZED_ONLY" if materialized else "PROJECTOR_NOT_MATERIALIZED"
    manifest["files"] = copied
    _atomic_manifest(args.output_dir / "materialization.json", manifest)
    print(json.dumps(manifest, indent=2, sort_keys=True))
    if not materialized:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
