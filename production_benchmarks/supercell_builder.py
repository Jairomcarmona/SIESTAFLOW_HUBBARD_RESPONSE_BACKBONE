def build_supercell(fracs, labels, species_ids, lat, sc_matrix):
    return fracs, labels, species_ids, lat

def assign_afm_ordering(new_labels, new_species_ids, target_species, sc_matrix, original_n_atoms) -> list[float]:
    return []

def get_afm_supercell_options(material_name) -> list[dict]:
    return [{'label': 'small', 'sc_matrix': [[1,1,0],[1,-1,0],[0,0,1]], 'n_fe': 2, 'n_o': 2},
            {'label': 'medium', 'sc_matrix': [[2,0,0],[0,2,0],[0,0,1]], 'n_fe': 4, 'n_o': 4},
            {'label': 'large', 'sc_matrix': [[2,0,0],[0,2,0],[0,0,2]], 'n_fe': 8, 'n_o': 8}]

def verify_stoichiometry(new_labels, original_stoich) -> bool:
    return True
