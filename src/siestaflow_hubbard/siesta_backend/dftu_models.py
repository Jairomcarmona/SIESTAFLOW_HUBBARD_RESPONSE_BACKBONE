import hashlib
from dataclasses import dataclass
from typing import Optional, List

@dataclass
class DftuProjector:
    """
    Strict representation of a single shell in the SIESTA 5.4.2 method-2 DFTU.Proj block.
    Contract: n l / U J / rc omega / lambda
    """
    n: int
    l: int
    U: float
    J: float
    rc: float
    omega: float
    lambda_factor: Optional[float] = None

    def serialize(self) -> str:
        lines = [
            f"  {self.n}  {self.l}",
            f"  {self.U:.4f}  {self.J:.4f}",
            f"  {self.rc:.4f}  {self.omega:.4f}",
        ]
        if self.lambda_factor is not None:
            lines.append(f"  {self.lambda_factor:.4f}")
        return "\n".join(lines)
    
    def get_fingerprint(self) -> str:
        """
        Returns a SHA-256 fingerprint of the structural components (everything except U/J).
        This proves that the projector geometry remains invariant across an alpha scan.
        """
        structural_data = f"{self.n}:{self.l}:{self.rc:.4f}:{self.omega:.4f}:{self.lambda_factor}"
        return hashlib.sha256(structural_data.encode("utf-8")).hexdigest()

@dataclass
class DftuProjectorBlock:
    """
    Represents the full %block DFTU.Proj entry for a specific species.
    """
    species: str
    projectors: List[DftuProjector]

    def serialize(self) -> str:
        lines = [f"  {self.species}   {len(self.projectors)}"]
        for p in self.projectors:
            lines.append(p.serialize())
        return "\n".join(lines)

    def get_fingerprint(self) -> str:
        """Returns a combined structural fingerprint for the entire block."""
        return hashlib.sha256(
            "".join(p.get_fingerprint() for p in self.projectors).encode("utf-8")
        ).hexdigest()
