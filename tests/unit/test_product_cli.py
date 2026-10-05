"""Product FDF commands freeze exact plans and stop before unavailable runtime gates."""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import replace
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from hubbardflow import product_cli
from hubbardflow.cli import main
from hubbardflow.domain.perturbation_plan import PlanStatus
from hubbardflow.execution.campaign_plan import resolve_campaign_planning
from hubbardflow.execution.product_models import ProductBoundary, ProductError, ProductSnapshot
from hubbardflow.execution.product_plan import ProductRequest, load_product_snapshot, resolve_product_snapshot
from tests.unit.test_campaign_plan import ROOT, inputs, normalized
from tests.unit.test_coverage import _toy
from tests.unit.test_fdf_model import _fdf


def product_inputs(tmp_path: Path, text: str | None = None) -> tuple[Path, Path, dict[str, Any], Path]:
    fdf, raw, _ = inputs(tmp_path / "inputs", text)
    config = fdf.parent / "lr.json"
    config.write_text(json.dumps(raw), encoding="utf-8")
    return fdf, config, raw, tmp_path / "product"


def test_fermi_cli_tolerance_overrides_config_and_is_frozen(tmp_path: Path) -> None:
    fdf, config, raw, root = product_inputs(tmp_path)
    raw["tol_Fermi_eV"] = 0.003
    config.write_text(json.dumps(raw), encoding="utf-8")
    assert (
        main(
            [
                "plan",
                str(fdf),
                "--lr-config",
                str(config),
                "--output-dir",
                str(root),
                "--tol-fermi-ev",
                "0.002",
            ]
        )
        == 0
    )
    snapshot = load_product_snapshot(root)
    frozen = json.loads(snapshot.frozen_lr_config_json or "{}")
    assert frozen["tol_Fermi_eV"] == 0.002
    assert frozen["tol_Fermi_eV_source"] == "cli"
    request = json.loads(snapshot.request_json)
    assert request["tol_fermi_ev"] == 0.002


@pytest.mark.parametrize("value", ["-1", "nan", "inf"])
def test_fermi_cli_tolerance_rejects_invalid_values(tmp_path: Path, value: str) -> None:
    fdf, config, _, root = product_inputs(tmp_path)
    assert (
        main(
            ["plan", str(fdf), "--lr-config", str(config), "--output-dir", str(root), "--tol-fermi-ev", value]
        )
        == 2
    )


def test_fermi_cli_tolerance_requires_fdf_and_frozen_lr_config(tmp_path: Path) -> None:
    fdf, _, _, root = product_inputs(tmp_path)
    assert main(["plan", str(fdf), "--output-dir", str(root), "--tol-fermi-ev", "0.002"]) == 2
    assert main(["run", str(tmp_path / "campaign.v2.json"), "--tol-fermi-ev", "0.002"]) == 2


def _staged_product_inputs(
    tmp_path: Path,
) -> tuple[dict[str, object], ProductSnapshot, Path, dict[str, object]]:
    fdf, config, raw, _ = product_inputs(tmp_path)
    snapshot = resolve_product_snapshot(
        ProductRequest(
            str(fdf.resolve()),
            str(config.resolve()),
            None,
            None,
            None,
            None,
            (str(fdf.parent.resolve()),),
            None,
            None,
        )
    )
    frozen_config = json.loads(snapshot.frozen_lr_config_json or "{}")
    profile = fdf.parent / "profile.json"
    campaign_root = tmp_path / "staged-campaign"
    sources = {
        "provenance/source_reference.fdf": fdf,
        "execution_profile.json": profile,
        "software/backend_compatibility.json": Path(raw["compatibility_registry"]),
        "software/siesta_version.txt": Path(raw["version_text_source"]),
        **{f"pseudopotentials/{label}.psml": Path(path) for label, path in raw["pseudopotentials"].items()},
    }
    for relative, source in sources.items():
        target = campaign_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    frozen_path = campaign_root / "provenance/source_lr_config.json"
    frozen_path.write_bytes(((snapshot.frozen_lr_config_json or "{}") + "\n").encode())
    paths = sorted((*sources, "provenance/source_lr_config.json"))
    campaign: dict[str, object] = {
        "_campaign_root": str(campaign_root),
        "input_files": [
            {"path": relative, "sha256": sha256((campaign_root / relative).read_bytes()).hexdigest()}
            for relative in paths
        ],
    }
    return campaign, snapshot, profile, frozen_config


@pytest.mark.parametrize("metadata", ["mismatched", "absent", "malformed"])
def test_product_campaign_digest_metadata_only_warns_and_is_persisted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    metadata: str,
) -> None:
    campaign, snapshot, profile, frozen_config = _staged_product_inputs(tmp_path)
    digest = {"mismatched": "f" * 64, "absent": None, "malformed": "not-a-digest"}[metadata]
    entries = cast(list[dict[str, object]], campaign["input_files"])
    for entry in entries:
        if metadata == "absent":
            entry.pop("sha256")
        else:
            entry["sha256"] = digest
    source_hashes = json.loads(snapshot.input_sha256_json)
    snapshot = replace(
        snapshot,
        input_sha256_json=json.dumps(
            {} if metadata == "absent" else {path: digest for path in source_hashes}
        ),
    )
    if metadata == "absent":
        monkeypatch.setattr(ProductSnapshot, "frozen_lr_config_sha256", property(lambda self: None))
    warnings = product_cli._verify_campaign_inputs(campaign, snapshot, profile, frozen_config)
    expected_reason = {
        "mismatched": "ARTIFACT_DIGEST_MISMATCH",
        "absent": "ARTIFACT_DIGEST_ABSENT",
        "malformed": "ARTIFACT_DIGEST_MALFORMED",
    }[metadata]
    assert {warning.reason.value for warning in warnings} == {expected_reason}
    fields = {warning.field for warning in warnings}
    assert "input_files.provenance/source_reference.fdf.sha256" in fields
    assert "product_sources.provenance/source_reference.fdf.sha256" in fields
    if metadata == "absent":
        assert "product_sources.provenance/source_lr_config.json.sha256" in fields
    retained = [warning.to_mapping() for warning in warnings]
    assert campaign["_product_input_traceability_warnings"] == retained
    record = json.loads(
        (Path(str(campaign["_campaign_root"])) / "product-input-traceability.json").read_text(
            encoding="utf-8"
        )
    )
    assert record["warnings"] == retained


def test_changed_copy_bytes_warn_without_asserting_physical_difference(tmp_path: Path) -> None:
    campaign, snapshot, profile, frozen_config = _staged_product_inputs(tmp_path)
    path = Path(str(campaign["_campaign_root"])) / "provenance/source_reference.fdf"
    path.write_bytes(path.read_bytes() + b"\n# harmless trailing comment\n")
    warnings = product_cli._verify_campaign_inputs(campaign, snapshot, profile, frozen_config)
    assert {warning.reason.value for warning in warnings} == {"ARTIFACT_DIGEST_MISMATCH"}
    assert {warning.field for warning in warnings} == {
        "input_files.provenance/source_reference.fdf.sha256",
        "product_sources.provenance/source_reference.fdf.sha256",
    }


def test_unchanged_product_copies_have_no_digest_warnings(tmp_path: Path) -> None:
    campaign, snapshot, profile, frozen_config = _staged_product_inputs(tmp_path)
    assert product_cli._verify_campaign_inputs(campaign, snapshot, profile, frozen_config) == ()


@pytest.mark.parametrize(
    "relative",
    [
        "provenance/source_reference.fdf",
        "provenance/source_lr_config.json",
        "execution_profile.json",
        "software/backend_compatibility.json",
    ],
)
@pytest.mark.parametrize("unusable", ["missing", "directory"])
def test_required_real_input_remains_mandatory_independent_of_hashes(
    tmp_path: Path,
    relative: str,
    unusable: str,
) -> None:
    campaign, snapshot, profile, frozen_config = _staged_product_inputs(tmp_path)
    target = Path(str(campaign["_campaign_root"])) / relative
    target.unlink()
    if unusable == "directory":
        target.mkdir()
    with pytest.raises(OSError):
        product_cli._verify_campaign_inputs(campaign, snapshot, profile, frozen_config)


@pytest.fixture(autouse=True)
def forbid_simulator(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        pytest.fail("product boundary must not invoke a simulator, worker or initializer")

    monkeypatch.setattr("hubbardflow.execution.campaign_runner.run_campaign_worker", forbidden)
    monkeypatch.setattr("hubbardflow.execution.wsl_campaign_init.initialize_campaign", forbidden)
    monkeypatch.setattr("hubbardflow.cli.start_worker", forbidden)


def test_plan_exact_domain_status_and_frozen_provenance(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    fdf, config, raw, root = product_inputs(tmp_path)
    expected = resolve_campaign_planning(fdf, normalized(fdf, raw))
    assert main(["plan", str(fdf), "--lr-config", str(config), "--output-dir", str(root)]) == 0
    row = json.loads(capsys.readouterr().out)
    snapshot = load_product_snapshot(root)
    assert snapshot.status is expected.plan.status is PlanStatus.NOT_ESTABLISHED
    assert snapshot.planning is not None
    assert snapshot.planning.plan.digest == expected.plan.digest
    assert row["campaign_identity"] == snapshot.campaign_identity
    assert row["planning"]["plan"]["reason_codes"] == [r.value for r in expected.plan.reason_codes]
    assert ProductSnapshot.from_mapping(snapshot.to_mapping()).to_mapping() == snapshot.to_mapping()
    report = (root / "plan_report.md").read_text(encoding="utf-8")
    assert "NOT_ASSESSED" in report and "NOT_ESTABLISHED" in report
    assert "BOUNDS" not in report
    assert expected.plan.digest in report
    assert row["planning"]["diagnostic_coverage"]["policy"]["allow_spin_flip"] is False
    assert row["planning"]["diagnostic_coverage"]["policy"]["allow_rotations"] is False


def test_bare_fdf_retains_diagnostic_without_inventing_grid(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    fdf, _, _, root = product_inputs(tmp_path)
    assert main(["plan", str(fdf), "--output-dir", str(root)]) == 0
    row = json.loads(capsys.readouterr().out)
    assert row["status"] == "NOT_ESTABLISHED"
    assert row["reason_codes"] == ["LR_CONFIG_REQUIRED"]
    assert row["planning"] is None and row["inventory"]["subspaces"]
    assert not (root / "resolved_perturbation_plan.json").exists()
    assert main(["run", str(fdf), "--output-dir", str(root)]) == 3
    boundary = json.loads(capsys.readouterr().out)
    assert "LR_CONFIG_REQUIRED" in boundary["reason_codes"]


@pytest.mark.parametrize("command", ["run", "submit"])
def test_boundary_loads_frozen_plan_and_records_override(
    tmp_path: Path,
    command: str,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fdf, config, _, root = product_inputs(tmp_path)
    args = [command, str(fdf), "--lr-config", str(config), "--output-dir", str(root)]
    if command == "submit":
        args += ["--partition", "user-choice", "--account", "user-account"]
    assert main(args) == 3
    first = json.loads(capsys.readouterr().out)
    assert first["status"] == "NOT_ESTABLISHED"
    assert first["override_reason"] is None
    assert "PLAN_NOT_READY" in first["reason_codes"]
    assert "SCIENTIFIC_STATE_NOT_ESTABLISHED" in first["reason_codes"]
    assert first["resolved_perturbation_plan_digest"] is not None
    manifest_bytes = (root / "resolved_perturbation_plan.json").read_bytes()
    from hubbardflow import product_cli

    real_loader = load_product_snapshot
    loaded: list[Path] = []

    def recorded_loader(path: Path) -> ProductSnapshot:
        loaded.append(path)
        return real_loader(path)

    monkeypatch.setattr(product_cli, "load_product_snapshot", recorded_loader)
    again = [
        command,
        str(fdf),
        "--output-dir",
        str(root),
        "--override-plan-state",
        "declared exploratory request",
    ]
    if command == "submit":
        again += ["--partition", "user-choice", "--account", "user-account"]
    assert main(again) == 3
    second = json.loads(capsys.readouterr().out)
    assert loaded == [root]
    assert second["campaign_identity"] == first["campaign_identity"]
    assert second["override_reason"] == "declared exploratory request"
    assert "PLAN_NOT_READY" not in second["reason_codes"]
    assert "SCIENTIFIC_STATE_NOT_ESTABLISHED" in second["reason_codes"]
    assert "PILOT_REUSE_NOT_ESTABLISHED" in second["reason_codes"]
    assert (root / "resolved_perturbation_plan.json").read_bytes() == manifest_bytes
    receipts = sorted(root.glob(f"{command}.*.receipt.json"))
    assert len(receipts) == 2
    for path in receipts:
        row = json.loads(path.read_text(encoding="utf-8"))
        assert ProductBoundary.from_mapping(row).to_mapping() == row


@pytest.mark.parametrize("changed", ["fdf", "config", "dm", "plan", "lock", "missing-lock"])
def test_resume_rejects_changed_identity(
    tmp_path: Path, changed: str, capsys: pytest.CaptureFixture[str]
) -> None:
    fdf, config, raw, root = product_inputs(tmp_path)
    dm = fdf.parent / "reference.DM"
    dm.write_bytes(b"parent")
    raw["planning_reference_dm"] = str(dm)
    config.write_text(json.dumps(raw), encoding="utf-8")
    assert main(["plan", str(fdf), "--lr-config", str(config), "--output-dir", str(root)]) == 0
    capsys.readouterr()
    if changed == "fdf":
        fdf.write_text(fdf.read_text(encoding="utf-8") + "\nMeshCutoff 350 Ry\n", encoding="utf-8")
    elif changed == "config":
        raw["alpha_grid_ev"] = [-0.08, -0.04, -0.02, 0.02, 0.04, 0.08]
        config.write_text(json.dumps(raw), encoding="utf-8")
    elif changed == "dm":
        dm.write_bytes(b"different parent")
    elif changed == "missing-lock":
        (root / "product_campaign.lock").unlink()
    else:
        path = root / ("product_campaign.lock" if changed == "lock" else "resolved_perturbation_plan.json")
        row = json.loads(path.read_text(encoding="utf-8"))
        if changed == "lock":
            row["campaign_identity"] = "0" * 64
        else:
            row["run_specs"][0]["alpha_ev"] = -0.08
        path.write_text(json.dumps(row), encoding="utf-8")
    assert main(["run", str(fdf), "--output-dir", str(root)]) == 2
    assert "cannot consume frozen product plan" in capsys.readouterr().err
    assert not list(root.glob("run.*.receipt.json"))


def test_legacy_run_still_delegates_to_existing_control(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []

    def fake_control(args: Any) -> int:
        calls.append(args.campaign)
        return 17

    monkeypatch.setattr("hubbardflow.cli._public_control", fake_control)
    assert main(["run", str(tmp_path / "campaign.v2.json")]) == 17
    assert calls == [str(tmp_path / "campaign.v2.json")]


@pytest.mark.parametrize("command", ["plan", "run", "submit"])
def test_help_exposes_product_contract(command: str, capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main([command, "--help"])
    assert exc.value.code == 0
    help_text = capsys.readouterr().out
    for option in (
        "--coverage",
        "--alpha-strategy",
        "--allow-spin-flip",
        "--allow-rotations",
        "--output-dir",
    ):
        assert option in help_text
    if command == "submit":
        assert "--partition" in help_text and "--account" in help_text


def test_partition_required_and_empty_override_rejected(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    fdf, config, _, root = product_inputs(tmp_path)
    with pytest.raises(SystemExit) as exc:
        main(["submit", str(fdf)])
    assert exc.value.code == 2
    assert (
        main(
            [
                "run",
                str(fdf),
                "--lr-config",
                str(config),
                "--output-dir",
                str(root),
                "--override-plan-state",
                " ",
            ]
        )
        == 2
    )
    assert "nonempty reason" in capsys.readouterr().err


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_nonfinite_protocol_fails_closed(
    tmp_path: Path, value: float, capsys: pytest.CaptureFixture[str]
) -> None:
    fdf, config, raw, root = product_inputs(tmp_path)
    raw["alpha_grid_ev"][0] = value
    config.write_text(json.dumps(raw), encoding="utf-8")
    assert main(["plan", str(fdf), "--lr-config", str(config), "--output-dir", str(root)]) == 2
    assert "invalid product JSON" in capsys.readouterr().err
    assert not root.exists()


@settings(max_examples=8, deadline=None)
@given(st.permutations((-0.06, -0.04, -0.02, 0.02, 0.04, 0.06)))
def test_plan_identity_invariant_to_declared_grid_order(grid: list[float]) -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as directory:
        fdf, config, raw, root = product_inputs(Path(directory))
        assert main(["plan", str(fdf), "--lr-config", str(config), "--output-dir", str(root)]) == 0
        before = load_product_snapshot(root).campaign_identity
        raw["alpha_grid_ev"] = list(grid)
        config.write_text(json.dumps(raw), encoding="utf-8")
        assert load_product_snapshot(root).campaign_identity == before


@pytest.mark.parametrize("size", [2, 4])
def test_synthetic_column_and_translation_plans_reach_runtime_boundary(
    tmp_path: Path,
    size: int,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    text = (
        _fdf()
        .replace("NumberOfAtoms 1", f"NumberOfAtoms {size}")
        .replace("NumberOfSpecies 1", f"NumberOfSpecies {size}")
    )
    text = text.replace("1 27 Co", "\n".join(f"{i + 1} 27 Co{i}" for i in range(size)))
    text = text.replace("0 0 0 1 # Co label", "\n".join(f"{i / size} 0 0 {i + 1}" for i in range(size)))
    text = text.replace(
        "Co 1\n3 2\n0.2 0.1 0.0\n3.0 0.05 9.0",
        "\n".join(f"Co{i} 1\n1 0\n0 0\n3.0 0.05 9.0" for i in range(size)),
    )
    text = text.replace("Co\nn=3 0 2 E 40 5", "\n".join(f"Co{i}\nn=3 0 2 E 40 5" for i in range(size)))
    text += "\nDFTU.PotentialShift true\nXC.functional GGA\nXC.authors PBE\n"
    fdf, config, raw, root = product_inputs(tmp_path, text)
    for path in raw["pseudopotentials"].values():
        Path(path).write_text(
            "<psml><functional>PBE GGA</functional><input-file>Co 27</input-file></psml>", encoding="utf-8"
        )
    output, dm = fdf.parent / "reference.out", fdf.parent / "parent.DM"
    output.write_bytes(b"synthetic adapter injection")
    dm.write_bytes(b"synthetic parent")
    raw.update(
        coverage="TRANSLATION_SHADOWED", planning_reference_output=str(output), planning_reference_dm=str(dm)
    )
    inv = normalized(fdf, raw)
    from hubbardflow.execution.campaign_plan import campaign_inventory

    inventory = campaign_inventory(fdf, (fdf.parent,))
    _, reference, _ = _toy(size)
    reference = replace(
        reference,
        input_file_sha256=sha256(fdf.read_bytes()).hexdigest(),
        state=replace(
            reference.state,
            input_fdf_sha256=inventory.effective_fdf_sha256,
            occupation_spectra_by_subspace=tuple(
                replace(row, site_id=site.site_id)
                for row, site in zip(
                    reference.state.occupation_spectra_by_subspace, inventory.subspaces, strict=True
                )
            ),
        ),
    )
    monkeypatch.setattr(
        "hubbardflow.siesta_backend.coverage_reference.build_coverage_reference_evidence",
        lambda *_: reference,
    )
    monkeypatch.setattr(
        "hubbardflow.execution.product_plan.build_coverage_reference_evidence", lambda *_: reference
    )
    config.write_text(json.dumps(raw), encoding="utf-8")
    expected = resolve_campaign_planning(fdf, inv)
    assert main(["plan", str(fdf), "--lr-config", str(config), "--output-dir", str(root)]) == 0
    capsys.readouterr()
    frozen = load_product_snapshot(root)
    assert frozen.planning is not None and frozen.planning.plan.digest == expected.plan.digest
    assert len(frozen.planning.plan.computed_columns) == 2
    assert len(frozen.planning.plan.reconstruction_maps) == (2 if size == 4 else 0)
    assert main(["run", str(fdf), "--output-dir", str(root)]) == 3
    boundary = json.loads(capsys.readouterr().out)
    assert "SCIENTIFIC_STATE_NOT_ESTABLISHED" in boundary["reason_codes"]


@pytest.mark.parametrize(
    "source",
    [
        "benchmarks/lr_u/CoO/reference.fdf",
        "benchmarks/lr_u/stage_u_b/materials/NiO/reference.fdf",
        "campaigns/mno_afmii_strict_lr_v3r2/results/response-matrix-foreground-recovery-v4/00_REFERENCE/siesta.fdf",
        "tests/fixtures/cu3n_reference_siesta.fdf",
    ],
)
def test_archived_disabled_grid_plan_and_run_boundary_preserve_digest(
    tmp_path: Path,
    source: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    original = ROOT / source
    before = sha256(original.read_bytes()).hexdigest()
    fdf, config, raw, root = product_inputs(tmp_path, original.read_text(encoding="utf-8"))
    raw["coverage"] = "DISABLED"
    config.write_text(json.dumps(raw), encoding="utf-8")
    expected = resolve_campaign_planning(fdf, normalized(fdf, raw))
    assert main(["plan", str(fdf), "--lr-config", str(config), "--output-dir", str(root)]) == 0
    capsys.readouterr()
    assert main(["run", str(fdf), "--output-dir", str(root)]) == 3
    receipt = json.loads(capsys.readouterr().out)
    assert receipt["resolved_perturbation_plan_digest"] == expected.plan.digest
    assert sha256(original.read_bytes()).hexdigest() == before


def test_mno_translation_shadow_product_plan_uses_single_file_species_map(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = ROOT / (
        "campaigns/mno_afmii_strict_lr_v3r2/results/response-matrix-foreground-recovery-v4/00_REFERENCE/siesta.fdf"
    )
    archived_output = ROOT / (
        "campaigns/mno_afmii_strict_lr_v3r2/results/response-matrix-foreground-recovery-v4/00_REFERENCE/siesta.out"
    )
    fdf, config, raw, root = product_inputs(tmp_path, source.read_text(encoding="utf-8"))
    manganese_pseudo = ROOT / "campaigns/mno_afmii_strict_lr_v3r2/pseudopotentials/Mn.psml"
    oxygen_pseudo = ROOT / "campaigns/mno_afmii_strict_lr_v3r2/pseudopotentials/O.psml"
    raw["pseudopotentials"] = {
        **{f"MnLR{index:02d}": str(manganese_pseudo) for index in range(16)},
        "O": str(oxygen_pseudo),
    }
    raw["sites"] = normalized(fdf, raw)["sites"]
    dm = tmp_path / "planning-reference.DM"
    dm.write_bytes(b"small test parent DM")
    raw.update(
        coverage="TRANSLATION_SHADOWED",
        planning_reference_output=str(archived_output),
        planning_reference_dm=str(dm),
        reference_dm_name="00_REFERENCE.DM",
    )
    config.write_text(json.dumps(raw), encoding="utf-8")

    assert main(["plan", str(fdf), "--lr-config", str(config), "--output-dir", str(root)]) == 0
    capsys.readouterr()
    snapshot = load_product_snapshot(root)
    assert snapshot.planning is not None
    planning = snapshot.planning
    assert planning.plan.inventory.status.value == "OK"
    assert len(planning.plan.inventory.subspaces) == 16
    assert len(planning.plan.computed_columns) == 4
    assert len(planning.plan.run_specs) == 48
    assert planning.plan.status is PlanStatus.REVIEW
    assert [reason.value for reason in planning.plan.reason_codes] == ["SHADOW_PENDING"]
    classes = planning.diagnostic_coverage.classes
    assert [[member.split("@", 1)[0] for member in item.members] for item in classes] == [
        [f"MnLR{index:02d}" for index in range(0, 16, 2)],
        [f"MnLR{index:02d}" for index in range(1, 16, 2)],
    ]
    assert [item.shadow for item in classes] == ["MnLR02@4:3:2", "MnLR03@5:3:2"]
    assert json.loads(snapshot.frozen_lr_config_json or "{}")["shadow_rejection_policy"] == "STOP"
    report_path = root / "plan_report.md"
    report = report_path.read_text(encoding="utf-8")
    assert report_path.stat().st_size < 200_000
    assert "MnLR00" in report and "MnLR02@4:3:2" in report and "MnLR03@5:3:2" in report
    assert "| Representative | Shadow | Members | Status | Reasons |" in report
    accepted_operations = sum(row.accepted for row in planning.diagnostic_coverage.operations)
    assert f"Total operations: 128; accepted: {accepted_operations}." in report
    exactness_counts = {
        exactness: sum(
            row.operation.exactness_class.value == exactness
            for row in planning.diagnostic_coverage.operations
        )
        for exactness in sorted(
            {row.operation.exactness_class.value for row in planning.diagnostic_coverage.operations}
        )
    }
    first_failures: dict[str, int] = {}
    for operation in planning.diagnostic_coverage.operations:
        if operation.accepted:
            continue
        for condition in operation.conditions:
            if condition.status.value not in {"EQUAL", "NOT_APPLICABLE"} and not (
                condition.condition == "F8"
                and operation.operation.rotation_int == ((1, 0, 0), (0, 1, 0), (0, 0, 1))
            ):
                first_failures[condition.condition] = first_failures.get(condition.condition, 0) + 1
                break

    def table_rows(header: str) -> list[str]:
        lines = report.splitlines()
        start = lines.index(header) + 2
        rows = []
        for line in lines[start:]:
            if not line.startswith("|"):
                break
            rows.append(line)
        return rows

    expected_exactness_rows = [f"| {name} | {count} |" for name, count in exactness_counts.items()]
    assert table_rows("| Exactness class | Count |") == expected_exactness_rows
    expected_first_failure_rows = [
        f"| {condition} | {count} |" for condition, count in sorted(first_failures.items())
    ] or ["| None | 0 |"]
    assert table_rows("| First failing condition | Count |") == expected_first_failure_rows
    assert "| Rejected without a failed F-condition | Count |" in report
    assert "resolved_perturbation_plan.json" in report and "product_plan.json" in report
    assert all(len(block.encode("utf-8")) < 10_000 for block in report.split("```")[1::2])
    assert "Production requires the complete FDRC I.5 state producer" not in report

    launched: list[str] = []

    def record_launch(*args: Any, **kwargs: Any) -> int:
        launched.append(kwargs["name"])
        return 0

    monkeypatch.setattr(
        "hubbardflow.product_cli._execute_product_campaign",
        record_launch,
    )
    monkeypatch.setattr(
        cast(Any, product_cli),
        "os",
        SimpleNamespace(
            name="posix",
            fdopen=os.fdopen,
            fsync=os.fsync,
            replace=os.replace,
        ),
    )
    assert (
        main(
            [
                "run",
                str(fdf),
                "--lr-config",
                str(config),
                "--profile",
                str(config),
                "--name",
                "mno-ts",
                "--output-dir",
                str(root),
            ]
        )
        == 0
    )
    run_boundary = json.loads(capsys.readouterr().out)
    assert run_boundary["execution_admission"]["status"] == "ADMISSIBLE_TRANSLATION_SHADOWED"
    execution_report = (root / "run_report.md").read_text(encoding="utf-8")
    assert "Status: **ADMISSIBLE_TRANSLATION_SHADOWED**" in execution_report
    assert "Ready: run with `--profile`" in execution_report
    assert not {
        "SCIENTIFIC_STATE_NOT_ESTABLISHED",
        "PILOT_REUSE_NOT_ESTABLISHED",
        "PLAN_NOT_READY",
    } & set(run_boundary["reason_codes"])
    assert launched == ["mno-ts"]


def test_run_dry_run_requires_profile_but_never_launches(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fdf, config, _, root = product_inputs(tmp_path)
    calls: list[str] = []
    monkeypatch.setattr(
        "hubbardflow.product_cli.initialize_campaign",
        lambda *args, **kwargs: calls.append("initialize"),
    )
    monkeypatch.setattr(
        "hubbardflow.execution.wsl_campaign_init.initialize_campaign",
        lambda *args, **kwargs: calls.append("initialize"),
    )
    monkeypatch.setattr(
        "hubbardflow.execution.campaign_runner.run_campaign_worker",
        lambda *args, **kwargs: calls.append("worker"),
    )
    assert (
        main(
            [
                "run",
                str(fdf),
                "--dry-run",
                "--profile",
                str(config),
                "--lr-config",
                str(config),
                "--coverage",
                "TRANSLATION_SHADOWED",
                "--output-dir",
                str(root),
            ]
        )
        == 0
    )
    report = json.loads(capsys.readouterr().out)
    assert "artifact_directory" in report
    assert calls == []
    assert main(["run", str(fdf), "--dry-run", "--output-dir", str(tmp_path / "missing-profile")]) == 2
    assert "requires --profile" in capsys.readouterr().err


def test_v6_destination_is_rejected_without_writing() -> None:
    from hubbardflow.execution.product_plan import protect_product_destination

    with pytest.raises(ProductError, match="frozen V6"):
        protect_product_destination(ROOT / "benchmarks/lr_u/product-sidecars")


@pytest.mark.parametrize(
    "field,value,reason",
    [
        ("auto_split_species", True, "STAGED_PENDING_GENERATED_IDENTITY"),
        ("alpha_strategy", "CALIBRATED_GRID", "CALIBRATION_PROTOCOL_REQUIRED"),
    ],
)
def test_pending_features_have_explicit_artifact_states(
    tmp_path: Path,
    field: str,
    value: object,
    reason: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    fdf, config, raw, root = product_inputs(tmp_path)
    raw[field] = value
    config.write_text(json.dumps(raw), encoding="utf-8")
    assert main(["plan", str(fdf), "--lr-config", str(config), "--output-dir", str(root)]) == 0
    row = json.loads(capsys.readouterr().out)
    assert row["status"] == "NOT_ESTABLISHED" and row["reason_codes"] == [reason]
    assert row["planning"] is None
    assert main(["run", str(fdf), "--output-dir", str(root)]) == 3
    assert reason in json.loads(capsys.readouterr().out)["reason_codes"]


def test_reference_only_diagnostic_is_bound_to_output_bytes(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    fdf, _, _, root = product_inputs(tmp_path)
    output = tmp_path / "reference.out"
    output.write_text("truncated reference", encoding="utf-8")
    assert main(["plan", str(fdf), "--reference-output", str(output), "--output-dir", str(root)]) == 0
    row = json.loads(capsys.readouterr().out)
    assert row["diagnostic_coverage"]["reference"]["status"] == "REFERENCE_NOT_ADMISSIBLE"
    assert row["diagnostic_coverage"]["strategy"] == "ALL_SUBSPACES"
    assert "EVIDENCE_INCOMPLETE" in row["diagnostic_coverage"]["reasons"]
    output.write_text("changed truncated reference", encoding="utf-8")
    assert main(["run", str(fdf), "--output-dir", str(root)]) == 2
    assert "invalidated" in capsys.readouterr().err


def test_unmodified_frozen_resume_is_idempotent(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    fdf, config, _, root = product_inputs(tmp_path)
    args = ["run", str(fdf), "--lr-config", str(config), "--output-dir", str(root)]
    assert main(args) == 3
    first = json.loads(capsys.readouterr().out)
    saved = {p.name: p.read_bytes() for p in root.iterdir()}
    assert main(["run", str(fdf), "--output-dir", str(root)]) == 3
    assert json.loads(capsys.readouterr().out) == first
    assert {p.name: p.read_bytes() for p in root.iterdir()} == saved


def test_report_destination_cannot_overwrite_protocol_source(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    fdf, _, raw, root = product_inputs(tmp_path)
    root.mkdir()
    config = root / "plan_report.md"
    original = json.dumps(raw).encode()
    config.write_bytes(original)
    assert main(["plan", str(fdf), "--lr-config", str(config), "--output-dir", str(root)]) == 2
    assert "overwrite a declared input" in capsys.readouterr().err
    assert config.read_bytes() == original
    assert not (root / "product_campaign.lock").exists()


@pytest.mark.parametrize(
    "extra,reason",
    [
        (["--coverage", "TRANSLATION_SHADOWED"], "does not accept --coverage TRANSLATION_SHADOWED"),
        (["--reference-output", "foreign.out"], "does not accept --reference-output or --reference-dm"),
        (["--reference-dm", "foreign.DM"], "does not accept --reference-output or --reference-dm"),
    ],
)
def test_reference_command_refuses_shadowed_and_foreign_reference_inputs(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    extra: list[str],
    reason: str,
) -> None:
    fdf, config, _, root = product_inputs(tmp_path)
    status = main(
        [
            "reference",
            str(fdf),
            "--lr-config",
            str(config),
            "--profile",
            str(tmp_path / "unused-profile.json"),
            "--name",
            "reference-only",
            "--output-dir",
            str(root),
            *extra,
        ]
    )
    assert status == 2
    assert reason in capsys.readouterr().err
    assert not root.exists()


def test_reference_rejects_wrong_dm_name_before_initializer_or_worker(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fdf, config, _, root = product_inputs(tmp_path)
    profile = tmp_path / "profile.json"
    profile.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        cast(Any, product_cli),
        "os",
        SimpleNamespace(name="posix", fdopen=os.fdopen, fsync=os.fsync, replace=os.replace),
    )
    status = main(
        [
            "reference",
            str(fdf),
            "--lr-config",
            str(config),
            "--profile",
            str(profile),
            "--name",
            "reference-only",
            "--output-dir",
            str(root),
        ]
    )
    assert status == 2
    assert "reference.DM" in capsys.readouterr().err
    assert not (root / "campaign.pointer.json").exists()
