"""Campaign inventory, immutable plan identities and fixed-path golden tests."""

from __future__ import annotations

import json
import shutil
from dataclasses import replace
from hashlib import sha256
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from hubbardflow.domain.coverage_models import CoverageReason, CoverageStatus
from hubbardflow.domain.perturbation_plan import PlanStatus
from hubbardflow.domain.symmetry_operation_models import coverage_policy_v1
from hubbardflow.execution.campaign_plan import (
    CampaignPlanError,
    campaign_inventory,
    freeze_campaign_plan,
    resolve_campaign_planning,
    verify_frozen_campaign_plan,
)
from hubbardflow.execution.campaign_runner import _build_dag
from hubbardflow.execution.campaign_v2 import (
    CONFIG_SCHEMA,
    CampaignV2Error,
    load_campaign_v2,
    validate_lr_config,
    validate_reference_fdf,
    verify_campaign_inventory,
)
from hubbardflow.execution.wsl_campaign_init import initialize_campaign
from tests.unit.test_coverage import _toy
from tests.unit.test_fdf_model import _fdf

ROOT = Path(__file__).resolve().parents[2]


def inputs(tmp_path: Path, fdf_text: str | None = None) -> tuple[Path, dict[str, Any], Path]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    text = fdf_text or _fdf().replace("0.2 0.1 0.0", "0 0").replace(
        "Spin polarized", "Spin non-polarized\nDFTU.PotentialShift true\nXC.functional GGA\nXC.authors PBE"
    )
    fdf = tmp_path / "reference.fdf"
    fdf.write_text(text, encoding="utf-8")
    _, species, _ = validate_reference_fdf(text, "PBE")
    pseudo = {}
    for label, z in species.items():
        path = tmp_path / f"{label}.psml"
        path.write_text(
            f"<psml><functional>PBE GGA</functional><input-file>{label} {z}</input-file></psml>",
            encoding="utf-8",
        )
        pseudo[label] = str(path)
    registry = tmp_path / "backend.json"
    registry.write_text("{}", encoding="utf-8")
    version = tmp_path / "version.txt"
    version.write_text("SIESTA 5.4.2", encoding="utf-8")
    profile = tmp_path / "profile.json"
    profile.write_text(
        json.dumps(
            {
                "target": "slurm",
                "evidence": "VALIDATED_RUNTIME",
                "slurm": {"partition": "compute", "account": None, "qos": None},
                "allocation": {
                    "nodes": 1,
                    "total_cpus": 4,
                    "memory": "8G",
                    "walltime": "01:00:00",
                    "max_parallel_steps": 1,
                    "shutdown_margin_seconds": 60,
                    "termination_grace_seconds": 30,
                },
                "runtime": {
                    "module_commands": [],
                    "siesta_executable": "/opt/siesta",
                    "exclusive": True,
                    "environment": {},
                    "launcher": {
                        "kind": "hydra",
                        "command": ["mpiexec.hydra"],
                        "bootstrap": "ssh",
                        "processes_per_node": 4,
                    },
                },
                "task_policy": {"max_attempts": 1, "require_scf_converged": True},
            }
        ),
        encoding="utf-8",
    )
    config: dict[str, Any] = {
        "schema": CONFIG_SCHEMA,
        "functional": "PBE",
        "pseudopotentials": pseudo,
        "alpha_grid_ev": [-0.06, -0.04, -0.02, 0.02, 0.04, 0.06],
        "compatibility_registry": str(registry),
        "version_text_source": str(version),
        "declared_executable": "siesta",
        "analysis_policy": {"estimator": "polynomial", "polynomial_degree": 3},
    }
    return fdf, config, profile


def normalized(fdf: Path, raw: dict[str, Any]) -> dict[str, Any]:
    _, species, labels = validate_reference_fdf(fdf.read_text(encoding="utf-8"), "PBE")
    inventory = campaign_inventory(fdf, (fdf.parent,))
    from hubbardflow.siesta_backend.fdf_model import parse_effective_fdf

    return validate_lr_config(
        raw, species, labels, parse_effective_fdf(fdf).number_of_atoms, inventory=inventory
    )


def test_optional_sites_filled_and_explicit_mapping_validated(tmp_path: Path) -> None:
    fdf, raw, _ = inputs(tmp_path)
    result = normalized(fdf, raw)
    assert result["sites"] == [{"site_id": "Co", "atom_index": 1, "orbit_id": "Co"}]
    assert result["coverage"] == "DIAGNOSTIC"
    assert result["auto_split_species"] is False
    assert normalized(fdf, {**raw, "sites": result["sites"]}) == result
    with pytest.raises(CampaignV2Error, match="atom_index/species mismatch"):
        inv = campaign_inventory(fdf, (tmp_path,))
        validate_lr_config(
            {**raw, "sites": [{"site_id": "Co", "atom_index": 2}]}, {"Co": 27}, ["Co"], 2, inventory=inv
        )


@pytest.mark.parametrize(
    "field,value",
    [
        ("coverage", "infer"),
        ("auto_split_species", 1),
        ("auto_split_species", True),
        ("alpha_strategy", "CALIBRATED_GRID"),
    ],
)
def test_unsupported_or_pending_features_fail_closed(tmp_path: Path, field: str, value: object) -> None:
    fdf, raw, _ = inputs(tmp_path)
    with pytest.raises(CampaignV2Error):
        normalized(fdf, {**raw, field: value})


def test_shared_label_gate_never_silently_splits(tmp_path: Path) -> None:
    text = _fdf(coordinates="0 0 0 1\n0.5 0 0 1").replace("NumberOfAtoms 1", "NumberOfAtoms 2")
    text = (
        text.replace("0.2 0.1 0.0", "0 0") + "\nDFTU.PotentialShift true\nXC.functional GGA\nXC.authors PBE\n"
    )
    fdf, raw, _ = inputs(tmp_path, text)
    with pytest.raises(CampaignV2Error, match="SHARED_LABEL_NEEDS_SPLIT"):
        normalized(fdf, raw)


def test_missing_reference_freezes_explicit_incomplete_diagnostic(tmp_path: Path) -> None:
    fdf, raw, _ = inputs(tmp_path)
    config = normalized(fdf, raw)
    resolved = resolve_campaign_planning(fdf, config)
    assert resolved.plan.status is PlanStatus.NOT_ESTABLISHED
    assert CoverageReason.EVIDENCE_INCOMPLETE in resolved.diagnostic_coverage.reasons
    assert len(resolved.plan.run_specs) == 12
    freeze_campaign_plan(tmp_path, resolved, config)
    assert verify_frozen_campaign_plan(tmp_path, config).digest == resolved.plan.digest
    with pytest.raises(CampaignPlanError, match="already frozen"):
        freeze_campaign_plan(tmp_path, resolved, config)


def test_new_planner_version_is_v4_and_part_of_plan_digest(tmp_path: Path) -> None:
    fdf, raw, _ = inputs(tmp_path)
    resolved = resolve_campaign_planning(fdf, normalized(fdf, raw))
    assert resolved.plan.planner_version == "campaign-planner-v4"
    assert replace(resolved.plan, planner_version="campaign-planner-v1").digest != resolved.plan.digest


def test_plan_generation_does_not_call_lapack(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fdf, raw, _ = inputs(tmp_path)

    def fail_lstsq(*args: object, **kwargs: object) -> object:
        raise AssertionError("planner must not depend on numpy.linalg.lstsq")

    monkeypatch.setattr(np.linalg, "lstsq", fail_lstsq)
    resolved = resolve_campaign_planning(fdf, normalized(fdf, raw))
    assert resolved.plan.planner_version == "campaign-planner-v4"


def test_resume_plan_identity_is_portable_between_staging_directories(tmp_path: Path) -> None:
    original = tmp_path / "original"
    fdf, raw, _ = inputs(original)
    config = normalized(fdf, raw)
    resolved = resolve_campaign_planning(fdf, config)
    freeze_campaign_plan(original, resolved, config)
    copied = tmp_path / "copied"
    shutil.copytree(original, copied)
    raw["pseudopotentials"] = {
        label: str(copied / Path(path).name) for label, path in raw["pseudopotentials"].items()
    }
    raw["compatibility_registry"] = str(copied / "backend.json")
    raw["version_text_source"] = str(copied / "version.txt")
    moved = normalized(copied / "reference.fdf", raw)
    assert verify_frozen_campaign_plan(copied, moved).digest == resolved.plan.digest


def test_diagnostic_retains_candidates_in_lock_and_translation_retains_shadows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    text = (
        _fdf().replace("NumberOfAtoms 1", "NumberOfAtoms 4").replace("NumberOfSpecies 1", "NumberOfSpecies 4")
    )
    text = text.replace("1 27 Co", "\n".join(f"{i + 1} 27 Co{i}" for i in range(4)))
    text = text.replace("0 0 0 1 # Co label", "\n".join(f"{i / 4} 0 0 {i + 1}" for i in range(4)))
    text = text.replace(
        "Co 1\n3 2\n0.2 0.1 0.0\n3.0 0.05 9.0",
        "\n".join(f"Co{i} 1\n1 0\n0 0\n3.0 0.05 9.0" for i in range(4)),
    )
    text = text.replace("Co\nn=3 0 2 E 40 5", "\n".join(f"Co{i}\nn=3 0 2 E 40 5" for i in range(4)))
    text += "\nDFTU.PotentialShift true\nXC.functional GGA\nXC.authors PBE\n"
    fdf, raw, _ = inputs(tmp_path, text)
    for path in raw["pseudopotentials"].values():
        Path(path).write_text(
            "<psml><functional>PBE GGA</functional><input-file>Co 27</input-file></psml>", encoding="utf-8"
        )
    output = tmp_path / "ref.out"
    output.write_bytes(b"synthetic reference adapter injection")
    dm = tmp_path / "ref.DM"
    dm.write_bytes(b"synthetic parent")
    config = normalized(
        fdf, {**raw, "planning_reference_output": str(output), "planning_reference_dm": str(dm)}
    )
    inv = campaign_inventory(fdf, (tmp_path,))
    _, reference, _ = _toy(4)
    reference = replace(
        reference,
        input_file_sha256=sha256(fdf.read_bytes()).hexdigest(),
        state=replace(
            reference.state,
            input_fdf_sha256=inv.effective_fdf_sha256,
            occupation_spectra_by_subspace=tuple(
                replace(row, site_id=site.site_id)
                for row, site in zip(
                    reference.state.occupation_spectra_by_subspace, inv.subspaces, strict=True
                )
            ),
        ),
    )
    monkeypatch.setattr(
        "hubbardflow.siesta_backend.coverage_reference.build_coverage_reference_evidence",
        lambda *_: reference,
    )
    diagnostic = resolve_campaign_planning(fdf, config)
    assert diagnostic.diagnostic_coverage.classes[0].status is CoverageStatus.CANDIDATE_PENDING_SHADOW
    assert diagnostic.diagnostic_coverage.would_reduce_to == 1
    assert len(diagnostic.plan.computed_columns) == 4
    assert not diagnostic.plan.reconstruction_maps
    freeze_campaign_plan(tmp_path, diagnostic, config)
    lock = json.loads((tmp_path / "campaign.lock").read_text(encoding="utf-8"))
    assert lock["coverage_qualification"]["classes"][0]["status"] == "CANDIDATE_PENDING_SHADOW"
    translation = resolve_campaign_planning(fdf, {**config, "coverage": "TRANSLATION_SHADOWED"})
    assert translation.plan.status is PlanStatus.REVIEW
    assert len(translation.plan.computed_columns) == 2
    assert len(translation.plan.reconstruction_maps) == 2


@pytest.mark.parametrize("changed", ["fdf", "dm", "policy", "alpha", "backend", "static", "plan"])
def test_resume_invalidates_any_scientific_identity_change(tmp_path: Path, changed: str) -> None:
    fdf, raw, _ = inputs(tmp_path)
    dm = tmp_path / "reference.DM"
    dm.write_bytes(b"parent bytes")
    static = tmp_path / "basis.ion"
    static.write_bytes(b"basis bytes")
    config = normalized(
        fdf, {**raw, "planning_reference_dm": str(dm), "static_artifacts": {"basis.ion": str(static)}}
    )
    freeze_campaign_plan(tmp_path, resolve_campaign_planning(fdf, config), config)
    if changed == "fdf":
        fdf.write_text(fdf.read_text(encoding="utf-8") + "\nMeshCutoff 300 Ry\n", encoding="utf-8")
    elif changed == "dm":
        dm.write_bytes(b"another parent")
    elif changed == "policy":
        config["coverage_policy"] = replace(coverage_policy_v1(), version="declared-v2").to_mapping()
    elif changed == "alpha":
        config["alpha_grid_ev"] = [-0.08, -0.04, -0.02, 0.02, 0.04, 0.08]
    elif changed == "backend":
        Path(config["version_text_source"]).write_text("other backend", encoding="utf-8")
    elif changed == "static":
        static.write_bytes(b"other basis")
    else:
        path = tmp_path / "resolved_perturbation_plan.json"
        row = json.loads(path.read_text(encoding="utf-8"))
        row["run_specs"][0]["alpha_ev"] = -0.08
        path.write_text(json.dumps(row), encoding="utf-8")
    with pytest.raises(CampaignPlanError, match="cannot resume"):
        verify_frozen_campaign_plan(tmp_path, config)


@settings(max_examples=12, deadline=None)
@given(st.permutations((-0.06, -0.04, -0.02, 0.02, 0.04, 0.06)))
def test_input_order_invariance(grid: list[float]) -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as directory:
        fdf, raw, _ = inputs(Path(directory))
        first = resolve_campaign_planning(fdf, normalized(fdf, raw))
        second = resolve_campaign_planning(fdf, normalized(fdf, {**raw, "alpha_grid_ev": list(grid)}))
        assert first.plan.digest == second.plan.digest


@pytest.mark.parametrize(
    "source",
    [
        "benchmarks/lr_u/CoO/reference.fdf",
        "benchmarks/lr_u/stage_u_b/materials/NiO/reference.fdf",
        "campaigns/mno_afmii_strict_lr_v3r2/results/response-matrix-foreground-recovery-v4/00_REFERENCE/siesta.fdf",
        "tests/fixtures/cu3n_reference_siesta.fdf",
    ],
)
def test_real_init_fixed_disabled_golden_and_resume(tmp_path: Path, source: str) -> None:
    original = ROOT / source
    before = sha256(original.read_bytes()).hexdigest()
    fdf, raw, profile = inputs(tmp_path / "inputs", original.read_text(encoding="utf-8"))
    raw["coverage"] = "DISABLED"
    config_path = fdf.parent / "lr.json"
    config_path.write_text(json.dumps(raw), encoding="utf-8")
    result = initialize_campaign(
        fdf_path=str(fdf),
        lr_config_path=str(config_path),
        profile_path=str(profile),
        name="golden",
        campaign_root=str(tmp_path / "campaigns"),
    )
    manifest = load_campaign_v2(result["manifest_path"])
    verify_campaign_inventory(manifest)
    root = Path(manifest["_campaign_root"])
    plan = verify_frozen_campaign_plan(
        root,
        normalized(root / "reference.fdf", json.loads((root / "lr_config.json").read_text(encoding="utf-8"))),
    )
    expected_sites = list(normalized(fdf, raw)["sites"])
    _, old_specs = _build_dag(expected_sites, raw["alpha_grid_ev"])
    _, new_specs = _build_dag(manifest["sites"], manifest["alpha_grid_ev"])
    assert old_specs == new_specs
    names = {s.site_id: s.species_label for s in plan.inventory.subspaces}
    assert {(names[r.site_id], r.mode, r.alpha_ev) for r in plan.run_specs} == {
        (s.site_id, s.mode, s.alpha_ev) for s in old_specs.values()
    }
    assert sha256(original.read_bytes()).hexdigest() == before


@pytest.mark.parametrize(
    "field", ["sites", "alpha_grid_ev", "analysis_policy", "resolved_perturbation_plan_digest"]
)
def test_planned_manifest_cannot_change_targets_or_protocol(tmp_path: Path, field: str) -> None:
    fdf, raw, profile = inputs(tmp_path / "inputs")
    config_path = fdf.parent / "lr.json"
    config_path.write_text(json.dumps(raw), encoding="utf-8")
    result = initialize_campaign(
        fdf_path=str(fdf),
        lr_config_path=str(config_path),
        profile_path=str(profile),
        name="tampered",
        campaign_root=str(tmp_path / "campaigns"),
    )
    manifest_path = Path(result["manifest_path"])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if field == "sites":
        manifest[field][0]["atom_index"] = 2
    elif field == "alpha_grid_ev":
        manifest[field] = [-0.08, 0.08]
    elif field == "analysis_policy":
        manifest[field]["polynomial_degree"] = 1
    else:
        manifest[field] = sha256(b"different plan").hexdigest()
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(CampaignV2Error, match="disagree"):
        load_campaign_v2(manifest_path)


def test_resume_reports_explicit_planner_version_change(tmp_path: Path) -> None:
    fdf, raw, _ = inputs(tmp_path)
    config = normalized(fdf, raw)
    resolved = resolve_campaign_planning(fdf, config)
    freeze_campaign_plan(tmp_path, resolved, config)
    plan_path = tmp_path / "resolved_perturbation_plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    plan["planner_version"] = "campaign-planner-v2"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")

    with pytest.raises(CampaignPlanError) as error:
        verify_frozen_campaign_plan(tmp_path, config)

    assert str(error.value) == (
        "PLANNER_VERSION_CHANGED: stored planner version 'campaign-planner-v2', "
        "current version 'campaign-planner-v4'; re-initialize the campaign; "
        "frozen plans are not migrated"
    )
