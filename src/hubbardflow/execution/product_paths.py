"""Protect the complete frozen V6 inventory before any product sidecar write.

Named directories stay frozen even for files not in the manifest. Individual
manifest files and archive names are never usable as output directories, and
canonical sidecars cannot resolve onto a frozen file through an alias.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath, PureWindowsPath

from hubbardflow.domain.validation import require_sha256
from hubbardflow.execution.product_models import ProductError, V6ProtectionStatus

WORKSPACE: Path | None = None
PRODUCT_SIDECARS = (
    "product_plan.json",
    "product_campaign.lock",
    "resolved_perturbation_plan.json",
    "plan_report.md",
    "run_report.md",
    "submit_report.md",
)
_FROZEN_DIRECTORIES = (
    "validation_observables_v6",
    "results/stage-ub-v6-observables",
    "FEO_SCF_DIAGNOSTIC_EXPORT_20261001",
    "benchmarks/lr_u",
    "campaigns/nio_pbe_p5_20260928/results",
)


def _frozen_files(workspace: Path) -> tuple[Path, ...]:
    """Read the manifest as protected names, including the known moved absence."""
    manifest = workspace / "docs/history/SCIENTIFIC_BASELINE_V6.sha256"
    protected = {workspace / "FINAL_SIESTA_VALIDATION_REPORT_V6.md", manifest}
    try:
        rows = manifest.read_text(encoding="utf-8").splitlines()
        if not rows:
            raise ProductError("V6 manifest must contain the frozen inventory")
        for line in rows:
            digest, relative = line.split(maxsplit=1)
            require_sha256(digest, "V6 manifest digest")
            path = PurePosixPath(relative)
            if (
                path.is_absolute()
                or ".." in path.parts
                or not path.parts
                or PureWindowsPath(relative).anchor
                or ":" in relative
                or "\\" in relative
            ):
                raise ProductError("V6 manifest paths must remain inside the workspace")
            protected.add(workspace.joinpath(*path.parts))
    except (OSError, ValueError) as exc:
        raise ProductError(f"cannot establish frozen V6 destination protection: {exc}") from exc
    return tuple(sorted((p.resolve() for p in protected), key=str))


def _workspace_for(destination: Path) -> Path | None:
    for candidate in (destination, *destination.parents):
        if (candidate / "src/hubbardflow/__init__.py").is_file() or (
            candidate / "docs/history/SCIENTIFIC_BASELINE_V6.sha256"
        ).is_file():
            return candidate
    return None


def _same_or_descendant(path: Path, root: Path) -> bool:
    path_parts = tuple(part.casefold() for part in path.parts)
    root_parts = tuple(part.casefold() for part in root.parts)
    return len(path_parts) >= len(root_parts) and path_parts[: len(root_parts)] == root_parts


def _existing_ancestors(path: Path) -> tuple[Path, ...]:
    return tuple(candidate for candidate in (path, *path.parents) if candidate.exists())


def _same_inode(left: Path, right: Path) -> bool:
    try:
        left_stat = left.stat()
        right_stat = right.stat()
    except OSError:
        return False
    return (left_stat.st_dev, left_stat.st_ino) == (right_stat.st_dev, right_stat.st_ino)


def protect_product_destination(root: Path) -> V6ProtectionStatus:
    """Fail closed around a discovered checkout and report when no checkout is on-path."""
    destination = root.resolve()
    workspace = WORKSPACE.resolve() if WORKSPACE is not None else _workspace_for(destination)
    if workspace is None:
        return V6ProtectionStatus.NO_WORKSPACE_ON_PATH

    directories = tuple((workspace / path).resolve() for path in _FROZEN_DIRECTORIES)
    files = _frozen_files(workspace)
    frozen_roots = (*directories, *files)
    if any(_same_or_descendant(destination, path) for path in frozen_roots):
        raise ProductError("product output must stay outside frozen V6 paths")
    if _same_or_descendant(destination, workspace.resolve()) and any(
        part.casefold().startswith("production_benchmarks_v6.zip")
        for part in destination.relative_to(workspace.resolve()).parts
    ):
        raise ProductError("product output must stay outside frozen V6 archive paths")
    targets = {(destination / name).resolve() for name in PRODUCT_SIDECARS}
    if any(_same_or_descendant(target, path) for target in targets for path in frozen_roots):
        raise ProductError("product sidecar would overwrite a frozen V6 path")
    ancestor_paths = (
        *_existing_ancestors(destination),
        *(p for target in targets for p in _existing_ancestors(target)),
    )
    if any(_same_inode(ancestor, frozen) for ancestor in ancestor_paths for frozen in frozen_roots):
        raise ProductError("product output aliases a frozen V6 path")
    return V6ProtectionStatus.PROTECTED
