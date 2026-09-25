import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("mno_runner", ROOT / "tools/run_mno_afmii_strict_v3r2.py")
RUNNER = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(RUNNER)


def test_mno_preflight_reuses_canonical_foreground_slurm_contract():
    commands = RUNNER._foreground_commands()
    assert len(commands) == 5
    for command in commands:
        assert command[:4] == ["sbatch", "--wait", "--no-requeue", "--parsable"]
        assert "--export=NONE,OMP_NUM_THREADS=1" in command
