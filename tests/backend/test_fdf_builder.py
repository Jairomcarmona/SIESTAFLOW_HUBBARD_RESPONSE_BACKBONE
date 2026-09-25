import pytest
import re
from siestaflow_hubbard.siesta_backend.fdf_builder import FdfBuilder, LegacyBareMaterializationDisabledError


BASE_FDF_MOCK = """SystemName MnO Test
SystemLabel MnO_smoke
MaxSCFIterations 50
DM.MixingWeight 0.1
Mesh.Cutoff 400 Ry
"""


def test_fdf_builder_bare_mode_is_not_a_production_route(tmp_path):
    base_file = tmp_path / "base.fdf"
    target_file = tmp_path / "target_bare.fdf"
    base_file.write_text(BASE_FDF_MOCK, encoding="utf-8")

    builder = FdfBuilder()
    with pytest.raises(LegacyBareMaterializationDisabledError):
        builder.prepare_fdf_bare(
            base_fdf_path=str(base_file), target_fdf_path=str(target_file), alpha=0.05,
            run_name="MnO_BARE_p0p05",
        )
    assert not target_file.exists()


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

    assert "SystemLabel MnO_SCR_m0p10" in content
    # In SCREENED mode, MaxSCFIterations remains untouched
    assert "MaxSCFIterations 50" in content
    assert "DM.UseSaveDM true" in content
    assert "DFTU.PotentialShift true" in content
    assert "  -0.1000  0.0000" in content
