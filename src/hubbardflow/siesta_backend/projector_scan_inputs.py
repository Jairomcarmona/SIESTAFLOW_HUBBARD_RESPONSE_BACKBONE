"""Strict SIESTA FDF validation for one-parameter projector probe inputs."""

from __future__ import annotations

import math
import re

from hubbardflow.domain.projector_plateau import ProjectorParameterKind


class ProjectorScanInputError(ValueError):
    """FDF candidates do not satisfy the single-projector-line contract."""


_METHOD = re.compile(r"^\s*DFTU\.ProjectorGenerationMethod\s+(\S+)\s*(?:#.*)?$", re.IGNORECASE)
_CUTOFF = re.compile(r"^\s*DFTU\.CutoffNorm\s+\S+\s*(?:#.*)?$", re.IGNORECASE)
_FLOAT = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[EeDd][+-]?\d+)?$")


def _clean(line: str) -> str:
    return line.split("#", 1)[0].strip()


def _require_method_two(text: str) -> list[str]:
    if not isinstance(text, str) or not text:
        raise ProjectorScanInputError("FDF text must be a non-empty string")
    lines = text.splitlines()
    methods = [match.group(1) for line in lines if (match := _METHOD.match(line))]
    if methods != ["2"]:
        raise ProjectorScanInputError("FDF must declare DFTU.ProjectorGenerationMethod 2 exactly once")
    return lines


def _explicit_rc_line_indices(lines: list[str]) -> set[int]:
    """Return every effective projector-block row declaring an rc value.

    SIESTA 5.4.2 uses the legacy LDAU.Proj block when present, otherwise
    DFTU.Proj. The supported one-shell grammar follows the checked-in grammar
    contract; unsupported structures fail closed.
    """
    block_name = next(
        (
            name
            for name in ("LDAU.Proj", "DFTU.Proj")
            if any(
                re.fullmatch(rf"%block\s+{re.escape(name)}", _clean(line), re.IGNORECASE) for line in lines
            )
        ),
        None,
    )
    if block_name is None:
        return set()
    start = next(
        index
        for index, line in enumerate(lines)
        if re.fullmatch(rf"%block\s+{re.escape(block_name)}", _clean(line), re.IGNORECASE)
    )
    end = next(
        (
            index
            for index in range(start + 1, len(lines))
            if re.fullmatch(rf"%endblock\s+{re.escape(block_name)}", _clean(lines[index]), re.IGNORECASE)
        ),
        None,
    )
    if end is None:
        raise ProjectorScanInputError(f"unterminated %{block_name} projector block")
    indices: set[int] = set()
    index = start + 1
    while index < end:
        header = _clean(lines[index]).split()
        if len(header) != 2 or not header[1].isdigit() or int(header[1]) < 1:
            raise ProjectorScanInputError("unsupported projector block species header")
        shell_count = int(header[1])
        index += 1
        for _ in range(shell_count):
            if index + 2 >= end:
                raise ProjectorScanInputError("incomplete projector shell in effective FDF block")
            shell = _clean(lines[index]).split()
            uj = _clean(lines[index + 1]).split()
            rc_width = _clean(lines[index + 2]).split()
            if len(shell) < 2 or len(uj) != 2 or len(rc_width) != 2:
                raise ProjectorScanInputError("unsupported projector shell row structure")
            try:
                rc = float(rc_width[0].replace("D", "E").replace("d", "e"))
            except ValueError as exc:
                raise ProjectorScanInputError("projector rc field must be numeric") from exc
            if not math.isfinite(rc):
                raise ProjectorScanInputError("projector rc field must be finite")
            # Presence of an rc row is explicit policy even when the chosen
            # value is 0.0. A CutoffNorm scan cannot reinterpret that row.
            indices.add(index + 2)
            index += 3
            # A numeric one-field row is the optional contraction lambda.
            if index < end and len(_clean(lines[index]).split()) == 1:
                if not _FLOAT.fullmatch(_clean(lines[index]).split()[0]):
                    raise ProjectorScanInputError("unsupported optional projector lambda row")
                index += 1
    return indices


def validate_projector_only_fdf_change(
    baseline_fdf_text: str,
    candidate_fdf_text: str,
    kind: ProjectorParameterKind,
) -> None:
    """Require two Method-2 FDFs to differ only in the scanned projector field."""
    if not isinstance(kind, ProjectorParameterKind):
        raise ProjectorScanInputError("kind must be a ProjectorParameterKind")
    baseline = _require_method_two(baseline_fdf_text)
    candidate = _require_method_two(candidate_fdf_text)
    if len(baseline) != len(candidate):
        raise ProjectorScanInputError("candidate FDF must preserve line count")
    differences = [
        index for index, (left, right) in enumerate(zip(baseline, candidate, strict=True)) if left != right
    ]
    if len(differences) != 1:
        raise ProjectorScanInputError("candidate FDF must differ by exactly one projector line")
    changed_index = differences[0]
    if kind is ProjectorParameterKind.CUTOFF_NORM:
        if _explicit_rc_line_indices(baseline) or _explicit_rc_line_indices(candidate):
            raise ProjectorScanInputError("CutoffNorm scans reject explicit rc projector records")
        if _CUTOFF.match(baseline[changed_index]) is None or _CUTOFF.match(candidate[changed_index]) is None:
            raise ProjectorScanInputError("the sole changed FDF line must be DFTU.CutoffNorm")
        return
    if changed_index not in _explicit_rc_line_indices(
        baseline
    ) or changed_index not in _explicit_rc_line_indices(candidate):
        raise ProjectorScanInputError("the sole changed FDF line must be an explicit projector rc row")
