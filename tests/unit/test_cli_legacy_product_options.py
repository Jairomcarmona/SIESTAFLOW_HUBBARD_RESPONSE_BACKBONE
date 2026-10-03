import json
from pathlib import Path

import pytest
from _pytest.capture import CaptureFixture
from _pytest.monkeypatch import MonkeyPatch

from hubbardflow import cli
from hubbardflow.execution import campaign_runner


@pytest.mark.parametrize(
    ("option", "value"),
    [
        ("--lr-config", "protocol.json"),
        ("--reference-output", "reference.out"),
        ("--reference-dm", "parent.DM"),
        ("--coverage", "DIAGNOSTIC"),
        ("--alpha-strategy", "FIXED_PROTOCOL_GRID"),
        ("--identity-dir", "species"),
        ("--allow-spin-flip", None),
        ("--allow-rotations", None),
        ("--output-dir", "products"),
        ("--override-plan-state", "reason"),
    ],
)
def test_legacy_run_rejects_each_product_option(
    tmp_path: Path,
    capsys: CaptureFixture[str],
    monkeypatch: MonkeyPatch,
    option: str,
    value: str | None,
) -> None:
    manifest = tmp_path / "campaign.v2.json"
    manifest.write_text(json.dumps({"schema": "siestaflow.campaign.v2"}), encoding="utf-8")
    monkeypatch.setattr(
        campaign_runner,
        "run_campaign_worker",
        lambda *_args: pytest.fail("legacy worker must not be reached"),
    )

    arguments = ["run", str(manifest), option]
    if value is not None:
        arguments.append(value)

    assert cli.main(arguments) == 2
    assert option in capsys.readouterr().err
