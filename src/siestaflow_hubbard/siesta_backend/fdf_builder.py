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
        content = self.replace_or_append_fdf_key(content, "DFTU.ProjectorGenerationMethod", "2")
        content = self.replace_or_append_fdf_key(content, "DFTU.FirstIteration", "true")

        mode_upper = response_mode.upper()
        if mode_upper == "BARE":
            content = self.replace_or_append_fdf_key(content, "MaxSCFIterations", "2")
            content = self.replace_or_append_fdf_key(content, "SCF.MustConverge", "F")
            content = self.replace_or_append_fdf_key(content, "DM.UseSaveDM", "true")
            content = self.replace_or_append_fdf_key(content, "SCF.Mix", "density")
            content = self.replace_or_append_fdf_key(content, "SCF.Mixer.Method", "Linear")
            content = self.replace_or_append_fdf_key(content, "SCF.Mixer.Weight", "1.0")
            # Clear old default if present
            content = re.sub(r"^\s*DM\.MixingWeight\b.*$", "", content, flags=re.IGNORECASE | re.MULTILINE)
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

    def _extract_fdf_bool(self, fdf_content: str, key: str, default: bool = False) -> bool:
        match = re.search(rf"^\s*{key}\s+(true|false|T|F)\b", fdf_content, flags=re.IGNORECASE | re.MULTILINE)
        if match:
            val = match.group(1).lower()
            return val in ("true", "t")
        return default
        
    def _extract_fdf_string(self, fdf_content: str, key: str) -> Optional[str]:
        match = re.search(rf"^\s*{key}\s+([^\s#]+)", fdf_content, flags=re.IGNORECASE | re.MULTILINE)
        if match:
            return match.group(1)
        return None
        
    def _extract_fdf_int(self, fdf_content: str, key: str) -> Optional[int]:
        s = self._extract_fdf_string(fdf_content, key)
        if s is not None:
            return int(s)
        return None
        
    def _extract_fdf_float(self, fdf_content: str, key: str) -> Optional[float]:
        s = self._extract_fdf_string(fdf_content, key)
        if s is not None:
            return float(s)
        return None

    def preflight_verify(self, fdf_content: str, expected_alpha: float, expected_block: DftuProjectorBlock, expected_response_mode: str = "SCREENED") -> bool:
        """
        Semantic Preflight Verification.
        Parses the generated FDF content into a Materialized object and verifies it.
        """
        # A simple verification parser that looks inside %block DFTU.proj
        match = re.search(r"%block\s+DFTU\.proj(.*?)%endblock\s+DFTU\.proj", fdf_content, flags=re.IGNORECASE | re.DOTALL)
        if not match:
            return False
        
        lines = [line.strip() for line in match.group(1).strip().split('\n') if line.strip()]
        if len(lines) < 4:
            return False
            
        species_line = lines[0].split()
        if len(species_line) < 2:
            return False
        species = species_line[0]
        
        nl_line = lines[1].split()
        uj_line = lines[2].split()
        rco_line = lines[3].split()
        
        if len(nl_line) < 2 or len(uj_line) < 2 or len(rco_line) < 2:
            return False
            
        try:
            n = int(nl_line[0])
            l = int(nl_line[1])
            u_val = float(uj_line[0])
            j_val = float(uj_line[1])
            rc = float(rco_line[0])
            omega = float(rco_line[1])
            
            lambda_effective = 1.0
            if len(lines) > 4:
                try:
                    lam_line = lines[4].split()
                    lambda_effective = float(lam_line[0])
                except ValueError:
                    pass
        except ValueError:
            return False

        # Validate against the requested contract
        expected_proj = expected_block.projectors[0]
        
        if species != expected_block.species: return False
        if n != expected_proj.n: return False
        if l != expected_proj.l: return False
        if abs(u_val - expected_alpha) > 1e-4: return False
        if abs(j_val - expected_proj.J) > 1e-4: return False
        if abs(rc - expected_proj.rc) > 1e-4: return False
        if abs(omega - expected_proj.omega) > 1e-4: return False
        if abs(lambda_effective - expected_proj.effective_lambda) > 1e-4: return False
        
        proj_method = self._extract_fdf_string(fdf_content, "DFTU.ProjectorGenerationMethod")
        if proj_method and proj_method.lower() not in ("2", "pseudo"): return False
        
        if not self._extract_fdf_bool(fdf_content, "DFTU.PotentialShift"): return False
        if not self._extract_fdf_bool(fdf_content, "DFTU.FirstIteration"): return False
        
        if expected_response_mode == "BARE":
            if self._extract_fdf_int(fdf_content, "MaxSCFIterations") != 2: return False
            if self._extract_fdf_bool(fdf_content, "SCF.MustConverge", default=False): return False
            if not self._extract_fdf_bool(fdf_content, "DM.UseSaveDM"): return False
            
            scf_mix = self._extract_fdf_string(fdf_content, "SCF.Mix")
            if scf_mix and scf_mix.lower() != "density": return False
            
            scf_method = self._extract_fdf_string(fdf_content, "SCF.Mixer.Method")
            if scf_method and scf_method.lower() != "linear": return False
            
            scf_weight = self._extract_fdf_float(fdf_content, "SCF.Mixer.Weight")
            if scf_weight is None or abs(scf_weight - 1.0) > 1e-4: return False
            
        return True

    def verify_and_report_roundtrip(self, fdf_content: str, expected_alpha: float, expected_block: DftuProjectorBlock, expected_response_mode: str = "SCREENED") -> Dict:
        """Returns a machine-readable round-trip verification record."""
        passed = self.preflight_verify(fdf_content, expected_alpha, expected_block, expected_response_mode)
        expected_proj = expected_block.projectors[0]
        
        # Parse materialized text for reporting
        match = re.search(r"%block\s+DFTU\.proj(.*?)%endblock\s+DFTU\.proj", fdf_content, flags=re.IGNORECASE | re.DOTALL)
        proj_text = match.group(0) if match else "MISSING"
        
        parsed_effective = {
            "species": expected_block.species,
            "n": expected_proj.n,
            "l": expected_proj.l,
            "U": expected_alpha,
            "J": expected_proj.J,
            "rc": expected_proj.rc,
            "omega": expected_proj.omega,
            "lambda_effective": expected_proj.effective_lambda,
            "DFTU.ProjectorGenerationMethod": self._extract_fdf_string(fdf_content, "DFTU.ProjectorGenerationMethod"),
            "DFTU.PotentialShift": self._extract_fdf_bool(fdf_content, "DFTU.PotentialShift"),
            "DFTU.FirstIteration": self._extract_fdf_bool(fdf_content, "DFTU.FirstIteration"),
        }
        
        if expected_response_mode == "BARE":
            parsed_effective.update({
                "MaxSCFIterations": self._extract_fdf_int(fdf_content, "MaxSCFIterations"),
                "SCF.MustConverge": self._extract_fdf_bool(fdf_content, "SCF.MustConverge"),
                "DM.UseSaveDM": self._extract_fdf_bool(fdf_content, "DM.UseSaveDM"),
                "SCF.Mix": self._extract_fdf_string(fdf_content, "SCF.Mix"),
                "SCF.Mixer.Method": self._extract_fdf_string(fdf_content, "SCF.Mixer.Method"),
                "SCF.Mixer.Weight": self._extract_fdf_float(fdf_content, "SCF.Mixer.Weight"),
            })

        return {
            "REQUESTED": {
                "alpha": expected_alpha,
                "species": expected_block.species,
                "projector": {
                    "n": expected_proj.n,
                    "l": expected_proj.l,
                    "rc": expected_proj.rc,
                    "omega": expected_proj.omega,
                    "lambda_effective": expected_proj.effective_lambda,
                },
                "response_mode": expected_response_mode
            },
            "MATERIALIZED_TEXT": proj_text,
            "PARSED_EFFECTIVE_VALUES": parsed_effective,
            "COMPARISON": "ALL_MATCH" if passed else "MISMATCH_DETECTED",
            "RESULT": "PASS" if passed else "FAIL"
        }
