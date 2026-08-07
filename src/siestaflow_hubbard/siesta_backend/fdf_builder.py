import re
from typing import List, Dict, Optional
from siestaflow_hubbard.siesta_backend.fdf_validator import FdfValidator, FdfParser
from siestaflow_hubbard.siesta_backend.dftu_models import DftuProjector, DftuProjectorBlock

class FdfBuilder:
    """Handles reading an FDF file and writing it out with linear response modifications."""

    def __init__(self, base_fdf_path: Optional[str] = None):
        self.base_fdf_path = base_fdf_path

    def read_fdf(self, path: str) -> str:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()

    def write_fdf(self, path: str, content: str) -> None:
        with open(path, "w", encoding="utf-8", newline='\n') as f:
            f.write(content)

    def construct_dftu_proj_block(self, projections: List[Dict], alpha: float) -> str:
        """
        Constructs the DFTU.proj block enforcing the 4-line method-2 format.
        For linear response, U is strictly mapped to alpha, and J is strictly 0.0.
        """
        blocks = []
        # Group projections by species (assuming 1 block per species)
        species_map = {}
        for proj_dict in projections:
            sp = proj_dict.get("species", "Mn")
            if sp not in species_map:
                species_map[sp] = []
            
            # Map U to alpha and J to 0 for linear response
            proj = DftuProjector(
                n=proj_dict.get("n", 3),
                l=proj_dict.get("l", 2),
                U=alpha,  # LINEAR RESPONSE CONTRACT
                J=0.0,    # LINEAR RESPONSE CONTRACT
                rc=proj_dict.get("rc", 3.0),
                omega=proj_dict.get("omega", 0.05),
                lambda_factor=proj_dict.get("lambda_factor", None)
            )
            species_map[sp].append(proj)
        
        lines = ["%block DFTU.proj"]
        for sp, projs in species_map.items():
            block = DftuProjectorBlock(species=sp, projectors=projs)
            lines.append(block.serialize())
        lines.append("%endblock DFTU.proj")
        
        return "\n".join(lines)

    def replace_or_append_fdf_key(self, content: str, key: str, value: str) -> str:
        """Replaces an FDF key by value, or appends it if absent."""
        # Case insensitive match for the key at the start of a line
        pattern = re.compile(rf"^\s*{re.escape(key)}\b.*$", flags=re.IGNORECASE | re.MULTILINE)
        replacement = f"{key} {value}"
        
        if pattern.search(content):
            content = pattern.sub(replacement, content)
        else:
            # Ensure the file ends with a newline before appending
            if not content.endswith("\n"):
                content += "\n"
            content += f"{replacement}\n"
        return content

    def modify_fdf_content(
        self,
        content: str,
        alpha: float,
        run_name: Optional[str] = None,
        response_mode: str = "SCREENED",
        species: str = "Mn",
        n: int = 3,
        l: int = 2,
        rc: float = 3.0,
        omega: float = 0.05,
        lambda_factor: Optional[float] = None,
        projections: Optional[List[Dict]] = None,
    ) -> str:
        """Modifies FDF text content for BARE or SCREENED response mode."""
        
        if run_name:
            content = self.replace_or_append_fdf_key(content, "SystemLabel", run_name)

        if projections is None:
            projections = [
                {
                    "species": species,
                    "n": n,
                    "l": l,
                    "rc": rc,
                    "omega": omega,
                    "lambda_factor": lambda_factor
                }
            ]

        proj_block_str = self.construct_dftu_proj_block(projections, alpha)

        # Remove pre-existing DFTU.proj block if present (both LDAU and DFTU)
        content = re.sub(
            r"%block\s+(DFTU|LDAU)\.proj.*?%endblock\s+(DFTU|LDAU)\.proj",
            "",
            content,
            flags=re.IGNORECASE | re.DOTALL,
        )

        content = content.rstrip() + "\n\n" + proj_block_str + "\n"

        # Explicitly enforce linear response booleans by VALUE (not presence)
        content = self.replace_or_append_fdf_key(content, "DFTU.PotentialShift", "true")
        content = self.replace_or_append_fdf_key(content, "DFTU.FirstIteration", "true")

        mode_upper = response_mode.upper()
        if mode_upper == "BARE":
            content = self.replace_or_append_fdf_key(content, "MaxSCFIterations", "2")
            content = self.replace_or_append_fdf_key(content, "DM.MixingWeight", "1.0")
            content = self.replace_or_append_fdf_key(content, "DM.UseSaveDM", "true")
        elif mode_upper == "SCREENED":
            content = self.replace_or_append_fdf_key(content, "DM.UseSaveDM", "true")

        # Apply geometry enforcement
        parser = FdfParser(content)
        validator = FdfValidator(parser)
        content = validator.enforce_fixed_geometry(content)

        return content

    def prepare_fdf(
        self,
        base_fdf_path: str,
        target_fdf_path: str,
        alpha: float,
        run_name: Optional[str] = None,
        response_mode: str = "SCREENED",
        species: str = "Mn",
        n: int = 3,
        l: int = 2,
        rc: float = 3.0,
        omega: float = 0.05,
        lambda_factor: Optional[float] = None,
        projections: Optional[List[Dict]] = None,
    ) -> str:
        """Reads base FDF file, applies modifications, and writes target FDF file."""
        content = self.read_fdf(base_fdf_path)
        modified_content = self.modify_fdf_content(
            content=content,
            alpha=alpha,
            run_name=run_name,
            response_mode=response_mode,
            species=species,
            n=n,
            l=l,
            rc=rc,
            omega=omega,
            lambda_factor=lambda_factor,
            projections=projections,
        )
        self.write_fdf(target_fdf_path, modified_content)
        return modified_content

    def prepare_fdf_bare(
        self,
        base_fdf_path: str,
        target_fdf_path: str,
        alpha: float,
        run_name: Optional[str] = None,
        **kwargs,
    ) -> str:
        return self.prepare_fdf(
            base_fdf_path=base_fdf_path,
            target_fdf_path=target_fdf_path,
            alpha=alpha,
            run_name=run_name,
            response_mode="BARE",
            **kwargs,
        )

    def prepare_fdf_screened(
        self,
        base_fdf_path: str,
        target_fdf_path: str,
        alpha: float,
        run_name: Optional[str] = None,
        **kwargs,
    ) -> str:
        return self.prepare_fdf(
            base_fdf_path=base_fdf_path,
            target_fdf_path=target_fdf_path,
            alpha=alpha,
            run_name=run_name,
            response_mode="SCREENED",
            **kwargs,
        )

    def preflight_verify(self, fdf_content: str, expected_alpha: float) -> bool:
        """
        Semantic Preflight Verification.
        Parses the generated FDF content to ensure U == expected_alpha and J == 0.
        """
        # A simple verification parser that looks inside %block DFTU.proj
        match = re.search(r"%block\s+DFTU\.proj(.*?)%endblock\s+DFTU\.proj", fdf_content, flags=re.IGNORECASE | re.DOTALL)
        if not match:
            return False
        
        lines = [line.strip() for line in match.group(1).strip().split('\n') if line.strip()]
        # lines[0] = species num_shells
        # lines[1] = n l
        # lines[2] = U J
        if len(lines) < 3:
            return False
            
        parts = lines[2].split()
        if len(parts) < 2:
            return False
            
        try:
            u_val = float(parts[0])
            j_val = float(parts[1])
            # Account for floating point formatting precision
            if abs(u_val - expected_alpha) > 1e-4:
                return False
            if abs(j_val - 0.0) > 1e-4:
                return False
        except ValueError:
            return False
            
        # Verify booleans
        if not re.search(r"^\s*DFTU\.PotentialShift\s+true", fdf_content, flags=re.IGNORECASE | re.MULTILINE):
            return False
        if not re.search(r"^\s*DFTU\.FirstIteration\s+true", fdf_content, flags=re.IGNORECASE | re.MULTILINE):
            return False
            
        return True
