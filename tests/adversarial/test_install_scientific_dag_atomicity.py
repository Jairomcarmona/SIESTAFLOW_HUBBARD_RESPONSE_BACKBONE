import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).parents[2]
INSTALLER = ROOT / "tools" / "install_scientific_dag.py"


def test_missing_algebra_entrypoint_fails_without_partial_install(tmp_path):
    campaign = tmp_path / "campaign"
    (campaign / "runs" / "00_REFERENCE").mkdir(parents=True)
    (campaign / "pseudopotentials").mkdir()
    (campaign / "scripts").mkdir()
    (campaign / "runs" / "manifest.json").write_text(
        json.dumps(
            [
                {"id": "00_REFERENCE", "mode": "REFERENCE"},
                {"id": "10_A_BARE_MINUS", "mode": "BARE", "target": "MnLR00"},
            ]
        ),
        encoding="utf-8",
    )
    (campaign / "runs" / "00_REFERENCE" / "siesta.fdf").write_text(
        "# archived reference placeholder\n", encoding="utf-8"
    )
    (campaign / "pseudopotentials" / "Mn.psml").write_text(
        '<psml><pseudo-atom-spec atomic-number="25"/></psml>\n', encoding="utf-8"
    )
    (campaign / "scripts" / "validate_run.py").write_text(
        "raise SystemExit('test fixture only')\n", encoding="utf-8"
    )

    completed = subprocess.run(
        [sys.executable, str(INSTALLER), "--campaign-root", str(campaign)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode != 0
    assert "analysis" in (completed.stdout + completed.stderr).lower() or "algebra" in (
        completed.stdout + completed.stderr
    ).lower()
    assert not (campaign / "scripts" / "siestaflow_dag").exists()
    assert not (campaign / "scripts" / "scientific_dag.json").exists()
    assert not (campaign / "slurm" / "submit_scientific_lru_dag.slurm").exists()
    assert not (campaign / "slurm" / "site_profile.local.example").exists()
