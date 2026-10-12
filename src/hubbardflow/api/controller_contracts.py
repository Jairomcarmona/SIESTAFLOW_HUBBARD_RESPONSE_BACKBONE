"""Validation and durable writing for the QRAFT controller wire contracts.

These helpers implement only the file contracts in ADR-017. They do not decide
whether a scientific checkpoint may be reused or resumed.
"""

from __future__ import annotations

import json
import re
from calendar import timegm
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource


class ControllerContractError(ValueError):
    """A QRAFT controller descriptor or ledger entry violates its contract."""


_UTC_TIMESTAMP = re.compile(r"^(?P<whole>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.(?P<fraction>\d{1,9}))?Z$")


def utc_timestamp_nanoseconds(value: str) -> int:
    """Validate an ADR UTC timestamp and retain its full nanosecond precision."""
    match = _UTC_TIMESTAMP.fullmatch(value)
    if match is None:
        raise ControllerContractError("timestamp must be an RFC3339 UTC value with at most 9 decimals")
    try:
        parsed = datetime.strptime(match.group("whole"), "%Y-%m-%dT%H:%M:%S").replace(tzinfo=UTC)
    except ValueError as exc:
        raise ControllerContractError("timestamp has an invalid calendar date or time") from exc
    fraction = (match.group("fraction") or "").ljust(9, "0")
    return timegm(parsed.timetuple()) * 1_000_000_000 + int(fraction or "0")


@dataclass(frozen=True)
class ControllerReservation:
    """Validated reservation descriptor, retained byte-for-byte for evidence."""

    path: Path
    canonical_document: bytes

    def to_mapping(self) -> dict[str, object]:
        """Return a detached decoded copy of the validated descriptor."""
        value = json.loads(self.canonical_document)
        if not isinstance(value, dict):
            raise ControllerContractError("controller reservation must be a JSON object")
        return value


def controller_schema_validator(schema_name: str) -> Draft202012Validator:
    schema_path = Path(__file__).with_name("schemas") / schema_name.replace(".schema.json", ".schema")
    definitions_path = schema_path.with_name("defs.schema")
    try:
        schema = load_strict_json(schema_path.read_text(encoding="utf-8"))
        definitions = load_strict_json(definitions_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ControllerContractError(f"cannot load bundled controller schema {schema_name}: {exc}") from exc
    if (
        not isinstance(schema, dict)
        or not isinstance(definitions, dict)
        or not isinstance(schema.get("$id"), str)
        or not isinstance(definitions.get("$id"), str)
    ):
        raise ControllerContractError(f"bundled controller schema {schema_name} is malformed")
    registry = Registry().with_resource(str(definitions["$id"]), Resource.from_contents(definitions))
    return Draft202012Validator(schema, registry=registry, format_checker=FormatChecker())


def load_strict_json(value: str) -> object:
    """Decode contract JSON while rejecting duplicate names and non-finite numbers."""

    def unique_pairs(items: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, item in items:
            if key in result:
                raise ControllerContractError(f"duplicate JSON property: {key}")
            result[key] = item
        return result

    def reject_constant(value: str) -> None:
        raise ControllerContractError(f"non-finite JSON number is forbidden: {value}")

    return json.loads(value, object_pairs_hook=unique_pairs, parse_constant=reject_constant)


def load_controller_reservation(path: str | Path) -> ControllerReservation:
    """Load and strictly validate a QRAFT reservation descriptor."""
    descriptor_path = Path(path).resolve()
    try:
        raw = descriptor_path.read_bytes()
        value = load_strict_json(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ControllerContractError(f"controller reservation is unreadable: {exc}") from exc
    if not isinstance(value, dict):
        raise ControllerContractError("controller reservation must be a JSON object")
    errors = sorted(
        controller_schema_validator("qraft-controller-reservation.schema.json").iter_errors(value),
        key=lambda item: list(item.path),
    )
    if errors:
        raise ControllerContractError(f"invalid controller reservation: {errors[0].message}")
    reserved = value["reserved"]
    inner = value["inner"]
    allocation = value["allocation"]
    deadline = value["deadline"]
    if not all(isinstance(item, dict) for item in (reserved, inner, allocation, deadline)):
        raise ControllerContractError("controller reservation nested objects are malformed")
    ranks = int(inner["processes_per_node"])
    cpus_per_process = int(inner["cpus_per_process"])
    concurrency = int(inner["max_concurrent"])
    required_cpus = ranks * cpus_per_process * concurrency
    if ranks <= 0 or cpus_per_process <= 0 or concurrency <= 0 or required_cpus <= 0:
        raise ControllerContractError("controller launch dimensions must be positive")
    if (
        int(reserved["runtime_cpus"]) <= 0
        or int(reserved["min_cpus"]) != required_cpus
        or int(reserved["runtime_cpus"]) < required_cpus
    ):
        raise ControllerContractError(
            "controller CPU reservation is inconsistent with inner launch dimensions"
        )
    observed = reserved["scheduler_cpus_on_host"]
    if (
        allocation["scheduler"] == "slurm"
        and isinstance(observed, dict)
        and observed["value"] is not None
        and int(observed["value"]) < int(reserved["runtime_cpus"])
    ):
        raise ControllerContractError("SLURM host CPU observation is smaller than the QRAFT reservation")
    stop_at = utc_timestamp_nanoseconds(str(deadline["stop_launching_at"]))
    hard_stop_at = utc_timestamp_nanoseconds(str(deadline["hard_stop_at"]))
    if stop_at > hard_stop_at:
        raise ControllerContractError("controller launch deadline must not exceed its hard-stop deadline")
    for relative in value["paths"].values():
        candidate = Path(relative)
        if (
            candidate.is_absolute()
            or "\\" in str(relative)
            or any(part in {"", ".", ".."} for part in str(relative).split("/"))
        ):
            raise ControllerContractError("controller descriptor paths must be safe and relative")
    encoded = json.dumps(
        value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")
    ).encode()
    return ControllerReservation(descriptor_path, encoded)
