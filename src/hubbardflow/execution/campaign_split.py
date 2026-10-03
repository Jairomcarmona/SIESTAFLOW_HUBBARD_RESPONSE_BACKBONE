"""TASK15 campaign admission stages opt-in aliases and stops before physics.

Staged reference ions prove preservation of inputs only. The versioned manifest
binds the opt-in and every staged byte; it is not a production campaign manifest.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import cast

from hubbardflow.domain.validation import require_sha256
from hubbardflow.execution.product_paths import protect_product_destination
from hubbardflow.siesta_backend.fdf_model import parse_effective_fdf
from hubbardflow.siesta_backend.semantic_species_split import materialize_semantic_split_species_fdf
from hubbardflow.siesta_backend.semantic_split_models import (
    SemanticSpeciesSplitError,
    SemanticSpeciesSplitPolicy,
    SemanticSpeciesSplitResult,
    SemanticSplitCode,
    SemanticSplitStatus,
)

MANIFEST_NAME = "species_split_staging.json"


@dataclass(frozen=True)
class CampaignSplitStaging:
    policy: SemanticSpeciesSplitPolicy
    source_fdf_sha256: str
    splits: tuple[tuple[str, SemanticSpeciesSplitResult], ...]
    input_files: tuple[tuple[str, str], ...]
    status: SemanticSplitStatus = SemanticSplitStatus.STAGED_PENDING_GENERATED_IDENTITY

    def __post_init__(self) -> None:
        if (
            not isinstance(self.policy, SemanticSpeciesSplitPolicy)
            or not isinstance(self.splits, tuple)
            or not isinstance(self.input_files, tuple)
        ):
            raise SemanticSpeciesSplitError(
                SemanticSplitCode.INVALID_SPLIT_INPUT, "typed policy and immutable staging records required"
            )
        try:
            require_sha256(self.source_fdf_sha256, "split source FDF")
            for _, digest in self.input_files:
                require_sha256(digest, "staged input")
        except ValueError as exc:
            raise SemanticSpeciesSplitError(SemanticSplitCode.INVALID_SPLIT_INPUT, str(exc)) from exc
        if (
            not self.policy.auto_split_species
            or not self.splits
            or self.status is not SemanticSplitStatus.STAGED_PENDING_GENERATED_IDENTITY
            or tuple(label for label, _ in self.splits) != tuple(sorted({label for label, _ in self.splits}))
        ):
            raise SemanticSpeciesSplitError(SemanticSplitCode.INVALID_SPLIT_INPUT, "invalid pending staging")
        for _, result in self.splits:
            if result.policy_digest != self.policy.digest:
                raise SemanticSpeciesSplitError(
                    SemanticSplitCode.INVALID_SPLIT_INPUT, "split policy mismatch"
                )
        paths = tuple(path for path, _ in self.input_files)
        if paths != tuple(sorted(set(paths))) or "reference.fdf" not in paths:
            raise SemanticSpeciesSplitError(SemanticSplitCode.INVALID_SPLIT_INPUT, "invalid staged file set")
        for path, digest in self.input_files:
            if Path(path).name != path or path in {".", "..", MANIFEST_NAME} or "\\" in path:
                raise SemanticSpeciesSplitError(SemanticSplitCode.INVALID_SPLIT_INPUT, "unsafe staged file")

    def to_mapping(self) -> dict[str, object]:
        return {
            "schema": "hubbardflow.species_split_staging.v1",
            "status": self.status.value,
            "policy": self.policy.to_mapping(),
            "policy_digest": self.policy.digest,
            "source_fdf_sha256": self.source_fdf_sha256,
            "splits": [
                {"original_label": label, "result": result.to_mapping()} for label, result in self.splits
            ],
            "input_files": [{"path": path, "sha256": digest} for path, digest in self.input_files],
        }

    @classmethod
    def from_mapping(cls, row: Mapping[str, object]) -> CampaignSplitStaging:
        try:
            if set(row) != {
                "schema",
                "status",
                "policy",
                "policy_digest",
                "source_fdf_sha256",
                "splits",
                "input_files",
            }:
                raise ValueError("unexpected staging fields")
            policy = SemanticSpeciesSplitPolicy.from_mapping(cast(Mapping[str, object], row["policy"]))
            if (
                row["schema"] != "hubbardflow.species_split_staging.v1"
                or row["policy_digest"] != policy.digest
            ):
                raise ValueError("staging schema/policy digest mismatch")
            return cls(
                policy,
                cast(str, row["source_fdf_sha256"]),
                tuple(
                    (
                        cast(str, entry["original_label"]),
                        SemanticSpeciesSplitResult.from_mapping(cast(Mapping[str, object], entry["result"])),
                    )
                    for entry in cast(Sequence[Mapping[str, object]], row["splits"])
                ),
                tuple(
                    (cast(str, entry["path"]), cast(str, entry["sha256"]))
                    for entry in cast(Sequence[Mapping[str, object]], row["input_files"])
                ),
                SemanticSplitStatus(cast(str, row["status"])),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise SemanticSpeciesSplitError(SemanticSplitCode.INVALID_SPLIT_INPUT, str(exc)) from exc

    @property
    def digest(self) -> str:
        return sha256(_json(self.to_mapping()).encode()).hexdigest()


def _json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def stage_campaign_split(
    source_fdf: Path,
    config: Mapping[str, object],
    root: Path,
    *,
    identity_dirs: Sequence[Path] = (),
) -> CampaignSplitStaging | None:
    """Stage shared correlated labels on explicit opt-in; OFF performs no I/O.

    Every target is preflighted before copying the final input set. No campaign
    v2 manifest, lock permitting execution, or generated identity is created.
    """
    flag = config.get("auto_split_species", False)
    if type(flag) is not bool:
        raise SemanticSpeciesSplitError(
            SemanticSplitCode.INVALID_SPLIT_INPUT, "auto_split_species must be boolean"
        )
    if not flag:
        return None
    try:
        _json(dict(config))
    except (TypeError, ValueError) as exc:
        raise SemanticSpeciesSplitError(
            SemanticSplitCode.INVALID_SPLIT_INPUT, f"split configuration must be finite JSON: {exc}"
        ) from exc
    policy = SemanticSpeciesSplitPolicy(auto_split_species=True)
    model = parse_effective_fdf(source_fdf)
    labels = tuple(
        sorted(
            record.label
            for record in model.dftu_records
            if sum(atom.species_label == record.label for atom in model.atoms) > 1
        )
    )
    if not labels:
        return None
    destination = root / "species_split"
    protect_product_destination(destination)
    if destination.exists():
        raise SemanticSpeciesSplitError(
            SemanticSplitCode.INVALID_SPLIT_INPUT, "staging directory already exists"
        )
    dirs = {source_fdf.parent, *identity_dirs}
    for field in ("pseudopotentials", "static_artifacts"):
        for value in cast(Mapping[str, str], config.get(field, {})).values():
            dirs.add(Path(value).parent)
    with TemporaryDirectory(prefix="hubbardflow-campaign-split-") as temporary:
        temp = Path(temporary)
        current = source_fdf
        splits: list[tuple[str, SemanticSpeciesSplitResult]] = []
        for label in labels:
            output = temp / label
            result = materialize_semantic_split_species_fdf(
                current, label, f"{label}LR", output, tuple(sorted(dirs, key=str)), policy=policy
            )
            splits.append((label, result))
            dirs.add(output)
            current = output / "split-species.fdf"
        final = parse_effective_fdf(current)
        if final.dm_init_spin != model.dm_init_spin or any(
            record.label in labels for record in final.dftu_records
        ):
            raise SemanticSpeciesSplitError(
                SemanticSplitCode.INVALID_SPLIT_INPUT, "spin changed or orphan DFTU record"
            )
        blobs: dict[str, bytes] = {"reference.fdf": current.read_bytes()}
        for species in final.chemical_species_labels:
            for suffix in (".psml", ".psf", ".vps", ".ion"):
                name = f"{species.label}{suffix}"
                matches = tuple(
                    sorted(
                        {(directory / name).resolve() for directory in dirs if (directory / name).is_file()},
                        key=str,
                    )
                )
                payloads = {path.read_bytes() for path in matches}
                if len(payloads) > 1:
                    raise SemanticSpeciesSplitError(
                        SemanticSplitCode.SPECIES_IDENTITY_NOT_ESTABLISHED, f"conflicting {name}"
                    )
                if payloads:
                    blobs[name] = next(iter(payloads))
        staged = CampaignSplitStaging(
            policy,
            model.effective_fdf_sha256,
            tuple(splits),
            tuple((name, sha256(data).hexdigest()) for name, data in sorted(blobs.items())),
        )
        destination.mkdir(parents=True)
        for name, data in sorted(blobs.items()):
            target = destination / name
            protect_product_destination(target)
            with target.open("xb") as stream:
                stream.write(data)
        with (destination / MANIFEST_NAME).open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(_json(staged.to_mapping()) + "\n")
        return staged


def verify_campaign_split_staging(root: Path, expected: CampaignSplitStaging) -> None:
    """Resume checks every staged input; a generated receipt cannot relax this gate."""
    try:
        destination = root / "species_split"
        row = json.loads((destination / MANIFEST_NAME).read_text(encoding="utf-8"))
        if CampaignSplitStaging.from_mapping(row) != expected:
            raise ValueError("staging manifest changed")
        if any(
            sha256((destination / path).read_bytes()).hexdigest() != digest
            for path, digest in expected.input_files
        ):
            raise ValueError("staged input bytes changed")
    except (OSError, TypeError, ValueError) as exc:
        raise SemanticSpeciesSplitError(
            SemanticSplitCode.SPECIES_IDENTITY_NOT_ESTABLISHED, f"cannot resume split staging: {exc}"
        ) from exc
