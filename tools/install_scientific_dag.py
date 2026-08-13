"""Install the validated resumable scientific-DAG contract into a campaign.

The campaign must already provide its scientific inputs, a run manifest,
``scripts/validate_run.py``, and its own ``scripts/package_results.py``.
This installer does not generate a material-specific FDF or alter LR algebra.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOLS = (
    "scientific_dag_gate.py",
    "materialize_method2_projector.py",
    "audit_method2_projector.py",
    "stage_fdf_pseudos.py",
    "select_psml_for_label.py",
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
    if not args.force and any(path.exists() for path in (destination, slurm, config)):
        raise SystemExit("scientific DAG already installed; use --force only to update its deployment files")

    destination.mkdir(parents=True, exist_ok=True)
    for name in TOOLS:
        shutil.copy2(ROOT / "tools" / name, destination / name)
    write_unix(slurm, (ROOT / "templates" / "slurm" / "submit_scientific_lru_dag.slurm").read_text(encoding="utf-8"))
    write_unix(profile_example, (ROOT / "templates" / "slurm" / "site_profile.local.example").read_text(encoding="utf-8"))
    try:
        analysis_script = args.analysis_script or infer_analysis_script(campaign)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    if not (campaign / analysis_script).is_file():
        raise SystemExit(f"analysis script is absent: {analysis_script}")
    config_data = {
        "schema_version": 1,
        "central_label": args.central_label or infer_central_label(campaign),
        "result_file": args.result_file,
        "analysis_script": analysis_script,
        "contract": "projector audit -> accepted reference -> materialized children -> validated responses -> direct LR algebra -> evidence",
    }
    write_unix(config, json.dumps(config_data, indent=2) + "\n")
    print(json.dumps({"status": "SCIENTIFIC_DAG_INSTALLED", "campaign_root": str(campaign), "submit_script": str(slurm), "site_profile_example": str(profile_example), "central_label": config_data["central_label"]}, indent=2))


if __name__ == "__main__":
    main()
