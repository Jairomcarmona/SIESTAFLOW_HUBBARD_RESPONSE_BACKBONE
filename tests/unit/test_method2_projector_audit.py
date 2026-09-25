import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parents[2] / "tools"))
from audit_method2_projector import (  # noqa: E402
    cumulative_norm,
    neighbour_distances,
    parse_fdf,
    parse_method2_parameters,
    parse_projector,
)
from verify_method2_projector_identity import verify, verify_preflight  # noqa: E402


def test_method2_auditor_parses_fractional_geometry_and_radial_norm(tmp_path):
    fdf = tmp_path / "case.fdf"
    fdf.write_text(
        """LatticeConstant 1.0 Ang
%block LatticeVectors
 10 0 0
 0 10 0
 0 0 10
%endblock LatticeVectors
AtomicCoordinatesFormat Fractional
%block ChemicalSpeciesLabel
 1 25 MnLR00
 2 8 O
%endblock ChemicalSpeciesLabel
%block AtomicCoordinatesAndAtomicSpecies
 0 0 0 1
 0.2 0 0 2
%endblock AtomicCoordinatesAndAtomicSpecies
%block DFTU.Proj
 MnLR00 1
 3 2
 0.0 0.0
 3.0 0.05
%endblock DFTU.Proj
"""
    )
    projector = tmp_path / "MnLR00.dftu_proj"
    projector.write_text(
        """# DFT+U projectors
2 1 # l,n
4 1.0 3.0
0.0 1.0
1.0 1.0
2.0 0.0
3.0 0.0
"""
    )

    parsed = parse_fdf(fdf, "MnLR00")
    method2 = parse_method2_parameters(parsed["text"], "MnLR00")
    assert method2["n"] == 3
    assert method2["l"] == 2
    assert method2["rc_bohr"] == 3.0
    assert method2["cutoff_mode"] == "explicit_rc"
    assert neighbour_distances(parsed, "MnLR00")["nearest_any_neighbour_A"] == 2.0
    l_value, n_value, r, values, cutoff = parse_projector(projector)
    assert cutoff == 3.0
    assert (l_value, n_value) == (2, 1)
    norm = cumulative_norm(r, values, l_value)
    assert np.isclose(norm[-1], 1.0)
    assert np.all(np.diff(norm) >= 0.0)


def test_archived_mno_projector_uses_l_dependent_measure():
    archived = (Path(__file__).parents[2] / "campaigns/mno_afmii_strict_lr_v3r2/results/response-matrix-foreground-recovery-v4/A_BARE_p0d000/MnLR01.dftu_proj")
    if not archived.is_file():
        import pytest
        pytest.skip("archived MnO projector not present")
    l_value, _, r, values, _ = parse_projector(archived)
    cumulative = cumulative_norm(r, values, l_value)
    assert l_value == 2
    # SIESTA's saved d-orbital profile places 90% of the correct r^(2l+2) norm
    # near 1.7 Bohr; this also guards against accidentally reverting to r^2|f|^2.
    assert 1.65 < np.interp(0.90, cumulative, r) < 1.75


def test_projector_identity_rejects_second_alias_and_preflight_changes(tmp_path):
    import json
    import pytest
    from verify_method2_projector_identity import (
        fdf_sha256,
        projector_configuration_fingerprint,
        verify_preflight,
    )

    reference_fdf_text = """%block ChemicalSpeciesLabel
1 25 MnAlias
2 8 O
3 25 MnAlias2
%endblock ChemicalSpeciesLabel
%block DFTU.Proj
MnAlias 1
3 2
0 0
3 0.05
1.0
MnAlias2 1
3 2
0 0
3 0.05
1.0
O 1
2 1
0 0
3 0.05
%endblock DFTU.Proj
"""
    candidate_fdf_text = """%block ChemicalSpeciesLabel
1 25 MnAlias
2 8 O
3 25 MnAlias2
%endblock ChemicalSpeciesLabel
%block DFTU.Proj
MnAlias 1
3 2
0 0
3 0.05
1.0
MnAlias2 1
3 2
0 0
3 0.05
1.0
O 1
2 1
0 0
3 0.05
%endblock DFTU.Proj
DFTU.ProjectorGenerationMethod 2
"""
    pseudo_mn = "<psml><pseudo-atom-spec atomic-number=\"25\"/></psml>"
    pseudo_o = "<psml><pseudo-atom-spec atomic-number=\"8\"/></psml>"
    profile = """# projector
2 1 # l,n
3 1.0 3.0
0 1
1 1
2 0
"""
    reference_fdf = tmp_path / "reference.fdf"
    candidate_fdf = tmp_path / "candidate.fdf"
    reference_fdf.write_text(reference_fdf_text)
    candidate_fdf.write_text(candidate_fdf_text)
    reference_dir = tmp_path / "reference"
    candidate_dir = tmp_path / "candidate"
    preflight_dir = tmp_path / "preflight"
    for directory in (reference_dir, candidate_dir, preflight_dir):
        directory.mkdir()
    (reference_dir / "siesta.fdf").write_text(reference_fdf_text)
    for label in ("MnAlias", "MnAlias2", "O"):
        pseudo = pseudo_o if label == "O" else pseudo_mn
        (reference_dir / f"{label}.psml").write_text(pseudo)
        profile_text = profile if label != "O" else profile.replace("2 1 # l,n", "1 1 # l,n")
        (reference_dir / f"{label}.dftu_proj").write_text(profile_text)
        (preflight_dir / f"{label}.dftu_proj").write_text(profile_text)
    for label in ("MnAlias", "MnAlias2", "O"):
        pseudo = pseudo_o if label == "O" else pseudo_mn
        profile_text = profile if label != "O" else profile.replace("2 1 # l,n", "1 1 # l,n")
        (candidate_dir / f"{label}.psml").write_text(pseudo)
        (candidate_dir / f"{label}.dftu_proj").write_text(profile_text)
    manifest = {
        "schema_version": 2,
        "status": "PROJECTOR_MATERIALIZED_ONLY",
        "fdf_sha256": fdf_sha256(reference_fdf),
        "projector_configuration_sha256": projector_configuration_fingerprint(reference_fdf),
        "projected_labels": ["MnAlias", "MnAlias2", "O"],
        "projector_files": ["MnAlias.dftu_proj", "MnAlias2.dftu_proj", "O.dftu_proj"],
        "pseudopotential_sha256": {
            "MnAlias": __import__("hashlib").sha256(pseudo_mn.encode()).hexdigest(),
            "MnAlias2": __import__("hashlib").sha256(pseudo_mn.encode()).hexdigest(),
            "O": __import__("hashlib").sha256(pseudo_o.encode()).hexdigest(),
        },
        "files": ["MnAlias.dftu_proj", "MnAlias2.dftu_proj", "O.dftu_proj"],
    }
    (preflight_dir / "materialization.json").write_text(json.dumps(manifest))

    verify(reference_fdf, reference_dir, candidate_fdf, candidate_dir)
    verify_preflight(reference_fdf, reference_dir, preflight_dir, "MnAlias")
    (candidate_dir / "MnAlias2.dftu_proj").write_text(profile.replace("1 1\n2 0", "1 0.9\n2 0"))
    with pytest.raises(ValueError, match="candidate alias projector differs"):
        verify(reference_fdf, reference_dir, candidate_fdf, candidate_dir)
    (candidate_dir / "MnAlias2.dftu_proj").write_text(profile)
    (preflight_dir / "MnAlias.dftu_proj").write_text(profile.replace("1 1\n2 0", "1 0.9\n2 0"))
    with pytest.raises(ValueError, match="accepted reference projector differs from preflight"):
        verify_preflight(reference_fdf, reference_dir, preflight_dir, "MnAlias")


def test_projector_identity_rejects_missing_projected_alias(tmp_path):
    import pytest

    from verify_method2_projector_identity import verify

    fdf_text = """%block ChemicalSpeciesLabel
1 25 MnA
2 25 MnB
3 8 O
%endblock ChemicalSpeciesLabel
%block DFTU.Proj
MnA 1
3 2
0 0
3 0.05
MnB 1
3 2
0 0
3 0.05
O 1
2 1
0 0
3 0.05
%endblock DFTU.Proj
DFTU.ProjectorGenerationMethod 2
"""
    candidate_missing_alias = fdf_text.replace("2 25 MnB\n", "").replace(
        "MnB 1\n3 2\n0 0\n3 0.05\n", ""
    )
    profile_d = """# projector
2 1 # l,n
3 1.0 3.0
0 1
1 1
2 0
"""
    profile_s = profile_d.replace("2 1 # l,n", "0 1 # l,n")
    pseudo_mn = '<psml><pseudo-atom-spec atomic-number="25"/></psml>'
    pseudo_o = '<psml><pseudo-atom-spec atomic-number="8"/></psml>'
    reference_fdf = tmp_path / "reference.fdf"
    candidate_fdf = tmp_path / "candidate.fdf"
    reference_fdf.write_text(fdf_text)
    candidate_fdf.write_text(candidate_missing_alias)
    reference_dir, candidate_dir = tmp_path / "reference", tmp_path / "candidate"
    reference_dir.mkdir()
    candidate_dir.mkdir()
    for label, pseudo, profile in (
        ("MnA", pseudo_mn, profile_d), ("MnB", pseudo_mn, profile_d), ("O", pseudo_o, profile_s)
    ):
        (reference_dir / f"{label}.psml").write_text(pseudo)
        (reference_dir / f"{label}.dftu_proj").write_text(profile)
    for label, pseudo, profile in (("MnA", pseudo_mn, profile_d), ("O", pseudo_o, profile_s)):
        (candidate_dir / f"{label}.psml").write_text(pseudo)
        (candidate_dir / f"{label}.dftu_proj").write_text(profile)

    with pytest.raises(ValueError, match="projected alias label sets differ.*MnB"):
        verify(reference_fdf, reference_dir, candidate_fdf, candidate_dir)


def test_projector_specs_rejects_multishell_and_non_method2():
    from unittest.mock import patch
    from verify_method2_projector_identity import projector_specs
    fdf = Path("multi.fdf")
    multi = """%block ChemicalSpeciesLabel
1 25 Mn
%endblock ChemicalSpeciesLabel
%block DFTU.Proj
Mn 2
3 2
0 0
3 0.05
4 1
0 0
3 0.05
%endblock DFTU.Proj
DFTU.ProjectorGenerationMethod 2
"""
    with patch.object(Path, "read_text", lambda path, *a, **k: multi):
        import pytest
        with pytest.raises(ValueError, match="multi-shell audit is not supported"):
            projector_specs(fdf)
    wrong_method = multi.replace("Mn 2", "Mn 1").replace("DFTU.ProjectorGenerationMethod 2", "DFTU.ProjectorGenerationMethod 1")
    with patch.object(Path, "read_text", lambda path, *a, **k: wrong_method):
        with pytest.raises(ValueError, match="must be 2"):
            projector_specs(fdf)
