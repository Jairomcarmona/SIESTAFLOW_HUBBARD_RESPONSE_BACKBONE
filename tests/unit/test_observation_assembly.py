from __future__ import annotations

from hashlib import sha256
from pathlib import Path

import pytest

from hubbardflow.domain.matrix_lr import ResponseObservation
from hubbardflow.execution.campaign_files import (
    build_verified_dataset,
    campaign_relative_path,
    dataset_half_width,
    dataset_half_widths,
    source_record,
    verify_record_artifacts,
)
from hubbardflow.execution.dag_contract import NodeState
from hubbardflow.execution.generic_executor import NodeReceipt


def test_campaign_file_helpers_build_and_verify_receipt_bound_data(tmp_path: Path) -> None:
    fdf = tmp_path / "input.fdf"
    output = tmp_path / "siesta.out"
    dm = tmp_path / "run.DM"
    fdf.write_text("NumberOfAtoms 1\n", encoding="utf-8")
    output.write_text("Job completed\n", encoding="utf-8")
    dm.write_bytes(b"density matrix")
    receipt = NodeReceipt("response:s0", NodeState.VALIDATED, "a" * 64)
    record = {
        "artifact_spec": {"dm": "run.DM"},
        "command": {"cwd": str(tmp_path), "stdin_path": str(fdf), "stdout_path": str(output)},
        "provenance": {
            "artifacts": {
                "fdf": sha256(fdf.read_bytes()).hexdigest(),
                "output": sha256(output.read_bytes()).hexdigest(),
                "dm": sha256(dm.read_bytes()).hexdigest(),
            }
        },
    }

    assert campaign_relative_path(tmp_path, fdf) == "input.fdf"
    assert campaign_relative_path(tmp_path, None) is None
    assert verify_record_artifacts(record, receipt.node_id) == {
        "fdf": sha256(fdf.read_bytes()).hexdigest(),
        "output": sha256(output.read_bytes()).hexdigest(),
        "dm": sha256(dm.read_bytes()).hexdigest(),
        "hash_warnings": [],
    }
    assert source_record(tmp_path, receipt.node_id, record, receipt, mode="BARE")["out_path"] == "siesta.out"

    observation = ResponseObservation(
        perturbation_site=0,
        alpha=0.02,
        site_labels=[0],
        occupations_ref=[1.0],
        occupations_bare=[1.1],
        occupations_screened=[1.2],
    )
    widths = {(0, 0.02, "bare"): [0.001], (0, 0.02, "screened"): [0.002]}
    assert dataset_half_widths(widths, (0, 0.02), "bare") == [0.001]
    assert dataset_half_width(widths, (0, 0.02), "screened", 0) == 0.002
    dataset = build_verified_dataset(
        [observation],
        [{"site_id": "s0", "atom_index": 1}],
        reference_source={"dm_sha256": "b" * 64},
        response_sources={(0, 0.02): {"bare": {"node_id": "b"}, "screened": {"node_id": "s"}}},
        trace_half_widths_electron=widths,
        reference_trace_half_widths_electron=[0.0005],
        occupation_source="siesta_occupations_total",
    )
    assert dataset["status"] == "AVAILABLE"
    assert dataset["rows"][0]["observed_sites"][0]["occupation_half_widths_electron"] == {
        "reference": 0.0005,
        "bare": 0.001,
        "screened": 0.002,
    }


def test_verify_record_artifacts_warns_on_changed_output(tmp_path: Path) -> None:
    fdf = tmp_path / "input.fdf"
    output = tmp_path / "siesta.out"
    dm = tmp_path / "run.DM"
    fdf.write_text("FDF\n", encoding="utf-8")
    output.write_text("initial\n", encoding="utf-8")
    dm.write_bytes(b"DM")
    record = {
        "artifact_spec": {"dm": "run.DM"},
        "command": {"cwd": str(tmp_path), "stdin_path": str(fdf), "stdout_path": str(output)},
        "provenance": {
            "artifacts": {
                "fdf": sha256(fdf.read_bytes()).hexdigest(),
                "output": sha256(output.read_bytes()).hexdigest(),
                "dm": sha256(dm.read_bytes()).hexdigest(),
            }
        },
    }
    output.write_text("changed\n", encoding="utf-8")
    verified = verify_record_artifacts(record, "response:s0")
    assert "ARTIFACT_DIGEST_MISMATCH:response:s0:output" in verified["hash_warnings"]
