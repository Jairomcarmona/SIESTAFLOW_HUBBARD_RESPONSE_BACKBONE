"""Material-agnostic finite-difference SIESTA linear-response U core."""
from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np

RUNS = (
    ("00_REFERENCE", "REFERENCE", None, 0.0),
    ("10_A_BARE_MINUS", "BARE", "A", -0.05),
    ("11_A_BARE_PLUS", "BARE", "A", 0.05),
    ("12_A_SCREENED_MINUS", "SCREENED", "A", -0.05),
    ("13_A_SCREENED_PLUS", "SCREENED", "A", 0.05),
    ("20_B_BARE_MINUS", "BARE", "B", -0.05),
    ("21_B_BARE_PLUS", "BARE", "B", 0.05),
    ("22_B_SCREENED_MINUS", "SCREENED", "B", -0.05),
    ("23_B_SCREENED_PLUS", "SCREENED", "B", 0.05),
)


def load_config(path: Path) -> dict:
    return json.loads(Path(path).read_text())


def translations():
    return [(i, j, k) for i in range(2) for j in range(2) for k in range(2)]


def build_atoms(config: dict):
    """Generate the 2x2x2 magnetic supercell and deterministic site map."""
    atoms, sites = [], []
    label_prefix = config["correlated"]["label_prefix"]
    for t_index, (i, j, k) in enumerate(translations()):
        for parent in config["parent_atoms"]:
            role, sublattice, frac = parent["role"], parent["sublattice"], parent["fractional"]
            fsc = [(frac[d] + (i, j, k)[d]) / 2.0 for d in range(3)]
            if sublattice in {"A", "B"}:
                index = 2 * t_index + (0 if sublattice == "A" else 1)
                label = f"{label_prefix}{index:02d}"
                sites.append({"index": index, "label": label, "parent_sublattice": sublattice,
                              "parent_site": role, "translation": [i, j, k],
                              "fractional_supercell": fsc})
                atoms.append({"label": label, "sublattice": sublattice, "fractional": fsc})
            else:
                atoms.append({"label": config["oxygen"]["label"], "sublattice": "O", "fractional": fsc})
    return atoms, sites


def _f(value: float) -> str:
    return f"{value:.8f}"


def projector_policy(projector: dict) -> tuple[float, float | None]:
    """Return explicit radius and optional automatic cutoff norm."""
    policy = projector["cutoff_policy"]
    if policy == "explicit_rc":
        return float(projector["rc_bohr"]), None
    if policy == "cutoff_norm":
        return 0.0, float(projector["cutoff_norm"])
    raise ValueError(f"Unknown Hubbard projector cutoff policy: {policy}")


def render_fdf(config: dict, run_id: str, mode: str, target: str | None, alpha: float, atoms: list[dict]) -> str:
    corr = config["correlated"]
    element, z, prefix = corr["element"], corr["atomic_number"], corr["label_prefix"]
    labels = [f"{prefix}{i:02d}" for i in range(16)]
    p = config["projector"]
    rc_bohr, cutoff_norm = projector_policy(p)
    lines = [f"SystemName {config['material']} PBE LR-U SC222", f"SystemLabel {run_id}",
             "NumberOfAtoms 32", "NumberOfSpecies 17", "%block ChemicalSpeciesLabel"]
    lines += [f"  {i + 1} {z} {label}" for i, label in enumerate(labels)]
    lines += [f"  17 {config['oxygen']['atomic_number']} {config['oxygen']['label']}", "%endblock ChemicalSpeciesLabel", "",
              f"LatticeConstant {config['lattice_constant_ang']:.4f} Ang", "%block LatticeVectors"]
    lines += ["  " + " ".join(f"{x:.6f}" for x in row) for row in config["lattice_vectors_supercell"]]
    lines += ["%endblock LatticeVectors", "AtomicCoordinatesFormat Fractional", "%block AtomicCoordinatesAndAtomicSpecies"]
    for atom_index, atom in enumerate(atoms, 1):
        species = labels.index(atom["label"]) + 1 if atom["sublattice"] in {"A", "B"} else 17
        lines.append(f"  {_f(atom['fractional'][0])} {_f(atom['fractional'][1])} {_f(atom['fractional'][2])} {species} # {atom['label']}")
    lines += ["%endblock AtomicCoordinatesAndAtomicSpecies", "", "XC.Functional GGA", "XC.Authors PBE", "Spin polarized",
              "PAO.BasisSize DZP", "PAO.EnergyShift 0.005 Ry", "PAO.SplitNorm 0.15", "PAO.BasisType split",
              "MeshCutoff 200 Ry", "%block kgrid_Monkhorst_Pack", "  3 0 0 0.0", "  0 3 0 0.0", "  0 0 3 0.0", "%endblock kgrid_Monkhorst_Pack",
              "OccupationFunction FD", "ElectronicTemperature 300 K", "MD.NumCGsteps 0"]
    controls = config.get("output_controls", {})
    if controls.get("write_dm", False): lines.append("Write.DM true")
    if controls.get("write_mulliken", False): lines.append("WriteMullikenPop 1")
    lines.append("%block DM.InitSpin")
    for atom_index, atom in enumerate(atoms, 1):
        spin = config["initial_moments"][atom["sublattice"]]
        lines.append(f"  {atom_index} {spin:+.1f}")
    lines += ["%endblock DM.InitSpin", "%block DFTU.Proj"]
    for label in labels:
        shift = alpha if label == target else 0.0
        lines += [f"  {label} 1", "  3 2", f"  {shift:+.4f} 0.0000", f"  {rc_bohr:.4f} {p['omega']:.4f}"]
    lines += ["%endblock DFTU.Proj", f"DFTU.ProjectorGenerationMethod {p['method']}"]
    if cutoff_norm is not None:
        lines.append(f"DFTU.CutoffNorm {cutoff_norm:.2f}")
    lines.append("DFTU.PotentialShift true")
    if mode == "REFERENCE":
        lines += ["DFTU.FirstIteration false", "SCF.MustConverge T", "SCF.Mix Hamiltonian", "SCF.Mixer.Method Pulay", "SCF.Mixer.Weight 0.05", "SCF.Mixer.History 8", "SCF.DM.Converge T", "SCF.H.Converge T", "SCF.DM.Tolerance 1.0e-5", "SCF.H.Tolerance 1.0e-4 eV", "MaxSCFIterations 300", "DM.UseSaveDM false"]
    elif mode == "BARE":
        # This is the source-audited SIESTA 5.4.2 first-Hamiltonian response:
        # exactly one diagonalisation with Hamiltonian mixing.  A density-mixed
        # two-step run cannot be parsed by the locked BARE observation profile.
        lines += ["DFTU.FirstIteration true", "MaxSCFIterations 1", "SCF.MustConverge F", "SCF.Mix Hamiltonian", "SCF.Mixer.Method Pulay", "SCF.Mixer.Weight 0.05", "SCF.Mixer.History 8", "DM.UseSaveDM true"]
    else:
        lines += ["DFTU.FirstIteration true", "SCF.MustConverge T", "SCF.Mix Hamiltonian", "SCF.Mixer.Method Pulay", "SCF.Mixer.Weight 0.05", "SCF.Mixer.History 8", "SCF.DM.Converge T", "SCF.H.Converge T", "SCF.DM.Tolerance 1.0e-5", "SCF.H.Tolerance 1.0e-4 eV", "MaxSCFIterations 300", "DM.UseSaveDM true"]
    return "\n".join(lines) + "\n"


def write_campaign(config: dict, root: Path) -> None:
    root = Path(root); atoms, sites = build_atoms(config)
    (root / "geometry").mkdir(parents=True, exist_ok=True)
    parent = {"lattice_constant_ang": config["lattice_constant_ang"], "lattice_vectors": config["lattice_vectors_parent"], "atoms": config["parent_atoms"]}
    (root / "geometry" / "parent_magnetic_cell.json").write_text(json.dumps(parent, indent=2) + "\n")
    (root / "geometry" / "site_map.json").write_text(json.dumps(sites, indent=2) + "\n")
    (root / "geometry" / "supercell_222.fdf").write_text(render_fdf(config, "GEOMETRY_ONLY", "REFERENCE", None, 0.0, atoms))
    records = []
    for run_id, mode, rep, alpha in RUNS:
        target = config["representatives"].get(rep) if rep else None
        directory = root / "runs" / run_id; directory.mkdir(parents=True, exist_ok=True)
        record = {"id": run_id, "mode": mode, "target": target, "alpha_ev": alpha,
                  "parent_dm": "00_REFERENCE/00_REFERENCE.DM" if mode != "REFERENCE" else None}
        (directory / "run.json").write_text(json.dumps(record, indent=2) + "\n")
        (directory / "siesta.fdf").write_text(render_fdf(config, run_id, mode, target, alpha, atoms))
        records.append(record)
    (root / "runs" / "manifest.json").write_text(json.dumps(records, indent=2) + "\n")


def parse_events(text: str, n_sites: int):
    current, result, scf = None, [], 1
    for line in text.splitlines():
        match = re.match(r"\s*scf:\s+(\d+)", line)
        if match: scf = int(match.group(1)) + 1
        match = re.search(r"siesta:\s+iscf\s*=\s*(\d+)", line)
        if match: scf = int(match.group(1))
        if "hubbard_term: recalculating local occupations" in line:
            if current is not None: result.append(current)
            current = {"scf": scf, "occupations": []}
        elif current is not None and "Occupations:" in line:
            values = re.findall(r"[-+]?(?:\d*\.\d+|\d+)", line.split("Occupations:", 1)[1])
            if len(values) != 3: raise ValueError(f"unrecognized Occupations line: {line}")
            current["occupations"].append(float(values[2]))
    if current is not None: result.append(current)
    return [event for event in result if len(event["occupations"]) == n_sites]


def select_occupations(path: Path, mode: str, n_sites: int = 16):
    path = Path(path); text = path.read_text(errors="ignore")
    err = (path.parent / "siesta.err").read_text(errors="ignore") if (path.parent / "siesta.err").is_file() else ""
    status = (text + "\n" + err).lower()
    if mode in {"REFERENCE", "SCREENED"} and ("scf_not_conv" in status or "scf: not converged" in status):
        raise RuntimeError(f"unconverged {mode}: {path}")
    if not ((path.parent / "0_NORMAL_EXIT").is_file() or "siesta: normal completion" in status):
        raise RuntimeError(f"normal completion missing: {path}")
    events = parse_events(text, n_sites)
    if not events: raise RuntimeError(f"no complete {n_sites}-site Occupations event: {path}")
    if mode == "BARE":
        candidates = [event for event in events if event["scf"] == 2]
        if len(candidates) != 1: raise RuntimeError(f"ambiguous BARE event: {path}")
        return candidates[0]["occupations"]
    return events[-1]["occupations"]


def translated_column(vector, site_map: list[dict], translation: tuple[int, int, int]):
    by_key = {(tuple(site["translation"]), site["parent_sublattice"]): site["index"] for site in site_map}
    out = np.empty(len(vector), dtype=float)
    for site in site_map:
        t = tuple(site["translation"]); sub = site["parent_sublattice"]
        destination = ((t[0] + translation[0]) % 2, (t[1] + translation[1]) % 2, (t[2] + translation[2]) % 2)
        out[by_key[(destination, sub)]] = vector[site["index"]]
    return out


def reconstruct(a_column, b_column, site_map: list[dict]):
    n = len(site_map); matrix = np.empty((n, n), dtype=float)
    by_index = {site["index"]: site for site in site_map}
    for column in range(n):
        site = by_index[column]
        source = a_column if site["parent_sublattice"] == "A" else b_column
        matrix[:, column] = translated_column(np.asarray(source, dtype=float), site_map, tuple(site["translation"]))
    return matrix


def magnetic_state(path: Path, site_map: list[dict]):
    text = Path(path).read_text(errors="ignore")
    blocks = re.findall(r"Mulliken Atomic Populations:\s*\nAtom #.*?\n(.*?)(?:\n-+\n\s*Total|\Z)", text, re.S)
    if not blocks: raise RuntimeError("REFERENCE_STATE_INVALID: final Mulliken magnetic table missing")
    spins = {}
    for line in blocks[-1].splitlines():
        match = re.match(r"\s*\d+\s+[-+0-9.Ee]+\s+[-+0-9.Ee]+\s+([-+0-9.Ee]+)\s+(\S+)", line)
        if match: spins[match.group(2)] = float(match.group(1))
    expected = {site["label"]: site["parent_sublattice"] for site in site_map}
    if set(expected) - set(spins): raise RuntimeError("REFERENCE_STATE_INVALID: Mn moments incomplete")
    a = np.array([spins[label] for label, sub in expected.items() if sub == "A"])
    b = np.array([spins[label] for label, sub in expected.items() if sub == "B"])
    if np.any(np.abs(a) < 1e-3) or np.any(np.abs(b) < 1e-3) or not np.all(np.sign(a) == np.sign(a[0])) or not np.all(np.sign(b) == np.sign(b[0])) or np.sign(a[0]) == np.sign(b[0]):
        raise RuntimeError("REFERENCE_STATE_INVALID: AFM A/B signs not preserved")
    if abs(float(a.sum() + b.sum())) > max(0.25, 0.10 * float(np.abs(np.r_[a, b]).sum())):
        raise RuntimeError("REFERENCE_STATE_INVALID: Mn magnetization not compensated")
    return {"A_moments": a.tolist(), "B_moments": b.tolist(), "Mn_total_moment": float(a.sum() + b.sum())}


def analyze(raw: dict, config: dict, site_map: list[dict]):
    n = len(site_map); required = [run[0] for run in RUNS if run[1] != "REFERENCE"]
    u_key = f"U_{config['correlated']['element']}_eV"
    result = {"campaign_id": config["campaign_id"], "material": config["material"], "status": "FAIL", "matrix_dimension": n,
              "rank_chi0": None, "rank_chi": None, "condition_chi0": None, "condition_chi": None,
              "antisymmetry_chi0": None, "antisymmetry_chi": None, u_key: None,
              "U_A_mean_eV": None, "U_B_mean_eV": None, "U_A_std_eV": None, "U_B_std_eV": None,
              "max_site_deviation_from_mean_eV": None, "U_by_site_eV": {}, "linearity": {}, "notes": []}
    missing = [run for run in required + ["00_REFERENCE"] if run not in raw]
    if missing:
        result["notes"].append("missing occupations: " + ", ".join(missing)); return result, None
    d = lambda plus, minus: (np.asarray(raw[plus]) - np.asarray(raw[minus])) / (2 * config["alpha_ev"])
    chi0_raw = reconstruct(d("11_A_BARE_PLUS", "10_A_BARE_MINUS"), d("21_B_BARE_PLUS", "20_B_BARE_MINUS"), site_map)
    chi_raw = reconstruct(d("13_A_SCREENED_PLUS", "12_A_SCREENED_MINUS"), d("23_B_SCREENED_PLUS", "22_B_SCREENED_MINUS"), site_map)
    chi0 = (chi0_raw + chi0_raw.T) / 2; chi = (chi_raw + chi_raw.T) / 2
    result.update(antisymmetry_chi0=float(np.linalg.norm(chi0_raw - chi0_raw.T) / max(np.linalg.norm(chi0_raw), 1e-16)),
                  antisymmetry_chi=float(np.linalg.norm(chi_raw - chi_raw.T) / max(np.linalg.norm(chi_raw), 1e-16)),
                  rank_chi0=int(np.linalg.matrix_rank(chi0)), rank_chi=int(np.linalg.matrix_rank(chi)),
                  condition_chi0=float(np.linalg.cond(chi0)), condition_chi=float(np.linalg.cond(chi)))
    ref = np.asarray(raw["00_REFERENCE"])
    pairs = {"A_BARE": ("11_A_BARE_PLUS", "10_A_BARE_MINUS"), "A_SCREENED": ("13_A_SCREENED_PLUS", "12_A_SCREENED_MINUS"), "B_BARE": ("21_B_BARE_PLUS", "20_B_BARE_MINUS"), "B_SCREENED": ("23_B_SCREENED_PLUS", "22_B_SCREENED_MINUS")}
    for key, (plus, minus) in pairs.items():
        dp, dm = np.asarray(raw[plus]) - ref, np.asarray(raw[minus]) - ref
        den = max(np.linalg.norm(dp - dm), 1.0e-12)
        result["linearity"][key] = float(np.linalg.norm(dp + dm) / den)
    payload = {"chi0_raw": chi0_raw, "chi_raw": chi_raw, "chi0": chi0, "chi": chi}
    if result["rank_chi0"] != n or result["rank_chi"] != n:
        result["notes"].append("SCIENTIFIC_ANALYSIS_FAILED: SINGULAR_RESPONSE_MATRIX"); return result, payload
    kernel = direct_kernel(chi0, chi); site_u = np.diag(kernel)
    a_indices = [site["index"] for site in site_map if site["parent_sublattice"] == "A"]
    b_indices = [site["index"] for site in site_map if site["parent_sublattice"] == "B"]
    a, b = site_u[a_indices], site_u[b_indices]
    result.update(status="PASS", **{u_key: float((a.mean() + b.mean()) / 2)}, U_A_mean_eV=float(a.mean()), U_B_mean_eV=float(b.mean()), U_A_std_eV=float(a.std()), U_B_std_eV=float(b.std()), max_site_deviation_from_mean_eV=float(np.max(np.abs(site_u - site_u.mean()))), U_by_site_eV={site["label"]: float(site_u[site["index"]]) for site in site_map}, inversion_residuals={"chi0": float(np.linalg.norm(np.linalg.inv(chi0) @ chi0 - np.eye(n))), "chi": float(np.linalg.norm(np.linalg.inv(chi) @ chi - np.eye(n)) )})
    payload["kernel"] = kernel; payload["site_u"] = site_u
    return result, payload


def direct_kernel(chi0: np.ndarray, chi: np.ndarray) -> np.ndarray:
    """Direct LR kernel; intentionally no pseudoinverse fallback."""
    n = chi0.shape[0]
    if np.linalg.matrix_rank(chi0) != n or np.linalg.matrix_rank(chi) != n:
        raise ValueError("response matrix is rank deficient; direct inversion impossible")
    return np.linalg.inv(chi0) - np.linalg.inv(chi)
