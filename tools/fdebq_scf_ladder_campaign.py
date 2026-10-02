"""Materialize same-parent SCF tolerance ladders from existing ±a inputs.

Only DM.Tolerance changes between levels. Every request explicitly lists the
parent DM and required assets. Outputs must lie outside the source checkout;
the user runs SIESTA separately. No executable is launched here.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from hubbardflow.domain.response_budget_models import _Record
from hubbardflow.domain.scf_ladder_models import ScfLadderError, ScfLadderProtocol
from hubbardflow.domain.symmetry_reduction import ResponseMode
from hubbardflow.domain.validation import require_fdf_representable_ev
from hubbardflow.siesta_backend.scf_ladder_inputs import bind_ladder_input


@dataclass(frozen=True)
class LadderRunInput(_Record):
    site_id: str
    mode: ResponseMode
    alpha_ev: float
    source_fdf: str
    parent_dm: str
    assets: tuple[str, ...]

    def __post_init__(self) -> None:
        super().__post_init__()
        require_fdf_representable_ev(self.alpha_ev, "alpha_ev")
        if self.alpha_ev == 0:
            raise ScfLadderError("ladder inputs must be nonzero perturbations, never alpha=0 replicas")


@dataclass(frozen=True)
class LadderRunReceipt(_Record):
    directory: str
    site_id: str
    mode: ResponseMode
    alpha_ev: float
    level_id: str
    dm_tolerance: float
    effective_source_fdf_sha256: str
    parent_dm_sha256: str
    materialized_fdf_sha256: str
    protocol_sha256: str


def build_ladder_runs(
    inputs: Sequence[LadderRunInput], protocol: ScfLadderProtocol, output: Path
) -> tuple[LadderRunReceipt, ...]:
    """Prepare twelve runs per column/mode with an identical parent DM.

    Sources must already encode the exact requested site/mode/alpha. The
    receipt binds their effective FDF identity; TASK13 reuse validation remains
    responsible for backend and scientific provenance on production admission.
    """
    if not protocol.enabled:
        raise ScfLadderError("SCF_LADDER_DISABLED")
    root = output.resolve()
    checkout = Path(__file__).resolve().parents[1]
    if root == checkout or checkout in root.parents or root.exists():
        raise ScfLadderError("output must be a new directory outside the checkout")
    ordered = sorted(inputs, key=lambda r: (r.site_id, r.mode.value, r.alpha_ev))
    keys = {(r.site_id, r.mode, r.alpha_ev) for r in ordered}
    if len(keys) != len(ordered) or not keys:
        raise ScfLadderError("ladder requests require distinct nonempty site/mode/alpha keys")
    groups = {(r.site_id, r.mode) for r in ordered}
    for site, mode in sorted(groups):
        alphas = {r.alpha_ev for r in ordered if (r.site_id, r.mode) == (site, mode)}
        if len(alphas) != 4 or any(-a not in alphas for a in alphas):
            raise ScfLadderError("each column/mode requires exactly two symmetric nonzero amplitudes")
    prepared = []
    for item in ordered:
        source, parent = Path(item.source_fdf).resolve(), Path(item.parent_dm).resolve()
        binding = bind_ladder_input(source, item.site_id, item.mode, item.alpha_ev)
        text = binding.effective_text
        if re.search(r"(?im)^\s*File\.DM\.Init\b", text):
            raise ScfLadderError("File.DM.Init is prohibited; supply DM.UseSaveDM true")
        if not re.search(r"(?im)^\s*DM\.UseSaveDM\s+true\s*(?:[#;!].*)?$", text):
            raise ScfLadderError("input must explicitly declare DM.UseSaveDM true")
        if parent.suffix.lower() != ".dm":
            raise ScfLadderError("parent_dm must name the saved .DM file")
        labels = re.findall(r"(?im)^\s*SystemLabel\s+(\S+)\s*(?:[#;!].*)?$", text)
        if len(labels) != 1 or parent.name != labels[0] + ".DM":
            raise ScfLadderError("parent DM basename must match the single explicit SystemLabel")
        assets = tuple(Path(asset).resolve() for asset in item.assets)
        names = [p.name.casefold() for p in assets] + [parent.name.casefold(), "input.fdf"]
        if len(set(names)) != len(names):
            raise ScfLadderError("asset basenames must be distinct from parent DM and input.fdf")
        for path in (parent, *assets):
            if not path.is_file():
                raise ScfLadderError(f"missing required input asset: {path}")
        prepared.append((item, text, parent, assets))
    if len({hashlib.sha256(parent.read_bytes()).hexdigest() for _, _, parent, _ in prepared}) != 1:
        raise ScfLadderError("all ladder runs must preserve the same parent DM identity")
    # All validation precedes materialization. No existing path is overwritten.
    receipts = []
    for index, (item, text, parent, assets) in enumerate(prepared):
        for level_index, level in enumerate(protocol.levels):
            directory = root / f"run-{index:04d}-level-{level_index}"
            directory.mkdir(parents=True)
            materialized = (
                re.sub(r"(?im)^\s*DM\.Tolerance\b[^\r\n]*", "", text).rstrip()
                + f"\nDM.Tolerance {level.dm_tolerance!r}\n"
            )
            (directory / "input.fdf").write_text(materialized, encoding="utf-8")
            for asset in (parent, *assets):
                shutil.copyfile(asset, directory / asset.name)
            receipts.append(
                LadderRunReceipt(
                    str(directory),
                    item.site_id,
                    item.mode,
                    item.alpha_ev,
                    level.level_id,
                    level.dm_tolerance,
                    hashlib.sha256(text.encode()).hexdigest(),
                    hashlib.sha256(parent.read_bytes()).hexdigest(),
                    hashlib.sha256(materialized.encode()).hexdigest(),
                    protocol.digest,
                )
            )
    (root / "scf_ladder_receipt.json").write_text(
        json.dumps([r.to_mapping() for r in receipts], sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return tuple(receipts)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("protocol", type=Path)
    parser.add_argument("inputs", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args(argv)
    protocol = ScfLadderProtocol.from_mapping(json.loads(args.protocol.read_text(encoding="utf-8")))
    inputs = tuple(
        LadderRunInput.from_mapping(row) for row in json.loads(args.inputs.read_text(encoding="utf-8"))
    )
    receipts = build_ladder_runs(inputs, protocol, args.output)
    print(json.dumps([r.to_mapping() for r in receipts], sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
