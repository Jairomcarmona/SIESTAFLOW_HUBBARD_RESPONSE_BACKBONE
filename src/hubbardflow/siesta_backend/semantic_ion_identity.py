"""Narrow SIESTA .ion label normalization; every physical byte is retained."""

from __future__ import annotations

import re


class IonIdentityError(ValueError):
    """An ion file does not have the two audited species label fields."""


def relabel_ion_bytes(data: bytes, original_label: str, new_label: str) -> bytes:
    """Replace only the basis_specs header and the scalar before '# Label'.

    Fixed field widths and every other byte, including radial data, are preserved.
    Unknown layouts fail closed instead of applying a global text replacement.
    """
    try:
        old = original_label.encode("ascii")
        new = new_label.encode("ascii")
    except UnicodeEncodeError as exc:
        raise IonIdentityError("ion species labels must be ASCII") from exc
    if not re.fullmatch(rb"[A-Za-z][A-Za-z0-9_]*", old) or not re.fullmatch(rb"[A-Za-z][A-Za-z0-9_]*", new):
        raise IonIdentityError("invalid ion species label")
    scope = re.search(rb"<basis_specs>([\s\S]*?)</basis_specs>", data)
    if scope is None:
        raise IonIdentityError("ion basis_specs missing")
    header = re.compile(rb"(?m)^([ \t]*)" + re.escape(old) + rb"([ \t]+)(?=Z=)")
    label = re.compile(rb"(?m)^([ \t]*)" + re.escape(old) + rb"([ \t]+)(?=# Label\s*$)")

    def replace(match: re.Match[bytes]) -> bytes:
        width = len(old) + len(match[2])
        if len(new) >= width:
            raise IonIdentityError("new label exceeds audited ion field width")
        return match[1] + new + b" " * (width - len(new))

    body, headers = header.subn(replace, scope[1])
    if headers != 1:
        raise IonIdentityError("ion must have exactly one matching basis_specs species header")
    result = data[: scope.start(1)] + body + data[scope.end(1) :]
    result, labels = label.subn(replace, result)
    if labels != 1:
        raise IonIdentityError("ion must have exactly one matching # Label scalar")
    return result


def canonical_ion_bytes(data: bytes, label: str) -> bytes:
    """Normalize the two label fields to a fixed sentinel for exact equality."""
    return relabel_ion_bytes(data, label, "X")
