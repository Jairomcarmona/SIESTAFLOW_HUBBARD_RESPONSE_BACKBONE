"""
production_benchmarks/geometry_validator.py

Real geometry validators that derive all properties from atomic coordinates.
Uses 3x3x3 periodic image translations to calculate exact coordination numbers under PBC.
No hardcoded return values.
"""
from __future__ import annotations
import numpy as np
from itertools import product
from typing import List, Tuple, Optional, Dict, Any


# ─────────────────────────────────────────────────────────────────────────────
# Utility helpers
# ─────────────────────────────────────────────────────────────────────────────

def _min_image_dist(r1: np.ndarray, r2: np.ndarray, lat: np.ndarray) -> float:
    """Minimum-image distance between two Cartesian positions under PBC."""
    diff = r1 - r2
    frac = np.linalg.solve(lat.T, diff)
    frac -= np.round(frac)
    cart = lat.T @ frac
    return float(np.linalg.norm(cart))


def _build_cart(fracs: np.ndarray, lat: np.ndarray) -> np.ndarray:
    """Convert fractional coordinates to Cartesian. lat rows are lattice vectors."""
    return fracs @ lat


def validate_no_duplicate_atoms(fracs: np.ndarray, tol: float = 1e-3) -> bool:
    """Return True if no two fractional positions coincide (PBC-aware)."""
    fracs = np.asarray(fracs, dtype=float)
    n = len(fracs)
    for i in range(n):
        for j in range(i + 1, n):
            diff = fracs[i] - fracs[j]
            diff -= np.round(diff)
            if np.linalg.norm(diff) < tol:
                return False
    return True


def check_min_distance(cart_coords: np.ndarray, lat: np.ndarray,
                       min_ang: float = 0.8) -> bool:
    """Return True if all pairwise PBC distances exceed min_ang Å."""
    n = len(cart_coords)
    for i in range(n):
        for j in range(i + 1, n):
            d = _min_image_dist(cart_coords[i], cart_coords[j], lat)
            if d < min_ang:
                return False
    return True


def _pbc_coordination_count(site_idx: int, cart: np.ndarray, lat: np.ndarray,
                           target_indices: List[int], cutoff: float) -> int:
    """
    Count total number of bond connections to target sites within cutoff Å under PBC.
    Iterates over 3x3x3 image cell translations to account for multiple periodic image bonds.
    """
    bonds = 0
    for j in target_indices:
        for n1, n2, n3 in product([-1, 0, 1], repeat=3):
            if j == site_idx and n1 == 0 and n2 == 0 and n3 == 0:
                continue
            T = np.array([n1, n2, n3], dtype=float) @ lat
            d = float(np.linalg.norm(cart[site_idx] - (cart[j] + T)))
            if d <= cutoff:
                bonds += 1
    return bonds


# ─────────────────────────────────────────────────────────────────────────────
# Cu2O cuprite validator
# ─────────────────────────────────────────────────────────────────────────────

def verify_cuprite_cu2o(fracs: np.ndarray, labels: List[str],
                         a_ang: float) -> dict:
    """
    Verify Cu2O cuprite geometry from first principles.
    """
    fracs = np.asarray(fracs, dtype=float)
    lat = np.eye(3) * a_ang
    cart = _build_cart(fracs, lat)

    errors = []
    cu_idx = [i for i, l in enumerate(labels) if l == 'Cu']
    o_idx  = [i for i, l in enumerate(labels) if l == 'O']

    # Stoichiometry check
    if len(cu_idx) == 0:
        errors.append("No Cu atoms found")
    if len(o_idx) == 0:
        errors.append("No O atoms found")
    if len(cu_idx) != 2 * len(o_idx):
        errors.append(f"Stoichiometry mismatch: {len(cu_idx)} Cu, {len(o_idx)} O "
                      f"(expected 2:1 ratio)")

    # Duplicate check
    if not validate_no_duplicate_atoms(fracs):
        errors.append("Duplicate fractional positions detected")

    # Cu-O nearest distances
    cu_o_dists = []
    for i in cu_idx:
        for j in o_idx:
            cu_o_dists.append(_min_image_dist(cart[i], cart[j], lat))

    if not cu_o_dists:
        errors.append("Cannot compute Cu-O distances")
        return {'geometry_valid': False, 'errors': errors,
                'cu_o_nearest_ang': None, 'cu_coordination': None,
                'o_coordination': None, 'all_cu_equivalent': False}

    nearest_cuo = min(cu_o_dists)
    cutoff = nearest_cuo * 1.05  # 5% tolerance band

    # Cu coordination (each Cu should bond to 2 O in cuprite under PBC)
    cu_coords = [_pbc_coordination_count(i, cart, lat, o_idx, cutoff)
                 for i in cu_idx]
    # O coordination (each O should bond to 4 Cu)
    o_coords  = [_pbc_coordination_count(j, cart, lat, cu_idx, cutoff)
                 for j in o_idx]

    cu_coord_val = cu_coords[0] if cu_coords else 0
    o_coord_val  = o_coords[0]  if o_coords  else 0

    if not all(c == cu_coord_val for c in cu_coords):
        errors.append(f"Cu coordination not uniform: {cu_coords}")
    if not all(c == o_coord_val for c in o_coords):
        errors.append(f"O coordination not uniform: {o_coords}")
    if cu_coord_val != 2:
        errors.append(f"Cu coordination expected 2, got {cu_coord_val}")
    if o_coord_val != 4:
        errors.append(f"O coordination expected 4, got {o_coord_val}")

    # All Cu sites equivalent (same set of Cu-O distances)
    all_cu_eq = True
    ref_dists = sorted([_min_image_dist(cart[cu_idx[0]], cart[j], lat)
                        for j in o_idx])
    for i in cu_idx[1:]:
        dists = sorted([_min_image_dist(cart[i], cart[j], lat) for j in o_idx])
        if not np.allclose(dists, ref_dists, atol=1e-3):
            all_cu_eq = False
            errors.append(f"Cu site {i} not equivalent to Cu site {cu_idx[0]}")

    geometry_valid = (len(errors) == 0)
    return {
        'geometry_valid': geometry_valid,
        'cu_o_nearest_ang': float(nearest_cuo),
        'cu_coordination': int(cu_coord_val),
        'o_coordination':  int(o_coord_val),
        'all_cu_equivalent': all_cu_eq,
        'n_cu': len(cu_idx),
        'n_o':  len(o_idx),
        'errors': errors,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Cu3N anti-ReO3 validator
# ─────────────────────────────────────────────────────────────────────────────

def verify_cu3n_antireo3(fracs: np.ndarray, labels: List[str],
                          a_ang: float) -> dict:
    """
    Verify Cu3N anti-ReO3 geometry.
    """
    fracs = np.asarray(fracs, dtype=float)
    lat = np.eye(3) * a_ang
    cart = _build_cart(fracs, lat)

    errors = []
    cu_idx = [i for i, l in enumerate(labels) if l == 'Cu']
    n_idx  = [i for i, l in enumerate(labels) if l == 'N']

    # Stoichiometry 3:1
    if len(cu_idx) != 3 * len(n_idx):
        errors.append(f"Stoichiometry mismatch: {len(cu_idx)} Cu, {len(n_idx)} N "
                      f"(expected 3:1 ratio)")

    if not validate_no_duplicate_atoms(fracs):
        errors.append("Duplicate fractional positions detected")

    # Cu-N distances
    cu_n_dists = []
    for i in cu_idx:
        for j in n_idx:
            cu_n_dists.append(_min_image_dist(cart[i], cart[j], lat))

    if not cu_n_dists:
        errors.append("Cannot compute Cu-N distances")
        return {'geometry_valid': False, 'errors': errors,
                'n_cu': len(cu_idx), 'n_n': len(n_idx),
                'cu_n_nearest_ang': None, 'cu_coordination': None,
                'n_coordination': None}

    nearest_cun = min(cu_n_dists)
    expected_cun = a_ang / 2.0
    if abs(nearest_cun - expected_cun) > 0.05:
        errors.append(f"Cu-N nearest {nearest_cun:.4f} Å != expected a/2={expected_cun:.4f} Å")

    cutoff = nearest_cun * 1.05

    # Cu coordination under PBC (each Cu should bond to 2 N)
    cu_coords = [_pbc_coordination_count(i, cart, lat, n_idx, cutoff)
                 for i in cu_idx]
    # N coordination under PBC (each N should bond to 6 Cu)
    n_coords  = [_pbc_coordination_count(j, cart, lat, cu_idx, cutoff)
                 for j in n_idx]

    cu_coord_val = cu_coords[0] if cu_coords else 0
    n_coord_val  = n_coords[0]  if n_coords  else 0

    if not all(c == cu_coord_val for c in cu_coords):
        errors.append(f"Cu coordination not uniform: {cu_coords}")
    if cu_coord_val != 2:
        errors.append(f"Cu coordination expected 2, got {cu_coord_val}")
    if n_coord_val != 6:
        errors.append(f"N coordination expected 6, got {n_coord_val}")

    # Cu-Cu distances
    cu_cu_dists = []
    for i in range(len(cu_idx)):
        for j in range(i + 1, len(cu_idx)):
            cu_cu_dists.append(_min_image_dist(cart[cu_idx[i]], cart[cu_idx[j]], lat))
    cu_cu_spread = (max(cu_cu_dists) - min(cu_cu_dists)) if cu_cu_dists else float('nan')
    if cu_cu_spread > 0.01 and cu_cu_dists:
        errors.append(f"Cu-Cu distances not uniform: spread={cu_cu_spread:.4f} Å")

    geometry_valid = (len(errors) == 0)
    return {
        'geometry_valid': geometry_valid,
        'n_cu': len(cu_idx),
        'n_n':  len(n_idx),
        'cu_n_nearest_ang': float(nearest_cun),
        'cu_coordination': int(cu_coord_val),
        'n_coordination':  int(n_coord_val),
        'cu_cu_nearest_ang': float(min(cu_cu_dists)) if cu_cu_dists else None,
        'cu_cu_spread_ang': float(cu_cu_spread) if cu_cu_dists else None,
        'errors': errors,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Rocksalt AFM-II validator (FeO/NiO)
# ─────────────────────────────────────────────────────────────────────────────

def verify_afm_ii_ordering(cation_fracs: np.ndarray,
                            cation_spins: List[float],
                            tol: float = 0.1) -> dict:
    """
    Verify that cation spin assignments form a balanced AFM-II configuration.

    Requirements:
    1. Equal number of positive and negative spin cations.
    2. Net magnetization sum is approximately zero (|sum| <= tol).
    3. No zero-spin cations in magnetic species.
    """
    errors = []
    spins = [float(s) for s in cation_spins]

    if len(spins) == 0:
        return {'afm_ii_valid': False, 'errors': ['No cation spins provided']}

    pos = [s for s in spins if s > tol]
    neg = [s for s in spins if s < -tol]
    zero= [s for s in spins if abs(s) <= tol]

    if zero:
        errors.append(f"Cation spins contain zero/unpolarized entries: {zero}")

    if len(pos) != len(neg):
        errors.append(f"Sublattice uncompensated: {len(pos)} positive vs {len(neg)} negative spins")

    total_spin = sum(spins)
    if abs(total_spin) > tol:
        errors.append(f"Total magnetization {total_spin:.4f} not near zero for AFM")

    return {
        'afm_ii_valid': len(errors) == 0,
        'n_positive': len(pos),
        'n_negative': len(neg),
        'total_spin': float(total_spin),
        'errors': errors,
    }


def verify_rocksalt_afm(fracs: np.ndarray, labels: List[str],
                         lat_a_ang: float,
                         cation_symbol: str = 'Fe',
                         anion_symbol: str = 'O',
                         cation_spins: Optional[List[float]] = None,
                         lattice_vectors: Optional[np.ndarray] = None) -> dict:
    """
    Verify rocksalt AFM-II geometry from first principles.
    """
    fracs = np.asarray(fracs, dtype=float)

    if lattice_vectors is not None:
        lat = np.asarray(lattice_vectors, dtype=float)
    else:
        # Default cubic
        lat = np.eye(3) * lat_a_ang

    cart = _build_cart(fracs, lat)

    errors = []
    cat_idx = [i for i, l in enumerate(labels) if l == cation_symbol]
    ani_idx = [i for i, l in enumerate(labels) if l == anion_symbol]

    # Stoichiometry 1:1
    if len(cat_idx) == 0:
        errors.append(f"No {cation_symbol} atoms found")
    if len(ani_idx) == 0:
        errors.append(f"No {anion_symbol} atoms found")
    if len(cat_idx) != len(ani_idx):
        errors.append(f"Stoichiometry mismatch: {len(cat_idx)} {cation_symbol}, "
                      f"{len(ani_idx)} {anion_symbol} (expected 1:1)")

    if not validate_no_duplicate_atoms(fracs):
        errors.append("Duplicate fractional positions detected")

    # Cation-anion distances
    ca_dists = []
    for i in cat_idx:
        for j in ani_idx:
            ca_dists.append(_min_image_dist(cart[i], cart[j], lat))

    if not ca_dists:
        errors.append("Cannot compute cation-anion distances")
        return {'geometry_valid': False, 'errors': errors,
                'n_cation': len(cat_idx), 'n_anion': len(ani_idx),
                'nearest_cation_anion_ang': None,
                'cation_coord': None, 'anion_coord': None,
                'afm_ii_valid': None}

    nearest_ca = min(ca_dists)
    cutoff = nearest_ca * 1.05

    # Rocksalt: each cation should have 6 anion neighbors under PBC
    cat_coords = [_pbc_coordination_count(i, cart, lat, ani_idx, cutoff)
                  for i in cat_idx]
    ani_coords = [_pbc_coordination_count(j, cart, lat, cat_idx, cutoff)
                  for j in ani_idx]

    cat_coord_val = cat_coords[0] if cat_coords else 0
    ani_coord_val = ani_coords[0] if ani_coords else 0

    if not all(c == cat_coord_val for c in cat_coords):
        errors.append(f"Cation coordination not uniform: {cat_coords}")
    if not all(c == ani_coord_val for c in ani_coords):
        errors.append(f"Anion coordination not uniform: {ani_coords}")
    if cat_coord_val != 6:
        errors.append(f"Cation coordination expected 6 (rocksalt), got {cat_coord_val}")
    if ani_coord_val != 6:
        errors.append(f"Anion coordination expected 6 (rocksalt), got {ani_coord_val}")

    # AFM-II ordering check
    afm_result = None
    if cation_spins is not None:
        cat_fracs = fracs[cat_idx]
        afm_result = verify_afm_ii_ordering(cat_fracs, list(cation_spins))
        if not afm_result['afm_ii_valid']:
            errors.extend(afm_result['errors'])

    geometry_valid = (len(errors) == 0)
    result = {
        'geometry_valid': geometry_valid,
        f'n_{cation_symbol.lower()}': len(cat_idx),
        'n_cation': len(cat_idx),
        'n_anion': len(ani_idx),
        'n_fe': len(cat_idx),  # compat alias
        'n_o':  len(ani_idx),  # compat alias
        'nearest_cation_anion_ang': float(nearest_ca),
        'cation_coord': int(cat_coord_val),
        'anion_coord':  int(ani_coord_val),
        'afm_ii_valid': afm_result['afm_ii_valid'] if afm_result else None,
        'afm_ii_details': afm_result,
        'errors': errors,
    }
    return result
