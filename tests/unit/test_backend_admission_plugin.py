import json
from pathlib import Path

import pytest

from siestaflow_hubbard.siesta_backend.backend_admission import BackendAdmissionError
from siestaflow_hubbard.siesta_backend.backend_admission_plugin import (
    admit_siesta542_from_campaign_contract,
    admit_siesta542_from_registry_file,
    load_backend_compatibility_registry,
)
from siestaflow_hubbard.domain.backend_compatibility import ScientificProfile
from siestaflow_hubbard.domain.lr_campaign_contract import LinearResponseBareCampaignContract
from siestaflow_hubbard.siesta_backend.backend_identity import sha256_file
from siestaflow_hubbard.siesta_backend.siesta542_bare_profile import (
    Siesta542PotentialShiftHamiltonianProfile,
)


def _write_registry(path: Path, executable: Path, profile: Siesta542PotentialShiftHamiltonianProfile):
    digest = sha256_file(executable)
    path.write_text(json.dumps({
        "schema": "backend_compatibility_v1",
        "records": [{
            "backend": {"backend_id": "siesta", "version": "5.4.2", "executable_sha256": digest},
            "profile": {
                "profile_id": profile.profile_id,
                "version": profile.profile_version,
                "metadata": {"source_revision": profile.source_revision},
            },
            "state": "compatible",
            "reason": "fixture",
        }],
    }), encoding="utf-8")


def test_plugin_loads_matrix_and_returns_admission(tmp_path: Path):
    executable = tmp_path / "siesta"
    executable.write_bytes(b"known backend")
    profile = Siesta542PotentialShiftHamiltonianProfile()
    registry_path = tmp_path / "backend.json"
    _write_registry(registry_path, executable, profile)

    registry = load_backend_compatibility_registry(registry_path)
    assert len(registry.records) == 1
    admission = admit_siesta542_from_registry_file(
        executable_path=executable,
        version_text="Version : 5.4.2",
        registry_path=registry_path,
        profile=profile,
    )
    assert admission.observed.executable_sha256 == sha256_file(executable)


def test_plugin_rejects_missing_registry(tmp_path: Path):
    executable = tmp_path / "siesta"
    executable.write_bytes(b"known backend")
    with pytest.raises(BackendAdmissionError, match="registry path does not exist"):
        admit_siesta542_from_registry_file(
            executable_path=executable,
            version_text="Version : 5.4.2",
            registry_path=tmp_path / "missing.json",
        )


def test_plugin_rejects_malformed_registry(tmp_path: Path):
    registry_path = tmp_path / "backend.json"
    registry_path.write_text('{"schema":"wrong"}', encoding="utf-8")
    with pytest.raises(BackendAdmissionError, match="registry cannot be loaded"):
        load_backend_compatibility_registry(registry_path)


def test_plugin_rejects_unregistered_executable(tmp_path: Path):
    executable = tmp_path / "siesta"
    executable.write_bytes(b"unknown backend")
    registered = tmp_path / "registered"
    registered.write_bytes(b"known backend")
    profile = Siesta542PotentialShiftHamiltonianProfile()
    registry_path = tmp_path / "backend.json"
    _write_registry(registry_path, registered, profile)
    with pytest.raises(BackendAdmissionError, match="admission rejected"):
        admit_siesta542_from_registry_file(
            executable_path=executable,
            version_text="Version : 5.4.2",
            registry_path=registry_path,
            profile=profile,
        )


def test_contract_composition_binds_logical_name_version_text_and_registry(tmp_path: Path):
    executable = tmp_path / "private-siesta"; executable.write_bytes(b"known backend")
    profile = Siesta542PotentialShiftHamiltonianProfile()
    registry_path = tmp_path / "private/backend.json"; registry_path.parent.mkdir()
    _write_registry(registry_path, executable, profile)
    (tmp_path / "private/version.txt").write_text("Version : 5.4.2\n", encoding="utf-8")
    contract = LinearResponseBareCampaignContract(
        campaign_id="fixture",
        scientific_profile=ScientificProfile(profile.profile_id, profile.profile_version),
        compatibility_registry="private/backend.json",
        declared_executable="private-siesta",
        version_text_source="private/version.txt",
    )
    admitted = admit_siesta542_from_campaign_contract(
        campaign_root=tmp_path, contract=contract, executable_path=executable,
    )
    assert admitted.observed.version == "5.4.2"
    bad_contract = LinearResponseBareCampaignContract(
        campaign_id="fixture",
        scientific_profile=ScientificProfile(profile.profile_id, profile.profile_version),
        compatibility_registry="private/backend.json",
        declared_executable="other-siesta",
        version_text_source="private/version.txt",
    )
    with pytest.raises(BackendAdmissionError, match="declared executable name"):
        admit_siesta542_from_campaign_contract(
            campaign_root=tmp_path, contract=bad_contract, executable_path=executable,
        )
