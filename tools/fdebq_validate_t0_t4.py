"""Check user-produced T0–T4 metrics; never invoke SIESTA or fabricate results."""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import cast

from hubbardflow.domain.response_budget_models import _Record
from hubbardflow.domain.scf_ladder_models import ScfLadderError, ScfLadderProtocol, ScfReason, ScfStatus
from hubbardflow.domain.scf_validation import (
    ValidationMetrics,
    ValidationProtocol,
    ValidationStatus,
    validate_t0_t4,
)
from hubbardflow.siesta_backend.output_validator import SiestaOutputValidationError, _normal_and_converged
from hubbardflow.siesta_backend.scf_ladder_inputs import validate_ladder_output
from tools.fdebq_scf_ladder_campaign import LadderReferenceReceipt, LadderRunReceipt


@dataclass(frozen=True)
class LadderValidationResult(_Record):
    status: ScfStatus
    reason_codes: tuple[ScfReason, ...]
    output_sha256: tuple[tuple[str, str], ...]


def validate_ladder_receipts(
    protocol: ScfLadderProtocol,
    receipts: Sequence[LadderRunReceipt],
    references: Sequence[LadderReferenceReceipt],
) -> LadderValidationResult:
    """Check archived user outputs against the frozen level/materialization receipts.

    Parent identity comes exclusively from the preparation receipt. A user's
    perturbed run may overwrite its DM; that output never becomes parent evidence.
    """
    if protocol.status is not ScfStatus.ESTABLISHED:
        return LadderValidationResult(ScfStatus.NOT_ESTABLISHED, protocol.reason_codes, ())
    levels = {level.level_id: level for level in protocol.levels}
    if len(references) != 3 or {r.level_id for r in references} != set(levels):
        raise ScfLadderError("NOT_ESTABLISHED: missing or duplicate level references")
    if not receipts:
        raise ScfLadderError("NOT_ESTABLISHED: no perturbed output receipts")
    reasons: set[ScfReason] = set()
    hashes: list[tuple[str, str]] = []
    reference_hashes: dict[str, tuple[str, str]] = {}
    for reference in references:
        directory = Path(reference.directory)
        fdf = directory / "input.fdf"
        digest = sha256(fdf.read_bytes()).hexdigest()
        if (
            reference.protocol_sha256 != protocol.digest
            or digest != reference.materialization.materialized_fdf_sha256
        ):
            raise ScfLadderError("NOT_ESTABLISHED: level reference input/protocol changed")
        checked = validate_ladder_output(
            directory / "siesta.out", levels[reference.level_id], reference_fdf=fdf
        )
        reasons.update(checked.reason_codes)
        hashes.append((str(directory / "siesta.out"), checked.output_sha256))
        reference_hashes[reference.level_id] = (digest, checked.output_sha256)
    parents: dict[str, set[str]] = {key: set() for key in levels}
    grids: dict[tuple[str, str, str], set[float]] = {}
    keys: set[tuple[str, str, str, float]] = set()
    for receipt in receipts:
        if receipt.level_id not in levels or receipt.protocol_sha256 != protocol.digest:
            raise ScfLadderError("NOT_ESTABLISHED: run level/protocol mismatch")
        level = levels[receipt.level_id]
        if receipt.dm_tolerance != level.dm_tolerance or receipt.h_tolerance_ev != level.h_tolerance_ev:
            raise ScfLadderError("NOT_ESTABLISHED: run tolerance/protocol mismatch")
        if (receipt.level_reference_fdf_sha256, receipt.level_reference_output_sha256) != reference_hashes[
            receipt.level_id
        ]:
            raise ScfLadderError("NOT_ESTABLISHED: run/reference identity changed")
        directory = Path(receipt.directory)
        if sha256((directory / "input.fdf").read_bytes()).hexdigest() != receipt.materialized_fdf_sha256:
            raise ScfLadderError("NOT_ESTABLISHED: materialized run input changed")
        key = (receipt.site_id, receipt.mode.value, receipt.level_id, receipt.alpha_ev)
        if key in keys:
            raise ScfLadderError("NOT_ESTABLISHED: duplicate run receipt")
        keys.add(key)
        grids.setdefault(key[:3], set()).add(receipt.alpha_ev)
        parents[receipt.level_id].add(receipt.parent_dm_sha256)
        checked = validate_ladder_output(directory / "siesta.out", level)
        reasons.update(checked.reason_codes)
        if receipt.mode.value == "SCREENED":
            try:
                _normal_and_converged(
                    (directory / "siesta.out").read_text(encoding="utf-8", errors="replace"),
                    require_convergence=True,
                )
            except SiestaOutputValidationError:
                reasons.add(ScfReason.SCF_UNDER_RESOLVED)
        hashes.append((str(directory / "siesta.out"), checked.output_sha256))
    groups = {(key[0], key[1]) for key in grids}
    for site, mode in sorted(groups):
        values = [grids.get((site, mode, level), set()) for level in sorted(levels)]
        if any(len(grid) != 4 or any(-a not in grid or a == 0 for a in grid) for grid in values) or any(
            grid != values[0] for grid in values[1:]
        ):
            raise ScfLadderError("NOT_ESTABLISHED: incomplete or differing level amplitude grids")
    if any(len(values) != 1 for values in parents.values()) or len(set.union(*parents.values())) != 3:
        reasons.add(ScfReason.PARENT_LEVEL_NOT_DISTINCT)
    ordered = tuple(sorted(reasons, key=lambda reason: reason.value))
    return LadderValidationResult(
        ScfStatus.NOT_ESTABLISHED if ordered else ScfStatus.ESTABLISHED, ordered, tuple(sorted(hashes))
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("protocol", type=Path)
    parser.add_argument("metrics", type=Path)
    parser.add_argument("--validate-ladder", action="store_true")
    parser.add_argument("--reference-receipt", type=Path)
    args = parser.parse_args(argv)
    if args.validate_ladder:
        if args.reference_receipt is None:
            parser.error("--validate-ladder requires --reference-receipt")
        ladder_protocol = ScfLadderProtocol.from_mapping(
            json.loads(args.protocol.read_text(encoding="utf-8"))
        )
        receipts = tuple(
            LadderRunReceipt.from_mapping(row) for row in json.loads(args.metrics.read_text(encoding="utf-8"))
        )
        references = tuple(
            LadderReferenceReceipt.from_mapping(row)
            for row in json.loads(args.reference_receipt.read_text(encoding="utf-8"))
        )
        checked = validate_ladder_receipts(ladder_protocol, receipts, references)
        print(json.dumps(checked.to_mapping(), sort_keys=True, allow_nan=False))
        return 0 if checked.status is ScfStatus.ESTABLISHED else 2
    protocol = ValidationProtocol.from_mapping(
        cast(Mapping[str, object], json.loads(args.protocol.read_text(encoding="utf-8")))
    )
    rows = json.loads(args.metrics.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        parser.error("metrics must be a JSON array of ValidationMetrics records")
    metrics = tuple(ValidationMetrics.from_mapping(row) for row in rows)
    result = validate_t0_t4(protocol, metrics)
    print(
        json.dumps(
            {"result": result.to_mapping(), "result_sha256": result.digest}, sort_keys=True, allow_nan=False
        )
    )
    return 0 if result.status is ValidationStatus.PASSED else 2


if __name__ == "__main__":
    raise SystemExit(main())
