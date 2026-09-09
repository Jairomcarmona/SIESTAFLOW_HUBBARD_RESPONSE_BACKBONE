import json
from pathlib import Path

from tools.local_lr_gate_smoke import centred_alphas, materialize_response_plan


def test_centred_grid_has_exactly_the_required_seven_points():
    assert centred_alphas(0.05) == (-0.1, -0.05, -0.025, 0.0, 0.025, 0.05, 0.1)


def test_materialized_local_plan_is_complete_and_fail_closed(tmp_path: Path):
    base = tmp_path / "base.fdf"
    base.write_text(
        "SystemLabel base\nNumberOfAtoms 1\nNumberOfSpecies 1\n"
        "%block ChemicalSpeciesLabel\n1 25 Mn\n%endblock ChemicalSpeciesLabel\n"
        "AtomicCoordinatesFormat Ang\n%block AtomicCoordinatesAndAtomicSpecies\n0 0 0 1\n%endblock AtomicCoordinatesAndAtomicSpecies\n",
        encoding="utf-8",
    )
    records = materialize_response_plan(
        base, tmp_path / "campaign", alpha_step_ev=0.05, species="Mn", n=3, l=2,
        rc_bohr=3.0, omega=0.05,
    )
    assert len(records) == 14
    assert {(item["mode"], item["alpha_ev"]) for item in records} == {
        (mode, alpha) for mode in ("BARE", "SCREENED") for alpha in centred_alphas(0.05)
    }
    assert all((tmp_path / "campaign" / item["fdf"]).is_file() for item in records)
