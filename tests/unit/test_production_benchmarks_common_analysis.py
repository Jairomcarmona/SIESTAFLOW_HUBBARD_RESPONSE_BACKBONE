import copy
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from production_benchmarks import campaign_controller as controller
from production_benchmarks.lr_arithmetic import response_observations_from_records
from hubbardflow.domain.lr_analysis_v2 import LRAnalysisPolicy, analyze_verified_lr
from hubbardflow.reporting.lr_u_report import render_lr_u_report


_DM = "a" * 64


def _record(mode, alpha, site, vector, *, key, ref=False):
    record = {
        "material": "NiO",
        "candidate_id": "candidate-test",
        "mode": mode,
        "alpha": alpha,
        "perturbed_site": site,
        "identity_key": key,
        "stdout_sha256": ("b" if mode == "BARE" else "c") * 64,
        "fdf_sha256": ("d" if mode == "BARE" else "e") * 64,
        "return_code": 0,
        "semantic_validation": "PASSED",
        "selected_occurrence_index": 4,
        "selected_scf_iteration": 8,
        "atom_indices": list(range(1, len(vector) + 1)),
        "occupation_vector": [float(value) for value in vector],
        "selection_role": mode,
        "selection_evidence": "synthetic verified semantic selection",
    }
    if ref:
        record["canonical_dm_sha256"] = _DM
    else:
        record["parent_dm_sha256"] = _DM
    record["observation_payload_sha256"] = controller.observation_receipt_digest(record)
    return record


def _synthetic_records(chi0, chi, alphas):
    n_sites = len(chi0)
    reference = [10.0 + site for site in range(n_sites)]
    rows = [_record("REFERENCE", 0.0, 0, reference, key="reference", ref=True)]
    for mode, matrix in (("BARE", chi0), ("SCREENED", chi)):
        for alpha in alphas:
            sites = [0] if alpha == 0.0 else range(n_sites)
            for site in sites:
                values = [reference[i] + matrix[i, site] * alpha for i in range(n_sites)]
                rows.append(_record(mode, alpha, site, values, key=f"{mode}:{site}:{alpha}"))
    return rows


def _state_for(records):
    completed = {}
    for record in records:
        mode = record["mode"]
        receipt = {
            field: record.get(field)
            for field in (
                "identity_key",
                "candidate_id",
                "response_mode",
                "alpha",
                "perturbed_site",
                "stdout_sha256",
                "fdf_sha256",
                "selected_occurrence_index",
                "selected_scf_iteration",
                "selection_role",
                "selection_evidence",
                "parent_dm_sha256",
                "canonical_dm_sha256",
                "observation_payload_sha256",
            )
        }
        receipt.update(
            {
                "return_code": 0,
                "semantic_validation": "PASSED",
                "response_mode": mode,
                "alpha": float(record["alpha"]),
                "perturbed_site": int(record.get("perturbed_site", 0)),
            }
        )
        completed[record["identity_key"]] = receipt
    return SimpleNamespace(completed=completed)


def test_legacy_rows_expand_shared_zero_and_match_common_analyzer_for_n1_and_n2(monkeypatch):
    scenarios = [
        (np.array([[-0.25]]), np.array([[-0.10]]), [-0.01, 0.0, 0.01], False),
        (
            np.array([[-0.25, 0.02], [0.01, -0.24]]),
            np.array([[-0.10, 0.01], [0.02, -0.09]]),
            [-0.02, -0.01, 0.0, 0.01, 0.02],
            True,
        ),
    ]
    for chi0, chi, alphas, five_point in scenarios:
        rows = _synthetic_records(chi0, chi, alphas)
        verified_receipts = _state_for(rows)
        observations = response_observations_from_records(rows, n_sites=len(chi0))
        assert len(observations) == len(chi0) * len(alphas)
        assert sorted(item.perturbation_site for item in observations if item.alpha == 0.0) == list(
            range(len(chi0))
        )
        expected = analyze_verified_lr(
            observations,
            LRAnalysisPolicy(estimator="linear"),
            campaign={"material": "NiO", "candidate_id": "candidate-test"},
            scf_validated=True,
        )
        outputs = {"json": [], "markdown": []}
        monkeypatch.setattr(controller, "load_observations", lambda *_args: rows)
        monkeypatch.setattr(controller, "CampaignState", lambda *_args: verified_receipts)
        monkeypatch.setattr(controller.Path, "mkdir", lambda *_args, **_kwargs: None)
        monkeypatch.setattr(
            controller,
            "write_lr_analysis_v2",
            lambda path, result: outputs["json"].append((Path(path), result)) or Path(path),
        )
        monkeypatch.setattr(
            controller,
            "write_lr_u_report",
            lambda path, result: outputs["markdown"].append((Path(path), result)) or Path(path),
        )

        legacy_path = controller.matrix_analysis(
            "synthetic-campaign",
            "NiO",
            "candidate-test",
            len(chi0),
            mode_5point=five_point,
        )

        actual = outputs["json"][0][1]
        assert actual["schema_version"] == "siestaflow.lr_u_analysis.v2"
        assert np.allclose(actual["primary"]["chi0_raw"], expected["primary"]["chi0_raw"])
        assert np.allclose(actual["primary"]["chi_raw"], expected["primary"]["chi_raw"])
        assert np.allclose(actual["primary"]["U_matrix_eV"], expected["primary"]["U_matrix_eV"])
        assert np.allclose(actual["U"], actual["primary"]["U_matrix_eV"])
        assert actual["numerical_status"] == expected["numerical_status"]
        assert legacy_path.name == "candidate-test.json"
        assert len(outputs["json"]) == 2
        assert outputs["json"][0][1] == outputs["json"][1][1]
        assert outputs["markdown"][0][0].name == "LR_U_REPORT.md"
        assert outputs["markdown"][0][1] == actual
        rendered = render_lr_u_report(actual)
        assert "Hubbard Linear-Response Report" in rendered
        assert expected["numerical_status"] in rendered


def test_converter_rejects_missing_or_duplicate_mode_observations():
    chi0 = np.array([[-0.25]])
    chi = np.array([[-0.10]])
    rows = _synthetic_records(chi0, chi, [-0.01, 0.0, 0.01])
    with pytest.raises(ValueError, match="missing SCREENED"):
        response_observations_from_records(
            [row for row in rows if not (row["mode"] == "SCREENED" and row["alpha"] == 0.01)],
            n_sites=1,
        )
    duplicated = [*rows, dict(next(row for row in rows if row["mode"] == "BARE" and row["alpha"] == 0.0))]
    with pytest.raises(ValueError, match="duplicate response observation"):
        response_observations_from_records(duplicated, n_sites=1)


def test_controller_rejects_rows_without_a_matching_completion_receipt(monkeypatch):
    rows = _synthetic_records(np.array([[-0.25]]), np.array([[-0.10]]), [-0.01, 0.0, 0.01])
    monkeypatch.setattr(controller, "load_observations", lambda *_args: rows)
    monkeypatch.setattr(controller, "CampaignState", lambda *_args: SimpleNamespace(completed={}))
    with pytest.raises(ValueError, match="completed-run receipt"):
        controller.matrix_analysis("synthetic-campaign", "NiO", "candidate-test", 1)


@pytest.mark.parametrize("field", ["occupation_vector", "atom_indices", "selected_occurrence_index"])
def test_controller_rejects_edited_semantic_event_even_when_file_hashes_are_unchanged(monkeypatch, field):
    rows = _synthetic_records(
        np.array([[-0.25, 0.02], [0.01, -0.24]]),
        np.array([[-0.10, 0.01], [0.02, -0.09]]),
        [-0.01, 0.0, 0.01],
    )
    receipts = _state_for(rows)
    tampered = copy.deepcopy(rows)
    selected = next(row for row in tampered if row["mode"] == "BARE" and row["alpha"] == 0.01)
    if field == "occupation_vector":
        selected[field][0] += 0.5
    elif field == "atom_indices":
        selected[field] = [2, 1]
    else:
        selected[field] += 1
    monkeypatch.setattr(controller, "CampaignState", lambda *_args: receipts)
    with pytest.raises(
        ValueError,
        match="receipt field observation_payload_sha256|receipt field selected_occurrence_index|semantic payload digest",
    ):
        controller._verified_candidate_records("synthetic-campaign", "NiO", "candidate-test", tampered)


def test_persist_observation_is_idempotent_by_identity_before_completion(monkeypatch):
    class MemoryPath:
        files = {}

        def __init__(self, value):
            self.value = str(value).rstrip("/")

        def __truediv__(self, part):
            return MemoryPath(f"{self.value}/{part}")

        @property
        def parent(self):
            return MemoryPath(self.value.rsplit("/", 1)[0])

        @property
        def stem(self):
            return self.value.rsplit("/", 1)[-1].rsplit(".", 1)[0]

        def with_name(self, name):
            return self.parent / name

        def mkdir(self, *args, **kwargs):
            return None

        def exists(self):
            return self.value in self.files

        def read_text(self, encoding="utf-8"):
            return self.files[self.value]

        def __str__(self):
            return self.value

    MemoryPath.files = {}
    monkeypatch.setattr(controller, "Path", MemoryPath)
    atomic_writes = []

    def memory_atomic_replace(path, records):
        atomic_writes.append(str(path))
        MemoryPath.files[str(path)] = "".join(
            json.dumps(row, sort_keys=True, allow_nan=False) + "\n" for row in records
        )

    monkeypatch.setattr(controller, "_atomic_replace_observation_log", memory_atomic_replace)
    monkeypatch.setattr(controller, "CampaignState", lambda *_args: SimpleNamespace(completed={}))
    record = _record("BARE", 0.01, 0, [10.5], key="persist-before-mark-complete")

    controller.persist_observation("memory-campaign", record)
    retry = copy.deepcopy(record)
    controller.persist_observation("memory-campaign", retry)
    assert len(atomic_writes) == 1

    # No completed receipt means the first row is an interrupted-run orphan;
    # a validated retry with a changed event replaces that row atomically.
    changed_retry = copy.deepcopy(record)
    changed_retry["occupation_vector"] = [9.5]
    changed_retry.pop("observation_payload_sha256")
    changed_digest = controller.observation_receipt_digest(changed_retry)
    controller.persist_observation("memory-campaign", changed_retry)
    assert len(atomic_writes) == 3

    main_log = next(value for key, value in MemoryPath.files.items() if key.endswith("candidate-test.jsonl"))
    archive_log = next(
        value for key, value in MemoryPath.files.items() if key.endswith("candidate-test.orphaned.jsonl")
    )
    archived_lines = archive_log.splitlines()
    assert len(archived_lines) == 1
    assert json.loads(archived_lines[0])["occupation_vector"] == [10.5]
    stored_lines = main_log.splitlines()
    assert len(stored_lines) == 1
    assert json.loads(stored_lines[0])["occupation_vector"] == [9.5]
    assert json.loads(stored_lines[0])["observation_payload_sha256"] == changed_digest

    # Once completion is durable, only the digest in that receipt is allowed.
    completed_state = SimpleNamespace(
        completed={
            record["identity_key"]: {"observation_payload_sha256": changed_digest},
        }
    )
    monkeypatch.setattr(controller, "CampaignState", lambda *_args: completed_state)
    controller.persist_observation("memory-campaign", copy.deepcopy(changed_retry))
    assert len(atomic_writes) == 3

    conflicting = copy.deepcopy(changed_retry)
    conflicting["occupation_vector"] = [8.5]
    conflicting.pop("observation_payload_sha256")
    conflicting["observation_payload_sha256"] = controller.observation_receipt_digest(conflicting)
    with pytest.raises(ValueError, match="conflicts with completed receipt"):
        controller.persist_observation("memory-campaign", conflicting)


def test_common_analyzer_reports_singular_response_without_fabricating_u():
    rows = _synthetic_records(
        np.array([[-0.25, -0.50], [-0.50, -1.00]]),
        np.array([[-0.10, -0.20], [-0.20, -0.40]]),
        [-0.01, 0.0, 0.01],
    )
    observations = response_observations_from_records(rows, n_sites=2)
    result = analyze_verified_lr(observations, LRAnalysisPolicy(estimator="linear"))
    assert result["primary"]["matrix_status"] == "RANK_DEFICIENT"
    assert result["primary"]["U_matrix_eV"] is None
    assert result["numerical_status"] == "NO_NUMERICAL_U"
