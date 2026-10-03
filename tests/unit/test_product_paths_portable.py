from hashlib import sha256
from pathlib import Path

import pytest

from hubbardflow.domain.perturbation_plan import PlanStatus
from hubbardflow.execution import product_paths
from hubbardflow.execution.product_models import (
    ProductBoundary,
    ProductCommand,
    ProductError,
    V6ProtectionStatus,
)


@pytest.mark.parametrize(
    "relative",
    [
        "VALIDATION_OBSERVABLES_V6/x",
        "Validation_Observables_V6",
        "benchmarks/LR_U",
        "results/Stage-UB-V6-Observables",
        "FINAL_SIESTA_VALIDATION_REPORT_v6.md",
    ],
)
def test_frozen_paths_compare_case_insensitively(
    relative: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = Path(__file__).resolve().parents[2]
    monkeypatch.setattr(product_paths, "WORKSPACE", None)
    with pytest.raises(ProductError, match="frozen V6"):
        product_paths.protect_product_destination(root / relative)


def test_no_workspace_on_destination_path_is_reported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(product_paths, "WORKSPACE", None)
    assert product_paths.protect_product_destination(tmp_path / "new-output") is (
        V6ProtectionStatus.NO_WORKSPACE_ON_PATH
    )


def test_no_workspace_protection_state_round_trips_in_receipt() -> None:
    receipt = ProductBoundary(
        ProductCommand.RUN,
        "a" * 64,
        None,
        PlanStatus.NOT_ESTABLISHED,
        (),
        None,
        None,
        None,
        V6ProtectionStatus.NO_WORKSPACE_ON_PATH,
    )
    mapped = receipt.to_mapping()
    assert mapped["v6_protection"] == "NO_WORKSPACE_ON_PATH"
    assert ProductBoundary.from_mapping(mapped) == receipt


def test_existing_hard_link_to_frozen_file_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = tmp_path / "docs/history/SCIENTIFIC_BASELINE_V6.sha256"
    frozen = tmp_path / "frozen.dat"
    frozen.write_bytes(b"frozen bytes")
    manifest.parent.mkdir(parents=True)
    manifest.write_text(f"{sha256(frozen.read_bytes()).hexdigest()}  frozen.dat\n", encoding="utf-8")
    monkeypatch.setattr(product_paths, "WORKSPACE", tmp_path)
    destination = tmp_path / "output"
    destination.mkdir()
    try:
        (destination / "product_plan.json").hardlink_to(frozen)
    except (OSError, NotImplementedError):
        pytest.skip("hard links are unavailable on this filesystem")

    with pytest.raises(ProductError, match="aliases a frozen V6 path"):
        product_paths.protect_product_destination(destination)
