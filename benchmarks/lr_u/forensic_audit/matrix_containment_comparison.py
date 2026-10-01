"""Export exact active-grid chi nominal/certificate comparisons."""
from __future__ import annotations

import csv
import json
from fractions import Fraction
from pathlib import Path

BASE = Path(
    "/mnt/c/Users/Jairo/Downloads/"
    "SIESTAFLOW_HUBBARD_RESPONSE_BACKBONE_V0_1_0/benchmarks/lr_u/forensic_audit"
)
OUT = BASE / "matrix_containment_comparison.csv"
rows = []
for material in ("MnO", "CoO"):
    artifact = json.loads((BASE / f"{material}_u_certificate.superseding.v2.json").read_text())
    cert = artifact["certificate"]
    root = Path(
        "/home/jmc/.local/state/siestaflow/campaigns/"
        + ("lr-u-mno-afmii-stage-u-a-20260930" if material == "MnO" else "lr-u-coo-ideal-afmii-stage-u-a-20260930")
    )
    analysis = json.loads((root / cert["analysis_artifact_path"]).read_text())
    for mode, key, nominal_key in (
        ("BARE", "chi0_interval", "matrix_used_chi0"),
        ("SCREENED", "chi_interval", "matrix_used_chi"),
    ):
        intervals = cert[key]
        nominal = analysis["primary"][nominal_key]
        for i in range(2):
            for j in range(2):
                low = Fraction(intervals[i][j]["lower"])
                high = Fraction(intervals[i][j]["upper"])
                center = (low + high) / 2
                nv = Fraction(str(nominal[i][j]))
                rows.append({
                    "material": material,
                    "mode": mode,
                    "observed_row_I": i,
                    "perturbed_column_J": j,
                    "alpha_vector_nominal_eV": "[-0.02,-0.01,-0.005,0.005,0.01,0.02]",
                    "alpha_vector_exact_rational_eV": "[-1/50,-1/100,-1/200,1/200,1/100,1/50]",
                    "polynomial_degree": 3,
                    "nominal_slope": str(nv),
                    "exact_center_slope": str(center),
                    "exact_center_slope_decimal": f"{float(center):.17g}",
                    "certified_slope_lower": str(low),
                    "certified_slope_upper": str(high),
                    "nominal_contained": str(low <= nv <= high).lower(),
                })
with OUT.open("w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
print(f"wrote {len(rows)} cells to {OUT}")
