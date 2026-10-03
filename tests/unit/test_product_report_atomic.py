import os
from pathlib import Path

import pytest

from hubbardflow import product_cli


def test_product_report_replaces_existing_file_atomically(tmp_path: Path) -> None:
    report = tmp_path / "plan_report.md"
    report.write_text("old report", encoding="utf-8")

    product_cli._write_report_atomically(report, "complete new report\n")

    assert report.read_text(encoding="utf-8") == "complete new report\n"
    assert list(tmp_path.iterdir()) == [report]


def test_product_report_replace_failure_preserves_previous_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report = tmp_path / "plan_report.md"
    report.write_text("old report", encoding="utf-8")

    def fail_replace(_source: Path, _destination: Path) -> None:
        raise OSError("simulated replace failure")

    monkeypatch.setattr(os, "replace", fail_replace)
    with pytest.raises(OSError, match="simulated replace failure"):
        product_cli._write_report_atomically(report, "new report")

    assert report.read_text(encoding="utf-8") == "old report"
    assert list(tmp_path.iterdir()) == [report]
