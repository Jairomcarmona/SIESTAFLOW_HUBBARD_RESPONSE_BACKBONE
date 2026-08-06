import re
from typing import List, Dict, Optional
from siestaflow_hubbard.siesta_backend.fdf_validator import FdfValidator, FdfParser



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

    def construct_dftu_proj_block(self, projections: List[Dict]) -> str:
        """
        Constructs the DFTU.proj block with 5 lines per projection and exact spacing.
        Prototype format:
        %block DFTU.proj
          Mn   1
          3  2
          {rc:.4f}  {width:.4f}
          {alpha:.4f}  {u_val:.4f}
          {j_val:.4f}
        %endblock DFTU.proj
        """
        lines = ["%block DFTU.proj"]
        for proj in projections:
            species = proj.get("species", "Mn")
            num_shells = proj.get("num_shells", 1)
            n = proj.get("n", 3)
            l = proj.get("l", 2)
            rc = proj.get("rc", 0.0)
            width = proj.get("width", 0.0)
            alpha = proj.get("alpha", 0.0)
            u_val = proj.get("u_val", 0.0)
            j_val = proj.get("j_val", 0.0)

            lines.append(f"  {species}   {num_shells}")
            lines.append(f"  {n}  {l}")
            lines.append(f"  {rc:.4f}  {width:.4f}")
            lines.append(f"  {u_val:.4f}  {alpha:.4f}")
            lines.append(f"  {j_val:.4f}")
        lines.append("%endblock DFTU.proj")
        return "\n".join(lines)

    def modify_fdf_content(
        self,
        content: str,
        alpha: float,
        run_name: Optional[str] = None,
        response_mode: str = "SCREENED",
        species: str = "Mn",
        num_shells: int = 1,
        n: int = 3,
        l: int = 2,
        u_val: float = 0.0,
        j_val: float = 0.0,
        projections: Optional[List[Dict]] = None,
    ) -> str:
        """Modifies FDF text content for BARE or SCREENED response mode."""
        # Replace SystemLabel if run_name is provided
        if run_name:
            if re.search(r"(?i)^\s*SystemLabel\b.*$", content, flags=re.MULTILINE):
                content = re.sub(
                    r"(?i)^\s*SystemLabel\b.*$",
                    f"SystemLabel         {run_name}",
                    content,
                    flags=re.MULTILINE,
                )
            else:
                content = f"SystemLabel         {run_name}\n" + content

        # Construct projection specification
        if projections is None:
            projections = [
                {
                    "species": species,
                    "num_shells": num_shells,
                    "n": n,
                    "l": l,
                    "alpha": alpha,
                    "u_val": u_val,
                    "j_val": j_val,
                }
            ]

        proj_block_str = self.construct_dftu_proj_block(projections)

        # Remove pre-existing DFTU.proj block if present
        content = re.sub(
            r"(?i)%block\s+DFTU\.proj.*?%endblock\s+DFTU\.proj",
            "",
            content,
            flags=re.DOTALL,
        )

        content = content.rstrip() + "\n\n" + proj_block_str + "\n"

        # Append DFTU.PotentialShift true if not present
        if not re.search(r"(?i)^\s*DFTU\.PotentialShift\b", content, flags=re.MULTILINE):
            content += "DFTU.PotentialShift true\n"

        mode_upper = response_mode.upper()
        if mode_upper == "BARE":
            # BARE is intentionally a short, frozen-density response. After
            # two iterations the density is generally not converged to
            # DM.Tolerance, so prevent SIESTA from aborting the response job.
            if re.search(r"(?i)^\s*MaxSCFIterations\b.*$", content, flags=re.MULTILINE):
                content = re.sub(
                    r"(?i)^\s*MaxSCFIterations\b.*$",
                    "MaxSCFIterations    2",
                    content,
                    flags=re.MULTILINE,
                )
            else:
                content += "MaxSCFIterations    2\n"

            if re.search(r"(?i)^\s*DM\.MixingWeight\b.*$", content, flags=re.MULTILINE):
                content = re.sub(
                    r"(?i)^\s*DM\.MixingWeight\b.*$",
                    "DM.MixingWeight     1.0",
                    content,
                    flags=re.MULTILINE,
                )
            else:
                content += "DM.MixingWeight     1.0\n"

            if re.search(r"(?i)^\s*SCF\.MustConverge\b.*$", content, flags=re.MULTILINE):
                content = re.sub(
                    r"(?i)^\s*SCF\.MustConverge\b.*$",
                    "SCF.MustConverge    false",
                    content,
                    flags=re.MULTILINE,
                )
            else:
                content += "SCF.MustConverge    false\n"

            if not re.search(r"(?i)^\s*DM\.UseSaveDM\b", content, flags=re.MULTILINE):
                content += "DM.UseSaveDM true\n"
        elif mode_upper == "SCREENED":
            if not re.search(r"(?i)^\s*DM\.UseSaveDM\b", content, flags=re.MULTILINE):
                content += "DM.UseSaveDM true\n"

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
        num_shells: int = 1,
        n: int = 3,
        l: int = 2,
        u_val: float = 0.0,
        j_val: float = 0.0,
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
            num_shells=num_shells,
            n=n,
            l=l,
            u_val=u_val,
            j_val=j_val,
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
        """Convenience method for BARE response mode."""
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
        """Convenience method for SCREENED response mode."""
        return self.prepare_fdf(
            base_fdf_path=base_fdf_path,
            target_fdf_path=target_fdf_path,
            alpha=alpha,
            run_name=run_name,
            response_mode="SCREENED",
            **kwargs,
        )
