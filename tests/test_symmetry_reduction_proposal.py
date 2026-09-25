"""Protege equivalencia geométrica, magnética y de subespacios, no sólo distancias."""

from dataclasses import replace
import unittest

import numpy as np

from symmetry_reduction_proposal import detect_symmetry
from tests.support import geometry


class SymmetryTests(unittest.TestCase):
    def test_valid_translation_orbit_has_small_residuals(self):
        """Una traslación que preserva todos los datos permite compartir perturbaciones."""
        result = detect_symmetry(**geometry(4))
        result.verify()
        self.assertEqual(result.orbits, ((0, 1, 2, 3),))
        self.assertEqual(result.reduction_enabled, True)
        self.assertLess(max(operation.geometric_residual for operation in result.magnetic_operations), 1e-12)
        self.assertIn((1, 2, 3, 0), [operation.permutation for operation in result.magnetic_operations])

    def test_crystal_translation_not_magnetic_for_antiferromagnet(self):
        """Una traslación AFM sin inversión temporal no preserva el orden magnético."""
        data = geometry()
        data["moments"] = [[0, 0, 1], [0, 0, -1]]
        result = detect_symmetry(**data)
        identity_rotation = tuple(map(tuple, np.eye(3, dtype=int)))
        crystal_swaps = [operation for operation in result.crystal_operations
                         if operation.rotation == identity_rotation and operation.permutation == (1, 0)]
        magnetic_swaps = [operation for operation in result.magnetic_operations
                          if operation.rotation == identity_rotation and operation.permutation == (1, 0)]
        self.assertEqual(len(crystal_swaps), 1)
        self.assertEqual(magnetic_swaps, [])
        self.assertAlmostEqual(crystal_swaps[0].magnetic_residual, 2)

    def test_moment_magnitude_breaks_all_swaps(self):
        """Ninguna rotación axial puede igualar momentos de magnitudes distintas."""
        data = geometry()
        data["moments"] = [[0, 0, 1], [0, 0, 2]]
        result = detect_symmetry(**data)
        self.assertEqual(result.orbits, ((0,), (1,)))
        self.assertEqual(result.reduction_enabled, False)

    def test_labels_species_projectors_and_subspaces_must_match(self):
        """Proximidad geométrica no autoriza intercambiar especies ni definiciones físicas."""
        for field, replacement in (("labels", "Ni_distinto"), ("species", "O"),
                                   ("projectors", {"definition": "otra"}),
                                   ("subspaces", {"n": 4, "l": 2})):
            with self.subTest(field=field):
                data = geometry()
                data[field][1] = replacement
                result = detect_symmetry(**data)
                self.assertEqual(result.reduction_enabled, False)
                self.assertEqual(result.orbits, ((0,), (1,)))

    def test_duplicate_sites_disable_reduction(self):
        """Correspondencia no unívoca invalida toda reducción, no se elige el más cercano."""
        data = geometry()
        data["coordinates"][1] = data["coordinates"][0]
        result = detect_symmetry(**data)
        self.assertEqual(result.ambiguous, True)
        self.assertEqual(result.reduction_enabled, False)
        with self.assertRaisesRegex(ValueError, "ambiguo"):
            result.verify()

    def test_missing_definitions_disable_reduction(self):
        """La ausencia de evidencia no equivale a equivalencia de subespacios."""
        data = geometry()
        data["projectors"] = [{}, {}]
        self.assertEqual(detect_symmetry(**data).reduction_enabled, False)

    def test_geometric_distortion_breaks_site_orbit(self):
        """Desplazar un sitio destruye la equivalencia de una cadena periódica uniforme."""
        data = geometry(4)
        data["coordinates"][-1] = [0.81, 0.03, 0.02]
        result = detect_symmetry(**data)
        self.assertEqual(result.reduction_enabled, False)
        self.assertEqual(result.orbits, ((0,), (1,), (2,), (3,)))

    def test_cartesian_and_fractional_agree_in_skew_cell(self):
        """Unidades y convención de red no cambian órbitas en una celda oblicua."""
        data = geometry()
        data["lattice"] = np.array([[4, 0, 0], [1.1, 5, 0], [0.3, 0.2, 6]])
        fractional = detect_symmetry(**data)
        data["coordinates"] = np.asarray(data["coordinates"]) @ data["lattice"]
        cartesian = detect_symmetry(**data, coordinate_format="cartesian_angstrom")
        self.assertEqual(fractional.orbits, cartesian.orbits)
        self.assertEqual(cartesian.reduction_enabled, True)

    def test_certificate_tampering_detected(self):
        """No usar una permutación modificada sin renovar su evidencia."""
        result = detect_symmetry(**geometry())
        with self.assertRaisesRegex(ValueError, "alterado"):
            replace(result, input_hash="0" * 64).verify()

    def test_invalid_lattice_and_units_rejected(self):
        """Una geometría degenerada o de unidades desconocidas no certifica simetría."""
        data = geometry()
        with self.assertRaisesRegex(ValueError, "Normalizar"):
            detect_symmetry(**data, coordinate_format="scaled_unknown")
        data["lattice"] = np.zeros((3, 3))
        with self.assertRaisesRegex(ValueError, "singular"):
            detect_symmetry(**data)
