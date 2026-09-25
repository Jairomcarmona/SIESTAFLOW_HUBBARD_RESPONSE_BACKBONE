import pytest

from siestaflow_hubbard.domain.backend_compatibility import (
    BackendCompatibilityError,
    BackendCompatibilityRegistry,
    BackendIdentity,
    CompatibilityRecord,
    CompatibilityState,
    ScientificProfile,
)


def _record(state=CompatibilityState.COMPATIBLE):
    return CompatibilityRecord(
        BackendIdentity("siesta", "5.4.2", "a" * 64),
        ScientificProfile("potential_shift_hamiltonian", "1", {"mix": "hamiltonian"}),
        state,
        "test record",
    )


def test_exact_hashed_identity_resolves_and_unknown_is_fail_closed():
    registry = BackendCompatibilityRegistry().add(_record())
    assert registry.resolve(_record().identity).state is CompatibilityState.COMPATIBLE
    unknown = registry.resolve(BackendIdentity("siesta", "5.4.2", "b" * 64))
    assert unknown.state is CompatibilityState.UNKNOWN
    with pytest.raises(BackendCompatibilityError):
        registry.require_compatible(unknown.identity)


def test_hashless_identity_does_not_match_hashed_entry():
    registry = BackendCompatibilityRegistry().add(_record())
    unknown = registry.resolve(BackendIdentity("siesta", "5.4.2"))
    assert unknown.state is CompatibilityState.UNKNOWN


def test_blocked_entry_is_not_authorized():
    registry = BackendCompatibilityRegistry().add(_record(CompatibilityState.BLOCKED))
    with pytest.raises(BackendCompatibilityError, match="blocked"):
        registry.require_compatible(_record().identity)


def test_registry_is_persistent_and_rejects_duplicates():
    first = BackendCompatibilityRegistry()
    second = first.add(_record())
    assert first.records == ()
    assert len(second.records) == 1
    with pytest.raises(BackendCompatibilityError, match="duplicate"):
        second.add(_record())


def test_invalid_identity_and_metadata_are_rejected():
    with pytest.raises(BackendCompatibilityError):
        BackendIdentity("siesta", "5.4.2", "not-a-hash")
    with pytest.raises(TypeError):
        ScientificProfile("profile", "1", {"bad": object()})


def test_serialization_is_deterministic_and_hashable():
    record = _record()
    left = BackendCompatibilityRegistry().add(record)
    right = BackendCompatibilityRegistry((record,))
    assert left.to_json() == right.to_json()
    assert left.sha256() == right.sha256()
    assert '"schema":"backend_compatibility_v1"' in left.to_json()
    assert BackendCompatibilityRegistry.from_json(left.to_json()).to_json() == left.to_json()


def test_serialization_orders_hashless_and_hashed_entries():
    profile = ScientificProfile("profile", "1")
    records = (
        CompatibilityRecord(BackendIdentity("backend", "1"), profile, "compatible"),
        CompatibilityRecord(BackendIdentity("backend", "1", "c" * 64), profile, "blocked", "revoked"),
    )
    payload = BackendCompatibilityRegistry(records).to_json()
    assert payload.index('"executable_sha256":null') < payload.index('"executable_sha256":"')


def test_profile_mismatch_is_unknown():
    registry = BackendCompatibilityRegistry().add(_record())
    result = registry.resolve(_record().identity, ("other_profile", "1"))
    assert result.state is CompatibilityState.UNKNOWN


def test_unknown_schema_and_malformed_records_fail_closed():
    with pytest.raises(BackendCompatibilityError, match="schema"):
        BackendCompatibilityRegistry.from_dict({"schema": "other", "records": []})
    with pytest.raises(BackendCompatibilityError, match="malformed"):
        BackendCompatibilityRegistry.from_dict({"schema": "backend_compatibility_v1", "records": [{}]})
