import re
from pathlib import Path

import pytest

from siestaflow_hubbard.domain.symmetry_reduction import PerturbationSpec, ResponseMode
from siestaflow_hubbard.siesta_backend.symmetry_materializer import (
    ResponseMaterializationError,
    materialize_response_fdf,
    write_materialized_response,
)
from siestaflow_hubbard.siesta_backend.siesta542_bare_profile import (
    Siesta542PotentialShiftHamiltonianProfile,
)


ROOT = Path(__file__).resolve().parents[2]
REFERENCE = ROOT / "tests/fixtures/cu3n_reference_siesta.fdf"


def _spec(mode=ResponseMode.BARE, site="CuLR03", alpha=-0.05):
    return PerturbationSpec("portable_shadow", "orbit_001", 3, site, mode, alpha, "shadow")


def _shifts(content):
    block = content.split("%block DFTU.Proj", 1)[1].split("%endblock DFTU.Proj", 1)[0]
    return {
        match.group(1): float(match.group(2))
        for match in re.finditer(
            r"^\s*(CuLR\d+)\s+1\s*\n\s*3\s+2\s*\n\s*([+-]?\d+\.\d+)\s+0\.0000",
            block,
            re.MULTILINE,
        )
    }


def _value(content, key):
    match = re.search(rf"^{re.escape(key)}\s+(.+)$", content, re.MULTILINE)
    return match.group(1).strip() if match else None


def test_site_specific_materializer_preserves_reference_geometry_and_projector_records():
    source = REFERENCE.read_text()
    profile = Siesta542PotentialShiftHamiltonianProfile()
    with pytest.raises(ResponseMaterializationError, match="admitted"):
        materialize_response_fdf(REFERENCE, _spec(), bare_profile=profile)


def test_screened_materialization_requires_and_sets_converged_scf_controls():
    rendered = materialize_response_fdf(REFERENCE, _spec(ResponseMode.SCREENED, "CuLR04", 0.05))
    assert _value(rendered.content, "MaxSCFIterations") == "300"
    assert _value(rendered.content, "SCF.MustConverge") == "T"
    assert _value(rendered.content, "SCF.Mixer.Method") == "Pulay"
    assert _shifts(rendered.content)["CuLR04"] == 0.05


def test_public_bare_materialization_requires_campaign_admission():
    profile = Siesta542PotentialShiftHamiltonianProfile()
    with pytest.raises(ResponseMaterializationError, match="requires"):
        materialize_response_fdf(REFERENCE, _spec(), bare_profile=profile)
    with pytest.raises(ResponseMaterializationError, match="requires"):
        materialize_response_fdf(REFERENCE, _spec())


def test_public_bare_write_creates_no_fdf_without_campaign_admission(tmp_path: Path):
    destination = tmp_path / "bare.fdf"
    with pytest.raises(ResponseMaterializationError, match="admitted"):
        write_materialized_response(
            REFERENCE, _spec(), destination,
            bare_profile=Siesta542PotentialShiftHamiltonianProfile(),
        )
    assert not destination.exists()


def test_unknown_target_cannot_mutate_a_reference_fdf():
    with pytest.raises(ResponseMaterializationError, match="absent"):
        materialize_response_fdf(REFERENCE, _spec(ResponseMode.SCREENED, site="CuLR99"))
