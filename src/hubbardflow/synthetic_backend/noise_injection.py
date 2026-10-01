from dataclasses import dataclass

@dataclass
class NoiseParams:
    """Parameters for Gaussian noise injection into synthetic occupation data.
    
    Attributes:
        sigma: Standard deviation of Gaussian noise to inject (default 0.0).
        seed: Random seed for reproducible noise generation (default None).
    """
    sigma: float = 0.0
    seed: int | None = None

