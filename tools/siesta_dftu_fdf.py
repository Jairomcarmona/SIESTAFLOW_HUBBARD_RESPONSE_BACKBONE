"""Effective SIESTA 5.4.2 Method-2 DFT+U settings parsed from an FDF."""

from __future__ import annotations

import math
import re
from typing import Any

from psml_selection import parse_fdf_species


_AUTO_RC_THRESHOLD = 1.0e-4  # Src/dftu_specs.f: fermicutoff eps
_DEFAULT_CUTOFF_NORM = 0.90
_DEFAULT_METHOD = 2
_DEFAULT_WIDTH = 0.05


def _clean_line(line: str) -> str:
    return line.split("#", 1)[0].strip()


def _parse_scalar(text: str, key: str, default: str | None = None) -> str | None:
    values = []
    for line in text.splitlines():
        fields = _clean_line(line).split()
        if fields and fields[0].casefold() == key.casefold():
            if len(fields) != 2:
                raise ValueError(f"{key} must have exactly one value")
            values.append(fields[1].strip("\"'"))
    if len(values) > 1:
        raise ValueError(f"multiple declarations of {key} are ambiguous")
    return values[0] if values else default


def _effective_scalar(text: str, legacy_key: str, dftu_key: str, default: str) -> str:
    legacy = _parse_scalar(text, legacy_key)
    modern = _parse_scalar(text, dftu_key)
    return modern if modern is not None else legacy if legacy is not None else default


def _float(value: str, context: str) -> float:
    try:
        result = float(value.replace("D", "E").replace("d", "e"))
    except ValueError as exc:
        raise ValueError(f"{context} must be numeric") from exc
    if not math.isfinite(result):
        raise ValueError(f"{context} must be finite")
    return result


def _fdf_blocks(text: str, name: str) -> list[list[str]]:
    blocks: list[list[str]] = []
    lines = text.splitlines()
    index = 0
    while index < len(lines):
        clean = _clean_line(lines[index])
        if not re.fullmatch(rf"%block\s+{re.escape(name)}", clean, re.I):
            index += 1
            continue
        body: list[str] = []
        index += 1
        while index < len(lines):
            clean = _clean_line(lines[index])
            if re.fullmatch(rf"%endblock\s+{re.escape(name)}", clean, re.I):
                blocks.append(body)
                break
            if re.match(r"%endblock\b", clean, re.I):
                raise ValueError(f"%block {name} has a mismatched %endblock")
            body.append(lines[index])
            index += 1
        else:
            raise ValueError(f"unterminated %block {name}")
        index += 1
    return blocks


def _selected_projector_block(text: str) -> tuple[str, list[str]]:
    # SIESTA 5.4.2 asks for LDAU.proj first and only reads DFTU.proj if absent.
    for name in ("LDAU.proj", "DFTU.proj"):
        blocks = _fdf_blocks(text, name)
        if blocks:
            if len(blocks) != 1:
                raise ValueError(f"multiple %{name} blocks are ambiguous")
            return name, blocks[0]
    raise ValueError("missing both LDAU.proj and DFTU.proj blocks")


def _integer(token: str, context: str) -> int:
    try:
        value = int(token)
    except ValueError as exc:
        raise ValueError(f"{context} must be an integer") from exc
    return value


def _shell_row(tokens: list[str], source: str, label: str) -> tuple[int, int, tuple[float, float] | None]:
    e_positions = [index for index, token in enumerate(tokens) if token.casefold() == "e"]
    if len(e_positions) > 1:
        raise ValueError(f"{source}: multiple E soft-confinement clauses for {label}")
    soft: tuple[float, float] | None = None
    base = tokens
    if e_positions:
        position = e_positions[0]
        if position != 2 or len(tokens) != 5:
            raise ValueError(f"{source}: expected shell row '<n> <l> E <vcte> <rinn>' for {label}")
        soft = (_float(tokens[3], f"{source}: E vcte for {label}"),
                _float(tokens[4], f"{source}: E rinn for {label}"))
        base = tokens[:2]

    if len(base) == 1:
        raise ValueError(f"{source}: implicit-l-only shell for {label} needs PSML-derived n and is not auditable")
    if len(base) != 2:
        raise ValueError(f"{source}: malformed shell row for {label}")
    n_token = base[0]
    match = re.fullmatch(r"n\s*=\s*(\d+)", n_token, re.I)
    n_value = _integer(match.group(1) if match else n_token, f"{source}: principal quantum number for {label}")
    l_value = _integer(base[1], f"{source}: angular momentum for {label}")
    if n_value <= 0 or l_value < 0 or n_value <= l_value:
        raise ValueError(f"{source}: invalid n,l shell ({n_value},{l_value}) for {label}")
    return n_value, l_value, soft


def projector_specs_from_text(text: str, source: str = "FDF") -> dict[str, dict[str, Any]]:
    """Parse the one-shell-per-label subset used by the projector identity audit.

    The legacy/modern key precedence, block precedence, default method, default
    norm, automatic-rc threshold, width default, optional E clause, and lambda
    default match the inspected SIESTA 5.4.2 source. Unsupported shell forms
    fail closed instead of being interpreted approximately.
    """
    known_species = parse_fdf_species(text, source)
    method_token = _effective_scalar(
        text, "LDAU.ProjectorGenerationMethod", "DFTU.ProjectorGenerationMethod", str(_DEFAULT_METHOD)
    )
    try:
        method_value = int(method_token)
    except ValueError as exc:
        raise ValueError(f"{source}: effective ProjectorGenerationMethod must be an integer") from exc
    if not math.isfinite(method_value) or method_value != 2:
        raise ValueError(f"{source}: effective ProjectorGenerationMethod must be 2 (got {method_token})")

    norm_token = _effective_scalar(text, "LDAU.CutoffNorm", "DFTU.CutoffNorm", str(_DEFAULT_CUTOFF_NORM))
    cutoff_norm = _float(norm_token, f"{source}: effective CutoffNorm")

    block_name, block_rows = _selected_projector_block(text)
    rows = [tokens for raw in block_rows if (tokens := _clean_line(raw).split())]
    specs: dict[str, dict[str, Any]] = {}
    index = 0
    while index < len(rows):
        header = rows[index]
        if len(header) != 2 or header[0] not in known_species:
            raise ValueError(f"{source}: invalid {block_name} species row {header}")
        label = header[0]
        count = _integer(header[1], f"{source}: {block_name} projector count for {label}")
        if count != 1:
            raise ValueError(f"{source}: {label} declares {count} projectors; multi-shell audit is not supported")
        if label in specs:
            raise ValueError(f"{source}: duplicate {block_name} target label {label}")
        if index + 3 >= len(rows):
            raise ValueError(f"{source}: incomplete {block_name} shell for {label}")

        n_value, l_value, soft = _shell_row(rows[index + 1], source, label)
        uj_row, cutoff_row = rows[index + 2], rows[index + 3]
        if len(uj_row) != 2 or len(cutoff_row) != 2:
            raise ValueError(f"{source}: malformed U/J or rc/width row for {label}")
        uj = (_float(uj_row[0], f"{source}: U for {label}"),
              _float(uj_row[1], f"{source}: J for {label}"))
        rc, raw_width = (_float(cutoff_row[0], f"{source}: rc for {label}"),
                         _float(cutoff_row[1], f"{source}: width for {label}"))
        if raw_width < _AUTO_RC_THRESHOLD:
            effective_width = _DEFAULT_WIDTH
        else:
            effective_width = raw_width
        cutoff_mode = "cutoff_norm" if rc < _AUTO_RC_THRESHOLD else "explicit_rc"
        if cutoff_mode == "cutoff_norm" and not 0.0 < cutoff_norm <= 1.0:
            raise ValueError(f"{source}: effective CutoffNorm must be in (0,1] when rc is automatic")

        next_index = index + 4
        lambda_effective = 1.0
        if next_index < len(rows):
            next_row = rows[next_index]
            is_species_header = (len(next_row) == 2 and next_row[0] in known_species
                                 and next_row[1].lstrip("+-").isdigit())
            if not is_species_header:
                if len(next_row) != 1:
                    raise ValueError(f"{source}: malformed optional lambda row for {label}")
                lambda_effective = _float(next_row[0], f"{source}: lambda for {label}")
                next_index += 1

        if cutoff_mode == "cutoff_norm":
            cutoff_policy = (cutoff_mode, rc, effective_width, cutoff_norm)
        else:
            cutoff_policy = (cutoff_mode, rc, effective_width, None)
        structure = (count, n_value, l_value, *cutoff_policy, lambda_effective, soft)
        specs[label] = {
            "structure": structure,
            "n": n_value,
            "l": l_value,
            "uj": uj,
            "lambda": lambda_effective,
            "rc_bohr": rc,
            "omega_bohr": effective_width,
            "cutoff_mode": cutoff_mode,
            "cutoff_norm": cutoff_norm if cutoff_mode == "cutoff_norm" else None,
            "soft_confinement": soft,
            "effective_block": block_name,
        }
        index = next_index

    if not specs:
        raise ValueError(f"{source}: selected {block_name} block has no projector targets")
    return specs
