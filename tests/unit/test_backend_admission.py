from pathlib import Path

import pytest

from siestaflow_hubbard.domain.backend_compatibility import (
    BackendCompatibilityRegistry,
    BackendIdentity,
    CompatibilityRecord,
    CompatibilityState,
    ScientificProfile,
)
from siestaflow_hubbard.siesta_backend.backend_admission import (
    BackendAdmissionError,
    admit_siesta542_potential_shift_hamiltonian,
)
from siestaflow_hubbard.siesta_backend.backend_identity import sha256_file
from siestaflow_hubbard.siesta_backend.siesta542_bare_profile import (
    Siesta542PotentialShiftHamiltonianProfile,
)


def _registry(executable: Path, profile: Siesta542PotentialShiftHamiltonianProfile):
    identity = BackendIdentity("siesta", "5.4.2", sha256_file(executable))
    scientific = ScientificProfile(profile.profile_id, profile.profile_version, {
        "source_revision": profile.source_revision,
    })
    return BackendCompatibilityRegistry((CompatibilityRecord(
        identity, scientific, CompatibilityState.COMPATIBLE, "fixture backend",
    ),))


def test_admits_only_exact_registered_executable(tmp_path: Path):
    executable = tmp_path / "siesta"; executable.write_bytes(b"binary-a")
    profile = Siesta542PotentialShiftHamiltonianProfile()
    admission = admit_siesta542_potential_shift_hamiltonian(
        executable, "Version : 5.4.2", _registry(executable, profile), profile,
    )
    admission.require_declared_executable(executable)


def test_unknown_or_changed_executable_is_rejected(tmp_path: Path):
    executable = tmp_path / "siesta"; executable.write_bytes(b"binary-a")
    profile = Siesta542PotentialShiftHamiltonianProfile()
    registry = _registry(executable, profile)
    executable.write_bytes(b"binary-b")
    with pytest.raises(BackendAdmissionError, match="admission rejected"):
        admit_siesta542_potential_shift_hamiltonian(
            executable, "Version : 5.4.2", registry, profile,
        )
