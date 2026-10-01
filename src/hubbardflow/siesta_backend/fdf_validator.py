import re
import numpy as np
from typing import Dict, Any, Tuple, List

class FdfParser:
    def __init__(self, content: str):
        self.content = content
        self.lines = content.splitlines()

    def get_value(self, key: str, default: Any = None) -> Any:
        pattern = re.compile(rf"(?i)^\s*{re.escape(key)}\b\s+(.+)$", re.MULTILINE)
        match = pattern.search(self.content)
        if match:
            return match.group(1).split()[0].strip()
        return default

    def get_block(self, block_name: str) -> List[str]:
        pattern = re.compile(rf"(?i)%block\s+{re.escape(block_name)}\s*(.*?)%endblock\s+{re.escape(block_name)}", re.DOTALL)
        match = pattern.search(self.content)
        if match:
            return match.group(1).strip().splitlines()
        return []

class FdfValidator:
    def __init__(self, parser: FdfParser):
        self.parser = parser

    def check_unit(self, value_str: str) -> float:
        # Simplistic unit normalizer for lattice constants
        # Ang, Bohr, nm -> Ang
        if not value_str:
            return 1.0
        val_match = re.match(r"^([\d\.]+)\s*([a-zA-Z]*)$", str(value_str).strip())
        if val_match:
            val = float(val_match.group(1))
            unit = val_match.group(2).lower()
            if unit == 'bohr':
                return val * 0.529177
            elif unit == 'nm':
                return val * 10.0
            else:
                return val # default Ang
        try:
            return float(value_str)
        except:
            return 1.0

    def detect_spin_mode(self) -> str:
        spin_pol = self.parser.get_value("SpinPolarized", "false").lower() in ("true", "t", "1", "yes", ".true.")
        non_collinear = self.parser.get_value("NonCollinearSpin", "false").lower() in ("true", "t", "1", "yes", ".true.")
        spin_orbit = self.parser.get_value("SpinOrbit", "false").lower() in ("true", "t", "1", "yes", ".true.")
        
        if spin_orbit:
            return "spin-orbit"
        if non_collinear:
            return "non-collinear"
        if spin_pol:
            return "spin-polarized"
        return "non-polarized"

    def detect_orbital_dimension(self, l: int) -> int:
        if l == 2:
            return 25 # 5x5
        if l == 3:
            return 49 # 7x7
        return (2*l + 1)**2

    def validate_multi_species(self) -> bool:
        # Check chemical species label block for cloning
        block = self.parser.get_block("ChemicalSpeciesLabel")
        # Very basic check
        return len(block) > 0

    def enforce_fixed_geometry(self, content: str) -> str:
        # MD.NumCGsteps 0
        if re.search(r"(?i)^\s*MD\.NumCGsteps\b.*$", content, flags=re.MULTILINE):
            content = re.sub(r"(?i)^\s*MD\.NumCGsteps\b.*$", "MD.NumCGsteps       0", content, flags=re.MULTILINE)
        else:
            content += "\nMD.NumCGsteps       0\n"
            
        # Remove MD.TypeOfRun CG
        content = re.sub(r"(?i)^\s*MD\.TypeOfRun\s+CG\b.*$\n?", "", content, flags=re.MULTILINE)
        
        return content
