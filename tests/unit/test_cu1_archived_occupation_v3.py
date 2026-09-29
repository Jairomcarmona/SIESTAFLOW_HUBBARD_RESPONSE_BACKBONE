"""Real archived Cu1 regression for the Occupations v3 verified dataset.

This deliberately stops before response fitting: the immutable campaign gate
does not authorize chi reconstruction, inversion, or a numerical U.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from siestaflow_hubbard.domain.matrix_lr import ResponseObservation
from siestaflow_hubbard.execution.campaign_runner import (
    CampaignRunner,
    _build_verified_dataset,
)
from siestaflow_hubbard.siesta_backend.siesta542_bare_profile import (
    Siesta542PotentialShiftHamiltonianProfile,
)
from siestaflow_hubbard.siesta_backend.siesta542_screened_selection import (
    select_converged_screened_event,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
ARCHIVE_REL = Path(
    "docs/evidence/siesta542_openmpi_slurm_full_campaign_20260920_run2_wheel"
)


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _archive_file(root: Path, absolute_from_command: str) -> Path:
    """Map an archived Linux command path back to its checked-in relative path."""
    normalized = absolute_from_command.replace("\\", "/")
    marker = "/siesta542_openmpi_slurm_full_campaign_20260920_run2_wheel/"
    assert marker in normalized
    relative = normalized.split(marker, 1)[1]
    return root / Path(*relative.split("/"))


def _verify_manifested_file(root: Path, manifest: dict, path: Path) -> str:
    relative = path.relative_to(root).as_posix()
    expected = manifest[relative]
    contents = path.read_bytes()
    assert len(contents) == expected["size_bytes"], relative
    digest = hashlib.sha256(contents).hexdigest()
    assert digest == expected["sha256"], relative
    return digest


def test_archived_cu1_occupations_v3_builds_verified_dataset_without_authorizing_u():
    archive = REPO_ROOT / ARCHIVE_REL
    manifest_rows = _load_json(archive / "artifact-manifest.json")
    manifest = {row["path"]: row for row in manifest_rows}
    commands = _load_json(archive / "commands.json")
    receipts = {
        row["node_id"]: row
        for row in _load_json(archive / "result.json")["execution_receipts"]
    }
    projected = _load_json(archive / "analysis/projected-occupation-observations.json")

    assert len(commands) == 13
    # The archived diagnostic lists its single reference once per response
    # mode; the execution archive still contains only 13 distinct output nodes.
    assert len(projected) == 14
    command_by_node = {row["node_id"]: row for row in commands}
    projected_by_node = {
        ("reference" if row["node_id"] == "reference_as_alpha_zero" else row["node_id"]): row
        for row in projected
    }
    assert len(projected_by_node) == 13
    assert set(command_by_node) == set(receipts)
    assert set(command_by_node) == set(projected_by_node)

    reference_command = command_by_node["reference"]
    reference_out = _archive_file(archive, reference_command["stdout_path"])
    reference_fdf = _archive_file(archive, reference_command["stdin_path"])
    reference_dm = reference_out.parent / "CU_FULL_REFERENCE.DM"
    reference_out_hash = _verify_manifested_file(archive, manifest, reference_out)
    reference_dm_hash = _verify_manifested_file(archive, manifest, reference_dm)
    assert reference_out_hash == projected_by_node["reference"]["output_sha256"]

    reference_text = reference_out.read_text(encoding="utf-8", errors="replace")
    reference_event = select_converged_screened_event(reference_text)
    sites = [{"site_id": "Cu1", "atom_index": 1, "orbit_id": "Cu1"}]
    runner = object.__new__(CampaignRunner)
    runner._minimum_occupation_decimal_places = None
    reference_occupations = runner._event_occupations(
        reference_text, reference_event, sites,
    )
    reference_half_widths = runner._event_trace_half_widths(
        reference_text, reference_event, sites,
    )
    assert reference_half_widths is not None

    reference_receipt = receipts["reference"]
    reference_source = {
        "node_id": "reference",
        "mode": "REFERENCE_SCREENED",
        "state": reference_receipt["state"],
        "fdf_path": reference_fdf.relative_to(archive).as_posix(),
        "out_path": reference_out.relative_to(archive).as_posix(),
        "dm_path": reference_dm.relative_to(archive).as_posix(),
        "fdf_sha256": manifest[reference_fdf.relative_to(archive).as_posix()]["sha256"],
        "out_sha256": reference_out_hash,
        "dm_sha256": reference_dm_hash,
        "evidence_digest": reference_receipt["evidence_digest"],
    }

    response_index = {}
    source_metadata = {}
    half_widths = {}
    parsed_outputs = 1
    for node_id, command in command_by_node.items():
        if node_id == "reference":
            continue
        item = projected_by_node[node_id]
        output = _archive_file(archive, command["stdout_path"])
        fdf = _archive_file(archive, command["stdin_path"])
        own_dm = output.parent / f"{node_id.split(':', 1)[1]}.DM"
        parent_dm = output.parent / "CU_FULL_REFERENCE.DM"
        output_hash = _verify_manifested_file(archive, manifest, output)
        own_dm_hash = _verify_manifested_file(archive, manifest, own_dm)
        parent_dm_hash = _verify_manifested_file(archive, manifest, parent_dm)
        assert output_hash == item["output_sha256"]
        assert parent_dm_hash == reference_dm_hash
        parsed_outputs += 1

        output_text = output.read_text(encoding="utf-8", errors="replace")
        mode = item["mode"]
        if mode == "BARE":
            event = Siesta542PotentialShiftHamiltonianProfile().select_response(
                output_text
            ).response_event
        else:
            event = select_converged_screened_event(output_text)
        occupations = runner._event_occupations(output_text, event, sites)
        selected_half_widths = runner._event_trace_half_widths(
            output_text, event, sites,
        )
        assert selected_half_widths is not None

        alpha = float(item["alpha_ev"])
        pair = response_index.setdefault(alpha, {"bare": None, "screened": None})
        mode_key = mode.casefold()
        pair[mode_key] = occupations[0]
        half_widths[(0, alpha, mode_key)] = selected_half_widths
        receipt = receipts[node_id]
        source_metadata.setdefault((0, alpha), {})[mode_key] = {
            "node_id": node_id,
            "mode": mode,
            "state": receipt["state"],
            "fdf_path": fdf.relative_to(archive).as_posix(),
            "out_path": output.relative_to(archive).as_posix(),
            "dm_path": own_dm.relative_to(archive).as_posix(),
            "fdf_sha256": manifest[fdf.relative_to(archive).as_posix()]["sha256"],
            "out_sha256": output_hash,
            "dm_sha256": own_dm_hash,
            "evidence_digest": receipt["evidence_digest"],
        }

    assert parsed_outputs == 13
    assert len(response_index) == 6
    observations = []
    for alpha, pair in sorted(response_index.items()):
        assert pair["bare"] is not None and pair["screened"] is not None
        observations.append(ResponseObservation(
            perturbation_site=0,
            alpha=alpha,
            site_labels=[0],
            occupations_ref=reference_occupations,
            occupations_bare=[pair["bare"]],
            occupations_screened=[pair["screened"]],
            parent_dm_sha256=reference_dm_hash,
        ))

    dataset = _build_verified_dataset(
        observations,
        sites,
        reference_source=reference_source,
        response_sources=source_metadata,
        trace_half_widths_electron=half_widths,
        reference_trace_half_widths_electron=reference_half_widths,
        occupation_source="siesta_occupations_total",
    )

    assert dataset["schema_version"] == "siestaflow.lr_u_verified_dataset.v2"
    assert dataset["occupation_source"] == "siesta_occupations_total"
    assert dataset["site_index_map"] == [
        {"index": 0, "site_id": "Cu1", "atom_index": 1, "orbit_id": "Cu1"}
    ]
    assert len(dataset["rows"]) == 6
    first_observed = dataset["rows"][0]["observed_sites"][0]
    assert first_observed["occupation_half_widths_electron"] == {
        "reference": reference_half_widths[0],
        "bare": half_widths[(0, dataset["rows"][0]["alpha_eV"], "bare")][0],
        "screened": half_widths[(0, dataset["rows"][0]["alpha_eV"], "screened")][0],
    }
    assert dataset["rows"][0]["sources"]["bare"]["dm_sha256"]
    assert dataset["rows"][0]["sources"]["screened"]["dm_sha256"]

    # This test intentionally does not invoke analyze_verified_lr or derive chi/U.
    verdict = _load_json(archive / "final-verdict.json")
    result = _load_json(archive / "result.json")
    assert verdict["verdict"] == "FAIL_CLOSED_NO_AUTHORIZED_U"
    assert verdict["U_ev"] is None
    assert verdict["chi0"] is None and verdict["chi"] is None
    assert result["scientific_result"] is None
    assert result["analysis_gate"]["gate"] == "METHODOLOGY_LOCK_MISSING_EXTERNAL_OCCUPATION_NOISE_BOUND"
    assert result["analysis_gate"]["inversion"]["status"] == "NOT_AUTHORIZED"
