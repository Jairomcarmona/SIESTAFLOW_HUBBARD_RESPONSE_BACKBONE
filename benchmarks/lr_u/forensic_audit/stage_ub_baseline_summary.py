"""Summarize frozen U-A precision certificates and available timing evidence."""
from __future__ import annotations

import json
from fractions import Fraction
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))
from siestaflow_hubbard.domain.u_certification import interval_half_width

BASE = Path(__file__).resolve().parent


def interval_metrics(lower: str, upper: str, nominal: str, tolerance: str) -> dict[str, Fraction]:
    """Return exact interval summary values; nominal distances are diagnostics."""
    lo, hi, center, tol = map(Fraction, (lower, upper, nominal, tolerance))
    half_width = interval_half_width(lo, hi)
    return {
        "width": hi - lo,
        "half_width": half_width,
        "interval_center": (lo + hi) / 2,
        "lower_distance_from_nominal": center - lo,
        "upper_distance_from_nominal": hi - center,
        "precision_margin": tol - half_width,
    }


def main() -> None:
    frozen = json.loads((BASE / "frozen_evidence.json").read_text())
    precision_policy = json.loads((BASE.parent / "stage_u_b" / "precision_policy.json").read_text())
    tolerance = precision_policy["u_precision_tolerance_eV"]
    for item in frozen["materials"]:
        name = item["material"]
        if name in ("MnO", "CoO"):
            wrapper = json.loads((BASE / f"{name}_u_certificate.superseding.v2.json").read_text())
            cert = wrapper["certificate"]
        else:
            root = Path(item["campaign_root"])
            cert = json.loads((root / item["certificate"]["path"]).read_text())
        print(f"[{name}]")
        for index, (nominal, iv) in enumerate(zip(cert["nominal_u_by_site_eV"], cert["u_interval_by_site"])):
            summary = interval_metrics(iv["lower"], iv["upper"], str(nominal), tolerance)
            print(f"site{index}: U={nominal:.15g} lower={float(Fraction(iv['lower'])):.15g} upper={float(Fraction(iv['upper'])):.15g} "
                  f"width={float(summary['width']):.15g} halfwidth={float(summary['half_width']):.15g} "
                  f"center={float(summary['interval_center']):.15g} "
                  f"lower_distance={float(summary['lower_distance_from_nominal']):.15g} "
                  f"upper_distance={float(summary['upper_distance_from_nominal']):.15g} "
                  f"margin={float(summary['precision_margin']):.15g}")
        root = Path(item["campaign_root"])
        analysis = json.loads((root / cert["analysis_artifact_path"]).read_text())
        policy = analysis.get("estimator_policy", {})
        print("historical analysis policy:", {key: policy.get(key) for key in ("u_precision_tolerance_eV", "sensitivity_tolerance_eV")})
        manifest = json.loads((root / cert["source_evidence_manifest_path"]).read_text())
        print("observation count:", len(manifest.get("observations", [])))
        print()


if __name__ == "__main__":
    main()
