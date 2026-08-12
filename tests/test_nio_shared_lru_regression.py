"""The generic core must regenerate the approved NiO FDF physics byte-for-byte."""
import json
from pathlib import Path

from lru_core import RUNS, build_atoms, render_fdf


ROOT = Path(__file__).resolve().parents[1]


def test_shared_core_preserves_all_frozen_nio_fdfs():
    config = json.loads((ROOT / "materials" / "NiO_PBE_SC222.json").read_text())
    atoms, _ = build_atoms(config)
    frozen = ROOT / "NIO_PBE_LRU_SC222_V1" / "runs"
    for run_id, mode, representative, alpha in RUNS:
        target = config["representatives"].get(representative) if representative else None
        regenerated = render_fdf(config, run_id, mode, target, alpha, atoms)
        assert regenerated == (frozen / run_id / "siesta.fdf").read_text()
