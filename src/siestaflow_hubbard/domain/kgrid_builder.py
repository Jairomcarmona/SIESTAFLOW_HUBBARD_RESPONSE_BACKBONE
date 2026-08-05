import numpy as np
from typing import List

class KGridBuilder:
    @staticmethod
    def generate_kgrid(lattice_vectors: np.ndarray, k_cutoff_ang: float = 30.0, is_2d: bool = False) -> List[int]:
        # lattice_vectors is 3x3 matrix where rows are a, b, c vectors
        norms = np.linalg.norm(lattice_vectors, axis=1)
        
        grid = []
        for i in range(3):
            val = round(k_cutoff_ang / norms[i])
            grid.append(max(1, int(val)))
            
        if is_2d:
            grid[2] = 1
            
        # Check for cubic (a=b=c and alpha=beta=gamma=90)
        # Simplified check for cubic based on norms
        if np.isclose(norms[0], norms[1]) and np.isclose(norms[1], norms[2]):
            # Check orthogonality
            dot_ab = np.dot(lattice_vectors[0], lattice_vectors[1])
            dot_ac = np.dot(lattice_vectors[0], lattice_vectors[2])
            dot_bc = np.dot(lattice_vectors[1], lattice_vectors[2])
            if np.isclose(dot_ab, 0) and np.isclose(dot_ac, 0) and np.isclose(dot_bc, 0):
                # Cubic: enforce N x N x N
                max_n = max(grid)
                grid = [max_n, max_n, max_n]
                
        return grid

def generate_kgrid(lattice_vectors: np.ndarray, k_cutoff_ang: float = 30.0, is_2d: bool = False) -> List[int]:
    return KGridBuilder.generate_kgrid(lattice_vectors, k_cutoff_ang, is_2d)
