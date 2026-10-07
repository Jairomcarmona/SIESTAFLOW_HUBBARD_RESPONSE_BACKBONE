"""Linux/Slurm and PowerShell/WSL command line for v2 LR-U campaigns."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import re
import sys
from typing import Any

from hubbardflow.execution.campaign_v2 import POINTER_SCHEMA
from hubbardflow.execution.execution_profile import ExecutionProfile
from hubbardflow.execution.wsl_supervisor import (
    WslSupervisorError, daemon_launch, daemon_status, daemon_stop,
    read_worker_status, start_worker, stop_worker, windows_to_wsl_path, wsl_command,
)


def audit_fdf(args: argparse.Namespace) -> None:
    """Preserve the existing read-only FDF audit command."""
    from hubbardflow.siesta_backend.fdf_validator import FdfParser, FdfValidator

    fdf_path = Path(args.fdf_file)
    content = fdf_path.read_text(encoding="utf-8")
    parser = FdfParser(content)
    validator = FdfValidator(parser)
    lattice_value = parser.get_value("LatticeConstant")
    lattice_constant = None
    if lattice_value is not None:
        lattice_line = re.search(r"(?im)^\s*LatticeConstant\b\s+([^#\r\n]+)", content)
        lattice_text = lattice_value if lattice_line is None else lattice_line.group(1).strip()
        lattice_fields = lattice_text.split()
        if len(lattice_fields) > 2 or (len(lattice_fields) == 2 and lattice_fields[1].casefold() not in {"ang", "bohr", "nm"}):
            raise ValueError(f"unsupported LatticeConstant unit: {lattice_text!r}")
        try:
            numeric_lattice_value = float(lattice_fields[0].replace("D", "E").replace("d", "e"))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"invalid LatticeConstant value: {lattice_text!r}") from exc
        if not math.isfinite(numeric_lattice_value) or numeric_lattice_value <= 0:
            raise ValueError("LatticeConstant must be positive")
        unit = "ang" if len(lattice_fields) == 1 else lattice_fields[1].casefold()
        unit_scale_to_angstrom = {"ang": 1.0, "bohr": 0.529177, "nm": 10.0}
        # Pass a normalized numeric scalar through the validator API, then
        # apply the declared unit. This also handles Fortran D exponents.
        lattice_constant = validator.check_unit(str(numeric_lattice_value)) * unit_scale_to_angstrom[unit]
        if not math.isfinite(lattice_constant) or lattice_constant <= 0:
            raise ValueError("LatticeConstant could not be normalized to a positive finite value")

    spin_directive = parser.get_value("Spin")
    if spin_directive is None:
        spin_mode = validator.detect_spin_mode()
    else:
        normalized_spin = spin_directive.strip().casefold().replace("_", "-")
        spin_modes = {
            "polarized": "spin-polarized", "spin-polarized": "spin-polarized",
            "collinear": "spin-polarized", "non-polarized": "non-polarized",
            "nonpolarized": "non-polarized", "unpolarized": "non-polarized",
            "non-collinear": "non-collinear", "noncollinear": "non-collinear",
            "spin-orbit": "spin-orbit", "spinorbit": "spin-orbit",
        }
        try:
            spin_mode = spin_modes[normalized_spin]
        except KeyError as exc:
            raise ValueError(f"unsupported Spin directive: {spin_directive!r}") from exc

    if not validator.validate_multi_species():
        raise ValueError("ChemicalSpeciesLabel block is missing or empty")
    projector_block = parser.get_block("DFTU.Proj")
    projector_l_values: set[int] = set()
    for line in projector_block:
        fields = line.split("#", 1)[0].split()
        if len(fields) != 2:
            continue
        try:
            principal_n, angular_l = (int(field) for field in fields)
        except ValueError:
            continue
        if principal_n > angular_l >= 0:
            projector_l_values.add(angular_l)
    if projector_block and not projector_l_values:
        raise ValueError("DFTU.Proj is present but no principal/angular momentum pair could be read")
    orbital_dimensions = {
        angular_l: validator.detect_orbital_dimension(angular_l)
        for angular_l in sorted(projector_l_values)
    }
    orbital_dimension = next(iter(orbital_dimensions.values())) if len(orbital_dimensions) == 1 else None
    xc_functional = parser.get_value("XC.Functional")
    xc_authors = parser.get_value("XC.Authors")
    parsed_fields = sum(
        1 for line in parser.lines
        if line.strip() and not line.lstrip().startswith(("#", "%"))
    )
    print(json.dumps({
        "fdf_file": str(fdf_path.resolve()),
        "spin_mode": spin_mode,
        "xc_functional": xc_functional,
        "xc_authors": xc_authors,
        "lattice_constant": lattice_constant,
        "lattice_constant_units": "Ang",
        "dftu_projector_block": bool(projector_block),
        "dftu_projector_l_values": sorted(projector_l_values),
        "orbital_dimension": orbital_dimension,
        "orbital_dimensions_by_l": orbital_dimensions,
        "orbital_dimension_status": "inferred" if orbital_dimension is not None else "unknown",
        "parsed_fields": parsed_fields,
        "validation": "passed",
    }, indent=2, sort_keys=True))


def _read_pointer(path: str | Path) -> dict[str, Any]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("campaign pointer cannot be read") from exc
    if not isinstance(payload, dict) or payload.get("schema") != POINTER_SCHEMA:
        raise ValueError(f"campaign pointer must use schema {POINTER_SCHEMA!r}")
    for key in ("distribution", "python_executable", "manifest_path", "campaign_id"):
        if not isinstance(payload.get(key), str) or not payload[key]:
            raise ValueError(f"campaign pointer lacks {key}")
    return payload


def _public_init(args: argparse.Namespace) -> None:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", args.name):
        raise ValueError("campaign name must be one safe path component (letters, digits, . _ -)")
    try:
        profile_raw = json.loads(Path(args.profile).read_text(encoding="utf-8"))
        profile = ExecutionProfile.from_mapping(profile_raw)
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        raise ValueError(f"cannot load execution profile: {exc}") from exc
    if profile.target == "slurm":
        if sys.platform == "win32":
            raise ValueError("a slurm profile must be initialized by the Linux CLI from its direct manifest")
        from hubbardflow.execution.wsl_campaign_init import initialize_campaign
        result = initialize_campaign(
            fdf_path=args.fdf_file, lr_config_path=args.lr_config, profile_path=args.profile,
            name=args.name, campaign_root=args.campaign_root,
        )
        print(json.dumps(result, indent=2, sort_keys=True))
        return
    if profile.target != "local_wsl" or profile.wsl is None:
        raise ValueError("init requires target=local_wsl or target=slurm")
    pointer = Path(args.pointer or (Path.cwd() / f"{args.name}.siestaflow.json")).resolve()
    distribution, python_executable = profile.wsl.distribution, profile.wsl.python_executable
    wsl_inputs = [
        windows_to_wsl_path(distribution, value)
        for value in (args.fdf_file, args.lr_config, args.profile, pointer)
    ]
    raw = wsl_command(distribution, [
        python_executable, "-m", "hubbardflow.cli", "_init",
        *wsl_inputs[:3], args.name, wsl_inputs[3],
    ])
    print(raw)


def _public_control(args: argparse.Namespace) -> int | None:
    try:
        payload = json.loads(Path(args.campaign).read_text(encoding="utf-8"))
    except (ValueError, OSError, json.JSONDecodeError):
        payload = None
    if isinstance(payload, dict) and payload.get("schema") == POINTER_SCHEMA:
        pointer = _read_pointer(args.campaign)
    elif isinstance(payload, dict) and payload.get("schema") == "siestaflow.campaign.v2":
        pointer = None
    else:
        # Preserve a clear error for old manifests and malformed pointer files.
        _read_pointer(args.campaign)
        raise AssertionError("unreachable")
    if pointer is None:
        from hubbardflow.execution.campaign_runner import (
            campaign_status, render_campaign_report, request_campaign_stop, run_campaign_worker,
        )
        if args.command in {"run", "resume"}:
            code = run_campaign_worker(args.campaign, args.command)
            print(json.dumps(campaign_status(args.campaign), indent=2, sort_keys=True))
            return int(code)
        if args.command == "status":
            print(json.dumps(campaign_status(args.campaign), indent=2, sort_keys=True))
            return
        if args.command == "stop":
            print(json.dumps(request_campaign_stop(args.campaign), indent=2, sort_keys=True))
            return
        if args.command == "report":
            _write_console_text(render_campaign_report(args.campaign))
            return
        raise ValueError("unsupported campaign command")
    if args.command in {"run", "resume"}:
        response = start_worker(
            distribution=pointer["distribution"], python_executable=pointer["python_executable"],
            manifest_path=pointer["manifest_path"], mode=args.command,
        )
    elif args.command == "status":
        response = read_worker_status(
            distribution=pointer["distribution"], python_executable=pointer["python_executable"],
            manifest_path=pointer["manifest_path"],
        )
    elif args.command == "stop":
        response = stop_worker(
            distribution=pointer["distribution"], python_executable=pointer["python_executable"],
            manifest_path=pointer["manifest_path"],
        )
    elif args.command == "report":
        response = wsl_command(pointer["distribution"], [
            pointer["python_executable"], "-m", "hubbardflow.cli", "_report", pointer["manifest_path"],
        ])
        _write_console_text(response)
        return
    else:  # pragma: no cover - argparse constrains public commands
        raise ValueError("unsupported campaign command")
    print(json.dumps(response, indent=2, sort_keys=True))


def _write_console_text(text: str) -> None:
    """Write UTF-8 report text safely through legacy Windows console encodings."""
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    safe_text = text.encode(encoding, errors="backslashreplace").decode(encoding)
    sys.stdout.write(safe_text + "\n")


def _internal_report(manifest_path: str) -> str:
    from hubbardflow.execution.campaign_runner import render_campaign_report
    return render_campaign_report(manifest_path)


def main(argv: list[str] | None = None) -> int:
    from hubbardflow.product_cli import add_product_commands, add_product_options, product_command

    parser = argparse.ArgumentParser(description="HubbardFlow Linux/Slurm and PowerShell-to-WSL campaign CLI")
    sub = parser.add_subparsers(dest="command", required=True)
    add_product_commands(sub)
    audit = sub.add_parser("audit-fdf", help="run the existing read-only FDF consistency audit")
    audit.add_argument("fdf_file", help="FDF path")
    projector_check = sub.add_parser(
        "check-projector",
        help="compare an LR campaign projector with a DFT+U FDF using explicit label mappings",
    )
    projector_check.add_argument("--campaign", required=True, help="campaign.v2.json with resolved projector evidence")
    projector_check.add_argument("--target-fdf", required=True, help="DFT+U application FDF path")
    projector_check.add_argument(
        "--map", dest="label_mappings", action="append", required=True,
        metavar="LR_LABEL=DFTU_LABEL", help="explicit mapping; repeat for each Hubbard species",
    )
    projector_check.add_argument(
        "--artifact-dir", action="append", default=[],
        help="additional directory containing .psml, .ion, or .dftu_proj files; repeatable",
    )
    projector_check.add_argument(
        "--force", action="store_true",
        help="record explicit user override for MISMATCH or INCOMPLETE",
    )
    projector_check.add_argument("--json-out", help="optional path to save the machine-readable report")
    init = sub.add_parser("init", help="create a fixed-grid or policy-driven adaptive v2 campaign as a WSL pointer or direct Linux manifest")
    init.add_argument("fdf_file", help="reference FDF path")
    init.add_argument("--lr-config", required=True, help="material/site/alpha/config JSON")
    init.add_argument("--profile", required=True, help="versioned local_wsl or Slurm execution profile JSON")
    init.add_argument("--name", required=True, help="safe campaign directory name")
    init.add_argument("--pointer", help="Windows path for the campaign pointer JSON")
    init.add_argument("--campaign-root", help="Linux parent directory for direct manifest campaigns (defaults to cwd)")
    controls = {
        "run": "consume an FDF product plan, or start an existing campaign worker",
        "resume": "resume an interrupted campaign in WSL",
        "status": "read the durable campaign status",
        "report": "regenerate the report from the saved analysis JSON",
        "stop": "request a safe worker stop",
    }
    for command, description in controls.items():
        control = sub.add_parser(command, help=description)
        control.add_argument("campaign", help="FDF product input (run), Windows pointer JSON (local_wsl), or campaign.v2.json (Linux/Slurm)")
        if command == "run":
            add_product_options(control)
            control.add_argument("--profile", help="validated Linux execution profile for product execution")
            control.add_argument("--name", help="campaign directory name for product execution")
            control.add_argument("--campaign-root", help="Linux parent directory for the initialized campaign")
    # Private WSL implementation commands; public users should use the pointer.
    internal = sub.add_parser("_init", help=argparse.SUPPRESS)
    internal.add_argument("fdf_wsl")
    internal.add_argument("config_wsl")
    internal.add_argument("profile_wsl")
    internal.add_argument("name")
    internal.add_argument("pointer_wsl")
    launch = sub.add_parser("_daemon-launch", help=argparse.SUPPRESS)
    launch.add_argument("manifest")
    launch.add_argument("mode", choices=("run", "resume"))
    status = sub.add_parser("_status", help=argparse.SUPPRESS)
    status.add_argument("manifest")
    stop = sub.add_parser("_stop", help=argparse.SUPPRESS)
    stop.add_argument("manifest")
    report = sub.add_parser("_report", help=argparse.SUPPRESS)
    report.add_argument("manifest")
    worker = sub.add_parser("_worker", help=argparse.SUPPRESS)
    worker.add_argument("manifest")
    worker.add_argument("mode", choices=("run", "resume"))

    args = parser.parse_args(argv)
    try:
        if args.command == "run" and Path(args.campaign).suffix.casefold() != ".fdf":
            product_options = (
                ("--lr-config", args.lr_config),
                ("--sensitivity-tolerance-ev", args.sensitivity_tolerance_ev),
                ("--reference-output", args.reference_output),
                ("--reference-dm", args.reference_dm),
                ("--tol-fermi-ev", args.tol_fermi_ev),
                ("--coverage", args.coverage),
                ("--alpha-strategy", args.alpha_strategy),
                ("--identity-dir", args.identity_dir),
                ("--allow-spin-flip", args.allow_spin_flip),
                ("--allow-rotations", args.allow_rotations),
                ("--output-dir", args.output_dir),
                ("--override-plan-state", args.override_plan_state),
                ("--dry-run", True if args.dry_run else None),
            )
            supplied_options = [name for name, value in product_options if value is not None]
            if supplied_options:
                raise ValueError(
                    "product options require an FDF target: " + ", ".join(supplied_options)
                )
        if args.command == "audit-fdf":
            audit_fdf(args)
        elif args.command == "check-projector":
            from hubbardflow.siesta_backend.projector_compatibility import check_campaign_projectors

            mappings: list[tuple[str, str]] = []
            for raw_mapping in args.label_mappings:
                source, separator, target = raw_mapping.partition("=")
                if not separator or not source or not target:
                    raise ValueError("--map must use LR_LABEL=DFTU_LABEL")
                mappings.append((source, target))
            projector_report = check_campaign_projectors(
                args.campaign,
                args.target_fdf,
                mappings,
                force=args.force,
                artifact_dirs=args.artifact_dir,
            )
            if args.json_out:
                rendered_json = json.dumps(projector_report.to_mapping(), indent=2, sort_keys=True, allow_nan=False)
                Path(args.json_out).write_text(rendered_json + "\n", encoding="utf-8")
            from hubbardflow.reporting.projector_compatibility_report import render_projector_compatibility_report

            print(render_projector_compatibility_report(projector_report))
            return 0 if projector_report.application_permitted else 1
        elif args.command == "init":
            _public_init(args)
        elif args.command in {"plan", "submit", "reference"} or (args.command == "run" and Path(args.campaign).suffix.casefold() == ".fdf"):
            return product_command(args)
        elif args.command in {"run", "resume", "status", "report", "stop"}:
            result = _public_control(args)
            return 0 if result is None else result
        elif args.command == "_init":
            from hubbardflow.execution.wsl_campaign_init import initialize_wsl_campaign
            print(json.dumps(initialize_wsl_campaign(
                fdf_path=args.fdf_wsl, lr_config_path=args.config_wsl, profile_path=args.profile_wsl,
                name=args.name, pointer_path=args.pointer_wsl,
            ), indent=2, sort_keys=True))
        elif args.command == "_daemon-launch":
            print(json.dumps(daemon_launch(args.manifest, args.mode), sort_keys=True))
        elif args.command == "_status":
            print(json.dumps(daemon_status(args.manifest), sort_keys=True))
        elif args.command == "_stop":
            print(json.dumps(daemon_stop(args.manifest), sort_keys=True))
        elif args.command == "_report":
            print(_internal_report(args.manifest))
        elif args.command == "_worker":
            from hubbardflow.execution.campaign_runner import run_campaign_worker
            return int(run_campaign_worker(args.manifest, args.mode))
    except (ValueError, OSError, WslSupervisorError) as exc:
        print(f"hubbardflow: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
