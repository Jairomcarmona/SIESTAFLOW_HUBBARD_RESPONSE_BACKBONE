"""Protected admission of an operationally released Hubbard U artifact."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Any

from .u_release_gate import UReleaseError, canonical_hash, verify_u_release
from .u_certification_node import UCertificationNodeError, verify_certificate_source_chain


class DownstreamUAdmissionError(ValueError):
    pass


_CONSTRUCTOR_KEY = object()


class ValidatedURelease:
    """Opaque capability returned only by :func:`load_verified_u_release`."""

    __slots__ = ("_release", "_certificate_sha256", "_key")

    def __init__(self, release: dict[str, Any], certificate_sha256: str, key: object):
        if key is not _CONSTRUCTOR_KEY:
            raise TypeError("ValidatedURelease values must be obtained through the verifier")
        self._release = dict(release)
        self._certificate_sha256 = certificate_sha256
        self._key = key

    @property
    def nominal_u_by_site_eV(self) -> tuple[str, ...]:
        return tuple(str(value) for value in self._release["nominal_u_by_site_eV"])

    @property
    def release_sha256(self) -> str:
        return str(self._release["release_sha256"])

    @property
    def certificate_sha256(self) -> str:
        return self._certificate_sha256


def _file_digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def load_verified_u_release(
    release_path: str | Path,
    certificate_path: str | Path,
    *,
    require_preregistered: bool = False,
    registered_release_sha256: str | None = None,
    execution_mode: str,
) -> ValidatedURelease:
    """Load the only accepted downstream U input and bind it to its certificate."""
    # Paths, rather than a free numeric argument, are the API's required input.
    release_file, certificate_file = Path(release_path).resolve(strict=True), Path(certificate_path).resolve(strict=True)
    if execution_mode != "PRODUCTION":
        raise DownstreamUAdmissionError("ValidatedURelease admission requires explicit PRODUCTION mode")
    try:
        release = json.loads(release_file.read_text(encoding="utf-8"))
        certificate = json.loads(certificate_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DownstreamUAdmissionError("release or certificate artifact is unreadable") from exc
    try:
        verify_u_release(release)
    except UReleaseError as exc:
        raise DownstreamUAdmissionError(str(exc)) from exc
    certificate_digest = canonical_hash(certificate)
    if release.get("u_certificate_sha256") != certificate_digest:
        raise DownstreamUAdmissionError("release source certificate hash mismatch")
    if certificate.get("schema_version") != "u_certificate.v1" or certificate.get("certificate_status") not in {
        "CERTIFIED", "CERTIFIED_WITH_FALLBACK",
    }:
        raise DownstreamUAdmissionError("source certificate is not valid and certified")
    try:
        release_root = release_file.parent.resolve(strict=True)
        certificate_file.relative_to(release_root)
        verify_certificate_source_chain(certificate, release_root)
    except (ValueError, OSError, UCertificationNodeError) as exc:
        raise DownstreamUAdmissionError(f"SOURCE_EVIDENCE_CHANGED_AFTER_CERTIFICATION: {exc}") from exc
    if (release.get("campaign_uuid") != certificate.get("campaign_uuid")
            or release.get("analysis_policy_sha256") != certificate.get("analysis_policy_sha256")
            or release.get("nominal_u_by_site_eV") != certificate.get("nominal_u_by_site_eV")
            or release.get("deterministic_interval_by_site") != certificate.get("u_interval_by_site")):
        raise DownstreamUAdmissionError("release and certificate contents do not match")
    if require_preregistered and registered_release_sha256 != release.get("release_sha256"):
        raise DownstreamUAdmissionError("release was not preregistered under the required policy")
    return ValidatedURelease(release, certificate_digest, _CONSTRUCTOR_KEY)
