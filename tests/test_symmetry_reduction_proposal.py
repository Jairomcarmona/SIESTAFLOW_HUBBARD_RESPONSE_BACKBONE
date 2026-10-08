"""Protects geometric, magnetic, and subspace equivalence, not only distances."""

from dataclasses import replace
import unittest

import numpy as np

from symmetry_reduction_proposal import detect_symmetry
from tests.support import geometry


class SymmetryTests(unittest.TestCase):
    def test_valid_translation_orbit_has_small_residuals(self):
        """A translation that preserves all data permits sharing perturbations."""
        result = detect_symmetry(**geometry(4))
        result.verify()
        self.assertEqual(result.orbits, ((0, 1, 2, 3),))
        self.assertEqual(result.reduction_enabled, True)
        self.assertLess(max(operation.geometric_residual for operation in result.magnetic_operations), 1e-12)
        self.assertIn((1, 2, 3, 0), [operation.permutation for operation in result.magnetic_operations])

    def test_crystal_translation_not_magnetic_for_antiferromagnet(self):
        """An AFM translation without time reversal does not preserve magnetic order."""
        data = geometry()
        data["moments"] = [[0, 0, 1], [0, 0, -1]]
        result = detect_symmetry(**data)
        identity_rotation = tuple(map(tuple, np.eye(3, dtype=int)))
        crystal_swaps = [
            operation
            for operation in result.crystal_operations
            if operation.rotation == identity_rotation and operation.permutation == (1, 0)
        ]
        magnetic_swaps = [
            operation
            for operation in result.magnetic_operations
            if operation.rotation == identity_rotation and operation.permutation == (1, 0)
        ]
        self.assertEqual(len(crystal_swaps), 1)
        self.assertEqual(magnetic_swaps, [])
        self.assertAlmostEqual(crystal_swaps[0].magnetic_residual, 2)

    def test_moment_magnitude_breaks_all_swaps(self):
        """No axial rotation can match moments of different magnitudes."""
        data = geometry()
        data["moments"] = [[0, 0, 1], [0, 0, 2]]
        result = detect_symmetry(**data)
        self.assertEqual(result.orbits, ((0,), (1,)))
        self.assertEqual(result.reduction_enabled, False)

    def test_labels_species_projectors_and_subspaces_must_match(self):
        """Geometric proximity does not authorize swapping species or physical definitions."""
        for field, replacement in (
            ("labels", "Ni_distinto"),
            ("species", "O"),
            ("projectors", {"definition": "otra"}),
            ("subspaces", {"n": 4, "l": 2}),
        ):
            with self.subTest(field=field):
                data = geometry()
                data[field][1] = replacement
                result = detect_symmetry(**data)
                self.assertEqual(result.reduction_enabled, False)
                self.assertEqual(result.orbits, ((0,), (1,)))

    def test_duplicate_sites_disable_reduction(self):
        """A non-unique correspondence invalidates all reduction; the nearest match is not selected."""
        data = geometry()
        data["coordinates"][1] = data["coordinates"][0]
        result = detect_symmetry(**data)
        self.assertEqual(result.ambiguous, True)
        self.assertEqual(result.reduction_enabled, False)
        with self.assertRaisesRegex(ValueError, "ambiguous"):
            result.verify()

    def test_missing_definitions_disable_reduction(self):
        """Missing evidence does not establish subspace equivalence."""
        data = geometry()
        data["projectors"] = [{}, {}]
        self.assertEqual(detect_symmetry(**data).reduction_enabled, False)

    def test_geometric_distortion_breaks_site_orbit(self):
        """Displacing a site breaks equivalence in a uniform periodic chain."""
        data = geometry(4)
        data["coordinates"][-1] = [0.81, 0.03, 0.02]
        result = detect_symmetry(**data)
        self.assertEqual(result.reduction_enabled, False)
        self.assertEqual(result.orbits, ((0,), (1,), (2,), (3,)))

    def test_cartesian_and_fractional_agree_in_skew_cell(self):
        """Coordinate units and lattice convention do not change orbits in a skew cell."""
        data = geometry()
        data["lattice"] = np.array([[4, 0, 0], [1.1, 5, 0], [0.3, 0.2, 6]])
        fractional = detect_symmetry(**data)
        data["coordinates"] = np.asarray(data["coordinates"]) @ data["lattice"]
        cartesian = detect_symmetry(**data, coordinate_format="cartesian_angstrom")
        self.assertEqual(fractional.orbits, cartesian.orbits)
        self.assertEqual(cartesian.reduction_enabled, True)

    def test_certificate_tampering_detected(self):
        """Do not use a modified permutation without renewing its evidence."""
        result = detect_symmetry(**geometry())
        with self.assertRaisesRegex(ValueError, "altered"):
            replace(result, input_hash="0" * 64).verify()

    def test_invalid_lattice_and_units_rejected(self):
        """Degenerate geometry or unknown units does not certify symmetry."""
        data = geometry()
        with self.assertRaisesRegex(ValueError, "Normalize"):
            detect_symmetry(**data, coordinate_format="scaled_unknown")
        data["lattice"] = np.zeros((3, 3))
        with self.assertRaisesRegex(ValueError, "singular"):
            detect_symmetry(**data)
