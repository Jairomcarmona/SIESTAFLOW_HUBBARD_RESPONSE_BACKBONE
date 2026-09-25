"""Datos inventados para pruebas algebraicas, sin archivos de cálculos reales."""

from hashlib import sha256

import numpy as np

from symmetry_reduction_proposal import detect_symmetry


def digest(text):
    return sha256(text.encode()).hexdigest()


def geometry(count=2):
    return {
        "lattice": np.diag([4.0, 5.0, 6.0]),
        "coordinates": [[index / count, 0, 0] for index in range(count)],
        "species": ["Ni"] * count, "labels": ["Ni"] * count,
        "moments": [[0, 0, 0] for index in range(count)],
        "subspaces": [{"complete_l_shell": True, "scalar_occupation": True,
                       "n": 3, "l": 2} for index in range(count)],
        "projectors": [{"rotationally_invariant": True, "definition": "synthetic_3d"}
                       for index in range(count)],
    }


def certificate(count=2):
    return detect_symmetry(**geometry(count))


def projector_fixture():
    content = (b'<psml xmlns="urn:synthetic-psml"><pseudo-atom-spec atomic-label="Ni" '
               b'atomic-number="28"><valence-configuration><shell n="3" l="2"/>'
               b'</valence-configuration></pseudo-atom-spec></psml>')
    projector = {"species": "Ni", "atomic_number": 28, "n": 3, "l": 2,
                 "shell": "3d", "m_values": [-2, -1, 0, 1, 2], "rc_bohr": 2.5,
                 "method": "method2", "pseudo_sha256": sha256(content).hexdigest()}
    subspace = {key: projector[key] for key in ("species", "n", "l", "m_values")}
    subspace["occupation_definition"] = "trace_full_l_shell"
    return projector, subspace, {"Ni": content}
