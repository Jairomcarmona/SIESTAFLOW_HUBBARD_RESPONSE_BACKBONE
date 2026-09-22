import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("mno_response", ROOT / "tools/run_mno_afmii_response_v3r2.py")
RUNNER = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(RUNNER)


def test_response_defaults_to_its_original_evidence_root():
    assert RUNNER.RESULTS.name == "response-matrix-foreground-v1"


def test_response_wrapper_exports_its_evidence_root():
    wrapper = RUNNER._frozen_wheel_wrapper(RUNNER.RESULTS.with_suffix(".runtime"))
    assert "SIESTAFLOW_MNO_RESPONSE_RESULTS=response-matrix-foreground-v1" in wrapper


def test_correlated_indices_follow_site_map_for_interleaved_atoms():
    atoms = [{"label": label} for label in ("MnLR00", "O", "MnLR01", "O", "MnLR02")]
    site_map = [{"index": 2, "label": "MnLR02"}, {"index": 0, "label": "MnLR00"}, {"index": 1, "label": "MnLR01"}]

    assert RUNNER._correlated_atom_indices(atoms, site_map) == [1, 3, 5]


def test_correlated_indices_do_not_require_interleaved_atoms():
    atoms = [{"label": label} for label in ("O", "MnLR00", "MnLR01", "MnLR02", "O")]
    site_map = [{"index": 0, "label": "MnLR00"}, {"index": 1, "label": "MnLR01"}, {"index": 2, "label": "MnLR02"}]

    assert RUNNER._correlated_atom_indices(atoms, site_map) == [2, 3, 4]


def test_mno_source_map_derives_real_siesta_indices():
    core, config = RUNNER._load_core(), RUNNER._load("source-material.json")
    atoms, site_map = core.build_atoms(config)

    indices = RUNNER._correlated_atom_indices(atoms, site_map)
    assert len(indices) == 16
    assert indices[:4] == [1, 2, 5, 6]
    assert all(atoms[index - 1]["label"].startswith("MnLR") for index in indices)


def test_occupation_extraction_uses_derived_interleaved_indices_in_site_order():
    values = {1: 4.81, 2: 4.82, 3: 6.0, 4: 6.0, 5: 4.83, 6: 4.84}

    assert RUNNER._ordered_occupations(values, [5, 1, 6, 2], Path("siesta.out")) == [4.83, 4.81, 4.84, 4.82]
