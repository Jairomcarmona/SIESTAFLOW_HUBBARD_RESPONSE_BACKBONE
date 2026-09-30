"""Render numeric Stage U-B tables from frozen certificates and policy."""
from __future__ import annotations

from decimal import Decimal, localcontext
from fractions import Fraction
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[3]
STAGE_DIR = Path(__file__).resolve().parent
AUDIT_DIR = ROOT / "benchmarks" / "lr_u" / "forensic_audit"
PROTOCOL = STAGE_DIR / "STAGE_U_B_REPEATABILITY_PROTOCOL_20260930.md"
sys.path.insert(0, str(ROOT / "src"))
from siestaflow_hubbard.domain.u_certification import interval_half_width


def _decimal(value: Fraction, places: int = 9) -> str:
    with localcontext() as context:
        context.prec = max(40, places + len(str(abs(value.numerator))) + 6)
        number = Decimal(value.numerator) / Decimal(value.denominator)
        return f"{number:.{places}f}"


def _maximum(values: dict[str, object]) -> Fraction | None:
    if not values:
        return None
    return max(Fraction(str(value)) for value in values.values())


def _load_material(item: dict[str, object], precision_tolerance: Fraction,
                   sensitivity_tolerance: Fraction) -> dict[str, object]:
    name = str(item["material"])
    root = Path(str(item["campaign_root"]))
    if name in {"MnO", "CoO"}:
        wrapper = json.loads((AUDIT_DIR / f"{name}_u_certificate.superseding.v2.json").read_text(encoding="utf-8"))
        cert = wrapper["certificate"]
        if wrapper.get("new_scientific_digest") != cert.get("certificate_scientific_sha256"):
            raise ValueError(f"{name}: superseding certificate digest mismatch")
    else:
        cert_path = root / str(item["certificate"]["path"])
        raw = cert_path.read_bytes()
        from hashlib import sha256
        if sha256(raw).hexdigest() != item["certificate"]["file_sha256"]:
            raise ValueError(f"{name}: frozen certificate file digest mismatch")
        cert = json.loads(raw)
    analysis_path = root / str(cert["analysis_artifact_path"])
    analysis = json.loads(analysis_path.read_text(encoding="utf-8"))
    policy = analysis.get("estimator_policy", {})
    gate = analysis.get("sensitivity_gate", {})
    if policy.get("u_precision_tolerance_eV") is not None or policy.get("sensitivity_tolerance_eV") is not None:
        raise ValueError(f"{name}: U-A tolerance fields must stay historical/null")
    intervals = cert["u_interval_by_site"]
    nominals = [Fraction(str(value)) for value in cert["nominal_u_by_site_eV"]]
    rows = []
    for nominal, interval in zip(nominals, intervals):
        lower, upper = Fraction(interval["lower"]), Fraction(interval["upper"])
        if not lower <= nominal <= upper:
            raise ValueError(f"{name}: nominal U lies outside its certificate")
        rows.append({
            "nominal": nominal, "lower": lower, "upper": upper,
            "width": upper - lower, "half": interval_half_width(lower, upper),
            "center": (lower + upper) / 2,
            "lower_distance": nominal - lower,
            "upper_distance": upper - nominal,
        })
    old_half = max(max(row["lower_distance"], row["upper_distance"]) for row in rows)
    new_half = max(row["half"] for row in rows)
    estimator = gate.get("estimator_sensitivity_eV", {})
    window = gate.get("window_sensitivity_eV", {})
    estimator_max, window_max = _maximum(estimator), _maximum(window)
    ready = (
        cert.get("certificate_status") in {"CERTIFIED", "CERTIFIED_WITH_FALLBACK"}
        and new_half <= precision_tolerance
        and estimator_max is not None and estimator_max <= sensitivity_tolerance
        and window_max is not None and window_max <= sensitivity_tolerance
    )
    return {
        "name": name, "certificate": cert, "rows": rows,
        "old_half": old_half, "new_half": new_half,
        "old_margin": precision_tolerance - old_half,
        "new_margin": precision_tolerance - new_half,
        "estimator": estimator, "window": window,
        "estimator_max": estimator_max, "window_max": window_max,
        "status": "READY_FOR_STAGE_UB" if ready else "PROTOCOL_REVIEW_REQUIRED",
    }


def render_baseline() -> str:
    policy = json.loads((STAGE_DIR / "precision_policy.json").read_text(encoding="utf-8"))
    precision_tolerance = Fraction(policy["u_precision_tolerance_eV"])
    sensitivity_tolerance = Fraction(policy["sensitivity_tolerance_eV"])
    frozen = json.loads((AUDIT_DIR / "frozen_evidence.json").read_text(encoding="utf-8"))
    materials = [_load_material(item, precision_tolerance, sensitivity_tolerance)
                 for item in frozen["materials"]]
    lines = [
        "The following tables are generated from the frozen certificate artifacts, source analyses, and `precision_policy.json`.",
        "The historical field reproduces the former nominal-to-endpoint deviation calculation; derived half-width is exactly `(upper-lower)/2`.",
        "",
        "| Material | Certificate half-width | Estimator sensitivity | Candidate precision policy | Repeatability budget | Stage U-B status |",
        "|---|---:|---:|---|---|---|",
    ]
    for material in materials:
        margin = "/".join(_decimal(precision_tolerance - row["half"], 9) for row in material["rows"])
        lines.append(
            f"| {material['name']} | {_decimal(material['new_half'], 9)} eV | "
            f"{_decimal(material['estimator_max'], 9)} eV/site | "
            f"U-B: ±{policy['u_precision_tolerance_eV']} eV/site; sensitivity ±{policy['sensitivity_tolerance_eV']} eV/site; "
            f"U-A fields null | R≤{policy['u_precision_tolerance_eV']}; cert margins {margin} eV | `{material['status']}` |"
        )
    lines.extend([
        "",
        "Nominal values, exact interval endpoints, endpoint-derived half-widths, interval centers, and separate nominal-to-endpoint distances (sites 0/1; eV):",
        "",
        "| Material | Nominal U-A (site 0 / 1) | Interval site 0 | Center 0 | Half-width 0 | Nominal lower / upper distance 0 | Interval site 1 | Center 1 | Half-width 1 | Nominal lower / upper distance 1 |",
        "|---|---|---:|---:|---:|---|---|---:|---:|---|",
    ])
    for material in materials:
        row0, row1 = material["rows"]
        def interval(row):
            return f"[{_decimal(row['lower'], 9)}, {_decimal(row['upper'], 9)}]"
        nominal = " / ".join(_decimal(row["nominal"], 9) for row in material["rows"])
        distance0 = f"{_decimal(row0['lower_distance'], 9)} / {_decimal(row0['upper_distance'], 9)}"
        distance1 = f"{_decimal(row1['lower_distance'], 9)} / {_decimal(row1['upper_distance'], 9)}"
        lines.append(
            f"| {material['name']} | {nominal} | {interval(row0)} | {_decimal(row0['center'], 9)} | "
            f"{_decimal(row0['half'], 9)} | {distance0} | {interval(row1)} | {_decimal(row1['center'], 9)} | "
            f"{_decimal(row1['half'], 9)} | {distance1} |"
        )
    lines.extend([
        "",
        "Per-site estimator and window sensitivities (eV/site):",
        "",
        "| Material | Estimator site 0 / site 1 | Window site 0 / site 1 |",
        "|---|---|---|",
    ])
    for material in materials:
        estimator = material["estimator"]
        window = material["window"]
        values = lambda data: " / ".join(_decimal(Fraction(str(data[str(i)])), 9) for i in range(2))
        lines.append(f"| {material['name']} | {values(estimator)} | {values(window)} |")
    lines.extend([
        "",
        "Before/after half-width derivation (eV):",
        "",
        "| Material | Old reported half-width | Derived half-width | Old margin | Derived margin | Changed? |",
        "|---|---:|---:|---:|---:|---|",
    ])
    for material in materials:
        lines.append(
            f"| {material['name']} | {_decimal(material['old_half'], 12)} | {_decimal(material['new_half'], 12)} | "
            f"{_decimal(material['old_margin'], 12)} | {_decimal(material['new_margin'], 12)} | "
            f"{'yes' if material['old_half'] != material['new_half'] else 'no'} |"
        )
    return "\n".join(lines)


def main() -> None:
    text = PROTOCOL.read_text(encoding="utf-8")
    start = "<!-- BEGIN GENERATED BASELINE: render_stage_u_b_protocol.py -->"
    end = "<!-- END GENERATED BASELINE -->"
    if text.count(start) != 1 or text.count(end) != 1:
        raise SystemExit("Stage U-B generated baseline markers are missing or duplicated")
    block = f"{start}\n{render_baseline()}\n{end}"
    text = re.sub(re.escape(start) + r"[\s\S]*?" + re.escape(end), block, text, count=1)
    text = text.replace("{{U_TOL}}", str(json.loads((STAGE_DIR / "precision_policy.json").read_text())["u_precision_tolerance_eV"]))
    text = text.replace("{{SENS_TOL}}", str(json.loads((STAGE_DIR / "precision_policy.json").read_text())["sensitivity_tolerance_eV"]))
    PROTOCOL.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
