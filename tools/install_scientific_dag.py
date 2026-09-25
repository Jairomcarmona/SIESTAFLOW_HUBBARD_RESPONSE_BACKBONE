"""Install the validated resumable scientific-DAG contract into a campaign.

The campaign must already provide its scientific inputs, a run manifest,
``scripts/validate_run.py``, and its own ``scripts/package_results.py``.
This installer does not generate a material-specific FDF or alter LR algebra.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOLS = (
    "scientific_dag_gate.py",
    "scientific_dag_analysis.py",
    "materialize_method2_projector.py",
    "audit_method2_projector.py",
    "verify_method2_projector_identity.py",
    "stage_fdf_pseudos.py",
    "select_psml_for_label.py",
    "psml_selection.py",
    "siesta_dftu_fdf.py",
)


def infer_central_label(campaign_root: Path) -> str:
    manifest = json.loads((campaign_root / "runs" / "manifest.json").read_text(encoding="utf-8"))
    targets = [record.get("target") for record in manifest if record.get("mode") != "REFERENCE" and record.get("target")]
    if not targets:
        raise ValueError("cannot infer central label: manifest contains no perturbed target")
    return str(targets[0])


def infer_analysis_script(campaign_root: Path) -> str:
    for relative in ("scripts/package_results.py", "scripts/analyze.py"):
        if (campaign_root / relative).is_file():
            return relative
    raise ValueError("cannot infer campaign algebra entry point; expected scripts/package_results.py or scripts/analyze.py")


def write_unix(path: Path, contents: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(contents.replace("\r\n", "\n"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-root", type=Path, required=True)
    parser.add_argument("--central-label")
    parser.add_argument("--result-file", default="results/final/campaign_result.json", help="Path relative to campaign root")
    parser.add_argument("--analysis-script", help="Python campaign algebra entry point relative to campaign root")
    parser.add_argument("--analysis-validator", help="Optional typed campaign validator, relative to campaign root")
    parser.add_argument("--campaign-id", help="Campaign ID required with --analysis-validator")
    parser.add_argument("--force", action="store_true", help="Replace an existing scientific-DAG installation")
    args = parser.parse_args()

    campaign = args.campaign_root.resolve()
    required = (campaign / "runs" / "manifest.json", campaign / "runs" / "00_REFERENCE" / "siesta.fdf", campaign / "pseudopotentials", campaign / "scripts" / "validate_run.py")
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise SystemExit("campaign cannot receive scientific DAG; missing: " + ", ".join(missing))
    destination = campaign / "scripts" / "siestaflow_dag"
    slurm = campaign / "slurm" / "submit_scientific_lru_dag.slurm"
    profile_example = campaign / "slurm" / "site_profile.local.example"
    config = campaign / "scripts" / "scientific_dag.json"
    if not args.force and any(path.exists() for path in (destination, slurm, profile_example, config)):
        raise SystemExit("scientific DAG already installed; use --force only to update its deployment files")

    # Validate campaign-specific interfaces before touching its deployment tree.
    try:
        analysis_script = args.analysis_script or infer_analysis_script(campaign)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    if not (campaign / analysis_script).is_file():
        raise SystemExit(f"analysis script is absent: {analysis_script}")
    if bool(args.analysis_validator) != bool(args.campaign_id):
        raise SystemExit("--analysis-validator and --campaign-id must be supplied together")
    if args.analysis_validator:
        validator_relative = Path(args.analysis_validator)
        if validator_relative.is_absolute() or ".." in validator_relative.parts:
            raise SystemExit("analysis validator must be a campaign-relative path without '..'")
        validator_path = (campaign / validator_relative).resolve()
        try:
            validator_path.relative_to(campaign)
        except ValueError as exc:
            raise SystemExit("analysis validator must remain inside campaign root") from exc
        if not validator_path.is_file():
            raise SystemExit(f"analysis validator is absent: {args.analysis_validator}")
        validator_hash = hashlib.sha256(validator_path.read_bytes()).hexdigest()
        analysis_acceptance = {
            "schema_version": 1,
            "kind": "campaign_hook",
            "campaign_id": args.campaign_id,
            "validator_script": validator_relative.as_posix(),
            "validator_sha256": validator_hash,
        }
    else:
        analysis_acceptance = {"schema_version": 1, "kind": "generic_full_rank"}
    central_label = args.central_label or infer_central_label(campaign)
    config_data = {
        "schema_version": 1,
        "central_label": central_label,
        "result_file": args.result_file,
        "analysis_script": analysis_script,
        "analysis_acceptance": analysis_acceptance,
        "contract": "projector audit -> accepted reference -> materialized children -> validated responses -> direct LR algebra -> evidence",
    }

    # Build the entire deployment off to the side, then atomically replace the
    # four install targets. If any rename fails, restore the old deployment.
    targets = (destination, slurm, profile_example, config)
    with tempfile.TemporaryDirectory(prefix=".scientific-dag-install-", dir=campaign) as temporary:
        staging = Path(temporary)
        staged_destination = staging / "scripts" / "siestaflow_dag"
        staged_slurm = staging / "slurm" / "submit_scientific_lru_dag.slurm"
        staged_profile = staging / "slurm" / "site_profile.local.example"
        staged_config = staging / "scripts" / "scientific_dag.json"
        staged_destination.mkdir(parents=True)
        for name in TOOLS:
            shutil.copy2(ROOT / "tools" / name, staged_destination / name)
        write_unix(staged_slurm, (ROOT / "templates" / "slurm" / "submit_scientific_lru_dag.slurm").read_text(encoding="utf-8"))
        write_unix(staged_profile, (ROOT / "templates" / "slurm" / "site_profile.local.example").read_text(encoding="utf-8"))
        write_unix(staged_config, json.dumps(config_data, indent=2) + "\n")

        staged_targets = (staged_destination, staged_slurm, staged_profile, staged_config)
        backup_dir = staging / "backups"
        backup_dir.mkdir()
        committed: list[tuple[Path, Path | None]] = []
        try:
            for index, (staged, target) in enumerate(zip(staged_targets, targets)):
                target.parent.mkdir(parents=True, exist_ok=True)
                backup = None
                if target.exists():
                    backup = backup_dir / f"{index}-{target.name}"
                    os.replace(target, backup)
                try:
                    os.replace(staged, target)
                except OSError:
                    if backup is not None:
                        os.replace(backup, target)
                    raise
                committed.append((target, backup))
        except OSError:
            for target, backup in reversed(committed):
                if target.is_dir():
                    shutil.rmtree(target)
                elif target.exists():
                    target.unlink()
                if backup is not None:
                    os.replace(backup, target)
            raise

    print(json.dumps({"status": "SCIENTIFIC_DAG_INSTALLED", "campaign_root": str(campaign), "submit_script": str(slurm), "site_profile_example": str(profile_example), "central_label": config_data["central_label"]}, indent=2))


if __name__ == "__main__":
    main()
