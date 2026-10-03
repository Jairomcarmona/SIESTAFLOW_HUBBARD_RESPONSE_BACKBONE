from pathlib import Path
from typing import Any

import pytest

from hubbardflow.execution import campaign_runner
from hubbardflow.siesta_backend.fdf_model import FdfModelError, parse_effective_fdf


def _legacy_fdf() -> str:
    return """NumberOfAtoms 1
NumberOfSpecies 1
%block ChemicalSpeciesLabel
1 27 Co
%endblock ChemicalSpeciesLabel
LatticeConstant 2 Ang
%block LatticeVectors
1 0 0
0 1 0
0 0 1
%endblock LatticeVectors
AtomicCoordinatesFormat Fractional
%block AtomicCoordinatesAndAtomicSpecies
0 0 0 1
%endblock AtomicCoordinatesAndAtomicSpecies
%block DFTU.Proj
Co 1
3 2
0.0 0.1 0.0
3.0 0.05 9.0
%endblock DFTU.Proj
DFTU.ProjectorGenerationMethod 2
DFTU.PotentialShift true
Spin polarized
XC.functional GGA
XC.authors PBE
%block LatticeParameters
1 1 1 90 90 90
%endblock LatticeParameters
"""


def test_legacy_manifest_uses_base_config_validation_for_unsupported_fdf(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fdf = tmp_path / "reference.fdf"
    fdf.write_text(_legacy_fdf(), encoding="utf-8")
    with pytest.raises(FdfModelError, match="LatticeParameters is unsupported"):
        parse_effective_fdf(fdf)

    normalized = {"functional": "PBE", "alpha_grid_ev": [-0.1, 0.1]}
    calls: list[tuple[Any, ...]] = []

    def base_validation(*args: Any, **kwargs: Any) -> dict[str, Any]:
        calls.append((args, kwargs))
        return normalized

    def strict_inventory(path: Path, _identity_dirs: tuple[Path, ...]) -> Any:
        return parse_effective_fdf(path)

    monkeypatch.setattr(campaign_runner, "validate_lr_config", base_validation)
    monkeypatch.setattr(campaign_runner, "campaign_inventory", strict_inventory)
    config = {"pseudopotentials": {"Co": str(tmp_path / "Co.psml")}}
    args = (config, fdf, {"Co": 27}, ["Co"], 1)

    assert campaign_runner._validate_resume_config(*args, None) is normalized
    assert calls == [((config, {"Co": 27}, ["Co"], 1), {})]

    with pytest.raises(FdfModelError, match="LatticeParameters is unsupported"):
        campaign_runner._validate_resume_config(*args, object())
    assert len(calls) == 1
