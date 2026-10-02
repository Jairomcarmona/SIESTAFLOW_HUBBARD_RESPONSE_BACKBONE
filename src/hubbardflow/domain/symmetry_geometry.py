"""Exact lattice and reciprocal-mesh tests without undeclared tolerances."""

from __future__ import annotations

from fractions import Fraction

from .symmetry_operation_models import Rotation, SymmetryModel


def _lattice_compatible(rotation: Rotation, model: SymmetryModel) -> bool:
    # Exact decimal rational arithmetic avoids introducing a lattice tolerance.
    lattice = [[Fraction(str(value)) for value in row] for row in model.lattice_vectors_angstrom]
    metric = [[sum(lattice[i][k] * lattice[j][k] for k in range(3)) for j in range(3)] for i in range(3)]
    return all(
        sum(rotation[k][i] * metric[k][l] * rotation[l][j] for k in range(3) for l in range(3))
        == metric[i][j]
        for i in range(3)
        for j in range(3)
    )


def _k_invariant(rotation: Rotation, mesh: tuple[tuple[int, int, int, float], ...] | None) -> bool:
    if mesh is None or len(mesh) != 3:
        return False
    # Each row is a supercell vector in the parent-lattice basis. Thus the
    # reciprocal subgroup satisfies K @ k in Z^3 and its generators are the
    # columns of inv(K), not its rows. SIESTA manual, kgrid.MonkhorstPack:
    # https://docs.siesta-project.org/projects/siesta/en/5.4/reference/siesta.html
    matrix = [[Fraction(value) for value in row[:3]] for row in mesh]
    augmented = [matrix[i] + [Fraction(int(i == j)) for j in range(3)] for i in range(3)]
    for column in range(3):
        pivot = next((i for i in range(column, 3) if augmented[i][column]), None)
        if pivot is None:
            return False
        augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
        divisor = augmented[column][column]
        augmented[column] = [x / divisor for x in augmented[column]]
        for i in range(3):
            if i != column:
                factor = augmented[i][column]
                augmented[i] = [x - factor * y for x, y in zip(augmented[i], augmented[column], strict=True)]
    inverse = [row[3:] for row in augmented]
    # A reciprocal mesh is invariant iff R maps its integer generators and its
    # offset into the same reciprocal subgroup modulo the parent reciprocal lattice.
    generators = [tuple(inverse[j][i] for j in range(3)) for i in range(3)]
    offset = [sum(Fraction(str(mesh[i][3])) * generators[i][j] for i in range(3)) for j in range(3)]
    for vector, is_offset in [*((vector, False) for vector in generators), (tuple(offset), True)]:
        transformed = [sum(rotation[i][j] * vector[i] for i in range(3)) for j in range(3)]
        if is_offset:
            transformed = [x - y for x, y in zip(transformed, offset, strict=True)]
        coefficients = [sum(matrix[i][j] * transformed[j] for j in range(3)) for i in range(3)]
        if any(x.denominator != 1 for x in coefficients):
            return False
    return True
