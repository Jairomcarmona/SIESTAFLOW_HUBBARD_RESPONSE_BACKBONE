from pathlib import Path
from dataclasses import replace

import pytest

from siestaflow_hubbard.domain.response_grid_reproducibility import (
    _VALIDATION_TOKEN,
    ValidatedResponseGridCalibration,
    ResponseGridCalibrationError,
    _validate_independent_execution_identities,
)
from siestaflow_hubbard.domain.lr_analysis_v2 import _response_grid_empirical_widths
from siestaflow_hubbard.domain.matrix_lr import ResponseObservation


def _campaign(root: Path, campaign_id: str, attempt_id: str) -> dict[str, object]:
    return {
        "campaign_id": campaign_id,
        "source_root": root,
        "attempt_ids": {attempt_id},
        # Identical bytes are valid under deterministic SIESTA execution.
        "reference_dm_sha256": "a" * 64,
        "response_out_sha256": "b" * 64,
    }


def test_identical_dm_and_outputs_are_admissible_with_distinct_attempts(tmp_path: Path) -> None:
    root_a = tmp_path / "campaign-a"
    root_b = tmp_path / "campaign-b"
    root_a.mkdir()
    root_b.mkdir()
    campaigns = [
        _campaign(root_a, "campaign-uuid-a", "attempt-100-aaaaaaaa"),
        _campaign(root_b, "campaign-uuid-b", "attempt-200-bbbbbbbb"),
    ]
    _validate_independent_execution_identities(campaigns)

    # Exercise the analyzer's actual primary-vs-replica gate with matching
    # occupations and DM hashes, the deterministic case that DM inequality
    # used to reject.
    calibration = ValidatedResponseGridCalibration(
        campaign_context_sha256="c" * 64,
        lock_sha256="d" * 64,
        result_sha256="e" * 64,
        replica_count=3,
        replica_campaign_ids=("campaign-uuid-a", "campaign-uuid-b", "campaign-uuid-c"),
        reference_dm_sha256s=("a" * 64, "a" * 64, "a" * 64),
        replica_source_roots=(str(root_a), str(root_b), str(tmp_path / "campaign-c")),
        reference_execution_attempt_ids=(
            "attempt-100-aaaaaaaa", "attempt-200-bbbbbbbb", "attempt-300-cccccccc",
        ),
        execution_attempt_ids=(
            "attempt-100-aaaaaaaa", "attempt-200-bbbbbbbb", "attempt-300-cccccccc",
            "attempt-101-aaaaaaaa", "attempt-201-bbbbbbbb", "attempt-301-cccccccc",
        ),
        safety_factor=1.0,
        deterministic_floor_e=1e-6,
        observed_replicas_by_coordinate={
            (0, 0.1, "BARE", 0): [0.4, 0.4, 0.4],
            (0, 0.1, "SCREENED", 0): [0.3, 0.3, 0.3],
        },
        replica_print_half_widths_by_coordinate={
            (0, 0.1, "BARE", 0): [0.0, 0.0, 0.0],
            (0, 0.1, "SCREENED", 0): [0.0, 0.0, 0.0],
        },
        scope="EMPIRICAL_RESPONSE_GRID_REPRODUCIBILITY_CONDITIONAL_ON_VERIFIED_NODE_EVIDENCE",
        _token=_VALIDATION_TOKEN,
    )
    observation = ResponseObservation(
        perturbation_site=0,
        alpha=0.1,
        site_labels=[0],
        occupations_ref=[0.5],
        occupations_bare=[0.4],
        occupations_screened=[0.3],
        parent_dm_sha256="a" * 64,
        bare_out_sha256="b" * 64,
        screened_out_sha256="b" * 64,
    )
    widths, evidence = _response_grid_empirical_widths(
        [observation],
        {(0, 0.1, "bare"): [0.0], (0, 0.1, "screened"): [0.0]},
        calibration,
        primary_campaign_id="primary-uuid",
        primary_source_root=str(tmp_path / "primary"),
        primary_execution_attempt_ids=("attempt-primary-reference", "attempt-primary-response"),
    )
    assert widths is not None
    assert evidence["status"] == "COMPLETE_EMPIRICAL_RESPONSE_GRID_REPLICAS"


def test_reused_attempt_is_rejected_even_when_campaign_roots_differ(tmp_path: Path) -> None:
    root_a = tmp_path / "campaign-a"
    root_b = tmp_path / "campaign-b"
    root_a.mkdir()
    root_b.mkdir()
    copied_attempt = "attempt-100-aaaaaaaa"
    campaigns = [
        _campaign(root_a, "campaign-uuid-a", copied_attempt),
        _campaign(root_b, "campaign-uuid-b", copied_attempt),
    ]

    with pytest.raises(ResponseGridCalibrationError, match="reuses a runner attempt"):
        _validate_independent_execution_identities(campaigns)


def test_primary_campaign_root_or_attempt_cannot_be_reused(tmp_path: Path) -> None:
    replica_root = tmp_path / "replica"
    primary_root = tmp_path / "primary"
    replica_root.mkdir()
    primary_root.mkdir()
    record = _campaign(replica_root, "replica-uuid", "attempt-300-cccccccc")

    with pytest.raises(ResponseGridCalibrationError, match="distinct UUIDs and source roots"):
        _validate_independent_execution_identities(
            [record], primary_campaign_id="replica-uuid", primary_source_root=primary_root,
        )
    copied_root_record = _campaign(primary_root, "different-replica-uuid", "attempt-301-dddddddd")
    with pytest.raises(ResponseGridCalibrationError, match="distinct UUIDs and source roots"):
        _validate_independent_execution_identities(
            [copied_root_record], primary_campaign_id="primary-uuid", primary_source_root=primary_root,
        )
    with pytest.raises(ResponseGridCalibrationError, match="reuses a runner attempt"):
        _validate_independent_execution_identities(
            [record], primary_campaign_id="primary-uuid", primary_source_root=primary_root,
            primary_attempt_ids={"attempt-300-cccccccc"},
        )

    calibration = ValidatedResponseGridCalibration(
        campaign_context_sha256="c" * 64, lock_sha256="d" * 64, result_sha256="e" * 64,
        replica_count=3,
        replica_campaign_ids=("replica-a", "replica-b", "replica-c"),
        reference_dm_sha256s=("a" * 64, "a" * 64, "a" * 64),
        replica_source_roots=(str(replica_root), str(replica_root), str(replica_root)),
        reference_execution_attempt_ids=("attempt-300-cccccccc", "attempt-b", "attempt-c"),
        execution_attempt_ids=("attempt-300-cccccccc", "attempt-b", "attempt-c"),
        safety_factor=1.0, deterministic_floor_e=1e-6,
        observed_replicas_by_coordinate={}, replica_print_half_widths_by_coordinate={},
        scope="EMPIRICAL_RESPONSE_GRID_REPRODUCIBILITY_CONDITIONAL_ON_VERIFIED_NODE_EVIDENCE",
        _token=_VALIDATION_TOKEN,
    )
    observation = ResponseObservation(0, 0.1, [0], [0.5], [0.4], [0.3], parent_dm_sha256="a" * 64)
    widths, evidence = _response_grid_empirical_widths(
        [observation], {(0, 0.1, "bare"): [0.0], (0, 0.1, "screened"): [0.0]},
        calibration, primary_campaign_id="primary-uuid", primary_source_root=str(primary_root),
        primary_execution_attempt_ids=("attempt-300-cccccccc",),
    )
    assert widths is None
    assert evidence["reason"] == "primary_and_replica_execution_attempt_ids_are_shared"

    root_shared_calibration = replace(
        calibration,
        replica_source_roots=(str(primary_root), str(tmp_path / "replica-b"), str(tmp_path / "replica-c")),
        execution_attempt_ids=("attempt-a", "attempt-b", "attempt-c"),
    )
    widths, evidence = _response_grid_empirical_widths(
        [observation], {(0, 0.1, "bare"): [0.0], (0, 0.1, "screened"): [0.0]},
        root_shared_calibration, primary_campaign_id="primary-uuid", primary_source_root=str(primary_root),
        primary_execution_attempt_ids=("attempt-primary",),
    )
    assert widths is None
    assert evidence["status"] == "PRIMARY_NOT_INDEPENDENT_OF_REPLICA_SET"
