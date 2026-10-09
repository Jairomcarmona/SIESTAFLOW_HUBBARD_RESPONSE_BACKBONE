from pathlib import Path

from hubbardflow.siesta_backend.geometry_output_parser import parse_reference_geometry_output

FIXTURES = Path(__file__).parents[1] / "fixtures"


def test_parses_real_cu3n_reference_force_and_stress_lines() -> None:
    text = (FIXTURES / "cu3n_probe_reference_siesta.out").read_text(encoding="utf-8")

    parsed = parse_reference_geometry_output(text)

    assert parsed is not None
    assert parsed.maximum_force_ev_ang == 0.0
    assert parsed.residual_ev_ang == 0.0
    assert parsed.maximum_constrained_force_ev_ang == 0.0
    assert parsed.stress_voigt_kbar == (7.4, 7.4, 7.4, 0.0, -0.0, 0.0)
    assert dict(parsed.source_lines) == {
        "maximum_force": 7081,
        "residual_force": 7082,
        "maximum_constrained_force": 7084,
        "stress": 7086,
    }


def test_parser_selects_last_force_block_and_ignores_constrained_maximum() -> None:
    text = """siesta: Atomic forces (eV/Ang):
Max 2.0
Res 1.0
Max 8.0 constrained
Stress tensor Voigt[x,y,z,yz,xz,xy] (kbar): 1 2 3 4 5 6
siesta: Atomic forces (eV/Ang):
Max 0.25
Res 0.125 sqrt
Max 0.5 constrained
Stress tensor Voigt[x,y,z,yz,xz,xy] (kbar): 0 0 0 0 0 0
"""

    parsed = parse_reference_geometry_output(text)

    assert parsed is not None
    assert parsed.maximum_force_ev_ang == 0.25
    assert parsed.maximum_constrained_force_ev_ang == 0.5
    assert parsed.stress_voigt_kbar == (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    assert dict(parsed.source_lines) == {
        "maximum_force": 7,
        "residual_force": 8,
        "maximum_constrained_force": 9,
        "stress": 10,
    }


def test_absent_force_block_is_not_assessed() -> None:
    assert parse_reference_geometry_output("SIESTA completed normally\n") is None
