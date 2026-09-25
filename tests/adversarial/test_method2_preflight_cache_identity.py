import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[2] / "tools"))
from verify_method2_projector_identity import (  # noqa: E402
    fdf_sha256,
    projector_configuration_fingerprint,
    verify_preflight,
)


def _fdf(coordinates: str, targets: tuple[str, ...] = ("MnA",)) -> str:
    species_rows = "\n".join(f"{index} 25 {label}" for index, label in enumerate(targets, 1))
    projector_rows = []
    for label in targets:
        projector_rows.extend([label + " 1", "3 2", "0 0", "0 0.05"])
    projector_block = "\n".join(projector_rows)
    return f"""LatticeConstant 10.0 Ang
%block LatticeVectors
1 0 0
0 1 0
0 0 1
%endblock LatticeVectors
AtomicCoordinatesFormat Fractional
%block ChemicalSpeciesLabel
{species_rows}
%endblock ChemicalSpeciesLabel
%block AtomicCoordinatesAndAtomicSpecies
{coordinates}
%endblock AtomicCoordinatesAndAtomicSpecies
%block DFTU.Proj
{projector_block}
%endblock DFTU.Proj
"""


PROFILE = """# projector
2 1 # l,n
3 1.0 3.0
0.0 1.0
1.0 1.0
2.0 0.0
"""
PSML = '<psml><pseudo-atom-spec atomic-number="25"/></psml>'


def _write_projector(directory: Path, label: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{label}.dftu_proj").write_text(PROFILE, encoding="utf-8")


def _write_pseudo(directory: Path, label: str) -> str:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{label}.psml"
    path.write_text(PSML, encoding="utf-8")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _manifest(fdf: Path, labels: tuple[str, ...], pseudo_hashes: dict[str, str], files: list[str]) -> dict:
    return {
        "schema_version": 2,
        "status": "PROJECTOR_MATERIALIZED_ONLY",
        "fdf_sha256": fdf_sha256(fdf),
        "projector_configuration_sha256": projector_configuration_fingerprint(fdf),
        "projected_labels": list(labels),
        "projector_files": sorted(f"{label}.dftu_proj" for label in labels),
        "pseudopotential_sha256": pseudo_hashes,
        "files": files,
    }


def test_preflight_cache_rejects_changed_geometry_input(tmp_path):
    original = tmp_path / "original.fdf"
    changed = tmp_path / "changed.fdf"
    original.write_text(_fdf("0 0 0 1\n0.2 0 0 1"), encoding="utf-8")
    changed.write_text(_fdf("0 0 0 1\n0.8 0 0 1"), encoding="utf-8")

    reference_dir = tmp_path / "reference"
    preflight_dir = tmp_path / "preflight"
    pseudo_hash = _write_pseudo(reference_dir, "MnA")
    _write_projector(reference_dir, "MnA")
    _write_projector(preflight_dir, "MnA")
    (preflight_dir / "materialization.json").write_text(
        json.dumps(_manifest(original, ("MnA",), {"MnA": pseudo_hash}, ["MnA.dftu_proj"])),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="FDF|fingerprint|configuration|stale"):
        verify_preflight(changed, reference_dir, preflight_dir, "MnA")


def test_preflight_cache_rejects_changed_selected_psml_source(tmp_path):
    fdf = tmp_path / "reference.fdf"
    fdf.write_text(_fdf("0 0 0 1"), encoding="utf-8")
    pseudo_directory = tmp_path / "pseudopotentials"
    preflight_dir = tmp_path / "preflight"
    pseudo_hash = _write_pseudo(pseudo_directory, "MnA")
    _write_projector(preflight_dir, "MnA")
    (preflight_dir / "materialization.json").write_text(
        json.dumps(_manifest(fdf, ("MnA",), {"MnA": pseudo_hash}, ["MnA.dftu_proj"])),
        encoding="utf-8",
    )

    verify_preflight(fdf, None, preflight_dir, "MnA", pseudo_directory)
    (pseudo_directory / "MnA.psml").write_text(
        PSML.replace("atomic-number=\"25\"", "atomic-number=\"25\" "),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="PSML identities differ"):
        verify_preflight(fdf, None, preflight_dir, "MnA", pseudo_directory)


def test_preflight_cache_requires_profiles_for_all_projector_aliases(tmp_path):
    fdf = tmp_path / "reference.fdf"
    fdf.write_text(
        _fdf("0 0 0 1\n0.2 0 0 2", ("MnA", "MnB")),
        encoding="utf-8",
    )
    reference_dir = tmp_path / "reference"
    preflight_dir = tmp_path / "preflight"
    pseudo_hashes = {label: _write_pseudo(reference_dir, label) for label in ("MnA", "MnB")}
    for label in ("MnA", "MnB"):
        _write_projector(reference_dir, label)
    _write_projector(preflight_dir, "MnA")
    (preflight_dir / "materialization.json").write_text(
        json.dumps(_manifest(fdf, ("MnA", "MnB"), pseudo_hashes, ["MnA.dftu_proj"])),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="MnB|alias|projector|profile"):
        verify_preflight(fdf, reference_dir, preflight_dir, "MnA")


def _run_fingerprint_script() -> str:
    template = Path(__file__).parents[2] / "templates/slurm/submit_scientific_lru_dag.slurm"
    source = template.read_text(encoding="utf-8")
    match = re.search(
        r"run_input_fingerprint\(\) \{.*?<<'PY'\n(.*?)\nPY\n\}",
        source,
        re.S,
    )
    assert match is not None, "Slurm template must expose its input fingerprint implementation"
    return match.group(1)


def _fingerprint(script: str, root: Path, run_dir: Path, run_id: str, mode: str) -> dict:
    tools = str(Path(__file__).parents[2] / "tools")
    env = os.environ.copy()
    env["PYTHONPATH"] = tools + os.pathsep + env.get("PYTHONPATH", "")
    completed = subprocess.run(
        [sys.executable, "-c", script, str(root), str(run_dir), run_id, mode],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    return json.loads(completed.stdout)


def test_run_fingerprint_changes_with_fdf_psml_and_parent_dm(tmp_path):
    script = _run_fingerprint_script()
    root = tmp_path / "campaign"
    reference_dir = root / "runs" / "00_REFERENCE"
    child_dir = root / "runs" / "01_CHILD"
    reference_dir.mkdir(parents=True)
    child_dir.mkdir(parents=True)
    fdf = _fdf("0 0 0 1\n0.2 0 0 1")
    (child_dir / "siesta.fdf").write_text(fdf, encoding="utf-8")
    (child_dir / "MnA.psml").write_text(PSML, encoding="utf-8")
    pseudo_directory = root / "pseudopotentials"
    _write_pseudo(pseudo_directory, "MnA")
    parent_dm = reference_dir / "00_REFERENCE.DM"
    parent_dm.write_bytes(b"parent density matrix v1")
    (root / "runs" / "manifest.json").write_text(
        json.dumps([{"id": "01_CHILD", "mode": "SCREENED", "target": "MnA", "parent_dm": "00_REFERENCE/00_REFERENCE.DM"}]),
        encoding="utf-8",
    )

    baseline = _fingerprint(script, root, child_dir, "01_CHILD", "SCREENED")
    assert baseline["fdf_sha256"] == fdf_sha256(child_dir / "siesta.fdf")
    assert baseline["pseudopotential_sha256"]["MnA"] == hashlib.sha256(PSML.encode()).hexdigest()
    assert baseline["selected_psml_sha256"] == baseline["pseudopotential_sha256"]
    assert baseline["parent_dm_sha256"] == hashlib.sha256(b"parent density matrix v1").hexdigest()

    (child_dir / "siesta.fdf").write_text(_fdf("0 0 0 1\n0.8 0 0 1"), encoding="utf-8")
    geometry_changed = _fingerprint(script, root, child_dir, "01_CHILD", "SCREENED")
    assert geometry_changed["fdf_sha256"] != baseline["fdf_sha256"]
    assert geometry_changed["projector_configuration_sha256"] == baseline["projector_configuration_sha256"]
    assert geometry_changed["input_sha256"] != baseline["input_sha256"]

    changed_psml = PSML.replace("atomic-number=\"25\"", "atomic-number=\"25\" ")
    (pseudo_directory / "MnA.psml").write_text(changed_psml, encoding="utf-8")
    with pytest.raises(subprocess.CalledProcessError):
        _fingerprint(script, root, child_dir, "01_CHILD", "SCREENED")

    (child_dir / "MnA.psml").write_text(changed_psml, encoding="utf-8")
    pseudo_changed = _fingerprint(script, root, child_dir, "01_CHILD", "SCREENED")
    assert pseudo_changed["input_sha256"] != geometry_changed["input_sha256"]
    assert pseudo_changed["selected_psml_sha256"] == pseudo_changed["pseudopotential_sha256"]

    (child_dir / "MnB.psml").write_text(PSML, encoding="utf-8")
    with pytest.raises(subprocess.CalledProcessError):
        _fingerprint(script, root, child_dir, "01_CHILD", "SCREENED")
    (child_dir / "MnB.psml").unlink()

    parent_dm.write_bytes(b"parent density matrix v2")
    parent_dm_changed = _fingerprint(script, root, child_dir, "01_CHILD", "SCREENED")
    assert parent_dm_changed["input_sha256"] != pseudo_changed["input_sha256"]


def test_run_marker_is_required_before_skip_and_written_after_validation():
    source = (Path(__file__).parents[2] / "templates/slurm/submit_scientific_lru_dag.slurm").read_text(encoding="utf-8")
    valid_run = source.split("valid_run() {", 1)[1].split("\n}", 1)[0]
    run_one = source.split("run_one() {", 1)[1].split("\n}", 1)[0]
    assert "siestaflow_run_inputs.json" in valid_run
    assert valid_run.index("recorded\"") < valid_run.index("validate_outputs")
    assert run_one.index("validate_outputs \"$run\"") < run_one.index("write_run_fingerprint")
    assert run_one.index("write_run_fingerprint") < run_one.rindex("valid_run \"$run\"")
    assert "preflight/materialized" in source
    gate_zero = source.split("# Gate 0:", 1)[1].split("# Gate 1:", 1)[0]
    assert gate_zero.index("gate_is_complete") < gate_zero.index("--preflight-dir")
    assert "--pseudo-directory \"$ROOT/pseudopotentials\"" in gate_zero


def test_stage_run_copies_the_parent_dm_file_path_from_the_manifest():
    source = (Path(__file__).parents[2] / "templates/slurm/submit_scientific_lru_dag.slurm").read_text(encoding="utf-8")
    stage_run = source.split("stage_run() {", 1)[1].split("\n}", 1)[0]
    assert 'parent="$(run_parent_dm "$run")"' in stage_run
    assert 'cp -fp "$ROOT/runs/$parent" "$directory/$run.DM"' in stage_run
    installer = (Path(__file__).parents[2] / "tools/install_scientific_dag.py").read_text(encoding="utf-8")
    assert "psml_selection.py" in installer
    assert "siesta_dftu_fdf.py" in installer
