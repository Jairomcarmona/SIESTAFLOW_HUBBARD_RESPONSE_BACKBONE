from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[2] / "tools"))

from psml_selection import parse_fdf_species, resolve_explicit_psmls, select_psml_sources  # noqa: E402
from siesta_dftu_fdf import projector_specs_from_text  # noqa: E402
from verify_method2_projector_identity import projector_configuration_fingerprint  # noqa: E402


def _fdf(projector_block: str, keys: str = "") -> str:
    return f"""{keys}
%block ChemicalSpeciesLabel
1 25 MnA
2 25 MnB
3 8 O
%endblock ChemicalSpeciesLabel
{projector_block}
"""


def test_native_precedence_defaults_cutoff_norm_and_optional_rows():
    text = _fdf(
        """%block LDAU.Proj
MnA 1
3 2 E 40.0 0.9
0.0 0.0
0.0 0.0
1.25
MnB 1
3 2
0.0 0.0
0.0 0.0
%endblock LDAU.Proj
%block DFTU.Proj
this stale block is ignored by SIESTA when LDAU.Proj exists
%endblock DFTU.Proj""",
        """LDAU.ProjectorGenerationMethod 1
DFTU.ProjectorGenerationMethod 2
LDAU.CutoffNorm 0.80
DFTU.CutoffNorm 0.95""",
    )
    specs = projector_specs_from_text(text, "precedence.fdf")
    assert set(specs) == {"MnA", "MnB"}
    assert specs["MnA"]["effective_block"] == "LDAU.proj"
    assert specs["MnA"]["cutoff_mode"] == "cutoff_norm"
    assert specs["MnA"]["cutoff_norm"] == 0.95
    assert specs["MnA"]["omega_bohr"] == 0.05  # values below 1e-4 take SIESTA's width default
    assert specs["MnA"]["lambda"] == 1.25
    assert specs["MnA"]["soft_confinement"] == (40.0, 0.9)
    assert specs["MnB"]["lambda"] == 1.0  # next species header is not mistaken for lambda


def test_method_default_legacy_and_modern_override_are_effective():
    from unittest.mock import patch

    base = _fdf(
        """%block DFTU.Proj
MnA 1
3 2
0 0
0 0
%endblock DFTU.Proj""",
        "LDAU.CutoffNorm 0.82\nDFTU.CutoffNorm 0.91",
    )
    # Method defaults to 2; DFTU.CutoffNorm overrides the inherited legacy value.
    specs = projector_specs_from_text(base)
    assert specs["MnA"]["cutoff_norm"] == 0.91
    path = Path("synthetic.fdf")
    current = [base]
    with patch.object(Path, "read_text", lambda *_args, **_kwargs: current[0]):
        first = projector_configuration_fingerprint(path)
        current[0] = base.replace("DFTU.CutoffNorm 0.91", "DFTU.CutoffNorm 0.92")
        assert projector_configuration_fingerprint(path) != first

        # The norm is not part of the effective configuration if an explicit rc is used.
        explicit = base.replace("0 0\n%endblock DFTU.Proj", "3.0 0.05\n%endblock DFTU.Proj")
        current[0] = explicit
        first = projector_configuration_fingerprint(path)
        current[0] = explicit.replace("DFTU.CutoffNorm 0.91", "DFTU.CutoffNorm 0.92")
        assert projector_configuration_fingerprint(path) == first

    with pytest.raises(ValueError, match="effective ProjectorGenerationMethod must be 2"):
        projector_specs_from_text(base + "\nDFTU.ProjectorGenerationMethod 1\n")
    assert projector_specs_from_text(base + "\nLDAU.ProjectorGenerationMethod 2\n")["MnA"]["l"] == 2


@pytest.mark.parametrize(
    "body, message",
    [
        ("MnA 2\n3 2\n0 0\n0 0\n4 1\n0 0\n0 0", "multi-shell audit is not supported"),
        ("MnA 1\n3 2 E 40\n0 0\n0 0", "expected shell row"),
    ],
)
def test_unsupported_shell_layers_and_incomplete_soft_rows_fail_closed(body, message):
    text = _fdf(f"%block DFTU.Proj\n{body}\n%endblock DFTU.Proj")
    with pytest.raises(ValueError, match=message):
        projector_specs_from_text(text)


def test_psml_exact_label_wins_and_ambiguous_atomic_number_fails(tmp_path):
    fdf = "%block ChemicalSpeciesLabel\n1 25 MnA\n2 25 MnB\n%endblock ChemicalSpeciesLabel\n"
    species = parse_fdf_species(fdf)
    exact = tmp_path / "MnA.psml"
    other = tmp_path / "Mn.psml"
    variant = tmp_path / "Mn_alt.psml"
    exact.write_text('<psml><pseudo-atom-spec atomic-number="25"/></psml>')
    other.write_text('<psml><pseudo-atom-spec atomic-number="25"/></psml>')
    variant.write_text('<psml><pseudo-atom-spec atomic-number="25"><variant>different</variant></pseudo-atom-spec></psml>')
    with pytest.raises(ValueError, match="ambiguous PSML sources for FDF label MnB"):
        select_psml_sources(species, [exact, other, variant])

    # Exact MnB.psml resolves the alias independently; exact files must still have the right Z.
    exact_b = tmp_path / "MnB.psml"
    exact_b.write_text('<psml><pseudo-atom-spec atomic-number="25"/></psml>')
    selected = select_psml_sources(species, [exact, exact_b, other, variant])
    assert selected["MnA"] == exact
    assert selected["MnB"] == exact_b
    wrong = tmp_path / "MnA_wrong.psml"
    wrong.write_text('<psml><pseudo-atom-spec atomic-number="8"/></psml>')
    with pytest.raises(ValueError, match="explicit PSML mapping label is absent"):
        resolve_explicit_psmls(species, [("Unknown", wrong), ("MnB", exact_b)])
    with pytest.raises(ValueError, match="expected Z=25"):
        resolve_explicit_psmls(species, [("MnA", wrong), ("MnB", exact_b)])
