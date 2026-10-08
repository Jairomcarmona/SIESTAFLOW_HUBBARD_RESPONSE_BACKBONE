"""End-to-end POSIX replay of the real NiO P5 SIESTA response grid."""

from __future__ import annotations

import hashlib
import json
import math
import re
import sys
import time
from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest

from hubbardflow.execution import campaign_v2, wsl_campaign_init
from hubbardflow.execution.campaign_runner import campaign_status, run_campaign_worker
from hubbardflow.execution.wsl_campaign_init import initialize_campaign
from hubbardflow.siesta_backend.siesta542_bare_profile import Siesta542PotentialShiftHamiltonianProfile

ROOT = Path(__file__).resolve().parents[2]
REAL_FIXTURE = ROOT / "tests" / "fixtures" / "real_nio_p5_rerun"
REPLAY_FIXTURE = ROOT / "tests" / "fixtures" / "replay_nio_p5"
ANALYSIS = "lr_u_analysis.v3.json"
GOLDEN_MANIFEST = REPLAY_FIXTURE / "campaign_manifest.sha256.json"
GOLDEN_JSON_SNAPSHOT = REPLAY_FIXTURE / "campaign_json_snapshot.json"
REPLAY_ANALYSIS = REPLAY_FIXTURE / "replay_analysis.v3.json"
REPLAY_STATE_GATE = REPLAY_FIXTURE / "replay_i5_state_gate.json"
_ATTEMPT = re.compile(r"attempt-\d+-[0-9a-f]{8}")
_ATTEMPT_BYTES = re.compile(rb"attempt-\d+-[0-9a-f]{8}")
_ATTEMPT_GROUP = re.compile(r"(?<=/attempts/)[0-9a-f]{20}")
_ATTEMPT_SUFFIX = re.compile(r"(?<=_)[0-9a-f]{12}(?=[/._]|$)")
_ATTEMPT_GROUP_BYTES = re.compile(rb"(?<=/attempts/)[0-9a-f]{20}")
_ATTEMPT_SUFFIX_BYTES = re.compile(rb"(?<=_)[0-9a-f]{12}(?=[/._]|$)")
_DYNAMIC_INPUT_HASH_ROW = re.compile(rb"(\| (?:execution_profile|lr_config) \| [^|]+ \| )[0-9a-f]{64}( \|)")
_EVIDENCE_DIGEST_ROW = re.compile(rb"(\| response:[^\n]*\| )[0-9a-f]{64}( \|)")
_SHA256_TOKEN = re.compile(rb"(?<![0-9a-f])[0-9a-f]{64}(?![0-9a-f])")


def test_analysis_comparator_accepts_physical_roundoff_at_measured_scale() -> None:
    expected = {"primary": {"U_by_site_eV": {"0": 6.8}}}
    actual = {"primary": {"U_by_site_eV": {"0": 6.8 * (1.0 + 1e-12)}}}

    _assert_replay_equivalent(actual, expected)


def test_analysis_comparator_rejects_physical_difference_above_tolerance() -> None:
    expected = {"primary": {"U_by_site_eV": {"0": 6.8}}}
    actual = {"primary": {"U_by_site_eV": {"0": 6.8 * (1.0 + 1e-6)}}}

    with pytest.raises(AssertionError, match="primary.U_by_site_eV.0"):
        _assert_replay_equivalent(actual, expected)


def test_analysis_comparator_requires_exact_state_and_decision() -> None:
    with pytest.raises(AssertionError, match="state"):
        _assert_replay_equivalent({"state": "VALIDATED"}, {"state": "FAILED"})
    with pytest.raises(AssertionError, match="decision"):
        _assert_replay_equivalent({"decision": "ACCEPT"}, {"decision": "REJECT"})


def test_analysis_comparator_compares_serialized_contraction_as_numeric_diagnostic() -> None:
    expected = {"verified_contraction_exact": "1/1000"}
    actual = {"verified_contraction_exact": "1000000000000001/1000000000000000000"}
    _assert_replay_equivalent(actual, expected)
    with pytest.raises(AssertionError):
        _assert_replay_equivalent({"verified_contraction_exact": "1/100"}, expected)
    with pytest.raises(AssertionError):
        _assert_replay_equivalent(
            {"other": actual["verified_contraction_exact"]}, {"other": expected["verified_contraction_exact"]}
        )


def test_analysis_comparator_derives_and_checks_sensitivity_state() -> None:
    removed: dict[str, str] = {}
    archived = _comparison_view(
        {"sensitivity_summary": {"assessment": "MEASURED_EXCEEDS_TOLERANCE"}},
        removed,
        "$",
    )
    current = _comparison_view(
        {
            "sensitivity_summary": {
                "assessment": "MEASURED_EXCEEDS_TOLERANCE",
                "state": "SENSITIVE",
                "declared_by": "config",
                "provided_via": "cli",
            }
        },
        {},
        "$",
    )
    _assert_replay_equivalent(current, archived)

    with pytest.raises(AssertionError, match="state disagrees with assessment"):
        _comparison_view(
            {
                "sensitivity_summary": {
                    "assessment": "MEASURED_EXCEEDS_TOLERANCE",
                    "state": "UNASSESSED",
                }
            },
            {},
            "$",
        )


@pytest.mark.parametrize(
    ("actual", "expected"),
    [
        ({"nodes": {"reference": {"state": "OK"}}}, {"nodes": {}}),
        ({"rows": [{"id": "a"}]}, {"rows": [{"id": "a"}, {"id": "b"}]}),
    ],
    ids=("missing-node", "missing-row"),
)
def test_analysis_comparator_rejects_missing_nodes_or_rows(actual: Any, expected: Any) -> None:
    with pytest.raises(AssertionError):
        _assert_replay_equivalent(actual, expected)


def test_json_manifest_diagnostic_reports_only_first_ten_differences() -> None:
    actual = {f"row-{index}": index for index in range(12)}
    expected = {f"row-{index}": -index for index in range(12)}

    differences = _first_json_differences(actual, expected)

    assert len(differences) == 10
    assert differences[0] == {"path": "$.row-1", "actual": 1, "expected": -1}


@pytest.mark.skipif(sys.platform == "win32", reason="campaign replay requires POSIX fcntl and executables")
def test_nio_p5_runner_replay_matches_part_a_and_resumes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Stable campaign identity and timestamps make the complete written-file
    # manifest reproducible; these patches affect only this isolated test.
    def fixed_campaign_id() -> str:
        return "00000000-0000-4000-8000-000000000021"

    monkeypatch.setattr(campaign_v2, "new_campaign_id", fixed_campaign_id)
    monkeypatch.setattr(wsl_campaign_init, "new_campaign_id", fixed_campaign_id)
    ticks = iter(range(1_791_100_000_000_000_000, 1_791_100_000_000_001_000))
    monkeypatch.setattr(time, "time", lambda: 1_791_100_000.0)
    monkeypatch.setattr(time, "time_ns", lambda: next(ticks))
    profile = Siesta542PotentialShiftHamiltonianProfile()
    executable = REPLAY_FIXTURE / "siesta"
    launcher = REPLAY_FIXTURE / "mpirun.openmpi"
    assert executable.stat().st_mode & 0o111, "replay SIESTA fixture must be executable on POSIX"
    assert launcher.stat().st_mode & 0o111, "replay MPI launcher fixture must be executable on POSIX"
    registry = tmp_path / "backend_compatibility.json"
    registry.write_text(
        json.dumps(
            {
                "schema": "backend_compatibility_v1",
                "records": [
                    {
                        "backend": {
                            "backend_id": "siesta",
                            "version": "5.4.2",
                            "executable_sha256": hashlib.sha256(executable.read_bytes()).hexdigest(),
                        },
                        "profile": {
                            "profile_id": profile.profile_id,
                            "version": profile.profile_version,
                            "metadata": {"source_revision": profile.source_revision},
                        },
                        "state": "compatible",
                        "reason": "hash-verified test replay fixture",
                    }
                ],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    inputs = REAL_FIXTURE / "inputs"
    config = json.loads((inputs / "source_lr_config.json").read_text(encoding="utf-8"))
    config["pseudopotentials"] = {
        label: str(inputs / "pseudopotentials" / f"{label}.psml") for label in ("NiLR0", "NiLR1", "O")
    }
    config["compatibility_registry"] = str(registry)
    config["version_text_source"] = str(inputs / "software" / "siesta_version.txt")
    config_path = tmp_path / "lr_config.json"
    config_path.write_text(json.dumps(config, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    profile_path = tmp_path / "execution_profile.json"
    profile_path.write_text(
        json.dumps(
            {
                "target": "local_wsl",
                "evidence": "VALIDATED_RUNTIME",
                "wsl": {
                    "distribution": "Ubuntu",
                    "python_executable": sys.executable,
                    "workspace_root": str(tmp_path),
                },
                "allocation": {
                    "nodes": 1,
                    "total_cpus": 1,
                    "memory": "1G",
                    "walltime": "01:00:00",
                    "max_parallel_steps": 1,
                    "shutdown_margin_seconds": 60,
                    "termination_grace_seconds": 30,
                },
                "runtime": {
                    "module_commands": [],
                    "siesta_executable": str(executable),
                    "exclusive": True,
                    "environment": {},
                    "launcher": {
                        "kind": "openmpi",
                        "command": [str(launcher)],
                        "bootstrap": "local",
                        "processes_per_node": 1,
                    },
                },
                "task_policy": {"max_attempts": 1, "require_scf_converged": True},
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    initialized = initialize_campaign(
        fdf_path=str(inputs / "reference.fdf"),
        lr_config_path=str(config_path),
        profile_path=str(profile_path),
        name="nio_p5_runner_replay",
        pointer_path=str(tmp_path / "nio_p5_runner_replay.pointer.json"),
    )
    manifest = Path(initialized["manifest_path"])

    run_exit_code = run_campaign_worker(manifest, "run")
    if run_exit_code != 0:
        control = manifest.parent / ".siestaflow"
        state_path = control / "worker-state.json"
        worker_state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.is_file() else {}
        working_directory = Path(str(worker_state.get("active_working_directory", "")))
        tails = {
            name: (working_directory / name).read_text(encoding="utf-8", errors="replace").splitlines()[-40:]
            for name in ("siesta.err", "siesta.out")
            if (working_directory / name).is_file()
        }
        worker_error_path = control / "worker-error.json"
        worker_error = (
            json.loads(worker_error_path.read_text(encoding="utf-8")) if worker_error_path.is_file() else None
        )
        raise AssertionError(
            json.dumps(
                {
                    "run_exit_code": run_exit_code,
                    "campaign_status": campaign_status(manifest),
                    "worker_state": worker_state,
                    "worker_error": worker_error,
                    "active_output_tails": tails,
                },
                sort_keys=True,
            )
        )
    stopped = campaign_status(manifest)
    assert stopped["status"] == "STOPPED"
    assert len(stopped["completed_nodes"]) >= 13

    assert run_campaign_worker(manifest, "resume") == 0
    completed = campaign_status(manifest)
    assert completed["status"] == "COMPLETED"
    assert len(completed["completed_nodes"]) == 27

    actual_analysis = json.loads((manifest.parent / "results" / ANALYSIS).read_text(encoding="utf-8"))
    part_a_analysis = json.loads((REAL_FIXTURE / ANALYSIS).read_text(encoding="utf-8"))
    projector_diagnostics = actual_analysis["projector_diagnostics"]
    assert projector_diagnostics["decision_role"] == "RECORD_ONLY"
    assert projector_diagnostics["method2_warning"]["code"] == (
        "SIESTA_METHOD_2_ATOMIC_NONORTHOGONALIZED_PROJECTOR"
    )
    assert projector_diagnostics["method2_warning"]["comparable_to_orthogonalized_projector_u"] is False
    for site in projector_diagnostics["sites"]:
        assert site["u_times_abs_chi0"] == pytest.approx(site["u_ev"] * abs(site["chi0_diagonal_per_ev"]))
        assert site["formal_comparison"] == "NOT_ASSESSED"
        assert site["ligand_charge_capture"] == "NOT_ASSESSED"
    removed: dict[str, str] = {}
    occupation_summary = actual_analysis["occupation_provenance"]
    assert occupation_summary["hash_policy"] == "WARN_ONLY"
    provenance_path = manifest.parent / occupation_summary["path"]
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    assert provenance["schema_version"] == "hubbardflow.occupation_provenance.v1"
    assert occupation_summary["status"] == provenance["status"]
    assert occupation_summary["record_count"] == len(provenance["records"])
    assert occupation_summary["hash_policy"] == provenance["hash_policy"]
    records = provenance["records"]
    assert records
    for record in records:
        assert record["mode"] in {"BARE", "SCREENED", "REFERENCE_SCREENED"}
        assert record["observed_site_id"]
        assert record["file"] == f"{record['run_folder']}/siesta.out"
        assert isinstance(record["selected_block_line"], int)
        assert record["selected_block_line"] > 0
    removed["$.projector_diagnostics"] = "record-only diagnostics absent from archived Part A"
    removed["$.occupation_provenance"] = (
        "TASK 34a summary is checked against its sidecar; archived Part A predates this provenance"
    )
    legacy_comparison_analysis = {
        key: value
        for key, value in actual_analysis.items()
        if key not in {"projector_diagnostics", "occupation_provenance"}
    }
    actual_view = _comparison_view(
        _part_a_rounding_compatibility_view(legacy_comparison_analysis), removed, "$"
    )
    expected_view = _comparison_view(part_a_analysis, removed, "$")
    _assert_replay_equivalent(actual_view, expected_view)
    _assert_part_a_u_within_rounding_bound(actual_analysis, part_a_analysis)

    analysis_path = manifest.parent / "results" / ANALYSIS
    report_path = manifest.parent / "results" / "HUBBARDFLOW.out"
    assert analysis_path.is_file() and analysis_path.stat().st_size > 0
    assert report_path.is_file() and report_path.stat().st_size > 0
    rendered_lr_report = report_path.read_text(encoding="ascii")
    assert "[12] DIAGNOSTICS" in rendered_lr_report
    assert "SIESTA_METHOD_2_ATOMIC_NONORTHOGONALIZED_PROJECTOR" in rendered_lr_report
    replay_golden = json.loads(REPLAY_ANALYSIS.read_text(encoding="utf-8"))
    replay_view = _analysis_comparison_view(legacy_comparison_analysis, manifest.parent.parent.parent)
    replay_golden_view = _analysis_comparison_view(replay_golden, manifest.parent.parent.parent)
    _assert_replay_equivalent(replay_view, replay_golden_view)

    state_gate_path = manifest.parent / "results" / "i5_state_gate.json"
    assert state_gate_path.is_file()
    actual_state_gate = json.loads(state_gate_path.read_text(encoding="utf-8"))
    state_gate_golden = json.loads(REPLAY_STATE_GATE.read_text(encoding="utf-8"))
    _assert_replay_equivalent(actual_state_gate, state_gate_golden)
    pairs = actual_state_gate["pairs"]
    assert len(pairs) == 4
    assert all(pair["verdict"] == "PASS" for pair in pairs)
    assert all(
        check["outcome"] == "NOT_AVAILABLE"
        for pair in pairs
        for amplitude in pair["amplitudes"]
        for sign in ("positive", "negative")
        for check in amplitude[sign]["checks"]
        if check["check"] == "G4"
    )
    assert "Pointwise state gate:" in rendered_lr_report
    node_evidence = json.loads((manifest.parent / ".siestaflow" / "node-evidence.json").read_text())
    assert (
        node_evidence["nodes"]["matrix-analysis"]["report_sha256"]
        == hashlib.sha256(report_path.read_bytes()).hexdigest()
    )

    actual_manifest = _campaign_file_manifest(manifest.parent)
    expected_manifest = json.loads(GOLDEN_MANIFEST.read_text(encoding="utf-8"))
    for analysis_artifact in (
        "results/lr_u_analysis.v3.json",
        "results/LR_U_REPORT.v3.md",
        "results/HUBBARDFLOW.out",
        "results/data/hubbardflow_report_source.v1.json",
        "results/data/occupation_provenance.v1.json",
        "results/data/u_by_site.csv",
        "results/data/chi0_matrix.csv",
        "results/data/chi_matrix.csv",
        "results/i5_state_gate.json",
    ):
        assert analysis_artifact not in actual_manifest
        assert analysis_artifact not in expected_manifest
    if actual_manifest != expected_manifest:
        differences = {
            path: {"actual": actual_manifest.get(path), "expected": expected_manifest.get(path)}
            for path in sorted(set(actual_manifest) | set(expected_manifest))
            if actual_manifest.get(path) != expected_manifest.get(path)
        }
        actual_json = _campaign_json_snapshot(manifest.parent)
        expected_json = (
            json.loads(GOLDEN_JSON_SNAPSHOT.read_text(encoding="utf-8"))
            if GOLDEN_JSON_SNAPSHOT.is_file()
            else {}
        )
        json_differences = {
            path: _first_json_differences(actual_json.get(path), expected_json.get(path))
            for path in sorted(differences)
            if path in actual_json or path in expected_json
        }
        raise AssertionError(
            "replay campaign manifest differs: "
            + json.dumps(
                {"files": differences, "json_field_differences_first_10": json_differences},
                sort_keys=True,
            )
        )


def _comparison_view(value: Any, removed: dict[str, str], path: str) -> Any:
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        if path.endswith(".sensitivity_summary"):
            state_by_assessment = {
                "UNASSESSED_TOLERANCE_MISSING": "UNASSESSED",
                "UNASSESSED_REQUIRED_METRIC_UNAVAILABLE": "UNASSESSED",
                "NOT_ASSESSED": "UNASSESSED",
                "MEASURED_EXCEEDS_TOLERANCE": "SENSITIVE",
                "WITHIN_TOLERANCE_EVIDENCE_INCOMPLETE": "WITHIN_TOLERANCE_EVIDENCE_INCOMPLETE",
                "WITHIN_TOLERANCE": "NUMERICAL_CANDIDATE",
            }
            assessment = value.get("assessment")
            if assessment not in state_by_assessment:
                raise AssertionError(f"{path}: unknown sensitivity assessment {assessment!r}")
            derived_state = state_by_assessment[assessment]
            recorded_state = value.get("state", derived_state)
            if recorded_state != derived_state:
                raise AssertionError(
                    f"{path}.state disagrees with assessment: {recorded_state!r} != {derived_state!r}"
                )
            result["state"] = recorded_state
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if path.endswith(".sensitivity_summary") and key in {"declared_by", "provided_via"}:
                # TASK 24b adds config provenance absent from the archived Part A result.
                removed[child_path] = "TASK 24b sensitivity-report metadata"
                continue
            if path.endswith(".sensitivity_summary") and key == "state":
                continue
            if key == "input_files" and isinstance(child, list):
                dynamic_input_paths = {
                    "backend_contract.json",
                    "execution_profile.json",
                    "lr_config.json",
                    "provenance/source_lr_config.json",
                }
                normalized_files = []
                for index, record in enumerate(child):
                    if not isinstance(record, dict):
                        normalized_files.append(record)
                        continue
                    file_record = dict(record)
                    if file_record.get("path") in dynamic_input_paths:
                        file_record.pop("sha256", None)
                    normalized_files.append(_comparison_view(file_record, removed, f"{child_path}[{index}]"))
                result[key] = normalized_files
                continue
            category: str | None = None
            if key in {"campaign_id", "input_identity"} or key == "name" and path.endswith(".campaign"):
                category = "campaign identity"
            elif key.endswith(("_epoch", "_utc")) or key in {"epoch", "timestamp"}:
                category = "timestamps"
            elif key in {"evidence_digest", "evidence_sha256", "report_sha256"}:
                category = "runtime binding: evidence digest"
            elif key in {"runtime_executable", "python_executable", "package_version"}:
                category = "runtime binding"
            elif key == "sha256" and any(
                field in child_path
                for field in (
                    ".lr_config.",
                    ".execution_profile.",
                    ".campaign_contract.",
                    "lr_config.json",
                    "execution_profile.json",
                    "backend_contract.json",
                )
            ):
                category = "path-bound or campaign-bound input hash"
            if category is not None:
                removed[child_path] = category
                continue
            result[key] = _comparison_view(child, removed, child_path)
        return result
    if isinstance(value, list):
        return [_comparison_view(child, removed, f"{path}[{index}]") for index, child in enumerate(value)]
    if isinstance(value, str):
        return _normalize_attempt_path(value)
    return value


def _part_a_rounding_compatibility_view(analysis: dict[str, Any]) -> dict[str, Any]:
    """Compare the full frozen Part A report using its original rounding fields.

    TASK 24a changes only the primary print-bound propagation. The archived
    artifact remains immutable; its exact original norm bound is still emitted
    in the compatibility subtree. All chi/U, occupation, state and decision
    fields retain the existing complete comparison. The new output is checked
    separately against the complete replay golden and truth-coverage tests.
    """
    compatible = json.loads(json.dumps(analysis))
    for section in (compatible["primary"], compatible["same_grid_linear"], *compatible["window_results"]):
        rounding = section.get("rounding_bound")
        if isinstance(rounding, dict) and "legacy_uniform_norm_bound" in rounding:
            section["rounding_bound"] = rounding["legacy_uniform_norm_bound"]
    rounding = compatible["printing_rounding_bounds"]
    if "legacy_uniform_norm_bound" in rounding:
        legacy = rounding["legacy_uniform_norm_bound"]
        compatible["printing_rounding_bounds"] = legacy
        compatible["printing_rounding_bound_eV"] = legacy["maximum_U_scalar_half_width_eV"]
    return compatible


def _assert_replay_equivalent(actual: Any, expected: Any, path: str = "$") -> None:
    """Compare exact structure and categorical fields with platform-safe float tolerances.

    These tolerances are for numerical reproducibility of this test across platforms,
    not scientific thresholds (AGENTS.md rule 6 does not apply). The author measured
    a maximum relative difference of 2.6e-11 in physical results and 1.4e-9 in
    ill-conditioned diagnostics across environments including NumPy 2.5.
    """
    if path.endswith(".verified_contraction_exact") and isinstance(actual, str) and isinstance(expected, str):
        # Runtime validates q<1 with Fraction. R includes a BLAS inverse, so
        # its exact residual's lexical encoding can vary in last bits across
        # platforms. Compare this new numeric diagnostic with the existing
        # numeric tolerances; state/reason and all other strings stay exact.
        _assert_replay_equivalent(float(Fraction(actual)), float(Fraction(expected)), path)
        return
    if type(actual) is not type(expected):
        raise AssertionError(f"{path}: type differs ({type(actual).__name__} != {type(expected).__name__})")
    if isinstance(actual, dict):
        actual_keys = set(actual)
        expected_keys = set(expected)
        if actual_keys != expected_keys:
            raise AssertionError(
                f"{path}: keys differ (missing={sorted(expected_keys - actual_keys, key=str)}, "
                f"unexpected={sorted(actual_keys - expected_keys, key=str)})"
            )
        for key in sorted(actual_keys, key=str):
            _assert_replay_equivalent(actual[key], expected[key], f"{path}.{key}")
        return
    if isinstance(actual, list):
        if len(actual) != len(expected):
            raise AssertionError(f"{path}: length differs ({len(actual)} != {len(expected)})")
        for index, (actual_item, expected_item) in enumerate(zip(actual, expected, strict=True)):
            _assert_replay_equivalent(actual_item, expected_item, f"{path}[{index}]")
        return
    if isinstance(actual, float):
        if not math.isfinite(actual) or not math.isfinite(expected):
            if actual != expected:
                raise AssertionError(f"{path}: non-finite floats differ ({actual!r} != {expected!r})")
            return
        rel_tol, abs_tol = _float_tolerances(path)
        if not math.isclose(actual, expected, rel_tol=rel_tol, abs_tol=abs_tol):
            raise AssertionError(
                f"{path}: floats differ ({actual!r} != {expected!r}; "
                f"rel_tol={rel_tol:g}, abs_tol={abs_tol:g})"
            )
        return
    if actual != expected:
        raise AssertionError(f"{path}: values differ ({actual!r} != {expected!r})")


def _float_tolerances(path: str) -> tuple[float, float]:
    normalized = path.lower()
    if "residual" in normalized or "diagnostic" in normalized:
        return 1e-6, 1e-12
    physical_fields = ("u_by_site_ev", "u_matrix_ev", "u_scalar", "interval", "half_width")
    path_segments = [segment for segment in re.split(r"[.\[\]]+", normalized) if segment]
    has_chi_field = any(segment == "chi" or segment.startswith(("chi0", "chi_")) for segment in path_segments)
    if any(field in normalized for field in physical_fields) or has_chi_field:
        return 1e-9, 1e-12
    return 1e-6, 1e-12


def _assert_part_a_u_within_rounding_bound(replay: dict[str, Any], part_a: dict[str, Any]) -> None:
    replay_u = replay["primary"]["U_by_site_eV"]
    part_a_u = part_a["primary"]["U_by_site_eV"]
    half_width = replay["primary"]["rounding_bound"]["U_scalar_half_width_by_site_eV"]
    if set(replay_u) != set(part_a_u) or set(replay_u) != set(half_width):
        raise AssertionError("Part A and replay U/half-width site keys differ")
    for site in sorted(replay_u):
        difference = abs(float(replay_u[site]) - float(part_a_u[site]))
        bound = float(half_width[site])
        if difference > bound:
            raise AssertionError(f"site {site}: |U_replay - U_PartA|={difference} exceeds half-width={bound}")


def _analysis_comparison_view(value: Any, workspace_root: Path) -> Any:
    removed: dict[str, str] = {}
    comparable = _comparison_view(value, removed, "$")
    comparable = _normalize_campaign_root(comparable, str(workspace_root))
    return _normalize_named_root(comparable, str(ROOT), "$REPOSITORY_ROOT")


def _normalize_named_root(value: Any, root: str, token: str) -> Any:
    if isinstance(value, dict):
        return {key: _normalize_named_root(child, root, token) for key, child in value.items()}
    if isinstance(value, list):
        return [_normalize_named_root(child, root, token) for child in value]
    if isinstance(value, str):
        return value.replace(root, token)
    return value


def _campaign_file_manifest(root: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = _normalize_attempt_path(path.relative_to(root).as_posix())
        if relative in {
            "results/lr_u_analysis.v3.json",
            "results/LR_U_REPORT.v3.md",
            "results/HUBBARDFLOW.out",
            "results/data/hubbardflow_report_source.v1.json",
            # TASK 34a validates this derived artifact against the analysis
            # summary above. Its output digests are advisory, not a replay gate.
            "results/data/occupation_provenance.v1.json",
            "results/data/u_by_site.csv",
            "results/data/chi0_matrix.csv",
            "results/data/chi_matrix.csv",
            "results/i5_state_gate.json",
        }:
            continue
        raw = path.read_bytes()
        try:
            value = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError):
            normalized = raw.replace(str(root.parent).encode(), b"$CAMPAIGN_ROOT")
            normalized = normalized.replace(str(ROOT).encode(), b"$REPOSITORY_ROOT")
            normalized = _ATTEMPT_BYTES.sub(b"attempt-NORMALIZED", normalized)
            normalized = _ATTEMPT_GROUP_BYTES.sub(b"ATTEMPT-GROUP", normalized)
            normalized = _ATTEMPT_SUFFIX_BYTES.sub(b"ATTEMPT-SUFFIX", normalized)
            if path.name in {"LR_U_REPORT.v3.md", "HUBBARDFLOW.out"}:
                normalized = _DYNAMIC_INPUT_HASH_ROW.sub(rb"\1DYNAMIC_INPUT_HASH\2", normalized)
                normalized = _EVIDENCE_DIGEST_ROW.sub(rb"\1DYNAMIC_EVIDENCE_DIGEST\2", normalized)
                # The report repeats hashes for artifacts that are checked as
                # separate manifest entries; canonicalize their rendered copies.
                normalized = _SHA256_TOKEN.sub(b"SHA256", normalized)
        else:
            comparable = _normalized_campaign_json(value, root)
            normalized = (json.dumps(comparable, sort_keys=True, separators=(",", ":")) + "\n").encode()
        result[relative] = hashlib.sha256(normalized).hexdigest()
    return result


def _normalized_campaign_json(value: Any, root: Path) -> Any:
    removed: dict[str, str] = {}
    comparable = _comparison_view(value, removed, "$")
    comparable = _normalize_campaign_root(comparable, str(root.parent))
    return _normalize_campaign_root(comparable, str(ROOT))


def _campaign_json_snapshot(root: Path) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = _normalize_attempt_path(path.relative_to(root).as_posix())
        if relative in {"results/lr_u_analysis.v3.json", "results/i5_state_gate.json"}:
            continue
        try:
            value = json.loads(path.read_bytes())
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
        result[relative] = _normalized_campaign_json(value, root)
    return result


def _first_json_differences(actual: Any, expected: Any, path: str = "$") -> list[dict[str, Any]]:
    """Return the first ten JSON value differences to diagnose manifest hash changes."""
    differences: list[dict[str, Any]] = []

    def visit(left: Any, right: Any, current: str) -> None:
        if len(differences) >= 10:
            return
        if isinstance(left, dict) and isinstance(right, dict):
            for key in sorted(set(left) | set(right), key=str):
                child = f"{current}.{key}"
                if key not in left or key not in right:
                    differences.append(
                        {
                            "path": child,
                            "actual": left.get(key, "<missing>"),
                            "expected": right.get(key, "<missing>"),
                        }
                    )
                else:
                    visit(left[key], right[key], child)
                if len(differences) >= 10:
                    return
            return
        if isinstance(left, list) and isinstance(right, list):
            for index in range(max(len(left), len(right))):
                child = f"{current}[{index}]"
                if index >= len(left) or index >= len(right):
                    differences.append(
                        {
                            "path": child,
                            "actual": left[index] if index < len(left) else "<missing>",
                            "expected": right[index] if index < len(right) else "<missing>",
                        }
                    )
                else:
                    visit(left[index], right[index], child)
                if len(differences) >= 10:
                    return
            return
        if type(left) is not type(right) or left != right:
            differences.append({"path": current, "actual": left, "expected": right})

    visit(actual, expected, path)
    return differences


def _normalize_attempt_path(value: str) -> str:
    value = _ATTEMPT.sub("attempt-NORMALIZED", value)
    value = _ATTEMPT_GROUP.sub("ATTEMPT-GROUP", value)
    return _ATTEMPT_SUFFIX.sub("ATTEMPT-SUFFIX", value)


def _normalize_campaign_root(value: Any, root: str) -> Any:
    if isinstance(value, dict):
        return {key: _normalize_campaign_root(child, root) for key, child in value.items()}
    if isinstance(value, list):
        return [_normalize_campaign_root(child, root) for child in value]
    if isinstance(value, str):
        return value.replace(root, "$CAMPAIGN_ROOT")
    return value
