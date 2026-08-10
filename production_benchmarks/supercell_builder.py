"""
production_benchmarks/supercell_builder.py

Real supercell builder with actual integer-matrix expansion,
physical AFM-II (111)-plane spin propagation, and stoichiometry verification.
"""
from __future__ import annotations
import numpy as np
from itertools import product
from typing import List, Tuple, Optional, Dict, Any


# ─────────────────────────────────────────────────────────────────────────────
# Core supercell expansion
# ─────────────────────────────────────────────────────────────────────────────

def build_supercell(
    fracs: np.ndarray,
    labels: List[str],
    species_ids: List[int],
    lat: np.ndarray,
    sc_matrix: np.ndarray,
) -> Tuple[np.ndarray, List[str], List[int], np.ndarray]:
    """
    Build a supercell by integer matrix transformation.
    """
    sc_matrix = np.asarray(sc_matrix, dtype=float)
    fracs = np.asarray(fracs, dtype=float)
    lat   = np.asarray(lat,   dtype=float)

    det = int(round(abs(np.linalg.det(sc_matrix))))
    if det == 0:
        raise ValueError("Supercell matrix is singular (det=0)")

    new_lat = sc_matrix @ lat  # new lattice vectors (rows)

    sc_inv = np.linalg.inv(sc_matrix)
    bound = int(np.ceil(np.max(np.abs(sc_matrix)))) + 1
    translations = []
    for i, j, k in product(range(-bound, bound + 1),
                            range(-bound, bound + 1),
                            range(-bound, bound + 1)):
        t_prim = np.array([i, j, k], dtype=float)
        t_sc   = sc_inv @ t_prim
        if np.all(t_sc >= -1e-8) and np.all(t_sc < 1.0 - 1e-8):
            translations.append(t_prim)

    if len(translations) != det:
        raise RuntimeError(
            f"Expected {det} lattice translations but found {len(translations)}. "
            f"sc_matrix={sc_matrix.tolist()}"
        )

    new_fracs_list   = []
    new_labels_list  = []
    new_species_list = []

    for t in translations:
        for atom_idx in range(len(fracs)):
            prim_pos = fracs[atom_idx] + t
            cart = prim_pos @ lat
            sc_frac = np.linalg.solve(new_lat.T, cart.T).T
            sc_frac = sc_frac % 1.0
            new_fracs_list.append(sc_frac)
            new_labels_list.append(labels[atom_idx])
            new_species_list.append(species_ids[atom_idx])

    new_fracs = np.array(new_fracs_list)

    seen = []
    keep = []
    for i, f in enumerate(new_fracs):
        is_dup = False
        for s in seen:
            diff = f - s
            diff -= np.round(diff)
            if np.linalg.norm(diff) < 1e-6:
                is_dup = True
                break
        if not is_dup:
            seen.append(f)
            keep.append(i)

    if len(keep) != det * len(fracs):
        raise RuntimeError(
            f"Supercell atom count mismatch after dedup: "
            f"expected {det * len(fracs)}, got {len(keep)}"
        )

    new_fracs       = new_fracs[keep]
    new_labels      = [new_labels_list[i]  for i in keep]
    new_species_ids = [new_species_list[i] for i in keep]

    return new_fracs, new_labels, new_species_ids, new_lat


# ─────────────────────────────────────────────────────────────────────────────
# AFM-II spin assignment (propagated from physical (111) interplanar phase)
# ─────────────────────────────────────────────────────────────────────────────

def assign_afm_ordering(
    new_fracs: np.ndarray,
    new_labels: List[str],
    target_species: str,
    moment_magnitude: float,
    new_lat: np.ndarray,
    prim_lat: np.ndarray,
) -> List[float]:
    """
    Assign AFM-II spin moments by propagating the physical (111) interplanar phase.

    No index-based parity assumption.
    """
    new_fracs = np.asarray(new_fracs, dtype=float)
    new_lat   = np.asarray(new_lat,   dtype=float)
    prim_lat  = np.asarray(prim_lat,  dtype=float)

    n_plane = np.array([1.0, 1.0, 1.0]) / np.sqrt(3.0)
    # Estimate d(111) interplanar spacing from primitive lattice
    d_111 = float(np.linalg.norm(prim_lat[0])) / np.sqrt(3.0)
    if d_111 < 0.5:
        d_111 = 2.0

    spins = []
    for frac, label in zip(new_fracs, new_labels):
        if label != target_species:
            spins.append(0.0)
            continue

        cart = new_lat.T @ frac
        proj = float(np.dot(cart, n_plane))
        plane_index = int(round(proj / d_111))
        sign = 1.0 if (plane_index % 2 == 0) else -1.0
        spins.append(sign * moment_magnitude)

    return spins


# ─────────────────────────────────────────────────────────────────────────────
# Standard supercell options
# ─────────────────────────────────────────────────────────────────────────────

def get_afm_supercell_options(material_name: str) -> List[Dict[str, Any]]:
    """
    Return the canonical set of AFM-compatible supercell specifications.
    """
    options = [
        {
            'label': 'small',
            'sc_matrix': [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
            'n_cation': 2,
            'n_anion':  2,
            'n_fe': 2,
            'n_o':  2,
            'n_ni': 2,
            'det': 1,
            'description': '4-atom primitive cell (2 formula units)',
        },
        {
            'label': 'medium',
            'sc_matrix': [[2, 0, 0], [0, 1, 0], [0, 0, 1]],
            'n_cation': 4,
            'n_anion':  4,
            'n_fe': 4,
            'n_o':  4,
            'n_ni': 4,
            'det': 2,
            'description': '2x1x1 supercell (8 atoms)',
        },
        {
            'label': 'large',
            'sc_matrix': [[2, 0, 0], [0, 2, 0], [0, 0, 1]],
            'n_cation': 8,
            'n_anion':  8,
            'n_fe': 8,
            'n_o':  8,
            'n_ni': 8,
            'det': 4,
            'description': '2x2x1 supercell (16 atoms)',
        },
    ]
    return options


def verify_stoichiometry(new_labels: List[str],
                          original_stoich: Dict[str, int]) -> bool:
    """
    Verify that new_labels have the correct stoichiometric ratios.
    """
    from collections import Counter
    actual = Counter(new_labels)

    if not original_stoich:
        return False

    scale = None
    for sp, count in original_stoich.items():
        if sp not in actual:
            return False
        ratio = actual[sp] / count
        if scale is None:
            scale = ratio
        else:
            if abs(ratio - scale) > 1e-6:
                return False

    for sp, count in original_stoich.items():
        expected = int(round(scale * count))
        if actual.get(sp, 0) != expected:
            return False

    for sp in actual:
        if sp not in original_stoich:
            return False

    return True
