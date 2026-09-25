#!/usr/bin/env python3
"""Materialize a bounded, restart-safe MnO observable convergence set."""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / "src"))
from siestaflow_hubbard.domain.hubbard_parameter_semantics import require_dudarev_evidence

SOURCE = ROOT / "campaigns/mno_afmii_strict_lr_v3r2/results/u1153_minimal_afmii_relaxation"
CAMPAIGN = ROOT / "campaigns/mno_afmii_strict_lr_v3r2"
TARGET = CAMPAIGN / "results/mno_bounded_physical_convergence_v2"
def file_hash(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def fdf_for(template: str, name: str, k: int, mesh: int, u: float, magnetic: str, relax: bool) -> str:
    text = re.sub(r"(?m)^SystemName\s+.*$", f"SystemName MnO bounded physical convergence {name}", template)
    text = re.sub(r"(?m)^SystemLabel\s+.*$", f"SystemLabel {name}", text)
    text = re.sub(r"(?m)^MeshCutoff\s+.*$", f"MeshCutoff {mesh} Ry", text)
    text = re.sub(
        r"(?ms)%block kgrid_Monkhorst_Pack\s*.*?%endblock kgrid_Monkhorst_Pack",
        "%block kgrid_Monkhorst_Pack\n"
        f"  {k} 0 0 0.0\n  0 {k} 0 0.0\n  0 0 {k} 0.0\n"
        "%endblock kgrid_Monkhorst_Pack", text,
    )
    spins = "+5.0\n  2 +5.0" if magnetic == "FM" else "+5.0\n  2 -5.0"
    text = re.sub(r"(?ms)(%block DM\.InitSpin\s*\n\s*1 )[-+0-9.]+\s*\n\s*2 [-+0-9.]+",
                  lambda m: m.group(1) + spins, text)
    text, replaced = re.subn(r"(?m)^\s*[-+0-9.]+\s+0\.00\s*$", f"  {u:.6f} 0.00", text)
    if replaced != 1 or not re.search(r"(?im)^DFTU\.PotentialShift\s+false\s*$", text):
        raise ValueError("physical template must contain exactly one Dudarev U-J entry and PotentialShift=false")
    text = re.sub(r"(?m)^SCF\.DM\.Tolerance\s+.*$", "SCF.DM.Tolerance        1.0e-6", text)
    text = re.sub(r"(?m)^SCF\.H\.Tolerance\s+.*$", "SCF.H.Tolerance         1.0e-5 eV", text)
    text = re.sub(r"(?m)^MaxSCFIterations\s+.*$", "MaxSCFIterations        300", text)
    text = re.sub(r"(?m)^WriteMullikenPop\s+.*$", "WriteMullikenPop        1\nWriteEigenvalues       true", text)
    if relax:
        text = re.sub(r"(?m)^MD\.MaxForceTol\s+.*$", "MD.MaxForceTol          0.01 eV/Ang", text)
        text = re.sub(r"(?m)^MD\.MaxStressTol\s+.*$", "MD.MaxStressTol         0.02 GPa", text)
    return text


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Prepare MnO observables with an independently justified Dudarev Ueff")
    parser.add_argument("--ueff-evidence", required=True, type=Path,
                        help="JSON with parameter_kind=Ueff_Dudarev, source_parameter_kind, value_eV, derivation, and source_reference")
    args = parser.parse_args(argv)
    evidence = json.loads(args.ueff_evidence.read_text(encoding="utf-8"))
    u_central, u_interval = require_dudarev_evidence(evidence)
    if TARGET.exists():
        raise SystemExit(f"Refusing to overwrite existing convergence evidence: {TARGET}")
    template_static = (SOURCE / "afmii_single_point/siesta.fdf").read_text(encoding="utf-8")
    template_relax = (SOURCE / "siesta.fdf").read_text(encoding="utf-8")
    cases = []
    for k in (4, 6, 8):
        for magnetic in ("AFMII", "FM"):
            cases.append({"name": f"k{k}_mesh400_{magnetic.lower()}", "k": k, "mesh": 400,
                          "u": u_central, "magnetic": magnetic, "relax": False})
    for mesh in (200, 300):
        for magnetic in ("AFMII", "FM"):
            cases.append({"name": f"k6_mesh{mesh}_{magnetic.lower()}", "k": 6, "mesh": mesh,
                          "u": u_central, "magnetic": magnetic, "relax": False})
    for u, key in (((u_interval[0], "low"), (u_interval[1], "high")) if u_interval else ()):
        for magnetic in ("AFMII", "FM"):
            cases.append({"name": f"u_{key}_k6_mesh400_{magnetic.lower()}", "k": 6, "mesh": 400,
                          "u": u, "magnetic": magnetic, "relax": False})
    cases.append({"name": "relax_k8_mesh400_central_u", "k": 8, "mesh": 400,
                  "u": u_central, "magnetic": "AFMII", "relax": True})

    TARGET.mkdir(parents=True)
    for case in cases:
        directory = TARGET / case["name"]
        directory.mkdir()
        template = template_relax if case["relax"] else template_static
        fdf = fdf_for(template, case["name"], case["k"], case["mesh"], case["u"],
                      case["magnetic"], case["relax"])
        (directory / "siesta.fdf").write_text(fdf, encoding="utf-8", newline="\n")
        for pseudo in ("Mn.psml", "O.psml"):
            (directory / pseudo).write_bytes((SOURCE / "afmii_single_point" / pseudo).read_bytes())
        case["directory"] = str(directory.relative_to(ROOT))
        case["fdf_sha256"] = file_hash(directory / "siesta.fdf")
    plan = {
        "schema": "mno-bounded-physical-convergence-v2",
        "purpose": "Converge MnO observables for an explicitly sourced Dudarev Ueff.",
        "parameter_kind": "Ueff_Dudarev",
        "Ueff_interval_eV": u_interval,
        "central_Ueff_eV": u_central,
        "ueff_evidence_sha256": file_hash(args.ueff_evidence),
        "ueff_derivation": evidence["derivation"],
        "ueff_source_parameter_kind": evidence["source_parameter_kind"],
        "ueff_source_reference": evidence["source_reference"],
        "fixed_projector": {"method": 2, "cutoff_norm": 0.90, "omega_bohr": 0.05},
        "fixed_basis": {"size": "DZP", "energy_shift_ry": 0.005, "split_norm": 0.15},
        "fixed_cell_for_single_points": "the saved four-atom AFM-II relaxed geometry used by the prior screen",
        "scf_tolerances": {"dm": "1.0e-6", "hamiltonian_ev": "1.0e-5"},
        "comparisons": ["k-grid at 400 Ry", "mesh cutoff at 6x6x6", "Ueff interval endpoints if supplied", "one tighter AFM-II variable-cell relaxation"],
        "interpretation": "Record energy ordering, local spin, band gap if present, volume and residual forces/stress. No artificial percentage pass cutoff; report grid trends and limitations. This does not converge basis or U with supercell.",
        "source_fdf_sha256": file_hash(SOURCE / "afmii_single_point/siesta.fdf"),
        "Mn_psml_sha256": file_hash(SOURCE / "afmii_single_point/Mn.psml"),
        "O_psml_sha256": file_hash(SOURCE / "afmii_single_point/O.psml"),
        "cases": cases,
    }
    (TARGET / "convergence-plan.json").write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PREPARED", "target": str(TARGET), "cases": len(cases),
                      "parameter_kind": "Ueff_Dudarev", "central_Ueff_eV": u_central,
                      "Ueff_interval_eV": u_interval}, indent=2))


if __name__ == "__main__":
    main()
