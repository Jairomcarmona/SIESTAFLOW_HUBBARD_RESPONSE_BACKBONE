"""Stable serializers and verified source records shared by campaign execution."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from hubbardflow.domain.matrix_lr import ResponseObservation
from hubbardflow.execution.campaign_v2 import sha256_file
from hubbardflow.execution.generic_executor import NodeReceipt


def campaign_relative_path(root: Path, value: str | Path | None) -> str | None:
    """Render campaign paths relative to the campaign root when possible."""
    if not value:
        return None
    path = Path(value)
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except (OSError, ValueError):
        return str(value)


def dataset_half_widths(
    trace_half_widths_electron: Mapping[tuple[int, float, str], list[float]] | None,
    key: tuple[int, float],
    mode: str,
) -> list[float] | None:
    if trace_half_widths_electron is None:
        return None
    values = trace_half_widths_electron.get((int(key[0]), float(key[1]), mode))
    return None if values is None else [float(value) for value in values]


def dataset_half_width(
    trace_half_widths_electron: Mapping[tuple[int, float, str], list[float]] | None,
    key: tuple[int, float],
    mode: str,
    offset: int,
) -> float | None:
    values = dataset_half_widths(trace_half_widths_electron, key, mode)
    return None if values is None else values[offset]


def build_verified_dataset(
    observations: list[ResponseObservation],
    sites: list[dict[str, Any]],
    *,
    reference_source: Mapping[str, Any],
    response_sources: Mapping[tuple[int, float], Mapping[str, Mapping[str, Any]]],
    trace_half_widths_electron: Mapping[tuple[int, float, str], list[float]] | None = None,
    reference_trace_half_widths_electron: list[float] | None = None,
    occupation_source: str = "matrix_trace_total",
) -> dict[str, Any]:
    """Persist verified occupations with the exact run evidence they came from."""
    site_index_map = [
        {
            "index": index,
            "site_id": str(site["site_id"]),
            "atom_index": site.get("atom_index"),
            "orbit_id": site.get("orbit_id"),
        }
        for index, site in enumerate(sites)
    ]
    by_index = {item["index"]: item for item in site_index_map}
    rows: list[dict[str, Any]] = []
    seen: set[tuple[int, float]] = set()
    for observation in observations:
        key = (int(observation.perturbation_site), float(observation.alpha))
        if key in seen:
            raise ValueError(f"duplicate verified observation for site={key[0]}, alpha={key[1]}")
        seen.add(key)
        expected_indices = list(range(len(sites)))
        if key[0] not in by_index or list(observation.site_labels) != expected_indices:
            raise ValueError("verified observations do not match the campaign site index map")
        if any(
            len(values) != len(sites)
            for values in (
                observation.occupations_ref,
                observation.occupations_bare,
                observation.occupations_screened,
            )
        ):
            raise ValueError("verified occupation vectors do not match the campaign site index map")
        sources = response_sources.get(key, {})
        bare_source = sources.get("bare")
        screened_source = sources.get("screened")
        if not isinstance(bare_source, Mapping) or not isinstance(screened_source, Mapping):
            raise ValueError(f"verified response sources are incomplete for site={key[0]}, alpha={key[1]}")  # noqa: TRY004
        observed_sites = []
        for offset, site_index in enumerate(observation.site_labels):
            site_index = int(site_index)
            if site_index not in by_index:
                raise ValueError(f"verified observation contains unknown site index {site_index}")
            observed_sites.append(
                {
                    "observed_site_index": site_index,
                    "observed_site_id": by_index[site_index]["site_id"],
                    "occupations_electron": {
                        "reference": float(observation.occupations_ref[offset]),
                        "bare": float(observation.occupations_bare[offset]),
                        "screened": float(observation.occupations_screened[offset]),
                    },
                    (
                        "occupation_half_widths_electron"
                        if occupation_source == "siesta_occupations_total"
                        else "matrix_trace_half_widths_electron"
                    ): {
                        "reference": (
                            None
                            if reference_trace_half_widths_electron is None
                            else float(reference_trace_half_widths_electron[offset])
                        ),
                        "bare": dataset_half_width(trace_half_widths_electron, key, "bare", offset),
                        "screened": dataset_half_width(trace_half_widths_electron, key, "screened", offset),
                    },
                }
            )
        rows.append(
            {
                "perturbed_site_index": key[0],
                "perturbed_site_id": by_index[key[0]]["site_id"],
                "alpha_eV": key[1],
                "observed_sites": observed_sites,
                "sources": {"bare": dict(bare_source), "screened": dict(screened_source)},
            }
        )
    rows.sort(key=lambda item: (item["perturbed_site_index"], item["alpha_eV"]))
    return {
        "schema_version": (
            "siestaflow.lr_u_verified_dataset.v2"
            if occupation_source == "siesta_occupations_total"
            else "siestaflow.lr_u_verified_dataset.v1"
        ),
        "occupation_source": occupation_source,
        "status": "AVAILABLE",
        "units": {"alpha": "eV", "occupations": "electron"},
        "site_index_map": site_index_map,
        "matrix_index_to_site_id": {str(item["index"]): item["site_id"] for item in site_index_map},
        "site_id_to_matrix_index": {item["site_id"]: item["index"] for item in site_index_map},
        "reference_source": dict(reference_source),
        "rows": rows,
    }


def source_record(
    root: Path,
    node_id: str,
    record: Mapping[str, Any],
    receipt: NodeReceipt,
    *,
    mode: str,
) -> dict[str, Any]:
    command = record.get("command") or {}
    provenance = record.get("provenance") or {}
    artifact_hashes = provenance.get("artifacts") or {}
    artifact_spec = record.get("artifact_spec") or {}
    cwd = Path(str(command.get("cwd", "")))
    dm_name = artifact_spec.get("dm")
    return {
        "node_id": node_id,
        "mode": mode,
        "state": receipt.state.value,
        "fdf_path": campaign_relative_path(root, command.get("stdin_path")),
        "out_path": campaign_relative_path(root, command.get("stdout_path")),
        "dm_path": campaign_relative_path(root, cwd / str(dm_name)) if dm_name else None,
        "fdf_sha256": artifact_hashes.get("fdf"),
        "out_sha256": artifact_hashes.get("output"),
        "dm_sha256": artifact_hashes.get("dm"),
        "evidence_digest": receipt.evidence_digest,
    }


def verify_record_artifacts(record: Mapping[str, Any], node_id: str) -> dict[str, str]:
    """Recheck artifact bytes against the validator provenance before extraction."""
    command = record.get("command")
    spec = record.get("artifact_spec")
    provenance = record.get("provenance")
    if not isinstance(command, Mapping) or not isinstance(spec, Mapping) or not isinstance(provenance, Mapping):
        raise ValueError(f"{node_id} has no complete validator provenance record")  # noqa: TRY004
    declared = provenance.get("artifacts")
    if not isinstance(declared, Mapping):
        raise ValueError(f"{node_id} validator provenance has no artifact hashes")  # noqa: TRY004
    cwd = Path(str(command.get("cwd", "")))
    paths = {
        "fdf": Path(str(command.get("stdin_path", ""))),
        "output": Path(str(command.get("stdout_path", ""))),
        "dm": cwd / str(spec.get("dm", "")),
    }
    actual: dict[str, str] = {}
    for label, path in paths.items():
        if not path.is_file():
            raise ValueError(f"{node_id} validated {label} artifact is missing")
        digest = sha256_file(path)
        if declared.get(label) != digest:
            raise ValueError(f"{node_id} {label} changed after output validation")
        actual[label] = digest
    parent_dm_name = spec.get("reference_dm")
    semantic = provenance.get("semantic", {})
    if parent_dm_name:
        parent_dm = cwd / str(parent_dm_name)
        if not parent_dm.is_file():
            raise ValueError(f"{node_id} reference DM copy is missing")
        parent_digest = sha256_file(parent_dm)
        if not isinstance(semantic, Mapping) or semantic.get("reference_dm_sha256") != parent_digest:
            raise ValueError(f"{node_id} reference DM changed after output validation")
        actual["parent_dm"] = parent_digest
    return actual
