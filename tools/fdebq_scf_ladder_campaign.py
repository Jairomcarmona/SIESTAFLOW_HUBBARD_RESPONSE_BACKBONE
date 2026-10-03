"""Prepare three user-run references, then ladders bound to each reference DM.

No executable is launched. Receipt hashes are captured before materialization;
a perturbed run's overwritten DM never replaces its parent identity.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Self

from hubbardflow.domain.response_budget_models import _Record
from hubbardflow.domain.scf_ladder_models import ScfLadderError, ScfLadderProtocol, ScfStatus
from hubbardflow.domain.symmetry_reduction import ResponseMode
from hubbardflow.domain.validation import require_fdf_representable_ev
from hubbardflow.siesta_backend.fdf_model import _one
from hubbardflow.siesta_backend.scf_ladder_inputs import (
    LadderMaterializedInput,
    bind_ladder_input,
    materialize_ladder_input,
    materialize_ladder_reference,
    validate_ladder_output,
)


@dataclass(frozen=True)
class LadderRunInput(_Record):
    site_id: str
    mode: ResponseMode
    alpha_ev: float
    source_fdf: str
    parent_dm: str
    assets: tuple[str, ...]
    level_id: str | None = None

    def __post_init__(self) -> None:
        super().__post_init__()
        require_fdf_representable_ev(self.alpha_ev, "alpha_ev")
        if self.alpha_ev == 0:
            raise ScfLadderError("ladder inputs must be nonzero perturbations, never alpha=0 replicas")

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> Self:
        historical = dict(payload)
        if "level_id" not in historical:
            historical["level_id"] = None
        return super().from_mapping(historical)


@dataclass(frozen=True)
class LadderReferenceInput(_Record):
    level_id: str
    source_fdf: str
    assets: tuple[str, ...]


@dataclass(frozen=True)
class LadderReferenceReceipt(_Record):
    directory: str
    level_id: str
    system_label: str
    materialization: LadderMaterializedInput
    protocol_sha256: str


@dataclass(frozen=True)
class LadderRunReceipt(_Record):
    directory: str
    site_id: str
    mode: ResponseMode
    alpha_ev: float
    level_id: str
    dm_tolerance: float
    h_tolerance_ev: float
    effective_source_fdf_sha256: str
    parent_dm_sha256: str
    level_reference_fdf_sha256: str
    level_reference_output_sha256: str
    materialized_fdf_sha256: str
    protocol_sha256: str
    effective_criteria: tuple[tuple[str, str | None], ...]


def _new_output(output: Path) -> Path:
    root = output.resolve()
    checkout = Path(__file__).resolve().parents[1]
    if root == checkout or checkout in root.parents or root.exists():
        raise ScfLadderError("output must be a new directory outside the checkout")
    return root


def _label(text: str) -> str:
    label = _one(text, "SystemLabel")
    if label is None or any(c in label for c in "/\\") or label in {".", ".."} or len(label.split()) != 1:
        raise ScfLadderError("one safe, explicit SystemLabel is required")
    return label


def _assets(names: tuple[str, ...], parent_name: str) -> tuple[Path, ...]:
    paths = tuple(Path(name).resolve() for name in names)
    basenames = [p.name.casefold() for p in paths] + [parent_name.casefold(), "input.fdf"]
    if len(set(basenames)) != len(basenames):
        raise ScfLadderError("asset basenames must be distinct from parent DM and input.fdf")
    for path in paths:
        if not path.is_file():
            raise ScfLadderError(f"missing required input asset: {path}")
    return paths


def build_ladder_references(
    inputs: Sequence[LadderReferenceInput], protocol: ScfLadderProtocol, output: Path
) -> tuple[LadderReferenceReceipt, ...]:
    """Materialize one independent zero-shift SCF reference per declared level."""
    protocol.require_evidence_v2()
    if not protocol.enabled:
        raise ScfLadderError("SCF_LADDER_DISABLED")
    root = _new_output(output)
    levels = {level.level_id: level for level in protocol.levels}
    if len(inputs) != 3 or {item.level_id for item in inputs} != set(levels):
        raise ScfLadderError("exactly one reference per protocol level is required")
    prepared = []
    for item in sorted(inputs, key=lambda item: item.level_id):
        materialized = materialize_ladder_reference(Path(item.source_fdf), levels[item.level_id])
        label = _label(materialized.effective_text)
        assets = _assets(item.assets, label + ".DM")
        prepared.append((item, materialized, label, assets))
    receipts = []
    for index, (item, materialized, label, assets) in enumerate(prepared):
        directory = root / f"reference-{index:02d}"
        directory.mkdir(parents=True)
        (directory / "input.fdf").write_bytes(materialized.effective_text.encode("utf-8"))
        for asset in assets:
            shutil.copyfile(asset, directory / asset.name)
        receipts.append(
            LadderReferenceReceipt(str(directory), item.level_id, label, materialized, protocol.digest)
        )
    (root / "scf_ladder_reference_receipt.json").write_text(
        json.dumps([row.to_mapping() for row in receipts], sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return tuple(receipts)


def build_ladder_runs(
    inputs: Sequence[LadderRunInput],
    protocol: ScfLadderProtocol,
    output: Path,
    references: Sequence[LadderReferenceReceipt] = (),
) -> tuple[LadderRunReceipt, ...]:
    """Bind every ±a to the converged reference of its own level, for either mode.

    Reference DM bytes are read and hashed here, before copying or any user run.
    BARE differences come from distinct parents, with MaxSCFIterations still one.
    """
    root = _new_output(output)
    ordered = sorted(inputs, key=lambda r: (r.site_id, r.mode.value, r.level_id or "", r.alpha_ev))

    # Inspect every source and required asset before rejecting legacy evidence.
    # This preserves the actionable safety error for unsafe or incomplete input.
    preflight: list[tuple[LadderRunInput, Path, tuple[Path, ...]]] = []
    for item in ordered:
        source = Path(item.source_fdf).resolve()
        parent = Path(item.parent_dm).resolve()
        binding = bind_ladder_input(source, item.site_id, item.mode, item.alpha_ev)
        text = binding.effective_text
        if (_one(text, "DM.UseSaveDM") or "").casefold() not in {"true", "t"}:
            raise ScfLadderError("input must explicitly declare DM.UseSaveDM true")
        if parent.suffix.lower() != ".dm":
            raise ScfLadderError("parent_dm must name the saved .DM file")
        label = _label(text)
        if parent.name != label + ".DM":
            raise ScfLadderError("parent DM basename must match the single explicit SystemLabel")
        if not parent.is_file():
            raise ScfLadderError(f"missing required input asset: {parent}")
        assets = _assets(item.assets, parent.name)
        preflight.append((item, parent, assets))

    keys = {(r.site_id, r.mode, r.level_id, r.alpha_ev) for r in ordered}
    if len(keys) != len(ordered) or not keys:
        raise ScfLadderError("ladder requests require distinct nonempty site/mode/level/alpha keys")
    input_groups = {(r.site_id, r.mode) for r in ordered}
    for site, mode in sorted(input_groups):
        amplitudes = {r.alpha_ev for r in ordered if (r.site_id, r.mode) == (site, mode)}
        if len(amplitudes) != 4 or any(-alpha not in amplitudes for alpha in amplitudes):
            raise ScfLadderError("each column/mode requires exactly two symmetric nonzero amplitudes")

    protocol.require_evidence_v2()
    if not protocol.enabled:
        raise ScfLadderError("SCF_LADDER_DISABLED")
    levels = {level.level_id: level for level in protocol.levels}
    if len(references) != 3 or {row.level_id for row in references} != set(levels):
        raise ScfLadderError("NOT_ESTABLISHED: exactly one produced reference per level is required")
    parents: dict[str, tuple[Path, bytes, LadderReferenceReceipt, str]] = {}
    for receipt in references:
        level = levels[receipt.level_id]
        directory = Path(receipt.directory).resolve()
        reference = directory / "input.fdf"
        if _label(reference.read_text(encoding="utf-8")) != receipt.system_label:
            raise ScfLadderError("NOT_ESTABLISHED: reference SystemLabel changed")
        if (
            receipt.protocol_sha256 != protocol.digest
            or receipt.materialization.level_id != level.level_id
            or receipt.materialization.dm_tolerance != level.dm_tolerance
            or receipt.materialization.h_tolerance_ev != level.h_tolerance_ev
            or hashlib.sha256(reference.read_bytes()).hexdigest()
            != receipt.materialization.materialized_fdf_sha256
        ):
            raise ScfLadderError("NOT_ESTABLISHED: reference receipt/input identity mismatch")
        checked = validate_ladder_output(directory / "siesta.out", level, reference_fdf=reference)
        if checked.status is not ScfStatus.ESTABLISHED:
            raise ScfLadderError(
                "NOT_ESTABLISHED: " + ",".join(reason.value for reason in checked.reason_codes)
            )
        parent = directory / (receipt.system_label + ".DM")
        data = parent.read_bytes()
        if not data:
            raise ScfLadderError("NOT_ESTABLISHED: reference output DM is empty")
        parents[level.level_id] = (parent, data, receipt, checked.output_sha256)
    if len({hashlib.sha256(data).hexdigest() for _, data, _, _ in parents.values()}) != 3:
        raise ScfLadderError("NOT_ESTABLISHED: PARENT_LEVEL_NOT_DISTINCT")
    keys = {(r.site_id, r.mode, r.level_id, r.alpha_ev) for r in ordered}
    if len(keys) != len(ordered) or not keys:
        raise ScfLadderError("ladder requests require distinct nonempty site/mode/level/alpha keys")
    groups = {(r.site_id, r.mode) for r in ordered}
    for site, mode in sorted(groups):
        grids = []
        for level_id in sorted(levels):
            alphas = {
                r.alpha_ev for r in ordered if (r.site_id, r.mode, r.level_id) == (site, mode, level_id)
            }
            if len(alphas) != 4 or any(-a not in alphas for a in alphas):
                raise ScfLadderError("each column/mode/level requires two symmetric nonzero amplitudes")
            grids.append(alphas)
        if any(grid != grids[0] for grid in grids[1:]):
            raise ScfLadderError("every level must use the same two amplitudes")
    prepared = []
    for item, parent, assets in preflight:
        if item.level_id not in levels:
            raise ScfLadderError("v2 inputs require an explicit protocol level_id")
        reference_parent, data, receipt, output_hash = parents[item.level_id]
        if parent != reference_parent:
            raise ScfLadderError("NOT_ESTABLISHED: declared parent is not the level reference output DM")
        materialized = materialize_ladder_input(
            Path(item.source_fdf), item.site_id, item.mode, item.alpha_ev, levels[item.level_id]
        )
        label = _label(materialized.effective_text)
        prepared.append((item, materialized, data, receipt, output_hash, label, assets))
    receipts = []
    for index, (item, materialized, data, reference_receipt, output_hash, label, assets) in enumerate(
        prepared
    ):
        directory = root / f"run-{index:04d}"
        directory.mkdir(parents=True)
        (directory / "input.fdf").write_bytes(materialized.effective_text.encode("utf-8"))
        (directory / (label + ".DM")).write_bytes(data)
        for asset in assets:
            shutil.copyfile(asset, directory / asset.name)
        receipts.append(
            LadderRunReceipt(
                str(directory),
                item.site_id,
                item.mode,
                item.alpha_ev,
                materialized.level_id,
                materialized.dm_tolerance,
                materialized.h_tolerance_ev,
                materialized.effective_source_fdf_sha256,
                hashlib.sha256(data).hexdigest(),
                reference_receipt.materialization.materialized_fdf_sha256,
                output_hash,
                materialized.materialized_fdf_sha256,
                protocol.digest,
                materialized.effective_criteria,
            )
        )
    (root / "scf_ladder_receipt.json").write_text(
        json.dumps([r.to_mapping() for r in receipts], sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return tuple(receipts)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("references", "runs"))
    parser.add_argument("protocol", type=Path)
    parser.add_argument("inputs", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--reference-receipt", type=Path)
    args = parser.parse_args(argv)
    protocol = ScfLadderProtocol.from_mapping(json.loads(args.protocol.read_text(encoding="utf-8")))
    rows = json.loads(args.inputs.read_text(encoding="utf-8"))
    if args.stage == "references":
        receipts: Sequence[_Record] = build_ladder_references(
            tuple(LadderReferenceInput.from_mapping(row) for row in rows), protocol, args.output
        )
    else:
        if args.reference_receipt is None:
            parser.error("runs requires --reference-receipt from the reference preparation stage")
        references = tuple(
            LadderReferenceReceipt.from_mapping(row)
            for row in json.loads(args.reference_receipt.read_text(encoding="utf-8"))
        )
        receipts = build_ladder_runs(
            tuple(LadderRunInput.from_mapping(row) for row in rows), protocol, args.output, references
        )
    print(json.dumps([r.to_mapping() for r in receipts], sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
