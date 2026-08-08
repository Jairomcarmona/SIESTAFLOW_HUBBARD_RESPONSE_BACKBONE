import re
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from siestaflow_hubbard.siesta_backend.fdf_validator import FdfValidator, FdfParser
from siestaflow_hubbard.siesta_backend.dftu_models import DftuProjector, DftuProjectorBlock

@dataclass(frozen=True)
class MaterializedDftuContract:
    species: str
    n: int
    l: int
    U: float
    J: float
    rc: float
    omega: float
    lambda_effective: float
    projector_method: Optional[str]
    potential_shift: bool
    first_iteration: bool
    max_scf_iterations: Optional[int]
    must_converge: Optional[bool]
    use_save_dm: Optional[bool]
    scf_mix: Optional[str]
    mixer_method: Optional[str]
    mixer_weight: Optional[float]
    
    @property
    def is_bare_valid(self) -> bool:
        if self.max_scf_iterations != 2: return False
        if self.must_converge is not False: return False
        if self.use_save_dm is not True: return False
        if not self.scf_mix or self.scf_mix.lower() != "density": return False
        if not self.mixer_method or self.mixer_method.lower() != "linear": return False
        if self.mixer_weight is None or abs(self.mixer_weight - 1.0) > 1e-4: return False
        if not self.projector_method or self.projector_method.lower() not in ("2", "pseudo"): return False
        if not self.potential_shift: return False
        if not self.first_iteration: return False
        return True

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

    def parse_materialized_dftu_contract(self, fdf_content: str, target_species: str) -> Optional[MaterializedDftuContract]:
        """Parses the materialized FDF text directly and returns a typed contract object."""
        # Find the DFTU.proj block and look for the specific species
        match = re.search(r"%block\s+DFTU\.proj(.*?)%endblock\s+DFTU\.proj", fdf_content, flags=re.IGNORECASE | re.DOTALL)
        if not match:
            return None
            
        block_text = match.group(1).strip()
        species_lines = []
        in_species = False
        for line in block_text.split('\n'):
            line = line.strip()
            if not line: continue
            
            parts = line.split()
            if not in_species:
                if parts[0] == target_species:
                    in_species = True
                    species_lines.append(line)
            else:
                species_lines.append(line)
                # If we have 5 lines, we definitely have the whole shell block (including lambda)
                # If we have 4 lines, we might be at the end of the block. We should peek at the next line,
                # but in a simple loop it's hard. Instead we can just collect all lines for this species
                # until we hit another species (line with 2 elements where first is string).
                if len(parts) == 2 and not parts[1].replace('.','',1).isdigit():
                    # Another species started (e.g. "O 1")
                    species_lines.pop()
                    break
                if len(species_lines) == 5:
                    break
        
        if len(species_lines) < 4:
            return None
            
        species = species_lines[0].split()[0]
        
        nl_line = species_lines[1].split()
        uj_line = species_lines[2].split()
        rco_line = species_lines[3].split()
        
        if len(nl_line) < 2 or len(uj_line) < 2 or len(rco_line) < 2:
            return None
            
        try:
            n = int(nl_line[0])
            l = int(nl_line[1])
            u_val = float(uj_line[0])
            j_val = float(uj_line[1])
            rc = float(rco_line[0])
            omega = float(rco_line[1])
            
            lambda_effective = 1.0
            if len(species_lines) > 4:
                lam_line = species_lines[4].split()
                if lam_line:
                    lambda_effective = float(lam_line[0])
        except ValueError:
            return None
            
        return MaterializedDftuContract(
            species=species,
            n=n,
            l=l,
            U=u_val,
            J=j_val,
            rc=rc,
            omega=omega,
            lambda_effective=lambda_effective,
            projector_method=self._extract_fdf_string(fdf_content, "DFTU.ProjectorGenerationMethod"),
            potential_shift=self._extract_fdf_bool(fdf_content, "DFTU.PotentialShift"),
            first_iteration=self._extract_fdf_bool(fdf_content, "DFTU.FirstIteration"),
            max_scf_iterations=self._extract_fdf_int(fdf_content, "MaxSCFIterations"),
            must_converge=self._extract_fdf_bool(fdf_content, "SCF.MustConverge"),
            use_save_dm=self._extract_fdf_bool(fdf_content, "DM.UseSaveDM"),
            scf_mix=self._extract_fdf_string(fdf_content, "SCF.Mix"),
            mixer_method=self._extract_fdf_string(fdf_content, "SCF.Mixer.Method"),
            mixer_weight=self._extract_fdf_float(fdf_content, "SCF.Mixer.Weight")
        )

    def preflight_verify(self, fdf_content: str, expected_alpha: float, expected_block: DftuProjectorBlock, expected_response_mode: str = "SCREENED") -> bool:
        """Wrapper around verify_and_report_roundtrip for backward compatibility."""
        res = self.verify_and_report_roundtrip(fdf_content, expected_alpha, expected_block, expected_response_mode)
        return res["RESULT"] == "PASS"

    def verify_and_report_roundtrip(self, fdf_content: str, expected_alpha: float, expected_block: DftuProjectorBlock, expected_response_mode: str = "SCREENED") -> Dict:
        """Returns a machine-readable round-trip verification record based on materialized parsing."""
        parsed_contract = self.parse_materialized_dftu_contract(fdf_content, expected_block.species)
        
        match = re.search(r"%block\s+DFTU\.proj(.*?)%endblock\s+DFTU\.proj", fdf_content, flags=re.IGNORECASE | re.DOTALL)
        proj_text = match.group(0) if match else "MISSING"
        
        passed = False
        parsed_effective = {}
        expected_proj = expected_block.projectors[0]
        
        if parsed_contract:
            # Map parsed_contract back to dict
            parsed_effective = {
                "species": parsed_contract.species,
                "n": parsed_contract.n,
                "l": parsed_contract.l,
                "U": parsed_contract.U,
                "J": parsed_contract.J,
                "rc": parsed_contract.rc,
                "omega": parsed_contract.omega,
                "lambda_effective": parsed_contract.lambda_effective,
                "DFTU.ProjectorGenerationMethod": parsed_contract.projector_method,
                "DFTU.PotentialShift": parsed_contract.potential_shift,
                "DFTU.FirstIteration": parsed_contract.first_iteration,
            }
            if expected_response_mode == "BARE":
                parsed_effective.update({
                    "MaxSCFIterations": parsed_contract.max_scf_iterations,
                    "SCF.MustConverge": parsed_contract.must_converge,
                    "DM.UseSaveDM": parsed_contract.use_save_dm,
                    "SCF.Mix": parsed_contract.scf_mix,
                    "SCF.Mixer.Method": parsed_contract.mixer_method,
                    "SCF.Mixer.Weight": parsed_contract.mixer_weight,
                })
            
            # Check correctness
            checks = [
                parsed_contract.species == expected_block.species,
                parsed_contract.n == expected_proj.n,
                parsed_contract.l == expected_proj.l,
                abs(parsed_contract.U - expected_alpha) < 1e-4,
                abs(parsed_contract.J - expected_proj.J) < 1e-4,
                abs(parsed_contract.rc - expected_proj.rc) < 1e-4,
                abs(parsed_contract.omega - expected_proj.omega) < 1e-4,
                abs(parsed_contract.lambda_effective - expected_proj.effective_lambda) < 1e-4,
                parsed_contract.projector_method and parsed_contract.projector_method.lower() in ("2", "pseudo"),
                parsed_contract.potential_shift is True,
                parsed_contract.first_iteration is True
            ]
            
            if expected_response_mode == "BARE":
                checks.append(parsed_contract.is_bare_valid)
                
            passed = all(checks)

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
