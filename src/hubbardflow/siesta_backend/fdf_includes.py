"""Read-only FDF include expansion shared by SIESTA input boundaries.

Expansion preserves the historical ordering and normalized effective bytes so
moving this boundary does not change materialized inputs or their identities.
"""

from __future__ import annotations

import re
from pathlib import Path


class FdfIncludeError(ValueError):
    """An include graph is cyclic or contains an unsupported directive."""


def resolve_fdf_includes(source: Path) -> tuple[str, list[Path]]:
    """Inline nested includes at their original location, rejecting cycles.

    Filesystem and decoding errors retain their original types; callers translate
    them at their own boundary. Repeated include occurrences are expanded each
    time, while the returned dependency inventory keeps first-occurrence order.
    """
    included: list[Path] = []
    stack: list[Path] = []
    include_re = re.compile(r"^\s*(?:%include|#include)\s+[\"']?([^\"'\s]+)", re.IGNORECASE)

    def expand(path: Path) -> str:
        resolved = path.resolve(strict=True)
        if resolved in stack:
            raise FdfIncludeError(f"FDF include cycle detected at {resolved}")
        if not resolved.is_file():
            raise FdfIncludeError(f"FDF include is not a file: {resolved}")
        stack.append(resolved)
        output: list[str] = []
        for line in resolved.read_text(encoding="utf-8").splitlines():
            match = include_re.match(line)
            if match:
                child = (resolved.parent / match.group(1)).resolve(strict=True)
                included.append(child)
                output.append(expand(child))
            else:
                output.append(line)
        stack.pop()
        return "\n".join(output) + "\n"

    text = expand(source)
    if re.search(r"^\s*(?:%include|#include)\b", text, re.IGNORECASE | re.MULTILINE):
        raise FdfIncludeError("unsupported or unresolved FDF include directive")
    return text, list(dict.fromkeys(included))
