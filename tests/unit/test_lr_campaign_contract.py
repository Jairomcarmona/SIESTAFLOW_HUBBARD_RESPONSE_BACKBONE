import json

import pytest

from siestaflow_hubbard.domain.backend_compatibility import (
    BackendCompatibilityRegistry,
    BackendIdentity,
    CompatibilityRecord,
    CompatibilityState,
    ScientificProfile,
)
from siestaflow_hubbard.domain.lr_campaign_contract import (
    LinearResponseBareCampaignContract,
    LinearResponseContractError,
)


PROFILE = ScientificProfile("siesta-5.4.2-potential-shift-hamiltonian", "v1")


def contract(**overrides):
    data = {
        "schema": "lr_bare_campaign_contract_v1",
        "campaign_id": "mnO-local-control",
        "backend_id": "siesta",
        "scientific_profile": {"profile_id": PROFILE.profile_id, "version": PROFILE.version},
        "compatibility_registry": "private/backend_compatibility.json",
        "declared_executable": "bin/siesta",
        "version_text_source": "private/siesta-version.txt",
    }
    data.update(overrides)
    return data


def test_contract_round_trip_and_safe_relative_paths(tmp_path):
    item = LinearResponseBareCampaignContract.from_dict(contract())
    assert item.to_dict()["schema"] == "lr_bare_campaign_contract_v1"
    assert item.registry_path(tmp_path) == tmp_path / "private/backend_compatibility.json"
    assert item.version_text_path(tmp_path) == tmp_path / "private/siesta-version.txt"
    assert LinearResponseBareCampaignContract.from_json(json.dumps(item.to_dict())) == item


@pytest.mark.parametrize("field,value", [
    ("compatibility_registry", "/etc/backend.json"),
    ("compatibility_registry", "../backend.json"),
    ("version_text_source", "../version.txt"),
    ("declared_executable", "/usr/bin/siesta"),
    ("declared_executable", "../siesta"),
])
def test_contract_rejects_nonportable_artifact_references(field, value):
    with pytest.raises(LinearResponseContractError):
        LinearResponseBareCampaignContract.from_dict(contract(**{field: value}))


@pytest.mark.parametrize("payload", [
    {},
    {"schema": "wrong"},
    {**contract(), "scientific_profile": None},
    {**contract(), "version_text_source": ""},
])
def test_contract_is_fail_closed_for_malformed_declarations(payload):
    with pytest.raises((LinearResponseContractError, KeyError)):
        LinearResponseBareCampaignContract.from_dict(payload)


def registry_for(identity, profile=PROFILE, state=CompatibilityState.COMPATIBLE):
    return BackendCompatibilityRegistry((CompatibilityRecord(
        identity=identity, profile=profile, state=state, reason="test record"
    ),))


def test_admit_requires_exact_registered_backend_and_profile(tmp_path):
    identity = BackendIdentity("siesta", "5.4.2", "a" * 64)
    root = tmp_path
    (root / "private").mkdir()
    (root / "private/backend_compatibility.json").write_text(
        registry_for(identity).to_json(), encoding="utf-8"
    )
    (root / "private/siesta-version.txt").write_text("Version : 5.4.2\n", encoding="utf-8")
    admitted = LinearResponseBareCampaignContract.from_dict(contract()).admit(root, identity)
    assert admitted.state is CompatibilityState.COMPATIBLE


def test_admit_rejects_unknown_hash_and_blocked_record(tmp_path):
    known = BackendIdentity("siesta", "5.4.2", "a" * 64)
    unknown = BackendIdentity("siesta", "5.4.2", "b" * 64)
    root = tmp_path
    (root / "private").mkdir()
    (root / "private/backend_compatibility.json").write_text(
        registry_for(known, state=CompatibilityState.BLOCKED).to_json(), encoding="utf-8"
    )
    (root / "private/siesta-version.txt").write_text("Version : 5.4.2\n", encoding="utf-8")
    campaign = LinearResponseBareCampaignContract.from_dict(contract())
    with pytest.raises(LinearResponseContractError):
        campaign.admit(root, unknown)
    with pytest.raises(LinearResponseContractError):
        campaign.admit(root, known)


def test_registry_resolution_is_relative_even_when_artifact_is_not_materialized(tmp_path):
    item = LinearResponseBareCampaignContract.from_dict(contract())
    assert item.registry_path(tmp_path).parent == tmp_path / "private"
