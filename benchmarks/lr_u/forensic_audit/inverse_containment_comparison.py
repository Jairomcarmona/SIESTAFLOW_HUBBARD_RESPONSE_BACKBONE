"""Exact nominal-vs-box inverse-diagonal containment after chi containment."""
from __future__ import annotations

import csv
import json
from fractions import Fraction
from pathlib import Path

BASE = Path(
    "/mnt/c/Users/Jairo/Downloads/"
    "SIESTAFLOW_HUBBARD_RESPONSE_BACKBONE_V0_1_0/benchmarks/lr_u/forensic_audit"
)
rows = []
for material in ("MnO", "CoO"):
    artifact = json.loads((BASE / f"{material}_u_certificate.superseding.v2.json").read_text())
    cert = artifact["certificate"]
    analysis_root = Path(
        "/home/jmc/.local/state/siestaflow/campaigns/"
        + ("lr-u-mno-afmii-stage-u-a-20260930" if material == "MnO" else "lr-u-coo-ideal-afmii-stage-u-a-20260930")
    )
    analysis = json.loads((analysis_root / cert["analysis_artifact_path"]).read_text())
    for mode, interval_key, nominal_key in (
        ("BARE", "chi0_interval", "matrix_used_chi0"),
        ("SCREENED", "chi_interval", "matrix_used_chi"),
    ):
        boxes = cert[interval_key]
        nominal = [[Fraction(str(value)) for value in row] for row in analysis["primary"][nominal_key]]
        det = Fraction(cert["regularity_certificates"]["chi0" if mode == "BARE" else "chi"]["determinant_vertices_min"]), Fraction(cert["regularity_certificates"]["chi0" if mode == "BARE" else "chi"]["determinant_vertices_max"])
        assert det[0] > 0
        det_central = nominal[0][0] * nominal[1][1] - nominal[0][1] * nominal[1][0]
        for site in (0, 1):
            numerator_index = (1, 1) if site == 0 else (0, 0)
            nbox = (Fraction(boxes[numerator_index[0]][numerator_index[1]]["lower"]), Fraction(boxes[numerator_index[0]][numerator_index[1]]["upper"]))
            candidates = [n / d for n in nbox for d in det]
            lower, upper = min(candidates), max(candidates)
            inverse_nominal = nominal[numerator_index[0]][numerator_index[1]] / det_central
            rows.append({
                "material": material,
                "mode": mode,
                "site": site,
                "determinant_nominal": str(det_central),
                "determinant_interval_lower": str(det[0]),
                "determinant_interval_upper": str(det[1]),
                "nominal_inverse_diagonal": str(inverse_nominal),
                "certified_inverse_diagonal_lower": str(lower),
                "certified_inverse_diagonal_upper": str(upper),
                "nominal_contained": str(lower <= inverse_nominal <= upper).lower(),
            })
out = BASE / "inverse_containment_comparison.csv"
with out.open("w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
print(f"wrote {len(rows)} inverse diagonal checks to {out}")
