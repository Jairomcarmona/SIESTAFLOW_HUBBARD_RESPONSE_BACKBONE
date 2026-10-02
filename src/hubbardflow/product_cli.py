"""Public FDF product commands preserve the legacy campaign control interface."""

from __future__ import annotations

import argparse
import json
from dataclasses import replace
from pathlib import Path

from hubbardflow.domain.perturbation_plan import AlphaStrategy
from hubbardflow.execution.campaign_plan import CampaignCoverage
from hubbardflow.execution.product_models import ProductCommand, ProductError, json_object
from hubbardflow.execution.product_plan import (
    ProductRequest,
    freeze_product_snapshot,
    load_product_snapshot,
    product_execution_boundary,
    protect_product_destination,
    resolve_product_snapshot,
)
from hubbardflow.reporting.product_report import render_product_report


def add_product_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--lr-config", help="versioned LR protocol JSON; no alpha grid is invented")
    parser.add_argument("--reference-output", help="single unperturbed reference SIESTA output")
    parser.add_argument("--reference-dm", help="parent DM whose bytes enter provenance")
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


def add_product_commands(sub: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    plan = sub.add_parser("plan", help="freeze an FDF perturbation plan and report exact qualification")
    plan.add_argument("fdf_file")
    add_product_options(plan)
    submit = sub.add_parser("submit", help="consume a frozen FDF plan at the SLURM admission boundary")
    submit.add_argument("fdf_file")
    submit.add_argument("--partition", required=True, help="explicit user-selected SLURM partition")
    submit.add_argument("--account", help="user-selected SLURM account; never defaulted")
    add_product_options(submit)


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
    )


def product_command(args: argparse.Namespace) -> int:
    """Plan or verify the frozen plan before recording a blocked execution request."""
    fdf = Path(args.campaign if args.command == "run" else args.fdf_file)
    root = Path(args.output_dir or (Path.cwd() / ".hubbardflow" / fdf.stem)).resolve()
    protect_product_destination(root)
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
    boundary = None
    if args.command != "plan":
        boundary = product_execution_boundary(
            root,
            snapshot,
            ProductCommand(args.command),
            override_reason=args.override_plan_state,
            partition=getattr(args, "partition", None),
            account=getattr(args, "account", None),
        )
    report = root / ("plan_report.md" if boundary is None else f"{args.command}_report.md")
    report.write_text(render_product_report(snapshot, boundary), encoding="utf-8", newline="\n")
    result = snapshot.to_mapping() if boundary is None else boundary.to_mapping()
    result["campaign_identity"] = snapshot.campaign_identity
    result["artifact_directory"] = str(root)
    result["report"] = str(report)
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    return 0 if boundary is None else 3
