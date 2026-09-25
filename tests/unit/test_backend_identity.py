from hashlib import sha256

import pytest

from siestaflow_hubbard.siesta_backend.backend_identity import (
    BackendIdentityError,
    identify_backend,
    parse_siesta_version,
    sha256_file,
)


def test_hashes_explicit_file_in_bounded_api(tmp_path):
    executable = tmp_path / "siesta"
    payload = b"backend bytes\x00"
    executable.write_bytes(payload)

    assert sha256_file(executable) == sha256(payload).hexdigest()


def test_identity_uses_supplied_text_and_normalizes_path(tmp_path):
    executable = tmp_path / "siesta"
    executable.write_bytes(b"known backend")

    identity = identify_backend(executable, "Version         : 5.4.2\nCompiler version: GNU-13.3.0")

    assert identity.backend == "siesta"
    assert identity.version == "5.4.2"
    assert identity.executable_path == str(executable.resolve())
    assert identity.executable_sha256 == sha256(b"known backend").hexdigest()


def test_parser_ignores_unrelated_version_lines():
    text = "PSML file version: 1.1\nCompiler version: GNU-13.3.0\nSIESTA version: 5.4.2"
    assert parse_siesta_version(text) == "5.4.2"


def test_missing_path_fails_closed(tmp_path):
    with pytest.raises(BackendIdentityError, match="does not exist"):
        sha256_file(tmp_path / "missing")


def test_directory_fails_closed(tmp_path):
    with pytest.raises(BackendIdentityError, match="regular file"):
        sha256_file(tmp_path)


@pytest.mark.parametrize("text", ["", "Compiler version: GNU-13.3.0", "SIESTA output without a banner"])
def test_missing_version_fails_closed(text):
    with pytest.raises(BackendIdentityError, match="version"):
        parse_siesta_version(text)


def test_conflicting_versions_fail_closed():
    with pytest.raises(BackendIdentityError, match="conflicting"):
        parse_siesta_version("Version: 5.4.2\nSIESTA version: 5.4.3")


def test_duplicate_same_version_is_not_ambiguous():
    assert parse_siesta_version("Version: 5.4.2\nSIESTA version: 5.4.2") == "5.4.2"


def test_empty_backend_name_fails_closed(tmp_path):
    executable = tmp_path / "siesta"
    executable.write_bytes(b"x")
    with pytest.raises(BackendIdentityError, match="backend name"):
        identify_backend(executable, "Version: 5.4.2", backend=" ")
