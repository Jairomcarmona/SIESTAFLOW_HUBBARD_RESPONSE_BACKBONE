"""Digest metadata never substitutes for physical state/context evidence."""

import json
from dataclasses import replace
from hashlib import sha256

import pytest

from hubbardflow.domain.hash_traceability import DigestWarning, DigestWarningReason, digest_warning
from hubbardflow.domain.response_reuse import ResponseRunIdentity, ReuseStatus, qualify_response_reuse
from hubbardflow.domain.symmetry_reduction import ResponseMode


@pytest.mark.parametrize(
    "recorded,reason",
    [
        (None, DigestWarningReason.ABSENT),
        ("", DigestWarningReason.ABSENT),
        ("malformed", DigestWarningReason.MALFORMED),
        (False, DigestWarningReason.MALFORMED),
        ("a" * 64, DigestWarningReason.MISMATCH),
    ],
)
def test_digest_discrepancies_are_serialized_warnings(recorded: object, reason: DigestWarningReason) -> None:
    warning = digest_warning(recorded, "b" * 64, "parent_dm_sha256")
    assert warning is not None and warning.reason is reason
    assert (
        DigestWarning.from_mapping(json.loads(json.dumps(warning.to_mapping(), allow_nan=False))) == warning
    )


@pytest.mark.parametrize("digest", [None, "", "bad", "b" * 64, "a" * 64])
def test_missing_physical_context_has_same_no_reuse_result_for_any_digest(digest: str | None) -> None:
    h = sha256(b"recorded input").hexdigest()
    key = ResponseRunIdentity(
        "hubbardflow.response_run_identity.v1",
        h,
        h,
        h,
        "Co@0:3:2",
        0.02,
        ResponseMode.BARE,
        h,
        h,
        "siesta",
        "5.4.2",
        h,
        "matrix-trace",
        "parser-v1",
        h,
        h,
        h,
    )
    production = replace(key, parent_dm_sha256=digest)
    result = qualify_response_reuse(key, production)
    assert result.status is ReuseStatus.NOT_ESTABLISHED
    assert result.mismatched_fields == ()
    assert result.to_mapping()["reason"] == "PHYSICAL_CONTEXT_NOT_ESTABLISHED"
    raw = production.to_mapping()
    raw.pop("parent_dm_sha256")
    absent = ResponseRunIdentity.from_mapping(raw)
    assert absent.parent_dm_sha256 is None
    assert qualify_response_reuse(key, absent).status is ReuseStatus.NOT_ESTABLISHED


@pytest.mark.parametrize("value", [None, "", "malformed", "f" * 64])
def test_semantic_comparison_ignores_artifact_hashes_but_retains_projector_identity(value):
    from hubbardflow.domain.hash_traceability import compare_traceable_mappings

    left = {"digest": "a" * 64, "n": 3, "occupation_e": 4.2, "identity_digest": "b" * 64}
    right = {**left, "digest": value}
    result = compare_traceable_mappings(left, right)
    assert result.equivalent
    assert result.warnings
    assert not compare_traceable_mappings(left, {**right, "occupation_e": 4.3}).equivalent
    assert not compare_traceable_mappings(left, {**right, "identity_digest": "c" * 64}).equivalent
