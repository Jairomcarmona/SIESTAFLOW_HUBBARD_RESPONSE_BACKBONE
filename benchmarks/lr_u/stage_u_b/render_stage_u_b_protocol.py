"""Render Stage U-B's self-contained A0/B1/B2/B3 policy."""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
POLICY = ROOT / "repeatability_policy.json"
PRECISION = ROOT / "precision_policy.json"
PROTOCOL = ROOT / "STAGE_U_B_REPEATABILITY_PROTOCOL_20260930.md"
START = "<!-- BEGIN GENERATED POLICY -->"
END = "<!-- END GENERATED POLICY -->"


def render() -> str:
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    precision = json.loads(PRECISION.read_text(encoding="utf-8"))
    if policy.get("runs_per_material") != ["A0", "B1", "B2", "B3"]:
        raise ValueError("Stage U-B requires one A0 anchor and exactly B1/B2/B3")
    if policy.get("replica_runs") != ["B1", "B2", "B3"] or policy.get("comparator_run") != "A0":
        raise ValueError("invalid A0 comparison contract")
    if precision.get("u_precision_tolerance_eV") != "0.020" or precision.get("sensitivity_tolerance_eV") != "0.020":
        raise ValueError("Stage U-B numeric gates must remain 0.020 eV/site")
    runs = ", ".join(policy["runs_per_material"])
    seq = " → ".join(policy["runs_per_material"])
    materials = ", ".join(policy["materials"])
    order = "\n".join(f"{i}. {name}" for i, name in enumerate(policy["run_order"], start=1))
    independent = ", ".join(policy["campaign_independence"])
    return "\n".join([
        f"Runs por material: **{runs}**; comparador: **A0**; tres réplicas: **B1/B2/B3**.",
        f"Materiales: {materials}. Orden preregistrado:", "", order, "",
        f"Campañas por run: UUID/raíz/referencia/DM/respuestas/análisis/certificación independientes ({independent}).",
        f"Cada run contiene {policy['nodes_per_run']} nodos SIESTA. Total: {policy['nodes_per_run'] * len(policy['run_order'])} nodos para {len(policy['run_order'])} campañas.",
        "",
        "```text",
        "delta_repeat[s,j] = abs(U_Bj[s] - U_A0[s])",
        "R[s] = max(delta_repeat[s,B1], delta_repeat[s,B2], delta_repeat[s,B3])",
        "envelope[s] = [U_A0[s] - R[s], U_A0[s] + R[s]]",
        "```",
        "",
        f"Gates por sitio, sin cambios: semiancho certificado ≤ {precision['u_precision_tolerance_eV']} eV; "
        f"sensibilidad de estimador ≤ {precision['sensitivity_tolerance_eV']} eV; "
        f"sensibilidad de ventana ≤ {precision['sensitivity_tolerance_eV']} eV; "
        f"R ≤ {precision['u_precision_tolerance_eV']} eV.",
        f"DAG exigido en cada run: `{' → '.join(policy['dag'])}`.",
        f"Ejecución: {policy['execution']['backend']}, {policy['execution']['mpi_ranks']} rangos MPI, "
        f"máximo {policy['execution']['max_concurrent_siesta']} SIESTA simultánea.",
        "",
        "No hay ninguna dependencia operativa de U-A, campaigns, locks, canarios ni outputs históricos.",
    ])


def main() -> None:
    text = PROTOCOL.read_text(encoding="utf-8")
    if text.count(START) != 1 or text.count(END) != 1:
        raise SystemExit("generated policy markers missing or duplicated")
    before, tail = text.split(START, 1)
    _, after = tail.split(END, 1)
    PROTOCOL.write_text(before + START + "\n" + render() + "\n" + END + after, encoding="utf-8")


if __name__ == "__main__":
    main()
