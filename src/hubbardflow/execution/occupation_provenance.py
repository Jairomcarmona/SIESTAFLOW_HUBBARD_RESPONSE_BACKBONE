"""Reconstruct observation-to-output provenance from retained campaign files."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
from pathlib import Path
from typing import Any

from hubbardflow.execution.campaign_store import atomic_json
from hubbardflow.siesta_backend.occupation_precision import read_printed_occupation_precision
from hubbardflow.siesta_backend.parser_models import HubbardPopulationEvent
from hubbardflow.siesta_backend.siesta542_bare_profile import (
    Siesta542PotentialShiftHamiltonianProfile,
)
from hubbardflow.siesta_backend.siesta542_screened_selection import (
    select_converged_screened_event,
)


class OccupationProvenanceStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    PARTIAL = "PARTIAL"
    NOT_ASSESSED = "NOT_ASSESSED"


@dataclass(frozen=True)
class OccupationProvenanceRecord:
    """Source location for one occupation value consumed by LR analysis."""

    mode: str
    perturbed_site_id: str | None
    alpha_ev: float | None
    observed_site_index: int
    observed_site_id: str
    occupation_electron: float
    occupation_at_selected_block_electron: float | None
    source_minus_analysis_occupation_electron: float | None
    run_folder: str
    file: str
    selected_block_line: int | None
    selected_block_end_line: int | None
    event_occurrence_index: int | None
    source_status: str
    output_sha256_recorded: str | None
    output_sha256_observed: str | None
    traceability_warnings: tuple[str, ...] = ()
    per_spin_occupation_e: float | None = None
    total_derived: bool = False

    def to_mapping(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "perturbed_site_id": self.perturbed_site_id,
            "alpha_eV": self.alpha_ev,
            "observed_site_index": self.observed_site_index,
            "observed_site_id": self.observed_site_id,
            "occupation_electron": self.occupation_electron,
            "occupation_at_selected_block_electron": self.occupation_at_selected_block_electron,
            "source_minus_analysis_occupation_electron": self.source_minus_analysis_occupation_electron,
            "run_folder": self.run_folder,
            "file": self.file,
            "selected_block_line": self.selected_block_line,
            "selected_block_end_line": self.selected_block_end_line,
            "event_occurrence_index": self.event_occurrence_index,
            "source_status": self.source_status,
            "output_sha256_recorded": self.output_sha256_recorded,
            "output_sha256_observed": self.output_sha256_observed,
            "traceability_warnings": list(self.traceability_warnings),
            "per_spin_occupation_e": self.per_spin_occupation_e,
            "total_derived": self.total_derived,
        }


@dataclass(frozen=True)
class OccupationProvenance:
    """Reconstructed provenance sidecar; hashes are advisory only."""

    status: OccupationProvenanceStatus
    campaign_root: str
    records: tuple[OccupationProvenanceRecord, ...]
    reasons: tuple[str, ...] = ()

    def to_mapping(self) -> dict[str, Any]:
        return {
            "schema_version": "hubbardflow.occupation_provenance.v1",
            "status": self.status.value,
            "campaign_root": self.campaign_root,
            "hash_policy": "WARN_ONLY",
            "records": [record.to_mapping() for record in self.records],
            "reasons": list(self.reasons),
        }


def _source_location(root: Path, source: Mapping[str, Any]) -> tuple[Path | None, str, str]:
    raw = source.get("out_path")
    if not isinstance(raw, str) or not raw:
        return None, "", ""
    path = Path(raw)
    if not path.is_absolute():
        path = root / path
    try:
        relative = path.resolve().relative_to(root.resolve()).as_posix()
    except (OSError, ValueError):
        relative = str(path)
    try:
        run_folder = path.parent.resolve().relative_to(root.resolve()).as_posix()
    except (OSError, ValueError):
        run_folder = str(path.parent)
    return path, run_folder, relative


def _select_event(
    output_text: str,
    mode: str,
    bare_profile: Siesta542PotentialShiftHamiltonianProfile,
    fdf_text: str | None,
) -> HubbardPopulationEvent:
    if mode == "BARE":
        return bare_profile.select_response(output_text, fdf_text=fdf_text).response_event
    if mode in {"SCREENED", "REFERENCE_SCREENED"}:
        return select_converged_screened_event(output_text)
    raise ValueError(f"unsupported occupation provenance mode: {mode}")


def _resolved_source(
    root: Path,
    source: Mapping[str, Any],
    *,
    mode: str,
    perturbed_site_id: str | None,
    alpha_ev: float | None,
    observed_site_index: int,
    observed_site_id: str,
    atom_index: int | None,
    occupation_electron: float,
    bare_profile: Siesta542PotentialShiftHamiltonianProfile,
) -> OccupationProvenanceRecord:
    output_path, run_folder, output_relative = _source_location(root, source)
    recorded_sha = source.get("out_sha256")
    recorded_sha = str(recorded_sha) if recorded_sha else None
    warnings: list[str] = []
    output_sha: str | None = None
    line: int | None = None
    end_line: int | None = None
    occurrence: int | None = None
    occupation_at_source: float | None = None
    source_minus_analysis: float | None = None
    per_spin_occupation: float | None = None
    total_derived = False
    source_status = "AVAILABLE"
    if output_path is None:
        source_status = "NOT_ASSESSED"
        warnings.append("SOURCE_OUTPUT_PATH_MISSING")
    else:
        try:
            raw = output_path.read_bytes()
            output_sha = sha256(raw).hexdigest()
            if recorded_sha and output_sha != recorded_sha:
                warnings.append("OUTPUT_SHA256_DIFFERS_FROM_RECORDED_VALUE")
            output_text = raw.decode("utf-8", errors="replace")
            raw_fdf_path = source.get("fdf_path")
            fdf_path = Path(str(raw_fdf_path)) if raw_fdf_path else None
            if fdf_path is not None and not fdf_path.is_absolute():
                fdf_path = root / fdf_path
            fdf_text = None if fdf_path is None else fdf_path.read_text(encoding="utf-8", errors="replace")
            event = _select_event(output_text, mode, bare_profile, fdf_text)
            if event.source_start_line is None:
                source_status = "NOT_ASSESSED"
                warnings.append("SELECTED_BLOCK_START_LINE_MISSING")
            else:
                line = event.source_start_line + 1
                end_line = None if event.source_end_line is None else event.source_end_line + 1
                occurrence = event.occurrence_index
                if atom_index is None:
                    warnings.append("ANALYSIS_ATOM_INDEX_MISSING")
                else:
                    try:
                        printed = read_printed_occupation_precision(output_text, event, fdf_text=fdf_text)
                        measurement = printed[atom_index]
                        occupation_at_source = float(measurement.total)
                        per_spin_occupation = measurement.per_spin_occupation_e
                        total_derived = measurement.total_derived
                        source_minus_analysis = occupation_at_source - occupation_electron
                        if source_minus_analysis != 0.0:
                            warnings.append("SOURCE_OCCUPATION_VALUE_DIFFERS_FROM_ANALYSIS")
                    except (ValueError, KeyError, IndexError):
                        warnings.append("SELECTED_ATOM_OCCUPATION_NOT_RECONSTRUCTED")
        except (OSError, ValueError, UnicodeError) as exc:
            source_status = "NOT_ASSESSED"
            warnings.append(f"SOURCE_RECONSTRUCTION_FAILED:{type(exc).__name__}")
    if recorded_sha is None:
        warnings.append("RECORDED_OUTPUT_SHA256_MISSING")
    return OccupationProvenanceRecord(
        mode=mode,
        perturbed_site_id=perturbed_site_id,
        alpha_ev=alpha_ev,
        observed_site_index=observed_site_index,
        observed_site_id=observed_site_id,
        occupation_electron=occupation_electron,
        occupation_at_selected_block_electron=occupation_at_source,
        source_minus_analysis_occupation_electron=source_minus_analysis,
        run_folder=run_folder,
        file=output_relative,
        selected_block_line=line,
        selected_block_end_line=end_line,
        event_occurrence_index=occurrence,
        source_status=source_status,
        output_sha256_recorded=recorded_sha,
        output_sha256_observed=output_sha,
        traceability_warnings=tuple(sorted(set(warnings))),
        per_spin_occupation_e=per_spin_occupation,
        total_derived=total_derived,
    )


def reconstruct_occupation_provenance(
    dataset: Mapping[str, Any],
    *,
    campaign_root: str | Path,
    bare_profile: Siesta542PotentialShiftHamiltonianProfile | None = None,
) -> OccupationProvenance:
    """Resolve every stored reference/BARE/SCREENED value to its selected block.

    The selection policies are the same production policies used during
    analysis. A digest mismatch is recorded as a warning and never controls
    whether the occupation is included.
    """
    root = Path(campaign_root)
    profile = bare_profile or Siesta542PotentialShiftHamiltonianProfile()
    rows = dataset.get("rows")
    site_map = dataset.get("site_index_map")
    reference_source = dataset.get("reference_source")
    if (
        not isinstance(rows, list)
        or not isinstance(site_map, list)
        or not isinstance(reference_source, Mapping)
    ):
        return OccupationProvenance(
            OccupationProvenanceStatus.NOT_ASSESSED,
            str(root),
            (),
            ("RESPONSE_OBSERVATION_DATASET_INCOMPLETE",),
        )

    site_ids = {
        int(item["index"]): str(item["site_id"])
        for item in site_map
        if isinstance(item, Mapping) and "index" in item and "site_id" in item
    }
    atom_indices = {
        int(item["index"]): int(item["atom_index"])
        for item in site_map
        if isinstance(item, Mapping) and "index" in item and item.get("atom_index") is not None
    }
    records: list[OccupationProvenanceRecord] = []
    reasons: list[str] = []
    reference_added = False
    for row in rows:
        if not isinstance(row, Mapping):
            reasons.append("INVALID_RESPONSE_ROW")
            continue
        perturbed_site_id = str(row.get("perturbed_site_id", "")) or None
        alpha = row.get("alpha_eV")
        alpha_ev = float(alpha) if isinstance(alpha, (int, float)) else None
        observed_sites = row.get("observed_sites")
        if not isinstance(observed_sites, list):
            reasons.append("OBSERVED_SITES_MISSING")
            continue
        if not reference_added:
            for observed in observed_sites:
                if not isinstance(observed, Mapping):
                    continue
                index = int(observed.get("observed_site_index", -1))
                values = observed.get("occupations_electron")
                if (
                    index not in site_ids
                    or not isinstance(values, Mapping)
                    or not isinstance(values.get("reference"), (int, float))
                ):
                    reasons.append("REFERENCE_OCCUPATION_INCOMPLETE")
                    continue
                records.append(
                    _resolved_source(
                        root,
                        reference_source,
                        mode=str(reference_source.get("mode", "REFERENCE_SCREENED")),
                        perturbed_site_id=None,
                        alpha_ev=None,
                        observed_site_index=index,
                        observed_site_id=str(observed.get("observed_site_id", site_ids[index])),
                        atom_index=atom_indices.get(index),
                        occupation_electron=float(values["reference"]),
                        bare_profile=profile,
                    )
                )
            reference_added = True

        sources = row.get("sources")
        if not isinstance(sources, Mapping):
            reasons.append("RESPONSE_SOURCE_MAP_MISSING")
            continue
        for key, mode in (("bare", "BARE"), ("screened", "SCREENED")):
            source = sources.get(key)
            if not isinstance(source, Mapping):
                reasons.append(f"{mode}_SOURCE_MISSING")
                continue
            for observed in observed_sites:
                if not isinstance(observed, Mapping):
                    continue
                index = int(observed.get("observed_site_index", -1))
                values = observed.get("occupations_electron")
                if (
                    index not in site_ids
                    or not isinstance(values, Mapping)
                    or not isinstance(values.get(key), (int, float))
                ):
                    reasons.append(f"{mode}_OCCUPATION_INCOMPLETE")
                    continue
                records.append(
                    _resolved_source(
                        root,
                        source,
                        mode=mode,
                        perturbed_site_id=perturbed_site_id,
                        alpha_ev=alpha_ev,
                        observed_site_index=index,
                        observed_site_id=str(observed.get("observed_site_id", site_ids[index])),
                        atom_index=atom_indices.get(index),
                        occupation_electron=float(values[key]),
                        bare_profile=profile,
                    )
                )

    records.sort(
        key=lambda item: (
            item.mode,
            item.perturbed_site_id or "",
            item.alpha_ev if item.alpha_ev is not None else float("-inf"),
            item.observed_site_index,
        )
    )
    unresolved = any(record.source_status != "AVAILABLE" for record in records)
    status = (
        OccupationProvenanceStatus.NOT_ASSESSED
        if not records
        else OccupationProvenanceStatus.PARTIAL
        if unresolved or reasons
        else OccupationProvenanceStatus.AVAILABLE
    )
    return OccupationProvenance(status, str(root), tuple(records), tuple(sorted(set(reasons))))


def write_occupation_provenance(path: str | Path, provenance: OccupationProvenance) -> None:
    """Persist the reconstructed sidecar using the campaign's atomic JSON writer."""
    atomic_json(Path(path), provenance.to_mapping())


def rebuild_campaign_occupation_provenance(
    analysis_path: str | Path,
    *,
    campaign_root: str | Path,
) -> OccupationProvenance:
    """Rebuild a sidecar from a saved analysis dataset and retained SIESTA outputs."""
    try:
        analysis = json.loads(Path(analysis_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        analysis = {}
    dataset = analysis.get("response_observation_dataset") if isinstance(analysis, Mapping) else None
    if not isinstance(dataset, Mapping):
        result = OccupationProvenance(
            OccupationProvenanceStatus.NOT_ASSESSED,
            str(campaign_root),
            (),
            ("RESPONSE_OBSERVATION_DATASET_MISSING",),
        )
    else:
        result = reconstruct_occupation_provenance(dataset, campaign_root=campaign_root)
    write_occupation_provenance(
        Path(campaign_root) / "results" / "data" / "occupation_provenance.v1.json",
        result,
    )
    return result
