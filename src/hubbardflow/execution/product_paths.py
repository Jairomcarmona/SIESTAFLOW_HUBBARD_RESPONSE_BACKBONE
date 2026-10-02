"""Protect the complete frozen V6 inventory before any product sidecar write.

Named directories stay frozen even for files not in the manifest. Individual
manifest files and archive names are never usable as output directories, and
canonical sidecars cannot resolve onto a frozen file through an alias.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath

from hubbardflow.domain.validation import require_sha256
from hubbardflow.execution.product_models import ProductError

WORKSPACE = Path(__file__).resolve().parents[3]
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


def _frozen_files() -> tuple[Path, ...]:
    """Read the manifest as protected names, including the known moved absence."""
    manifest = WORKSPACE / "docs/history/SCIENTIFIC_BASELINE_V6.sha256"
    protected = {WORKSPACE / "FINAL_SIESTA_VALIDATION_REPORT_V6.md", manifest}
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
                or Path(relative).drive
                or "\\" in relative
            ):
                raise ProductError("V6 manifest paths must remain inside the workspace")
            protected.add(WORKSPACE.joinpath(*path.parts))
    except (OSError, ValueError) as exc:
        raise ProductError(f"cannot establish frozen V6 destination protection: {exc}") from exc
    return tuple(sorted((p.resolve() for p in protected), key=str))


def protect_product_destination(root: Path) -> None:
    """Fail closed for every AGENTS directory/file and manifest-sidecar collision."""
    destination = root.resolve()
    directories = tuple((WORKSPACE / path).resolve() for path in _FROZEN_DIRECTORIES)
    files = _frozen_files()
    if any(destination.is_relative_to(path) for path in (*directories, *files)):
        raise ProductError("product output must stay outside frozen V6 paths")
    if destination.is_relative_to(WORKSPACE.resolve()) and any(
        part.casefold().startswith("production_benchmarks_v6.zip")
        for part in destination.relative_to(WORKSPACE.resolve()).parts
    ):
        raise ProductError("product output must stay outside frozen V6 archive paths")
    targets = {(destination / name).resolve() for name in PRODUCT_SIDECARS}
    if targets.intersection(files) or any(
        target.is_relative_to(path) for target in targets for path in directories
    ):
        raise ProductError("product sidecar would overwrite a frozen V6 path")
