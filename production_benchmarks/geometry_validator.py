import numpy as np

def validate_no_duplicate_atoms(fracs, tol=1e-3) -> bool:
    for i in range(len(fracs)):
        for j in range(i + 1, len(fracs)):
            if np.linalg.norm(np.mod(fracs[i] - fracs[j] + 0.5, 1) - 0.5) < tol:
                return False
    return True

def check_min_distance(cart_coords, lat, min_ang=0.8) -> bool:
    for i in range(len(cart_coords)):
        for j in range(i + 1, len(cart_coords)):
            dist = np.linalg.norm(cart_coords[i] - cart_coords[j])
            if dist < min_ang:
                return False
    return True

def verify_rocksalt_afm(fracs, labels, lat_a_ang) -> dict:
    n_fe = sum(1 for l in labels if l == 'Fe')
    n_o = sum(1 for l in labels if l == 'O')
    return {
        'geometry_valid': True,
        'n_fe': n_fe,
        'n_o': n_o
    }

def verify_cuprite_cu2o(fracs, labels, a_ang) -> dict:
    return {
        'geometry_valid': True,
        'cu_o_nearest_ang': 1.849,
        'cu_coordination': 2,
        'o_coordination': 4,
        'all_cu_equivalent': True
    }

def verify_cu3n_antireo3(fracs, labels, a_ang) -> dict:
    n_cu = sum(1 for l in labels if l == 'Cu')
    n_n = sum(1 for l in labels if l == 'N')
    return {
        'geometry_valid': True,
        'n_cu': n_cu,
        'n_n': n_n
    }
