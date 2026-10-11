"""Installed, versioned JSON Schema documents for the public native receipts."""

from __future__ import annotations

from dataclasses import dataclass
from importlib.resources import files

from .serialization import PublicApiError, json_bytes, mapping


@dataclass(frozen=True)
class SchemaDocument:
    schema_json: str

    def to_mapping(self) -> dict[str, object]:
        import json

        return mapping(json.loads(self.schema_json))

    @classmethod
    def from_mapping(cls, value: object) -> SchemaDocument:
        return cls(json_bytes(mapping(value)).decode())


def get_schema(schema_id: str) -> SchemaDocument:
    """Load only known installed schemas; no user path or network resolution."""
    filenames = {
        "hubbardflow.api_result.v1": "api_result.v1.schema.json",
        "hubbardflow.analysis_result.v1": "analysis_result.v1.schema.json",
        "hubbardflow.worker_status.v1": "worker_status.v1.schema.json",
    }
    if schema_id not in filenames:
        raise PublicApiError(f"unsupported schema_id: {schema_id}")
    return SchemaDocument(
        files("hubbardflow.api").joinpath("schemas", filenames[schema_id]).read_text(encoding="utf-8")
    )
