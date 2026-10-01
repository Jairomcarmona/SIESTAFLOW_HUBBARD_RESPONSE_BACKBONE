#!/usr/bin/env python3
"""Recreate FeO band observables from the converged SIESTA HSX files.

SIESTA's HSX eigenvalues are stored in Rydberg and the HSX reader used by the
original postprocessor returns eigenvalues relative to the HSX Fermi level.
This module makes both conventions explicit: ``energy_abs_ev`` is absolute,
while ``energy_rel_ev`` is E - Ef and is what the plot uses.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import re
import struct
from pathlib import Path
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parent
PBE = ROOT / "feo_pbe" / "seedDM_converged"
LRU = ROOT / "feo_lru_fullU_restart_from_near_converged_DM"
OUT = ROOT / "feo_seekpath_bands"
ROUTE_FILE = OUT / "seekpath_feo_high_symmetry_route.json"
N_INTERVALS_PER_SEGMENT = 40
ENERGY_WINDOW = (-8.0, 8.0)
FERMI_TOL_EV = 1.0e-7
RY_TO_EV = 13.605693122994
BOHR_TO_ANG = 0.529177210903
KB_EV_PER_K = 8.617333262145e-5


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _fortran_records(path: Path) -> list[bytes]:
    """Read the little-endian sequential-unformatted records in SIESTA HSX."""
    data = path.read_bytes()
    records: list[bytes] = []
    offset = 0
    while offset < len(data):
        if offset + 4 > len(data):
            raise ValueError(f"Truncated HSX record marker in {path}")
        size = struct.unpack_from("<i", data, offset)[0]
        if size < 0 or offset + size + 8 > len(data):
            raise ValueError(f"Invalid HSX record size {size} in {path}")
        end = offset + 4 + size
        trailing = struct.unpack_from("<i", data, end)[0]
        if trailing != size:
            raise ValueError(f"HSX record markers disagree in {path} at {offset}")
        records.append(data[offset + 4 : end])
        offset = end + 4
    return records


def read_hsx(path: Path) -> dict[str, Any]:
    """Read the SIESTA 5.4 HSX v1/v2 sparse matrices needed for band spectra.

    The file stores H and Ef in Ry, coordinates in Bohr, and one sparse row per
    unit-cell orbital. ``list_col`` is a one-based index into the HSX supercell.
    """
    records = _fortran_records(path)
    if len(records) < 11:
        raise ValueError(f"HSX is incomplete: {path}")

    def ints(record: bytes) -> np.ndarray:
        if len(record) % 4:
            raise ValueError("HSX integer record has a non-integer byte length")
        return np.frombuffer(record, dtype="<i4").copy()

    def doubles(record: bytes) -> np.ndarray:
        if len(record) % 8:
            raise ValueError("HSX real record has a non-double byte length")
        return np.frombuffer(record, dtype="<f8").copy()

    version_values = ints(records[0])
    precision_values = ints(records[1])
    if version_values.size != 1 or int(version_values[0]) not in (1, 2):
        raise ValueError(f"Unsupported HSX version in {path}")
    version = int(version_values[0])
    if precision_values.size != 1:
        raise ValueError(f"Invalid HSX precision flag in {path}")
    is_double = bool(precision_values[0])
    if not is_double:
        raise ValueError("Single-precision HSX is not supported by this analyzer")

    dims = ints(records[2])
    if dims.size != 7:
        raise ValueError(f"Expected 7 HSX dimensions, found {dims.size}")
    na, norb, nspin, nspecies = (int(x) for x in dims[:4])
    nsc = dims[4:].astype(int)
    ncells = int(np.prod(nsc))
    if nspin != 2:
        raise ValueError(f"Expected two collinear spin channels, found {nspin}")
    cell_bohr = doubles(records[3])[:9].reshape((3, 3), order="F")
    ef_and_thermal = doubles(records[3])[9:12]
    if ef_and_thermal.size != 3:
        raise ValueError("Invalid HSX Ef/qtot/temperature header")
    ef_ev = float(ef_and_thermal[0] * RY_TO_EV)
    temperature_k = float(ef_and_thermal[2] * RY_TO_EV / KB_EV_PER_K)

    geometry = records[4]
    offset_bytes = 3 * ncells * 4
    atom_xyz_bytes = 3 * na * 8
    atom_species_bytes = na * 4
    atom_lasto_bytes = na * 4
    if len(geometry) != offset_bytes + atom_xyz_bytes + atom_species_bytes + atom_lasto_bytes:
        raise ValueError("HSX geometry record size does not match dimensions")
    isc_off = np.frombuffer(geometry[:offset_bytes], dtype="<i4").copy().reshape((3, ncells), order="F")

    # Records 5 through (5 + nspecies - 1) hold species/orbital metadata.
    rec = 6 + nspecies
    if version == 2:
        # SIESTA v2 records kcell and kdispl; KP vectors themselves are read
        # from the matching KP file when evaluating the saved SCF mesh.
        rec += 1
    numh = ints(records[rec])
    rec += 1
    if numh.size != norb:
        raise ValueError("HSX sparse row count does not match orbital count")
    row_cols = [ints(records[rec + i]) for i in range(norb)]
    rec += norb
    if any(len(row_cols[i]) != int(numh[i]) for i in range(norb)):
        raise ValueError("HSX sparse column list does not match row counts")
    h_rows: list[list[np.ndarray]] = []
    for spin in range(nspin):
        spin_rows = [doubles(records[rec + i]) for i in range(norb)]
        if any(len(spin_rows[i]) != int(numh[i]) for i in range(norb)):
            raise ValueError("HSX Hamiltonian row does not match sparse columns")
        h_rows.append(spin_rows)
        rec += norb
    s_rows = [doubles(records[rec + i]) for i in range(norb)]
    if any(len(s_rows[i]) != int(numh[i]) for i in range(norb)):
        raise ValueError("HSX overlap row does not match sparse columns")

    row_index: list[int] = []
    col_index: list[int] = []
    cell_index: list[int] = []
    h_values = np.empty((nspin, int(np.sum(numh))), dtype=float)
    s_values = np.empty(int(np.sum(numh)), dtype=float)
    cursor = 0
    for row in range(norb):
        cols = row_cols[row]
        count = len(cols)
        row_index.extend([row] * count)
        col_index.extend(((cols - 1) % norb).tolist())
        cell_index.extend(((cols - 1) // norb).tolist())
        s_values[cursor : cursor + count] = s_rows[row]
        for spin in range(nspin):
            h_values[spin, cursor : cursor + count] = h_rows[spin][row]
        cursor += count

    return {
        "version": version,
        "norb": norb,
        "nspin": nspin,
        "cell_bohr": cell_bohr,
        "isc_off": isc_off,
        "rvec_bohr": (cell_bohr @ isc_off).T,
        "row_index": np.asarray(row_index, dtype=int),
        "col_index": np.asarray(col_index, dtype=int),
        "cell_index": np.asarray(cell_index, dtype=int),
        "h_values_ry": h_values,
        "s_values": s_values,
        "fermi_ev": ef_ev,
        "temperature_k": temperature_k,
    }


def diagonalize(hsx: dict[str, Any], k_cart_inv_bohr: np.ndarray) -> np.ndarray:
    """Return absolute energies (eV) for each k-point, spin and band."""
    nk = len(k_cart_inv_bohr)
    nspin = hsx["nspin"]
    norb = hsx["norb"]
    result = np.empty((nk, nspin, norb), dtype=float)
    rows = hsx["row_index"]
    cols = hsx["col_index"]
    cells = hsx["cell_index"]
    rvec = hsx["rvec_bohr"]
    for ik, kvec in enumerate(k_cart_inv_bohr):
        phase = np.exp(1j * (rvec @ kvec))
        for spin in range(nspin):
            hmat = np.zeros((norb, norb), dtype=complex)
            smat = np.zeros((norb, norb), dtype=complex)
            np.add.at(hmat, (rows, cols), hsx["h_values_ry"][spin] * phase[cells])
            np.add.at(smat, (rows, cols), hsx["s_values"] * phase[cells])
            hmat = (hmat + hmat.conj().T) * 0.5
            smat = (smat + smat.conj().T) * 0.5
            chol = np.linalg.cholesky(smat)
            transformed = np.linalg.solve(chol, hmat)
            transformed = np.linalg.solve(chol.conj(), transformed.T).T
            result[ik, spin] = np.linalg.eigvalsh((transformed + transformed.conj().T) * 0.5) * RY_TO_EV
    return result


def classify_spectrum(
    energies_rel_ev: np.ndarray,
    *,
    segments: list[dict[str, Any]] | None = None,
    fermi_tol_ev: float = FERMI_TOL_EV,
    occupations: np.ndarray | None = None,
    partial_occupation_tol: float = 1.0e-6,
) -> dict[str, Any]:
    """Classify a sampled mesh/path before extracting any insulating edges.

    Route crossings are checked within each continuous Seekpath segment. A
    sampled mesh checks actual EF-near states and any supplied partial
    occupations. No occupied-band index is assumed.
    """
    energies = np.asarray(energies_rel_ev, dtype=float)
    if energies.ndim != 3:
        raise ValueError("Expected energies shaped (kpoint, spin, band)")
    nk, nspin, nbands = energies.shape
    if segments is None:
        segments = [{"indices": list(range(nk))}]
    crossings: set[tuple[int, int, int]] = set()
    for segment in segments:
        ids = np.asarray(segment["indices"], dtype=int)
        for spin in range(nspin):
            for band in range(nbands):
                curve = energies[ids, spin, band]
                if float(curve.min()) <= fermi_tol_ev and float(curve.max()) >= -fermi_tol_ev:
                    crossings.add((spin, band, int(segment.get("index", 0))))
    if occupations is not None:
        occ = np.asarray(occupations, dtype=float)
        if occ.shape != energies.shape:
            raise ValueError("Occupation array must match the energy array")
        partial = (occ > partial_occupation_tol) & (occ < 1.0 - partial_occupation_tol)
        for k, spin, band in np.argwhere(partial):
            crossings.add((int(spin), int(band), -1))

    if crossings:
        return {
            "classification": "METAL",
            "crossing_bands": sorted({band + 1 for _, band, _ in crossings}),
            "crossing_channels": sorted({spin + 1 for spin, _, _ in crossings}),
            "crossings": [
                {"spin_channel": spin + 1, "band_index_1based": band + 1, "segment_index": seg}
                for spin, band, seg in sorted(crossings)
            ],
            "vbm_rel_ev": None,
            "cbm_rel_ev": None,
            "indirect_gap_ev": None,
            "minimum_direct_gap_ev": None,
        }

    occupied = energies < -fermi_tol_ev
    unoccupied = energies > fermi_tol_ev
    if not np.any(occupied) or not np.any(unoccupied):
        raise ValueError("Cannot identify both occupied and unoccupied states")
    occ_values = np.where(occupied, energies, -np.inf)
    unocc_values = np.where(unoccupied, energies, np.inf)
    iv = np.unravel_index(int(np.argmax(occ_values)), energies.shape)
    ic = np.unravel_index(int(np.argmin(unocc_values)), energies.shape)
    vbm = float(energies[iv])
    cbm = float(energies[ic])
    direct_gaps = []
    for k in range(nk):
        for spin in range(nspin):
            ev = energies[k, spin]
            occ_here = ev[ev < -fermi_tol_ev]
            unocc_here = ev[ev > fermi_tol_ev]
            if len(occ_here) and len(unocc_here):
                direct_gaps.append((float(unocc_here.min() - occ_here.max()), k, spin))
    direct = min(direct_gaps, default=(math.nan, -1, -1))
    return {
        "classification": "INSULATOR",
        "crossing_bands": [],
        "crossing_channels": [],
        "crossings": [],
        "vbm_rel_ev": vbm,
        "cbm_rel_ev": cbm,
        "indirect_gap_ev": cbm - vbm,
        "minimum_direct_gap_ev": direct[0],
        "vbm_index": tuple(int(x) for x in iv),
        "cbm_index": tuple(int(x) for x in ic),
        "direct_index": (direct[1], direct[2]),
    }


def read_kp(path: Path) -> tuple[np.ndarray, np.ndarray]:
    lines = path.read_text().splitlines()
    nk = int(lines[0].split()[0])
    data = np.asarray([[float(v) for v in line.split()[1:5]] for line in lines[1 : nk + 1]])
    if data.shape != (nk, 4):
        raise ValueError(f"Malformed KP file: {path}")
    return data[:, :3], data[:, 3]


def reconstruct_route(route: dict[str, Any]):
    """Rebuild the already-recorded Seekpath sampling without calling Seekpath."""
    lattice = np.asarray(route["lattice_vectors_ang"], dtype=float)
    reciprocal = 2.0 * math.pi * np.linalg.inv(lattice).T
    coords = route["point_coords_reciprocal_lattice_vectors"]
    points: list[dict[str, Any]] = []
    spans: list[dict[str, Any]] = []
    previous_end = None
    cursor = 0
    ticks = route["tick_positions"]
    for index, (start, end) in enumerate(route["path_segments"]):
        k0 = np.asarray(coords[start], dtype=float)
        k1 = np.asarray(coords[end], dtype=float)
        interp = np.linspace(k0, k1, N_INTERVALS_PER_SEGMENT + 1)
        distances = np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(interp, axis=0) @ reciprocal, axis=1))]
        connected = previous_end == start
        x0 = float(route["segments_sampling"][index]["x_start_inv_ang"])
        begin = 1 if connected else 0
        for j in range(begin, len(interp)):
            points.append({
                "k_frac": interp[j].tolist(),
                "x_inv_ang": float(x0 + distances[j]),
                "segment_index": index,
                "segment": [start, end],
                "t": float(j / N_INTERVALS_PER_SEGMENT),
            })
        count = N_INTERVALS_PER_SEGMENT + 1 - begin
        ids = list(range(cursor, cursor + count))
        if connected:
            ids.insert(0, cursor - 1)
        spans.append({"index": index, "indices": ids})
        cursor += count
        previous_end = end
    if len(points) != int(route["unique_path_kpoint_count"]):
        raise ValueError("Recorded Seekpath route sampling does not reconstruct")
    return points, spans, ticks, reciprocal


def point_location(row: dict[str, Any], special: dict[str, list[float]]) -> str:
    k = np.asarray(row["k_frac"])
    for name, coord in special.items():
        if np.linalg.norm(k - np.asarray(coord)) < 1e-7:
            return name
    return f"{row['segment'][0]}→{row['segment'][1]} (t={row['t']:.3f})"


def _edge_record(energies_rel: np.ndarray, ef: float, index: tuple[int, ...], point: dict[str, Any], special: dict[str, list[float]], spin_names: list[str]):
    k, spin, band = index
    relative = float(energies_rel[index])
    return {
        "energy_ev": relative + ef,
        "relative_to_ef_ev": relative,
        "band_index_1based": band + 1,
        "spin_channel": spin_names[spin],
        "k_fractional_original_reciprocal_vectors": point["k_frac"],
        "route_location": point_location(point, special),
    }


def draw_svg(path: Path, energies_rel: np.ndarray, full_points, segments, ticks, method: str):
    width, height = 1100, 680
    left, right, top, bottom = 90, 30, 40, 88
    plotw, ploth = width - left - right, height - top - bottom
    xs = np.array([p["x_inv_ang"] for p in full_points])
    xmin, xmax = float(xs.min()), float(xs.max())
    ymin, ymax = ENERGY_WINDOW
    xmap = lambda x: left + (x - xmin) / (xmax - xmin) * plotw
    ymap = lambda y: top + (ymax - y) / (ymax - ymin) * ploth
    colors = ["#2166ac", "#b2182b"]
    labels = {"GAMMA": "Γ", "GAMMA_1": "Γ₁", "H_0": "H₀", "H_1": "H₁", "H_2": "H₂", "S_0": "S₀", "S_1": "S₁", "S_2": "S₂", "S_3": "S₃", "S_4": "S₄", "S_5": "S₅"}
    chunks = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" data-energy-reference="E-EF" data-ef-ev="0">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<g font-family="Arial, sans-serif" fill="#111">',
        f'<text x="{left}" y="24" font-size="18" font-weight="bold">FeO {method}: Seekpath bands</text>',
    ]
    for y in range(math.ceil(ymin), math.floor(ymax) + 1, 2):
        yy = ymap(y)
        chunks.append(f'<line x1="{left}" y1="{yy:.3f}" x2="{width-right}" y2="{yy:.3f}" stroke="#dddddd" stroke-width="1"/>')
        chunks.append(f'<text x="{left-12}" y="{yy+5:.3f}" text-anchor="end" font-size="12">{y}</text>')
    ef_y = ymap(0.0)
    chunks.append(f'<line x1="{left}" y1="{ef_y:.3f}" x2="{width-right}" y2="{ef_y:.3f}" stroke="#222" stroke-width="1.3" stroke-dasharray="6,5" data-ef-line="0"/>')
    chunks.append(f'<text x="{width-right-5}" y="{ef_y-6:.3f}" text-anchor="end" font-size="11">E<tspan baseline-shift="sub" font-size="9">F</tspan>=0</text>')
    for tick in ticks:
        xx = xmap(tick["x_inv_ang"])
        chunks.append(f'<line x1="{xx:.3f}" y1="{top}" x2="{xx:.3f}" y2="{height-bottom}" stroke="#555" stroke-width="0.8"/>')
        label = "|".join(labels.get(n, n) for n in tick["labels"])
        chunks.append(f'<text x="{xx:.3f}" y="{height-bottom+23}" text-anchor="middle" font-size="13">{label}</text>')
    for seg in segments:
        ids = seg["indices"]
        for spin in range(energies_rel.shape[1]):
            for band in range(energies_rel.shape[2]):
                run = []
                points = []
                for idx in ids:
                    val = float(energies_rel[idx, spin, band])
                    points.append((xmap(full_points[idx]["x_inv_ang"]), ymap(val)) if ymin - 0.1 <= val <= ymax + 0.1 else None)
                for point in points + [None]:
                    if point is None:
                        if len(run) > 1:
                            coords = " ".join(f"{x:.2f},{y:.2f}" for x, y in run)
                            chunks.append(f'<polyline points="{coords}" fill="none" stroke="{colors[spin]}" stroke-width="0.75" opacity="0.72"/>')
                        run = []
                    else:
                        run.append(point)
    chunks.extend([
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{height-bottom}" stroke="#111" stroke-width="1.2"/>',
        f'<line x1="{left}" y1="{height-bottom}" x2="{width-right}" y2="{height-bottom}" stroke="#111" stroke-width="1.2"/>',
        f'<text x="23" y="{top+ploth/2:.1f}" transform="rotate(-90 23 {top+ploth/2:.1f})" text-anchor="middle" font-size="14">Energy relative to E<tspan baseline-shift="sub" font-size="10">F</tspan> (eV)</text>',
        f'<text x="{left+plotw/2:.1f}" y="{height-14}" text-anchor="middle" font-size="13">Seekpath wave vector</text>',
        f'<line x1="{width-255}" y1="30" x2="{width-225}" y2="30" stroke="{colors[0]}" stroke-width="2"/><text x="{width-218}" y="34" font-size="12">spin channel 1 (up)</text>',
        f'<line x1="{width-125}" y1="30" x2="{width-95}" y2="30" stroke="{colors[1]}" stroke-width="2"/><text x="{width-88}" y="34" font-size="12">spin channel 2 (down)</text>',
        '</g></svg>',
    ])
    path.write_text("\n".join(chunks), encoding="utf-8")


def analyze_scf_mesh(hsx: dict[str, Any], kp_path: Path) -> dict[str, Any]:
    kpoints, weights = read_kp(kp_path)
    energies_abs = diagonalize(hsx, kpoints)
    ef = hsx["fermi_ev"]
    energies_rel = energies_abs - ef
    temp = hsx["temperature_k"]
    if temp <= 0:
        occupations = (energies_rel < 0).astype(float)
    else:
        occupations = 1.0 / (1.0 + np.exp(np.clip(energies_rel / (KB_EV_PER_K * temp), -700, 700)))
    classified = classify_spectrum(energies_rel, occupations=occupations)
    result: dict[str, Any] = {
        "classification": classified["classification"],
        "fermi_crossing_bands": classified["crossing_bands"],
        "fermi_crossing_channels": classified["crossing_channels"],
        "kpoint_count": int(len(kpoints)),
        "occupation_weighted_electron_count": float(np.sum(occupations * weights[:, None, None])),
        "temperature_k": temp,
        "fermi_energy_ev": ef,
        "number_of_bands": int(hsx["norb"]),
        "number_of_spin_channels": int(hsx["nspin"]),
    }
    if classified["classification"] == "INSULATOR":
        vbm_rel = classified["vbm_rel_ev"]
        cbm_rel = classified["cbm_rel_ev"]
        result.update({
            "vbm_abs_ev": vbm_rel + ef,
            "cbm_abs_ev": cbm_rel + ef,
            "vbm_rel_ef_ev": vbm_rel,
            "cbm_rel_ef_ev": cbm_rel,
            "occupation_aware_gap_ev": classified["indirect_gap_ev"],
        })
    return result


def run_method(name: str, run_dir: Path, route, full_points, segments, ticks, special, out_dir: Path):
    hsx_path = run_dir / "FEO_PBE_REFERENCE.HSX"
    dm_path = run_dir / "FEO_PBE_REFERENCE.DM"
    out_path = run_dir / "siesta.out"
    hsx = read_hsx(hsx_path)
    expected_cell = np.asarray(route["lattice_vectors_ang"], dtype=float)
    observed_cell = hsx["cell_bohr"].T * BOHR_TO_ANG
    if not np.allclose(observed_cell, expected_cell, atol=2e-7, rtol=0):
        raise RuntimeError(f"HSX geometry differs from the saved V6 Seekpath cell for {name}")
    ef = hsx["fermi_ev"]
    route_lattice = np.asarray(route["lattice_vectors_ang"], dtype=float)
    reciprocal_inv_bohr = (2.0 * math.pi * np.linalg.inv(route_lattice).T) * BOHR_TO_ANG
    kcart = np.asarray([np.asarray(p["k_frac"]) @ reciprocal_inv_bohr for p in full_points])
    energies_abs = diagonalize(hsx, kcart)
    energies_rel = energies_abs - ef
    route_analysis = classify_spectrum(energies_rel, segments=segments)
    kp_path = run_dir / "FEO_PBE_REFERENCE.KP"
    scf = analyze_scf_mesh(hsx, kp_path) if kp_path.is_file() else {
        "classification": "NOT_RECOMPUTED_NO_SAVED_KP",
        "note": "No matching KP file is present in this PBE run directory; route results are still recomputed from its existing HSX.",
    }
    spin_names = ["spin channel 1 (up)", "spin channel 2 (down)"]
    result: dict[str, Any] = {
        "method": name,
        "siesta_version": "5.4.2",
        "evaluation": "non-self-consistent generalized diagonalization of the existing converged HSX; no SIESTA process or SCF iteration launched",
        "source_run": str(run_dir.relative_to(ROOT)),
        "source_dm": dm_path.name,
        "source_dm_sha256": sha256(dm_path),
        "source_hsx": hsx_path.name,
        "source_hsx_sha256": sha256(hsx_path),
        "source_siesta_out": out_path.name,
        "source_kp": "FEO_PBE_REFERENCE.KP",
        "fermi_energy_ev": ef,
        "energy_reference": "energies_rel_ev = E_abs_ev - HSX Ef; plotted at zero",
        "number_of_bands": int(hsx["norb"]),
        "number_of_spin_channels": int(hsx["nspin"]),
        "electron_count_total": 44,
        "route_kpoint_count": len(full_points),
        "route_electronic_classification": route_analysis["classification"],
        "fermi_crossing_bands": route_analysis["crossing_bands"],
        "fermi_crossing_channels": route_analysis["crossing_channels"],
        "fermi_crossings": route_analysis["crossings"],
        "classification_rule": "check EF crossings on each connected route segment before deriving insulating edges; no occupied-band index is assumed",
        "scf_mesh": scf,
        "bands_csv": f"FeO_{name}_seekpath_bands.csv",
        "figure_svg": f"FeO_{name}_SEEKPATH_BANDS.svg",
    }
    if route_analysis["classification"] == "INSULATOR":
        iv = route_analysis["vbm_index"]
        ic = route_analysis["cbm_index"]
        dk, dsp = route_analysis["direct_index"]
        direct_record = {
            "energy_ev": float(route_analysis["minimum_direct_gap_ev"]),
            "valence_band_index_1based": int(np.sum(energies_rel[dk, dsp] < -FERMI_TOL_EV)),
            "conduction_band_index_1based": int(np.sum(energies_rel[dk, dsp] < -FERMI_TOL_EV) + 1),
            "spin_channel": spin_names[dsp],
            "k_fractional_original_reciprocal_vectors": full_points[dk]["k_frac"],
            "route_location": point_location(full_points[dk], special),
        }
        result.update({
            "vbm": _edge_record(energies_rel, ef, iv, full_points[iv[0]], special, spin_names),
            "cbm": _edge_record(energies_rel, ef, ic, full_points[ic[0]], special, spin_names),
            "indirect_gap_ev_signed": float(route_analysis["indirect_gap_ev"]),
            "minimum_direct_gap_ev": float(route_analysis["minimum_direct_gap_ev"]),
            "minimum_direct_gap": direct_record,
            "route_note": "The gap is sampled on the Seekpath route; it does not prove the continuous global Brillouin-zone gap.",
        })
    else:
        result["route_note"] = "Fermi crossings occur on the sampled route; no insulating VBM/CBM gap is reported."

    data_path = out_dir / result["bands_csv"]
    with data_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["path_index", "segment_index", "segment_start", "segment_end", "t", "kx", "ky", "kz", "k_distance_inv_ang", "spin_channel", "band_index", "energy_ev", "energy_minus_ef_ev"])
        for i, point in enumerate(full_points):
            for spin in range(hsx["nspin"]):
                for band in range(hsx["norb"]):
                    relative = float(energies_rel[i, spin, band])
                    absolute = relative + ef
                    writer.writerow([
                        i, point["segment_index"], point["segment"][0], point["segment"][1], f"{point['t']:.8f}",
                        f"{point['k_frac'][0]:.10f}", f"{point['k_frac'][1]:.10f}", f"{point['k_frac'][2]:.10f}",
                        f"{point['x_inv_ang']:.10f}", spin + 1, band + 1, f"{absolute:.10f}", f"{relative:.10f}",
                    ])
    svg_path = out_dir / result["figure_svg"]
    draw_svg(svg_path, energies_rel, full_points, segments, ticks, name)
    return result, energies_rel


def main() -> None:
    if not ROUTE_FILE.is_file():
        raise FileNotFoundError(f"Existing Seekpath route is required: {ROUTE_FILE}")
    route = json.loads(ROUTE_FILE.read_text(encoding="utf-8"))
    full_points, segment_spans, tick_rows, _ = reconstruct_route(route)
    special = route["point_coords_reciprocal_lattice_vectors"]
    methods = {}
    lr_energies = None
    for name, run in (("PBE", PBE), ("PBE+LR-U", LRU)):
        methods[name], energies = run_method(name, run, route, full_points, segment_spans, tick_rows, special, OUT)
        if name == "PBE+LR-U":
            lr_energies = energies
    report = {
        "status": "COMPLETE",
        "route_file": ROUTE_FILE.name,
        "route_kpoint_count": len(full_points),
        "methods": methods,
        "distinction": "SCF-mesh sampled gap != Seekpath-route gap != mathematically proven global BZ gap",
    }
    (OUT / "feo_seekpath_band_results.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if lr_energies is None:
        raise RuntimeError("PBE+LR-U spectra were not generated")
    lr = methods["PBE+LR-U"]
    if lr["route_electronic_classification"] != "INSULATOR":
        raise RuntimeError("Corrected LR-U Seekpath route is not insulating")
    if np.any((lr_energies > -1.782046599 + 1e-7) & (lr_energies < 0.550951920 - 1e-7)):
        raise RuntimeError("LR-U route has sampled energies inside the expected insulating gap")
    svg = (OUT / lr["figure_svg"]).read_text(encoding="utf-8")
    if 'data-energy-reference="E-EF"' not in svg or 'data-ef-line="0"' not in svg:
        raise RuntimeError("LR-U SVG does not encode the corrected EF=0 reference")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
