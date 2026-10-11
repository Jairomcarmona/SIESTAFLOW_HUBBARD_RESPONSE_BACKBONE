"""Strict transport validation; scientific admission remains in the domain."""

from __future__ import annotations

import json
import types
from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from enum import Enum
from typing import Any, Literal, Union, cast, get_args, get_origin, get_type_hints

from hubbardflow.domain.validation import require_finite


class ApiErrorKind(str, Enum):
    TRANSPORT_INVALID = "TRANSPORT_INVALID"
    SCIENTIFIC_REJECTION = "SCIENTIFIC_REJECTION"


class PublicApiError(ValueError):
    """A public request is malformed or unsupported."""

    kind = ApiErrorKind.TRANSPORT_INVALID


class ScientificEvidenceError(PublicApiError):
    """Native science rejected evidence; adapters must emit an assessment, not HTTP failure."""

    kind = ApiErrorKind.SCIENTIFIC_REJECTION


def json_tree(value: object) -> object:
    """Copy JSON values without accepting NaN, non-string keys or opaque objects."""
    if value is None or type(value) in (str, bool, int):
        return value
    if type(value) is float:
        try:
            return require_finite(value, "JSON number")
        except ValueError as exc:
            raise PublicApiError(str(exc)) from exc
    if isinstance(value, (list, tuple)):
        return [json_tree(item) for item in value]
    if isinstance(value, Mapping) and all(type(key) is str for key in value):
        return {key: json_tree(value[key]) for key in sorted(value)}
    # Domain to_mapping() occasionally preserves str enums.
    if isinstance(value, Enum) and isinstance(value.value, str):
        return value.value
    raise PublicApiError("expected finite JSON with string object keys")


def mapping(value: object, label: str = "request") -> dict[str, object]:
    result = json_tree(value)
    if not isinstance(result, dict):
        raise PublicApiError(f"{label} must be an object")
    return cast(dict[str, object], result)


def object_fields(value: object, required: set[str], optional: set[str] | None = None) -> dict[str, object]:
    row = mapping(value)
    if set(row) - required - (optional or set()) or required - set(row):
        raise PublicApiError(f"explicit fields required: {sorted(required)}; unknown fields rejected")
    return row


def string(value: object, label: str) -> str:
    if type(value) is not str or not value.strip():
        raise PublicApiError(f"{label} must be a nonempty string")
    return value


def array(value: object, label: str) -> list[object]:
    if not isinstance(value, list):
        raise PublicApiError(f"{label} must be an array")
    return value


def decode_record[T](cls: type[T], value: object) -> T:
    """Decode typed native records with every field explicit, without coercion.

    Native default policies are deliberately not injected at this boundary.
    Enum constructors reject unsupported requests; unknown *result* statuses
    are retained by ApiResult instead of treated as scientific success.
    """
    try:
        return cast(T, decode_type(cls, value))
    except (ValueError, KeyError, TypeError, AttributeError, OverflowError) as exc:
        raise PublicApiError(f"invalid {cls.__name__}: {exc}") from exc


def decode_type(annotation: Any, value: object) -> Any:
    """Structural decoder used only for established native dataclass fields."""
    origin, args = get_origin(annotation), get_args(annotation)
    if annotation is Any or annotation is object:
        return json_tree(value)
    if origin in (Union, types.UnionType):
        for candidate in args:
            try:
                return decode_type(candidate, value)
            except (ValueError, TypeError):
                pass
        raise PublicApiError("value matches none of the declared field types")
    if origin is Literal:
        if not any(type(value) is type(item) and value == item for item in args):
            raise PublicApiError(f"expected one of {args}")
        return value
    if annotation is type(None):
        if value is not None:
            raise PublicApiError("expected null")
        return None
    if annotation is float:
        return require_finite(value, "record number")
    if annotation in (str, int, bool):
        if type(value) is not annotation:
            raise PublicApiError(f"expected {annotation.__name__}, without coercion")
        return value
    if isinstance(annotation, type) and issubclass(annotation, Enum):
        return annotation(string(value, "enum value"))
    if origin in (list, tuple):
        items = array(value, "record sequence")
        if origin is tuple and args and args[-1] is not Ellipsis:
            if len(items) != len(args):
                raise PublicApiError("tuple field has wrong length")
            return tuple(decode_type(kind, item) for kind, item in zip(args, items, strict=True))
        decoded = [decode_type(args[0] if args else object, item) for item in items]
        return tuple(decoded) if origin is tuple else decoded
    if annotation is dict or origin is dict:
        row = mapping(value)
        if not args:
            return row
        key_type, value_type = args
        if key_type is not str:
            raise PublicApiError("JSON object keys must be strings")
        return {key: decode_type(value_type, item) for key, item in row.items()}
    if isinstance(annotation, type) and is_dataclass(annotation):
        row = object_fields(value, {field.name for field in fields(annotation)})
        hints = get_type_hints(annotation)
        return annotation(**{key: decode_type(hints[key], item) for key, item in row.items()})
    raise PublicApiError(f"unsupported native transport type {annotation!r}")


def explicit_native_fields(supplied: object, native: object) -> None:
    """Reject omitted fields, unknown keys and legacy scalar coercions recursively.

    This checks transport structure, not scientific equivalence. Native domain
    functions remain responsible for ordering and admissibility. The optional
    traceability_warnings field is derived by native codecs, never admission.
    """
    supplied, native = json_tree(supplied), json_tree(native)
    if isinstance(native, dict):
        if not isinstance(supplied, dict):
            raise PublicApiError("native record must be an object")
        if set(supplied) - set(native) or set(native) - set(supplied) - {"traceability_warnings"}:
            raise PublicApiError("native record fields must be explicit and supported")
        for key in supplied:
            explicit_native_fields(supplied[key], native[key])
    elif isinstance(native, list):
        if not isinstance(supplied, list) or len(supplied) != len(native):
            raise PublicApiError("native array shape changed during decoding")
        for given, decoded in zip(supplied, native, strict=True):
            explicit_native_fields(given, decoded)
    elif type(native) in (int, float):
        require_finite(supplied, "native record number")
        if type(native) is int and type(supplied) is not int:
            raise PublicApiError("native integer cannot be coerced")
    elif type(supplied) is not type(native):
        raise PublicApiError("native scalar cannot be coerced")


def json_bytes(value: object) -> bytes:
    """Transport encoding only; never a replacement for an existing digest."""
    return json.dumps(json_tree(value), sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
