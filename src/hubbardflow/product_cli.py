"""Public FDF product commands preserve the legacy campaign control interface."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import tempfile
from collections.abc import Callable, Mapping, Sequence
from dataclasses import replace
from pathlib import Path
from typing import cast

from hubbardflow.domain.hash_traceability import DigestWarning, digest_warning
from hubbardflow.domain.perturbation_plan import AlphaStrategy
from hubbardflow.execution.campaign_plan import CampaignCoverage
from hubbardflow.execution.campaign_v2 import (
    load_campaign_v2,
    resolve_fdf_includes,
    verify_campaign_inventory,
)
from hubbardflow.execution.product_admission import (
    ExecutionAdmission,
    ExecutionAdmissionStatus,
    execution_admission,
    reference_dm_name_for_request,
)
from hubbardflow.execution.product_models import ProductCommand, ProductError, json_object
from hubbardflow.execution.product_plan import (
    ProductRequest,
    freeze_product_snapshot,
    load_product_snapshot,
    product_execution_boundary,
    protect_product_destination,
    resolve_product_snapshot,
)
from hubbardflow.execution.wsl_campaign_init import initialize_campaign
from hubbardflow.reporting.product_report import render_product_report


def _write_report_atomically(path: Path, text: str) -> None:
    """Replace a checked product report only after its full content is written."""
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def add_product_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--lr-config", help="versioned LR protocol JSON; no alpha grid is invented")
    parser.add_argument(
        "--sensitivity-tolerance-ev", type=float,
        help="explicit nonnegative absolute sensitivity tolerance in eV; frozen into the effective lr-config",
    )
    parser.add_argument("--reference-output", help="single unperturbed reference SIESTA output")
    parser.add_argument("--reference-dm", help="parent DM whose bytes enter provenance")
    parser.add_argument(
        "--tol-fermi-ev",
        type=float,
        default=None,
        help="declared Fermi tolerance in eV; requires --lr-config and overrides tol_Fermi_eV; absent means record only",
    )
    parser.add_argument("--coverage", choices=[v.value for v in CampaignCoverage])
    parser.add_argument("--alpha-strategy", choices=[v.value for v in AlphaStrategy])
    parser.add_argument("--identity-dir", action="append", help="species identity search directory")
    parser.add_argument(
        "--allow-spin-flip",
        action="store_const",
        const=True,
        default=None,
        help="explicit policy opt-in; default off; validation still required",
    )
    parser.add_argument(
        "--allow-rotations",
        action="store_const",
        const=True,
        default=None,
        help="explicit policy opt-in; default off; validation still required",
    )
    parser.add_argument("--output-dir", help="sidecar directory (default: .hubbardflow/<FDF stem> in cwd)")
    parser.add_argument(
        "--override-plan-state",
        metavar="REASON",
        help="record a deliberate non-READY override; missing production evidence still blocks",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="freeze and report product admission without initializing or executing a campaign",
    )


def add_product_commands(sub: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    plan = sub.add_parser("plan", help="freeze an FDF perturbation plan and report exact qualification")
    plan.add_argument("fdf_file")
    add_product_options(plan)
    submit = sub.add_parser("submit", help="consume a frozen FDF plan at the SLURM admission boundary")
    submit.add_argument("fdf_file")
    submit.add_argument("--partition", required=True, help="explicit user-selected SLURM partition")
    submit.add_argument("--account", help="user-selected SLURM account; never defaulted")
    add_product_options(submit)
    reference = sub.add_parser("reference", help="run and archive one validated reference SIESTA state")
    reference.add_argument("fdf_file")
    add_product_options(reference)
    reference.add_argument("--profile", required=True, help="validated Linux execution profile")
    reference.add_argument("--name", required=True, help="safe reference campaign directory name")
    reference.add_argument("--campaign-root", help="Linux parent directory for the reference campaign")


def _request(args: argparse.Namespace, fdf: Path) -> ProductRequest:
    def absolute(value: str | None) -> str | None:
        return None if value is None else str(Path(value).resolve(strict=True))

    return ProductRequest(
        str(fdf.resolve(strict=True)),
        absolute(args.lr_config),
        absolute(args.reference_output),
        absolute(args.reference_dm),
        None if args.coverage is None else CampaignCoverage(args.coverage),
        None if args.alpha_strategy is None else AlphaStrategy(args.alpha_strategy),
        tuple(sorted(str(Path(d).resolve(strict=True)) for d in (args.identity_dir or [str(fdf.parent)]))),
        args.allow_spin_flip,
        args.allow_rotations,
        getattr(args, "tol_fermi_ev", None),
        args.sensitivity_tolerance_ev,
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _verify_campaign_inputs(
    campaign: dict[str, object], snapshot: object, profile_path: Path, frozen_config: dict[str, object]
) -> tuple[DigestWarning, ...]:
    """Verify required files, retaining digest discrepancies without a byte veto."""
    from hubbardflow.execution.product_models import ProductSnapshot

    if not isinstance(snapshot, ProductSnapshot):
        raise ProductError("execution requires a verified product snapshot")
    root = Path(str(campaign["_campaign_root"])).resolve(strict=True)
    input_rows = cast(Sequence[Mapping[str, object]], campaign["input_files"])
    rows = {str(row["path"]): row.get("sha256") for row in input_rows}
    input_hashes = json_object(snapshot.input_sha256_json)
    warnings: list[DigestWarning] = []

    def require_copy(relative: str, expected: object) -> None:
        path = (root / relative).resolve(strict=True)
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise ProductError(f"required input escapes campaign root: {relative}") from exc
        observed = _sha256(path)  # Missing/unreadable real files still fail.
        for recorded, field in (
            (rows.get(relative), f"input_files.{relative}.sha256"),
            (expected, f"product_sources.{relative}.sha256"),
        ):
            warning = digest_warning(recorded, observed, field)
            if warning is not None:
                warnings.append(warning)

    request = ProductRequest.from_mapping(json_object(snapshot.request_json))
    source_fdf = str(Path(request.fdf).resolve(strict=True))
    require_copy("provenance/source_reference.fdf", input_hashes.get(source_fdf))
    config_digest = snapshot.frozen_lr_config_sha256
    require_copy("provenance/source_lr_config.json", config_digest)
    _, includes = resolve_fdf_includes(Path(request.fdf))
    for index, source in enumerate(includes):
        source_key = str(source.resolve(strict=True))
        relative = f"provenance/fdf_includes/{index:03d}_{source.name}"
        require_copy(relative, input_hashes.get(source_key))
    for label, source_value in sorted(
        cast(dict[str, str], frozen_config.get("pseudopotentials", {})).items()
    ):
        source_key = str(Path(source_value).resolve(strict=True))
        require_copy(f"pseudopotentials/{label}.psml", input_hashes.get(source_key))
    for destination, source_value in sorted(
        cast(dict[str, str], frozen_config.get("static_artifacts", {})).items()
    ):
        source_key = str(Path(source_value).resolve(strict=True))
        require_copy(f"static/{destination}", input_hashes.get(source_key))
    for field, relative in (
        ("compatibility_registry", "software/backend_compatibility.json"),
        ("version_text_source", "software/siesta_version.txt"),
        ("planning_reference_output", "planning/planning_reference_output"),
        ("planning_reference_dm", "planning/planning_reference_dm"),
    ):
        value = frozen_config.get(field)
        if value is not None:
            source_key = str(Path(str(value)).resolve(strict=True))
            require_copy(relative, input_hashes.get(source_key))
    profile_digest = _sha256(profile_path)
    require_copy("execution_profile.json", profile_digest)
    warnings.extend(DigestWarning.from_mapping(row) for row in verify_campaign_inventory(campaign))
    retained = tuple(
        sorted(
            set(warnings),
            key=lambda item: (item.field, item.reason.value, item.recorded or "", item.observed or ""),
        )
    )
    campaign["_product_input_traceability_warnings"] = [warning.to_mapping() for warning in retained]
    # Persist before subsequent run-spec validation or worker startup so a
    # later structural failure cannot discard already observed traceability.
    _write_report_atomically(
        root / "product-input-traceability.json",
        json.dumps(
            {
                "schema": "hubbardflow.product_input_traceability.v1",
                "warnings": [warning.to_mapping() for warning in retained],
            },
            sort_keys=True,
            allow_nan=False,
        )
        + "\n",
    )
    return retained


def _execute_product_campaign(
    root: Path,
    snapshot: object,
    *,
    profile_path: Path,
    name: str,
    campaign_root: Path | None,
) -> int:
    from hubbardflow.execution.campaign_runner import run_campaign_worker
    from hubbardflow.execution.execution_profile import ExecutionProfile
    from hubbardflow.execution.product_models import ProductSnapshot, canonical

    if not isinstance(snapshot, ProductSnapshot) or snapshot.planning is None:
        raise ProductError("admissible product execution requires a frozen resolved plan")
    if (root / "execution_link.json").exists():
        raise ProductError(
            "this product already has an execution link; continue with hubbardflow resume <campaign.v2.json>"
        )
    config_text = snapshot.frozen_lr_config_json
    if config_text is None:
        raise ProductError("admissible product execution requires a frozen lr-config")
    frozen_config = json_object(config_text)
    profile = ExecutionProfile.from_mapping(json_object(profile_path.read_text(encoding="utf-8")))
    pointer_path: Path | None = None
    if profile.target == "local_wsl":
        # Legacy local_wsl init always creates the campaign in the profile's
        # workspace and writes a control pointer; mirror that instead of
        # silently ignoring --campaign-root.
        assert profile.wsl is not None
        workspace = Path(profile.wsl.workspace_root).resolve()
        if campaign_root is not None and campaign_root.resolve() != workspace:
            raise ProductError(
                f"local_wsl campaigns are created in the profile's wsl.workspace_root ({workspace}); "
                "omit --campaign-root or set it to that path"
            )
        campaign_parent = workspace
        pointer_path = root / "campaign.pointer.json"
    else:
        campaign_parent = (campaign_root or root / "campaigns").resolve()
    destination = campaign_parent / name
    protect_product_destination(destination)
    if not name or Path(name).name != name or name in {".", ".."}:
        raise ProductError("campaign name must be one safe path component")

    handle, temporary_name = tempfile.mkstemp(prefix=".lr-config-frozen-", suffix=".json", dir=root)
    temporary_config = Path(temporary_name)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(config_text + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        initialized = initialize_campaign(
            fdf_path=ProductRequest.from_mapping(json_object(snapshot.request_json)).fdf,
            lr_config_path=str(temporary_config),
            profile_path=str(profile_path.resolve(strict=True)),
            name=name,
            campaign_root=str(campaign_parent),
            pointer_path=None if pointer_path is None else str(pointer_path),
        )
    finally:
        temporary_config.unlink(missing_ok=True)
    manifest_path = Path(str(initialized["manifest_path"])).resolve(strict=True)
    campaign = load_campaign_v2(manifest_path)
    input_warnings = _verify_campaign_inputs(
        campaign, snapshot, profile_path.resolve(strict=True), frozen_config
    )
    campaign_plan_path = manifest_path.parent / str(campaign["resolved_perturbation_plan_file"])
    campaign_plan = json_object(campaign_plan_path.read_text(encoding="utf-8"))
    expected_runs = [run.to_mapping() for run in snapshot.planning.plan.run_specs]
    actual_runs = campaign_plan.get("run_specs")
    if not isinstance(actual_runs, list):
        raise ProductError("initialized campaign plan has no run-spec list")

    def canonical_runs(values: Sequence[object]) -> list[str]:
        return sorted(canonical(value) for value in values)

    if canonical_runs(expected_runs) != canonical_runs(actual_runs):
        raise ProductError("initialized campaign run specs differ from the frozen product plan")
    link = {
        "schema": "hubbardflow.product_execution_link.v1",
        "campaign_path": str(manifest_path),
        "manifest_sha256": _sha256(manifest_path),
        "product_plan_digest": snapshot.planning.plan.digest,
        "input_traceability_warnings": [warning.to_mapping() for warning in input_warnings],
    }
    link_path = root / "execution_link.json"
    with link_path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(canonical(link) + "\n")
    worker = cast(Callable[[str | Path, str], int], run_campaign_worker)
    return worker(manifest_path, "run")


def _execute_product_reference(
    root: Path,
    snapshot: object,
    *,
    profile_path: Path,
    name: str,
    campaign_root: Path | None,
) -> int:
    """Run just the validated reference node and archive its exact output and DM bytes."""
    from hubbardflow.execution.campaign_runner import run_campaign_worker
    from hubbardflow.execution.execution_profile import ExecutionProfile
    from hubbardflow.execution.product_models import ProductSnapshot, canonical

    if not isinstance(snapshot, ProductSnapshot) or snapshot.planning is None:
        raise ProductError("reference execution requires a frozen resolved plan")
    if snapshot.frozen_lr_config_json is None:
        raise ProductError("reference execution requires a frozen lr-config")
    frozen_config = json_object(snapshot.frozen_lr_config_json)
    expected_dm_name = reference_dm_name_for_request(snapshot.request_json)
    configured_dm_name = frozen_config.get("reference_dm_name", "reference.DM")
    if configured_dm_name != expected_dm_name:
        raise ProductError(
            f"reference_dm_name {configured_dm_name!r} does not match the FDF SystemLabel output "
            f"name {expected_dm_name!r}"
        )

    profile = ExecutionProfile.from_mapping(json_object(profile_path.read_text(encoding="utf-8")))
    if (root / "reference_execution_link.json").exists():
        raise ProductError(
            "this product already has a reference execution link; choose a new output directory"
        )
    if profile.target == "local_wsl":
        assert profile.wsl is not None
        workspace = Path(profile.wsl.workspace_root).resolve()
        if campaign_root is not None and campaign_root.resolve() != workspace:
            raise ProductError(
                f"local_wsl campaigns are created in the profile's wsl.workspace_root ({workspace}); "
                "omit --campaign-root or set it to that path"
            )
        campaign_parent = workspace
        pointer_path: Path | None = root / "campaign.pointer.json"
    else:
        campaign_parent = (campaign_root or root / "campaigns").resolve()
        pointer_path = None
    destination = campaign_parent / name
    protect_product_destination(destination)
    if not name or Path(name).name != name or name in {".", ".."}:
        raise ProductError("campaign name must be one safe path component")

    reference_dir = root / "planning_reference"
    dm_destination = reference_dir / expected_dm_name
    output_destination = reference_dir / "reference.out"
    receipt_destination = reference_dir / "receipt.json"
    if any(path.exists() for path in (dm_destination, output_destination, receipt_destination)):
        raise ProductError("planning_reference artifacts already exist; choose a new output directory")

    handle, temporary_name = tempfile.mkstemp(prefix=".lr-config-frozen-", suffix=".json", dir=root)
    temporary_config = Path(temporary_name)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(snapshot.frozen_lr_config_json + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        request = ProductRequest.from_mapping(json_object(snapshot.request_json))
        initialized = initialize_campaign(
            fdf_path=request.fdf,
            lr_config_path=str(temporary_config),
            profile_path=str(profile_path.resolve(strict=True)),
            name=name,
            campaign_root=str(campaign_parent),
            pointer_path=None if pointer_path is None else str(pointer_path),
        )
    finally:
        temporary_config.unlink(missing_ok=True)
    manifest_path = Path(str(initialized["manifest_path"])).resolve(strict=True)
    campaign = load_campaign_v2(manifest_path)
    input_warnings = _verify_campaign_inputs(
        campaign, snapshot, profile_path.resolve(strict=True), frozen_config
    )
    worker = cast(Callable[[str | Path, str], int], run_campaign_worker)
    result = worker(manifest_path, "reference")
    if result != 0:
        return result

    control = manifest_path.parent / ".siestaflow"
    worker_state = json_object((control / "worker-state.json").read_text(encoding="utf-8"))
    if worker_state.get("status") != "STOPPED" or worker_state.get("stop_reason") != "reference_only":
        raise ProductError("reference worker did not stop after validating the reference node")
    evidence = json_object((control / "node-evidence.json").read_text(encoding="utf-8"))
    nodes = evidence.get("nodes")
    if not isinstance(nodes, Mapping) or not isinstance(nodes.get("reference"), Mapping):
        raise ProductError("validated reference node evidence is missing")
    record = nodes["reference"]
    command = record.get("command")
    artifact_spec = record.get("artifact_spec")
    if not isinstance(command, Mapping) or not isinstance(artifact_spec, Mapping):
        raise ProductError("reference node command/artifact evidence is incomplete")
    stdout_path = Path(str(command.get("stdout_path", ""))).resolve(strict=True)
    cwd = Path(str(command.get("cwd", ""))).resolve(strict=True)
    dm_path = (cwd / str(artifact_spec.get("dm", ""))).resolve(strict=True)
    if not isinstance(command.get("argv"), list) or not all(isinstance(arg, str) for arg in command["argv"]):
        raise ProductError("reference command argv evidence is malformed")
    if dm_path.name != expected_dm_name:
        raise ProductError(
            f"validated reference DM artifact {dm_path.name!r} differs from {expected_dm_name!r}"
        )

    reference_dir.mkdir(parents=True, exist_ok=True)
    for source, destination_path in ((stdout_path, output_destination), (dm_path, dm_destination)):
        with destination_path.open("xb") as stream:
            stream.write(source.read_bytes())
    fdf_path = Path(request.fdf).resolve(strict=True)
    receipt = {
        "schema": "hubbardflow.planning_reference_receipt.v1",
        "reference_output_sha256": _sha256(output_destination),
        "reference_dm_sha256": _sha256(dm_destination),
        "campaign_manifest_path": str(manifest_path),
        "node_id": "reference",
        "command_argv": command["argv"],
        "input_fdf_sha256": _sha256(fdf_path),
        "input_traceability_warnings": [warning.to_mapping() for warning in input_warnings],
    }
    with receipt_destination.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(receipt, sort_keys=True, indent=2, allow_nan=False) + "\n")
    root_link = {
        "schema": "hubbardflow.product_reference_execution_link.v1",
        "campaign_path": str(manifest_path),
        "manifest_sha256": _sha256(manifest_path),
        "product_plan_digest": snapshot.planning.plan.digest,
        "input_traceability_warnings": [warning.to_mapping() for warning in input_warnings],
    }
    with (root / "reference_execution_link.json").open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(canonical(root_link) + "\n")

    follow_up = ["hubbardflow", "run", str(fdf_path)]
    if request.lr_config is not None:
        follow_up.extend(("--lr-config", request.lr_config))
    follow_up.extend(("--profile", str(profile_path.resolve(strict=True)), "--name", f"{name}-run"))
    follow_up.extend(("--reference-output", str(output_destination), "--reference-dm", str(dm_destination)))
    if request.coverage is not None:
        follow_up.extend(("--coverage", request.coverage.value))
    if request.tol_fermi_ev is not None:
        follow_up.extend(("--tol-fermi-ev", str(request.tol_fermi_ev)))
    print("Follow-up run: " + shlex.join(follow_up))
    return 0


def product_command(args: argparse.Namespace) -> int:
    """Plan or verify the frozen plan before recording a blocked execution request."""
    dry_run = bool(getattr(args, "dry_run", False))
    if args.command == "reference":
        if (
            getattr(args, "reference_output", None) is not None
            or getattr(args, "reference_dm", None) is not None
        ):
            raise ProductError("reference does not accept --reference-output or --reference-dm")
        if getattr(args, "coverage", None) == CampaignCoverage.TRANSLATION_SHADOWED.value:
            raise ProductError(
                "reference is a direct campaign and does not accept --coverage TRANSLATION_SHADOWED"
            )
        if dry_run:
            raise ProductError("reference executes one campaign node and does not support --dry-run")
    if args.command == "run" and getattr(args, "profile", None) is not None:
        if os.name == "nt" and not dry_run:
            raise ProductError(
                "product execution requires a Linux shell; run the command inside WSL with the FDF, "
                "lr-config, profile and output paths available there"
            )
        if not dry_run and not getattr(args, "name", None):
            raise ProductError("product execution with --profile requires --name")
    elif args.command == "run" and dry_run:
        raise ProductError("run --dry-run requires --profile to evaluate execution admission")
    if args.command == "reference":
        if os.name == "nt":
            raise ProductError(
                "reference execution requires a Linux shell; run the command inside WSL with the FDF, "
                "lr-config, profile and output paths available there"
            )
        if not getattr(args, "profile", None):
            raise ProductError("reference requires --profile")
        if not getattr(args, "name", None):
            raise ProductError("reference with --profile requires --name")
    fdf = Path(args.campaign if args.command == "run" else args.fdf_file)
    default_root_name = f"{fdf.stem}-reference" if args.command == "reference" else fdf.stem
    root = Path(args.output_dir or (Path.cwd() / ".hubbardflow" / default_root_name)).resolve()
    protect_product_destination(root)
    if args.command == "run" and not dry_run and (root / "execution_link.json").exists():
        raise ProductError(
            "this product already has an execution link; continue with hubbardflow resume <campaign.v2.json>"
        )
    if args.command != "plan" and (root / "product_plan.json").exists():
        snapshot = load_product_snapshot(root)
        frozen_request = ProductRequest.from_mapping(json_object(snapshot.request_json))
        if str(fdf.resolve(strict=True)) != frozen_request.fdf:
            raise ProductError("requested FDF differs from the frozen campaign input")
        provided = any(
            getattr(args, field) is not None
            for field in (
                "lr_config",
                "reference_output",
                "reference_dm",
                "coverage",
                "alpha_strategy",
                "identity_dir",
                "allow_spin_flip",
                "allow_rotations",
                "tol_fermi_ev",
                "sensitivity_tolerance_ev",
            )
        )
        if provided:
            supplied = _request(args, fdf)
            merged = replace(
                frozen_request,
                lr_config=supplied.lr_config or frozen_request.lr_config,
                reference_output=supplied.reference_output or frozen_request.reference_output,
                reference_dm=supplied.reference_dm or frozen_request.reference_dm,
                coverage=supplied.coverage or frozen_request.coverage,
                alpha_strategy=supplied.alpha_strategy or frozen_request.alpha_strategy,
                identity_dirs=supplied.identity_dirs if args.identity_dir else frozen_request.identity_dirs,
                allow_spin_flip=supplied.allow_spin_flip
                if supplied.allow_spin_flip is not None
                else frozen_request.allow_spin_flip,
                allow_rotations=supplied.allow_rotations
                if supplied.allow_rotations is not None
                else frozen_request.allow_rotations,
                tol_fermi_ev=supplied.tol_fermi_ev
                if supplied.tol_fermi_ev is not None
                else frozen_request.tol_fermi_ev,
                sensitivity_tolerance_eV=(
                    supplied.sensitivity_tolerance_eV
                    if supplied.sensitivity_tolerance_eV is not None
                    else frozen_request.sensitivity_tolerance_eV
                ),
            )
            if resolve_product_snapshot(merged).to_mapping() != snapshot.to_mapping():
                raise ProductError(
                    "requested options differ from the frozen plan; create a new output directory"
                )
    else:
        snapshot = resolve_product_snapshot(_request(args, fdf))
        freeze_product_snapshot(root, snapshot)
        # Reload the immutable TASK 12 plan and campaign identity at this boundary.
        snapshot = load_product_snapshot(root)
    if args.command == "reference":
        frozen_config = (
            None if snapshot.frozen_lr_config_json is None else json_object(snapshot.frozen_lr_config_json)
        )
        expected_dm_name = reference_dm_name_for_request(snapshot.request_json)
        configured_dm_name = (
            "reference.DM"
            if frozen_config is None
            else frozen_config.get("reference_dm_name", "reference.DM")
        )
        if configured_dm_name != expected_dm_name:
            raise ProductError(
                f"reference_dm_name {configured_dm_name!r} does not match the FDF SystemLabel output "
                f"name {expected_dm_name!r}"
            )
    boundary = None
    admission: ExecutionAdmission | None = None
    if args.command != "plan":
        if args.command in {"run", "reference"} and getattr(args, "profile", None) is not None:
            config = (
                None
                if snapshot.frozen_lr_config_json is None
                else json_object(snapshot.frozen_lr_config_json)
            )
            admission = execution_admission(snapshot, config)
        boundary = product_execution_boundary(
            root,
            snapshot,
            ProductCommand(args.command),
            override_reason=args.override_plan_state,
            partition=getattr(args, "partition", None),
            account=getattr(args, "account", None),
            admission=admission,
        )
    report = root / ("plan_report.md" if boundary is None else f"{args.command}_report.md")
    _write_report_atomically(report, render_product_report(snapshot, boundary))
    result = snapshot.to_mapping() if boundary is None else boundary.to_mapping()
    result["campaign_identity"] = snapshot.campaign_identity
    result["artifact_directory"] = str(root)
    result["report"] = str(report)
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    if (
        args.command in {"run", "reference"}
        and admission is not None
        and (
            admission.status is ExecutionAdmissionStatus.ADMISSIBLE_LEGACY_EQUIVALENT
            if args.command == "reference"
            else admission.status
            in {
                ExecutionAdmissionStatus.ADMISSIBLE_LEGACY_EQUIVALENT,
                ExecutionAdmissionStatus.ADMISSIBLE_TRANSLATION_SHADOWED,
            }
        )
        and not dry_run
    ):
        profile_path = Path(args.profile).resolve(strict=True)
        campaign_root_value = getattr(args, "campaign_root", None)
        campaign_root = None if campaign_root_value is None else Path(campaign_root_value).resolve()
        if args.command == "reference":
            return _execute_product_reference(
                root,
                snapshot,
                profile_path=profile_path,
                name=args.name,
                campaign_root=campaign_root,
            )
        return _execute_product_campaign(
            root,
            snapshot,
            profile_path=profile_path,
            name=args.name,
            campaign_root=campaign_root,
        )
    return 0 if boundary is None or dry_run else 3
