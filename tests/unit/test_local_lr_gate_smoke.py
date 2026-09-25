import json
from pathlib import Path

import pytest

from tools.local_lr_gate_smoke import centred_alphas, materialize_response_plan
from siestaflow_hubbard.siesta_backend.fdf_builder import LegacyBareMaterializationDisabledError


def test_centred_grid_has_exactly_the_required_seven_points():
    assert centred_alphas(0.05) == (-0.1, -0.05, -0.025, 0.0, 0.025, 0.05, 0.1)


def test_legacy_local_response_plan_is_rejected_before_materialization(tmp_path: Path):
    base = tmp_path / "base.fdf"
    base.write_text(
        "SystemLabel base\nNumberOfAtoms 1\nNumberOfSpecies 1\n"
        "%block ChemicalSpeciesLabel\n1 25 Mn\n%endblock ChemicalSpeciesLabel\n"
        "AtomicCoordinatesFormat Ang\n%block AtomicCoordinatesAndAtomicSpecies\n0 0 0 1\n%endblock AtomicCoordinatesAndAtomicSpecies\n",
        encoding="utf-8",
    )
    with pytest.raises(LegacyBareMaterializationDisabledError, match="admitted SIESTA runtime"):
        materialize_response_plan(
            base, tmp_path / "campaign", alpha_step_ev=0.05, species="Mn", n=3, l=2,
            rc_bohr=3.0, omega=0.05,
        )
    assert not (tmp_path / "campaign").exists()
