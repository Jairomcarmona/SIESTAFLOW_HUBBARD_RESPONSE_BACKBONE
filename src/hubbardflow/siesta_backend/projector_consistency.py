"""Compare the effective Hubbard projector inputs of campaign FDF files.

This backend check protects an LR response from silently using a different
projector than its reference. It compares declared FDF settings, with the
effective CutoffNorm used for automatic radii; hashes never enter the result.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum


class ProjectorConsistencyError(ValueError):
    """The FDF projector definition cannot be parsed unambiguously."""


class ProjectorComparisonStatus(str, Enum):
    MATCH = "MATCH"
    MISMATCH = "MISMATCH"


class ProjectorDifferenceReason(str, Enum):
    METHOD_MISMATCH = "PROJECTOR_METHOD_MISMATCH"
    RECORDS_MISMATCH = "PROJECTOR_RECORDS_MISMATCH"
    RC_MISMATCH = "PROJECTOR_RC_MISMATCH"
    OMEGA_MISMATCH = "PROJECTOR_OMEGA_MISMATCH"
    CUTOFF_NORM_MISMATCH = "PROJECTOR_CUTOFF_NORM_MISMATCH"
    GENERATED_RC_MISMATCH = "PROJECTOR_GENERATED_RC_MISMATCH"
    GENERATED_RC_UNAVAILABLE = "PROJECTOR_GENERATED_RC_UNAVAILABLE"


@dataclass(frozen=True)
class ProjectorDifference:
    """One declared or effective projector field that differs."""

    reason: ProjectorDifferenceReason
    site_label: str | None
    n: int | None
    l: int | None
    reference_value: str
    response_value: str

    def to_mapping(self) -> dict[str, object]:
        return {
            "reason": self.reason.value,
            "site_label": self.site_label,
            "n": self.n,
            "l": self.l,
            "reference_value": self.reference_value,
            "response_value": self.response_value,
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> ProjectorDifference:
        label = value.get("site_label")
        n_value = value.get("n")
        l_value = value.get("l")
        reference_value = value.get("reference_value")
        response_value = value.get("response_value")
        if label is not None and not isinstance(label, str):
            raise ProjectorConsistencyError("invalid projector difference site label")
        if n_value is not None and (isinstance(n_value, bool) or not isinstance(n_value, int)):
            raise ProjectorConsistencyError("invalid projector difference n")
        if l_value is not None and (isinstance(l_value, bool) or not isinstance(l_value, int)):
            raise ProjectorConsistencyError("invalid projector difference l")
        if not isinstance(reference_value, str) or not isinstance(response_value, str):
            raise ProjectorConsistencyError("invalid projector difference values")
        try:
            reason = ProjectorDifferenceReason(value["reason"])
        except (KeyError, ValueError, TypeError) as exc:
            raise ProjectorConsistencyError("invalid projector difference reason") from exc
        return cls(reason, label, n_value, l_value, reference_value, response_value)


@dataclass(frozen=True)
class ProjectorComparison:
    """Typed comparison result for one response FDF and its parent reference."""

    status: ProjectorComparisonStatus
    differences: tuple[ProjectorDifference, ...]

    def __post_init__(self) -> None:
        if (self.status is ProjectorComparisonStatus.MATCH) != (not self.differences):
            raise ProjectorConsistencyError("projector comparison status disagrees with differences")

    @property
    def compatible(self) -> bool:
        return self.status is ProjectorComparisonStatus.MATCH

    def to_mapping(self) -> dict[str, object]:
        return {"status": self.status.value, "differences": [item.to_mapping() for item in self.differences]}

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> ProjectorComparison:
        raw_differences = value.get("differences")
        if not isinstance(raw_differences, list) or any(
            not isinstance(row, Mapping) for row in raw_differences
        ):
            raise ProjectorConsistencyError("invalid projector comparison differences")
        try:
            status = ProjectorComparisonStatus(value["status"])
            differences = tuple(ProjectorDifference.from_mapping(row) for row in raw_differences)
            return cls(status, differences)
        except (KeyError, TypeError, ValueError) as exc:
            raise ProjectorConsistencyError("invalid projector comparison mapping") from exc

    def describe(self) -> str:
        if self.compatible:
            return "reference and response projector definitions match"
        details = "; ".join(
            f"{item.reason.value} {item.site_label or 'campaign'}"
            f" n={item.n} l={item.l}: reference={item.reference_value},"
            f" response={item.response_value}"
            for item in self.differences
        )
        return f"reference and response projectors differ: {details}"


@dataclass(frozen=True)
class _ProjectorRecord:
    site_label: str
    n: int
    l: int
    rc_bohr: float
    omega: float


@dataclass(frozen=True)
class _Configuration:
    method: int
    cutoff_norm: float
    records: tuple[_ProjectorRecord, ...]


def _number(token: str, name: str) -> float:
    try:
        value = float(token.replace("D", "E").replace("d", "e"))
    except ValueError as exc:
        raise ProjectorConsistencyError(f"invalid numeric {name}: {token!r}") from exc
    if not math.isfinite(value):
        raise ProjectorConsistencyError(f"non-finite {name}: {token!r}")
    return value


def _directives(text: str, key: str) -> tuple[str, ...]:
    found: list[str] = []
    in_block = False
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        lowered = line.casefold()
        if lowered.startswith("%block "):
            in_block = True
            continue
        if lowered.startswith("%endblock"):
            in_block = False
            continue
        if in_block or not line:
            continue
        fields = line.split(maxsplit=1)
        if fields[0].casefold() == key.casefold():
            found.append(fields[1].strip() if len(fields) == 2 else "")
    return tuple(found)


def _one_directive(text: str, key: str) -> str | None:
    values = _directives(text, key)
    if len(values) > 1:
        raise ProjectorConsistencyError(f"duplicate FDF directive {key}")
    return values[0] if values else None


def _projector_block(text: str) -> tuple[str, ...]:
    lines = text.splitlines()
    starts = [
        index
        for index, line in enumerate(lines)
        if line.split("#", 1)[0].strip().casefold() == "%block dftu.proj"
    ]
    ends = [
        index
        for index, line in enumerate(lines)
        if line.split("#", 1)[0].strip().casefold() == "%endblock dftu.proj"
    ]
    if len(starts) != 1 or len(ends) != 1 or ends[0] <= starts[0]:
        raise ProjectorConsistencyError("exactly one complete DFTU.Proj block is required")
    rows = tuple(body for raw in lines[starts[0] + 1 : ends[0]] if (body := raw.split("#", 1)[0].strip()))
    if not rows or len(rows) % 4:
        raise ProjectorConsistencyError("DFTU.Proj must contain complete four-line records")
    return rows


def _effective_method(text: str) -> int:
    method = _one_directive(text, "DFTU.Method")
    legacy_method = _one_directive(text, "DFTU.ProjectorGenerationMethod")
    method_fields = method.split() if method is not None else []
    legacy_method_fields = legacy_method.split() if legacy_method is not None else []
    if method is not None and len(method_fields) != 1:
        raise ProjectorConsistencyError("DFTU.Method must declare one integer")
    if legacy_method is not None and len(legacy_method_fields) != 1:
        raise ProjectorConsistencyError("DFTU.ProjectorGenerationMethod must declare one integer")
    if method is not None and legacy_method is not None and method_fields[0] != legacy_method_fields[0]:
        raise ProjectorConsistencyError("DFTU method declarations conflict")
    method_text = method if method is not None else legacy_method
    if method_text is None:
        # SIESTA's documented default used by the existing Method-2 preflight.
        method_value = 2
    else:
        try:
            method_value = int(method_text.split()[0])
        except (ValueError, IndexError) as exc:
            raise ProjectorConsistencyError("DFTU projector generation method must be an integer") from exc
    return method_value


def _configuration(text: str) -> _Configuration:
    method_value = _effective_method(text)
    cutoff_text = _one_directive(text, "DFTU.CutoffNorm")
    if cutoff_text is None:
        cutoff_norm = 0.90
    else:
        cutoff_fields = cutoff_text.split()
        if len(cutoff_fields) != 1:
            raise ProjectorConsistencyError("DFTU.CutoffNorm must declare one number")
        cutoff_norm = _number(cutoff_fields[0], "DFTU.CutoffNorm")
    records: list[_ProjectorRecord] = []
    seen: set[tuple[str, int, int]] = set()
    rows = _projector_block(text)
    for offset in range(0, len(rows), 4):
        header, shell, _values, radial = rows[offset : offset + 4]
        header_fields, shell_fields, radial_fields = header.split(), shell.split(), radial.split()
        if len(header_fields) != 2 or len(shell_fields) != 2 or len(radial_fields) < 2:
            raise ProjectorConsistencyError("unsupported DFTU.Proj record shape")
        try:
            n, angular_momentum = int(shell_fields[0]), int(shell_fields[1])
        except ValueError as exc:
            raise ProjectorConsistencyError("DFTU.Proj shell n and l must be integers") from exc
        key = (header_fields[0], n, angular_momentum)
        if key in seen:
            raise ProjectorConsistencyError(f"duplicate DFTU.Proj shell record: {key!r}")
        seen.add(key)
        records.append(
            _ProjectorRecord(
                header_fields[0],
                n,
                angular_momentum,
                _number(radial_fields[0], "DFTU.Proj rc"),
                _number(radial_fields[1], "DFTU.Proj omega"),
            )
        )
    return _Configuration(
        method_value, cutoff_norm, tuple(sorted(records, key=lambda row: (row.site_label, row.n, row.l)))
    )


def compare_projector_definitions(
    reference_fdf: str,
    response_fdf: str,
    *,
    reference_generated_rc_bohr: Mapping[str, float] | None = None,
    response_generated_rc_bohr: Mapping[str, float] | None = None,
) -> ProjectorComparison:
    """Compare each response with its reference projector definition.

    Automatic rc compares effective CutoffNorm and, when supplied, generated
    radii keyed by ``site_label/n/l``. Explicit rc is compared directly; hashes
    never decide compatibility.
    """
    reference_method = _effective_method(reference_fdf)
    response_method = _effective_method(response_fdf)
    if reference_method != response_method:
        difference = ProjectorDifference(
            ProjectorDifferenceReason.METHOD_MISMATCH,
            None,
            None,
            None,
            str(reference_method),
            str(response_method),
        )
        return ProjectorComparison(ProjectorComparisonStatus.MISMATCH, (difference,))
    reference = _configuration(reference_fdf)
    response = _configuration(response_fdf)
    reference_generated = _generated_rc(reference_generated_rc_bohr, reference.records, "reference")
    response_generated = _generated_rc(response_generated_rc_bohr, response.records, "response")
    differences: list[ProjectorDifference] = []
    reference_by_key = {(row.site_label, row.n, row.l): row for row in reference.records}
    response_by_key = {(row.site_label, row.n, row.l): row for row in response.records}
    if set(reference_by_key) != set(response_by_key):
        differences.append(
            ProjectorDifference(
                ProjectorDifferenceReason.RECORDS_MISMATCH,
                None,
                None,
                None,
                ",".join(_format_key(key) for key in sorted(reference_by_key)),
                ",".join(_format_key(key) for key in sorted(response_by_key)),
            )
        )
    for key in sorted(set(reference_by_key) & set(response_by_key)):
        left, right = reference_by_key[key], response_by_key[key]
        label, n, angular_momentum = key
        if left.omega != right.omega:
            differences.append(
                ProjectorDifference(
                    ProjectorDifferenceReason.OMEGA_MISMATCH,
                    label,
                    n,
                    angular_momentum,
                    repr(left.omega),
                    repr(right.omega),
                )
            )
        if left.rc_bohr == 0.0 or right.rc_bohr == 0.0:
            if reference.cutoff_norm != response.cutoff_norm:
                differences.append(
                    ProjectorDifference(
                        ProjectorDifferenceReason.CUTOFF_NORM_MISMATCH,
                        label,
                        n,
                        angular_momentum,
                        repr(reference.cutoff_norm),
                        repr(response.cutoff_norm),
                    )
                )
            left_generated = reference_generated.get(key)
            right_generated = response_generated.get(key)
            if left_generated is not None and right_generated is not None:
                if left_generated != right_generated:
                    differences.append(
                        ProjectorDifference(
                            ProjectorDifferenceReason.GENERATED_RC_MISMATCH,
                            label,
                            n,
                            angular_momentum,
                            repr(left_generated),
                            repr(right_generated),
                        )
                    )
            elif left.rc_bohr != right.rc_bohr:
                differences.append(
                    ProjectorDifference(
                        ProjectorDifferenceReason.RC_MISMATCH,
                        label,
                        n,
                        angular_momentum,
                        repr(left.rc_bohr),
                        repr(right.rc_bohr),
                    )
                )
            elif (left_generated is None) != (right_generated is None):
                differences.append(
                    ProjectorDifference(
                        ProjectorDifferenceReason.GENERATED_RC_UNAVAILABLE,
                        label,
                        n,
                        angular_momentum,
                        "AVAILABLE" if left_generated is not None else "UNAVAILABLE",
                        "AVAILABLE" if right_generated is not None else "UNAVAILABLE",
                    )
                )
        elif left.rc_bohr != right.rc_bohr:
            differences.append(
                ProjectorDifference(
                    ProjectorDifferenceReason.RC_MISMATCH,
                    label,
                    n,
                    angular_momentum,
                    repr(left.rc_bohr),
                    repr(right.rc_bohr),
                )
            )
    differences.sort(key=lambda item: (item.reason.value, item.site_label or "", item.n or -1, item.l or -1))
    status = ProjectorComparisonStatus.MISMATCH if differences else ProjectorComparisonStatus.MATCH
    return ProjectorComparison(status, tuple(differences))


def _generated_rc(
    values: Mapping[str, float] | None,
    records: tuple[_ProjectorRecord, ...],
    source: str,
) -> dict[tuple[str, int, int], float]:
    if values is None:
        return {}
    expected = {f"{row.site_label}/{row.n}/{row.l}": (row.site_label, row.n, row.l) for row in records}
    result: dict[tuple[str, int, int], float] = {}
    for label in sorted(values):
        key = expected.get(label)
        value = values[label]
        if key is None:
            raise ProjectorConsistencyError(f"{source} generated rc has unknown record {label!r}")
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            raise ProjectorConsistencyError(f"{source} generated rc must be finite for {label}")
        result[key] = float(value)
    return result


def _format_key(key: tuple[str, int, int]) -> str:
    return f"{key[0]}/{key[1]}/{key[2]}"
