from pathlib import Path

import pytest

from hubbardflow.execution.product_models import ProductError
from tools import hubbardflow_plan_diagnose


def test_diagnose_refuses_frozen_v6_output_before_opening_it(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = Path(__file__).resolve().parents[2]
    json_output = root / "FINAL_SIESTA_VALIDATION_REPORT_V6.md"
    markdown_output = tmp_path / "diagnostic.md"
    monkeypatch.setattr(
        "sys.argv",
        [
            "hubbardflow_plan_diagnose.py",
            str(root / "tests/fixtures/cu3n_reference_siesta.fdf"),
            "--reference-output",
            str(root / "tests/fixtures/cu3n_reference_siesta.fdf"),
            "--json",
            str(json_output),
            "--markdown",
            str(markdown_output),
        ],
    )

    with pytest.raises(ProductError, match="frozen V6"):
        hubbardflow_plan_diagnose.main()
    assert not markdown_output.exists()
