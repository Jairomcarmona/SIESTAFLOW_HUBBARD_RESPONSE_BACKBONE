"""Every identity dimension must agree; filenames confer no reuse evidence."""

from __future__ import annotations

import json
from dataclasses import fields, replace
from hashlib import sha256
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from hubbardflow.domain.hash_traceability import DigestWarningReason
from hubbardflow.domain.response_reuse import (
    ResponseReuseError,
    ResponseRunIdentity,
    ReuseStatus,
    qualify_response_reuse,
)
from hubbardflow.domain.symmetry_reduction import ResponseMode
from hubbardflow.execution.campaign_pilot_reuse import (
    PilotArtifact,
    PilotReuse,
    PilotReuseReason,
    PilotReuseStatus,
    select_campaign_pilot,
)


def identity() -> ResponseRunIdentity:
    digest = sha256(b"scientific inputs").hexdigest()
    return ResponseRunIdentity(
        "hubbardflow.response_run_identity.v1",
        digest,
        digest,
        digest,
        "Co@0:3:2",
        0.02,
        ResponseMode.BARE,
        digest,
        digest,
        "siesta-hash",
        "5.4.2",
        digest,
        "matrix-trace",
        "parser-v1",
        digest,
        digest,
        digest,
    )


def artifact(path: Path) -> PilotArtifact:
    digest = sha256(path.read_bytes()).hexdigest()
    receipt = path.with_suffix(".receipt.json")
    receipt.write_text(
        json.dumps(
            {
                "schema": "hubbardflow.validated_pilot_response.v1",
                "state": "VALIDATED",
                "run_identity_digest": identity().digest,
                "output_sha256": digest,
            }
        ),
        encoding="utf-8",
    )
    return PilotArtifact(identity(), path, digest, sha256(receipt.read_bytes()).hexdigest(), receipt)


def test_roundtrip_complete_identity() -> None:
    key = identity()
    assert ResponseRunIdentity.from_mapping(json.loads(json.dumps(key.to_mapping()))) == key
    result = qualify_response_reuse(key, key)
    assert result.status is ReuseStatus.NOT_ESTABLISHED
    assert result.reason.value == "PHYSICAL_CONTEXT_NOT_ESTABLISHED"
    assert result.traceability_warnings == ()
    with pytest.raises(ResponseReuseError, match="complete"):
        ResponseRunIdentity.from_mapping({"target": key.target})


@pytest.mark.parametrize("field", [f.name for f in fields(ResponseRunIdentity) if f.name != "schema"])
def test_each_identity_dimension_is_required(field: str) -> None:
    key = identity()
    changed: object = (
        -0.02
        if field == "alpha_ev"
        else ResponseMode.SCREENED
        if field == "mode"
        else sha256(b"changed scientific input").hexdigest()
        if field.endswith("sha256") or field == "reference_node_digest"
        else "changed-declaration"
    )
    row = key.to_mapping()
    row[field] = changed
    result = qualify_response_reuse(key, ResponseRunIdentity.from_mapping(row))
    if field.endswith("sha256") or field == "reference_node_digest":
        assert result.status is ReuseStatus.NOT_ESTABLISHED
        assert result.mismatched_fields == ()
        assert any(
            w.field == field and w.reason is DigestWarningReason.MISMATCH
            for w in result.traceability_warnings
        )
    else:
        assert result.status is ReuseStatus.IDENTITY_MISMATCH
        assert result.mismatched_fields == (field,)


@given(st.sampled_from([float("nan"), float("inf"), -float("inf"), 0.020001]))
def test_nonfinite_or_nonrepresentable_alpha_rejected(alpha: float) -> None:
    with pytest.raises(ResponseReuseError):
        replace(identity(), alpha_ev=alpha)


def test_filename_never_establishes_reuse_and_changed_outputs_warn(tmp_path: Path) -> None:
    path = tmp_path / "production_named.out"
    path.write_bytes(b"validated response")
    pilot = artifact(path)
    initial = select_campaign_pilot(identity(), (pilot,))
    assert initial.artifact is None
    assert initial.status is PilotReuseStatus.NOT_ESTABLISHED
    assert initial.reason_codes == (PilotReuseReason.PHYSICAL_CONTEXT_NOT_ESTABLISHED,)
    assert initial.traceability_warnings == ()
    missing = select_campaign_pilot(replace(identity(), parser_version="other"), (pilot,))
    assert missing.artifact is None
    assert missing.status is PilotReuseStatus.NOT_ESTABLISHED
    assert PilotReuseReason.PHYSICAL_IDENTITY_MISMATCH in missing.reason_codes
    assert PilotReuse.from_mapping(missing.to_mapping()) == missing
    path.write_bytes(b"altered")
    changed = select_campaign_pilot(identity(), (pilot,))
    assert changed.artifact is None
    assert changed.status is PilotReuseStatus.NOT_ESTABLISHED
    assert {w.field for w in changed.traceability_warnings} == {
        "pilot_output_sha256",
        "receipt_output_sha256",
    }
    assert all(w.reason is DigestWarningReason.MISMATCH for w in changed.traceability_warnings)
    assert changed.reason_codes == initial.reason_codes


def test_conflicting_pilots_recalculate_and_selection_order_invariant(tmp_path: Path) -> None:
    paths = (tmp_path / "a.out", tmp_path / "b.out")
    for path in paths:
        path.write_bytes(b"same response")
    artifacts = tuple(artifact(p) for p in paths)
    assert select_campaign_pilot(identity(), artifacts) == select_campaign_pilot(
        identity(), tuple(reversed(artifacts))
    )
    paths[1].write_bytes(b"different response")
    conflict = artifact(paths[1])
    result = select_campaign_pilot(identity(), (artifacts[0], conflict))
    assert result.artifact is None
    assert result.reason_codes == (PilotReuseReason.PHYSICAL_CONTEXT_NOT_ESTABLISHED,)
    assert result == select_campaign_pilot(identity(), (conflict, artifacts[0]))


def test_validation_receipt_hashes_warn_without_authorizing_reuse(tmp_path: Path) -> None:
    path = tmp_path / "pilot.out"
    path.write_bytes(b"response")
    pilot = artifact(path)
    receipt = json.loads(pilot.validation_receipt.read_text(encoding="utf-8"))
    receipt["run_identity_digest"] = sha256(b"other run").hexdigest()
    pilot.validation_receipt.write_text(json.dumps(receipt), encoding="utf-8")
    result = select_campaign_pilot(identity(), (pilot,))
    assert result.artifact is None
    assert {w.field for w in result.traceability_warnings} == {"pilot_receipt_sha256", "run_identity_digest"}
    pilot = replace(
        pilot, validation_receipt_sha256=sha256(pilot.validation_receipt.read_bytes()).hexdigest()
    )
    result = select_campaign_pilot(identity(), (pilot,))
    assert result.artifact is None
    assert {w.field for w in result.traceability_warnings} == {"run_identity_digest"}
    assert result.reason_codes == (PilotReuseReason.PHYSICAL_CONTEXT_NOT_ESTABLISHED,)


@pytest.mark.parametrize("state", ["FAILED", None])
def test_receipt_state_is_revalidated_independently_of_hash(tmp_path: Path, state: str | None) -> None:
    path = tmp_path / "pilot.out"
    path.write_bytes(b"response")
    pilot = artifact(path)
    receipt = json.loads(pilot.validation_receipt.read_text(encoding="utf-8"))
    receipt["state"] = state
    pilot.validation_receipt.write_text(json.dumps(receipt), encoding="utf-8")
    result = select_campaign_pilot(identity(), (pilot,))
    assert result.artifact is None
    assert PilotReuseReason.PILOT_RECEIPT_NOT_VALIDATED in result.reason_codes


@pytest.mark.parametrize("digest", [None, "", "not-a-sha256"])
def test_missing_or_malformed_pilot_hashes_warn(tmp_path: Path, digest: str | None) -> None:
    path = tmp_path / "pilot.out"
    path.write_bytes(b"response")
    pilot = replace(artifact(path), output_sha256=digest, validation_receipt_sha256=digest)
    result = select_campaign_pilot(identity(), (pilot,))
    assert result.artifact is None
    assert result.reason_codes == (PilotReuseReason.PHYSICAL_CONTEXT_NOT_ESTABLISHED,)
    assert {w.field for w in result.traceability_warnings} == {"pilot_output_sha256", "pilot_receipt_sha256"}
