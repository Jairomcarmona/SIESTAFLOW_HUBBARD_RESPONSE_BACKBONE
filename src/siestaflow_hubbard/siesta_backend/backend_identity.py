"""Portable identity for an explicitly selected SIESTA executable.

This module is deliberately observation-only.  It never searches ``PATH``,
loads a module, invokes an executable, or knows about a scheduler.  Callers
must provide both the executable path and text already obtained from their
backend's version/provenance channel.  A backend is accepted only when its
file is hashable and exactly one supported version can be parsed.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import re
from typing import Union


PathLike = Union[str, bytes, Path]


class BackendIdentityError(ValueError):
    """Raised when backend identity cannot be established unambiguously."""


@dataclass(frozen=True)
class BackendIdentity:
    """Stable identity of one explicitly supplied backend executable."""

    backend: str
    version: str
    executable_path: str
    executable_sha256: str


# SIESTA's normal banner is ``Version         : 5.4.2``.  The second form is
# useful for captured wrappers, but intentionally excludes unrelated lines
# such as ``Compiler version`` and ``PSML file version``.
_VERSION_PATTERNS = (
    re.compile(r"(?im)^\s*Version\s*:\s*(\d+\.\d+(?:\.\d+)?)\s*$"),
    re.compile(r"(?im)^\s*SIESTA\s+version\s*:\s*(\d+\.\d+(?:\.\d+)?)\s*$"),
    re.compile(r"(?im)^\s*SIESTA\s+(\d+\.\d+(?:\.\d+)?)\s*$"),
)


def sha256_file(path: PathLike, *, chunk_size: int = 1024 * 1024) -> str:
    """Hash one explicit regular file in bounded memory.

    No default path or executable lookup is performed.  Missing paths,
    directories, unreadable paths, and invalid chunk sizes fail closed.
    """

    if chunk_size <= 0:
        raise BackendIdentityError("chunk_size must be positive")
    candidate = Path(path)
    try:
        resolved = candidate.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise BackendIdentityError("backend executable path does not exist") from exc
    if not resolved.is_file():
        raise BackendIdentityError("backend executable path is not a regular file")

    digest = sha256()
    try:
        with resolved.open("rb") as stream:
            while True:
                block = stream.read(chunk_size)
                if not block:
                    break
                digest.update(block)
    except OSError as exc:
        raise BackendIdentityError("backend executable cannot be read") from exc
    return digest.hexdigest()


def parse_siesta_version(version_text: str) -> str:
    """Extract exactly one SIESTA version from supplied text.

    Generic ``Compiler version`` and ``PSML file version`` lines are ignored.
    Multiple different SIESTA versions are rejected instead of selecting one
    heuristically.  The text is supplied by the caller; this function never
    launches SIESTA.
    """

    if not isinstance(version_text, str) or not version_text.strip():
        raise BackendIdentityError("version text is empty or not text")
    matches = []
    for pattern in _VERSION_PATTERNS:
        matches.extend(pattern.findall(version_text))
    versions = set(matches)
    if not versions:
        raise BackendIdentityError("no unambiguous SIESTA version found")
    if len(versions) != 1:
        raise BackendIdentityError("conflicting SIESTA versions found")
    return next(iter(versions))


def identify_backend(
    executable_path: PathLike,
    version_text: str,
    *,
    backend: str = "siesta",
) -> BackendIdentity:
    """Build a portable identity from explicit path and supplied text."""

    if not isinstance(backend, str) or not backend.strip():
        raise BackendIdentityError("backend name is empty")
    path = Path(executable_path)
    try:
        resolved = path.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise BackendIdentityError("backend executable path does not exist") from exc
    digest = sha256_file(resolved)
    return BackendIdentity(
        backend=backend.strip(),
        version=parse_siesta_version(version_text),
        executable_path=str(resolved),
        executable_sha256=digest,
    )


__all__ = [
    "BackendIdentity",
    "BackendIdentityError",
    "identify_backend",
    "parse_siesta_version",
    "sha256_file",
]
