"""All named V6 directories, archive names and manifest files reject output writes."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path

import pytest

from hubbardflow.execution import product_paths
from hubbardflow.execution.product_models import ProductError
from hubbardflow.execution.product_paths import PRODUCT_SIDECARS, protect_product_destination

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    "path",
    [
        "validation_observables_v6",
        "results/stage-ub-v6-observables",
        "FEO_SCF_DIAGNOSTIC_EXPORT_20261001",
        "benchmarks/lr_u",
        "campaigns/nio_pbe_p5_20260928/results",
        "production_benchmarks_v6.zip",
        "production_benchmarks_v6.zip.part001",
        "production_benchmarks_v6.zip.sha256",
        "FINAL_SIESTA_VALIDATION_REPORT_V6.md",
    ],
)
@pytest.mark.parametrize("child", ["", "product-sidecars"])
def test_named_frozen_paths_and_descendants_are_rejected(path: str, child: str) -> None:
    with pytest.raises(ProductError, match="frozen V6"):
        protect_product_destination(ROOT / path / child)


def test_every_manifest_path_is_rejected_read_only(monkeypatch: pytest.MonkeyPatch) -> None:
    manifest = ROOT / "docs/history/SCIENTIFIC_BASELINE_V6.sha256"
    before = sha256(manifest.read_bytes()).hexdigest()
    frozen = product_paths._frozen_files(ROOT)
    # Reuse the unchanged read-only inventory while checking every destination.
    monkeypatch.setattr(product_paths, "_frozen_files", lambda _workspace: frozen)
    for line in manifest.read_text(encoding="utf-8").splitlines():
        _, relative = line.split(maxsplit=1)
        with pytest.raises(ProductError, match="frozen V6"):
            protect_product_destination(ROOT / relative)
    assert sha256(manifest.read_bytes()).hexdigest() == before


@pytest.mark.parametrize("sidecar", PRODUCT_SIDECARS)
def test_canonical_sidecar_cannot_equal_manifest_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    sidecar: str,
) -> None:
    manifest = tmp_path / "docs/history/SCIENTIFIC_BASELINE_V6.sha256"
    manifest.parent.mkdir(parents=True)
    protected = tmp_path / "campaign-output" / sidecar
    protected.parent.mkdir()
    protected.write_bytes(b"frozen fixture")
    manifest.write_text(
        f"{sha256(protected.read_bytes()).hexdigest()}  campaign-output/{sidecar}\n", encoding="utf-8"
    )
    monkeypatch.setattr(product_paths, "WORKSPACE", tmp_path)
    with pytest.raises(ProductError, match="sidecar would overwrite"):
        protect_product_destination(protected.parent)
    assert protected.read_bytes() == b"frozen fixture"


def test_unfrozen_workspace_outputs_remain_available(tmp_path: Path) -> None:
    protect_product_destination(ROOT)
    protect_product_destination(ROOT / ".hubbardflow" / "new-campaign")
    protect_product_destination(ROOT / "docs/fdebq/new-product-output")
    protect_product_destination(tmp_path / "user-selected-output")


def test_missing_manifest_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(product_paths, "WORKSPACE", tmp_path)
    with pytest.raises(ProductError, match="cannot establish frozen V6 destination protection"):
        protect_product_destination(tmp_path / "output")


@pytest.mark.parametrize("relative", ["../outside", "C:/outside", "C:outside", "..\\outside"])
def test_manifest_traversal_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, relative: str
) -> None:
    manifest = tmp_path / "docs/history/SCIENTIFIC_BASELINE_V6.sha256"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(f"{sha256(b'fixture').hexdigest()}  {relative}\n", encoding="utf-8")
    monkeypatch.setattr(product_paths, "WORKSPACE", tmp_path)
    with pytest.raises(ProductError, match="must remain inside the workspace"):
        protect_product_destination(tmp_path / "output")


def test_empty_manifest_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    manifest = tmp_path / "docs/history/SCIENTIFIC_BASELINE_V6.sha256"
    manifest.parent.mkdir(parents=True)
    manifest.write_bytes(b"")
    monkeypatch.setattr(product_paths, "WORKSPACE", tmp_path)
    with pytest.raises(ProductError, match="must contain the frozen inventory"):
        protect_product_destination(tmp_path / "output")
