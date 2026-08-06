import pytest
import re
from siestaflow_hubbard.siesta_backend.fdf_builder import FdfBuilder


BASE_FDF_MOCK = """SystemName MnO Test
SystemLabel MnO_smoke
MaxSCFIterations 50
DM.MixingWeight 0.1
SCF.MustConverge true
Mesh.Cutoff 400 Ry
"""


def test_fdf_builder_bare_mode(tmp_path):
    base_file = tmp_path / "base.fdf"
    target_file = tmp_path / "target_bare.fdf"
    base_file.write_text(BASE_FDF_MOCK, encoding="utf-8")

    builder = FdfBuilder()
    content = builder.prepare_fdf_bare(
        base_fdf_path=str(base_file),
        target_fdf_path=str(target_file),
        alpha=0.05,
        run_name="MnO_BARE_p0p05",
    )

    # 1. SystemLabel replacement
    assert "SystemLabel         MnO_BARE_p0p05" in content

    # 2. Strict replacement (not duplicate append) of the BARE SCF controls
    max_iter_matches = re.findall(r"(?i)^\s*MaxSCFIterations\b.*$", content, flags=re.MULTILINE)
    assert len(max_iter_matches) == 1
    assert "MaxSCFIterations    2" in max_iter_matches[0]

    mixing_matches = re.findall(r"(?i)^\s*DM\.MixingWeight\b.*$", content, flags=re.MULTILINE)
    assert len(mixing_matches) == 1
    assert "DM.MixingWeight     1.0" in mixing_matches[0]

    must_converge_matches = re.findall(r"(?i)^\s*SCF\.MustConverge\b.*$", content, flags=re.MULTILINE)
    assert len(must_converge_matches) == 1
    assert "SCF.MustConverge    false" in must_converge_matches[0]

    # 3. DM.UseSaveDM true and DFTU.PotentialShift true appended
    assert "DM.UseSaveDM true" in content
    assert "DFTU.PotentialShift true" in content

    # 4. DFTU.proj block spacing and 5-line structure
    proj_block = """%block DFTU.proj
  Mn   1
  3  2
  0.0000  0.0000
  0.0000  0.0500
  0.0000
%endblock DFTU.proj"""
    assert proj_block in content


def test_fdf_builder_screened_mode(tmp_path):
    base_file = tmp_path / "base.fdf"
    target_file = tmp_path / "target_screened.fdf"
    base_file.write_text(BASE_FDF_MOCK, encoding="utf-8")

    builder = FdfBuilder()
    content = builder.prepare_fdf_screened(
        base_fdf_path=str(base_file),
        target_fdf_path=str(target_file),
        alpha=-0.10,
        run_name="MnO_SCR_m0p10",
    )

    assert "SystemLabel         MnO_SCR_m0p10" in content
    # In SCREENED mode, MaxSCFIterations remains untouched
    assert "MaxSCFIterations 50" in content
    assert "SCF.MustConverge true" in content
    assert not re.search(r"(?i)^\s*SCF\.MustConverge\b.*false", content, flags=re.MULTILINE)
    assert "DM.UseSaveDM true" in content
    assert "DFTU.PotentialShift true" in content
    assert "  0.0000  -0.1000" in content
