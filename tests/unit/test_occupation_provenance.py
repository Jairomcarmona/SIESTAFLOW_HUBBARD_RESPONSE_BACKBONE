from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

from hubbardflow.execution.occupation_provenance import (
    OccupationProvenanceStatus,
    rebuild_campaign_occupation_provenance,
    reconstruct_occupation_provenance,
)
from hubbardflow.siesta_backend.siesta542_bare_profile import (
    Siesta542PotentialShiftHamiltonianProfile,
)

ROOT = Path(__file__).resolve().parents[2]
BARE_OUTPUT = ROOT / "examples" / "MnO_BARE_+0.05.out"


def screened_output() -> str:
    return """SCF Convergence by density criterion
Using DM_out to compute the final energy and forces
hubbard_term: recalculating local occupations 2
 hubbard_term: projector occupations
 hubbard_term: atom, species: 1 1
   1   1     1.00000     1.00000
Occupations:     1.00000    1.00000    2.00000
hubbard_term: recalculating Hamiltonian
Job completed
siesta: normal completion
"""


def _source(path: Path, *, recorded_sha: str | None = None) -> dict[str, str]:
    return {
        "out_path": path.relative_to(path.parents[1]).as_posix(),
        "out_sha256": recorded_sha or sha256(path.read_bytes()).hexdigest(),
    }


def test_reconstructs_mode_and_selected_one_based_block_lines(tmp_path: Path) -> None:
    bare_path = tmp_path / "run-bare" / "siesta.out"
    reference_path = tmp_path / "run-reference" / "siesta.out"
    screened_path = tmp_path / "run-screened" / "siesta.out"
    for path in (bare_path, reference_path, screened_path):
        path.parent.mkdir(parents=True)
    bare_path.write_bytes(BARE_OUTPUT.read_bytes())
    reference_path.write_text(screened_output(), encoding="utf-8")
    screened_path.write_text(screened_output(), encoding="utf-8")

    bare_selection = Siesta542PotentialShiftHamiltonianProfile().select_response(
        bare_path.read_text(encoding="utf-8")
    )
    dataset = {
        "schema_version": "siestaflow.lr_u_verified_dataset.v2",
        "site_index_map": [{"index": 0, "site_id": "MnLR00", "atom_index": 1}],
        "reference_source": {
            "mode": "REFERENCE_SCREENED",
            **_source(reference_path),
        },
        "rows": [
            {
                "perturbed_site_index": 0,
                "perturbed_site_id": "MnLR00",
                "alpha_eV": 0.05,
                "observed_sites": [
                    {
                        "observed_site_index": 0,
                        "observed_site_id": "MnLR00",
                        "occupations_electron": {
                            "reference": 2.0,
                            "bare": 2.1,
                            "screened": 2.2,
                        },
                    }
                ],
                "sources": {
                    "bare": _source(bare_path),
                    "screened": _source(screened_path),
                },
            }
        ],
    }

    provenance = reconstruct_occupation_provenance(dataset, campaign_root=tmp_path)

    assert provenance.status is OccupationProvenanceStatus.AVAILABLE
    by_mode = {
        record.mode: record
        for record in provenance.records
        if record.mode != "BARE" or record.alpha_ev == 0.05
    }
    bare_source_line = bare_selection.response_event.source_start_line
    assert bare_source_line is not None
    assert by_mode["BARE"].selected_block_line == bare_source_line + 1
    assert by_mode["BARE"].run_folder == "run-bare"
    assert by_mode["BARE"].file == "run-bare/siesta.out"
    assert by_mode["BARE"].occupation_at_selected_block_electron is not None
    assert by_mode["BARE"].source_minus_analysis_occupation_electron is not None
    assert by_mode["BARE"].source_minus_analysis_occupation_electron != 0.0
    assert "SOURCE_OCCUPATION_VALUE_DIFFERS_FROM_ANALYSIS" in by_mode["BARE"].traceability_warnings
    assert provenance.status is OccupationProvenanceStatus.AVAILABLE
    assert by_mode["SCREENED"].selected_block_line == 3
    assert by_mode["REFERENCE_SCREENED"].selected_block_line == 3


def test_digest_mismatch_is_warned_but_does_not_block_provenance(tmp_path: Path) -> None:
    bare_path = tmp_path / "bare" / "siesta.out"
    bare_path.parent.mkdir()
    bare_path.write_bytes(BARE_OUTPUT.read_bytes())
    screened_path = tmp_path / "screened" / "siesta.out"
    screened_path.parent.mkdir()
    screened_path.write_text(screened_output(), encoding="utf-8")
    dataset = {
        "site_index_map": [{"index": 0, "site_id": "MnLR00", "atom_index": 1}],
        "reference_source": {"mode": "REFERENCE_SCREENED", **_source(screened_path)},
        "rows": [
            {
                "perturbed_site_id": "MnLR00",
                "alpha_eV": 0.05,
                "observed_sites": [
                    {
                        "observed_site_index": 0,
                        "observed_site_id": "MnLR00",
                        "occupations_electron": {"reference": 2.0, "bare": 2.1, "screened": 2.2},
                    }
                ],
                "sources": {
                    "bare": _source(bare_path, recorded_sha="0" * 64),
                    "screened": _source(screened_path),
                },
            }
        ],
    }

    provenance = reconstruct_occupation_provenance(dataset, campaign_root=tmp_path)
    bare_record = next(record for record in provenance.records if record.mode == "BARE")

    assert provenance.status is OccupationProvenanceStatus.AVAILABLE
    assert "OUTPUT_SHA256_DIFFERS_FROM_RECORDED_VALUE" in bare_record.traceability_warnings
    assert bare_record.selected_block_line is not None


def test_campaign_report_rebuilds_sidecar_from_saved_analysis_and_logs(tmp_path: Path) -> None:
    bare_path = tmp_path / "run-bare" / "siesta.out"
    reference_path = tmp_path / "run-reference" / "siesta.out"
    screened_path = tmp_path / "run-screened" / "siesta.out"
    for path in (bare_path, reference_path, screened_path):
        path.parent.mkdir(parents=True)
    bare_path.write_bytes(BARE_OUTPUT.read_bytes())
    reference_path.write_text(screened_output(), encoding="utf-8")
    screened_path.write_text(screened_output(), encoding="utf-8")
    dataset = {
        "site_index_map": [{"index": 0, "site_id": "MnLR00", "atom_index": 1}],
        "reference_source": {"mode": "REFERENCE_SCREENED", **_source(reference_path)},
        "rows": [
            {
                "perturbed_site_id": "MnLR00",
                "alpha_eV": 0.05,
                "observed_sites": [
                    {
                        "observed_site_index": 0,
                        "observed_site_id": "MnLR00",
                        "occupations_electron": {"reference": 2.0, "bare": 2.1, "screened": 2.2},
                    }
                ],
                "sources": {"bare": _source(bare_path), "screened": _source(screened_path)},
            }
        ],
    }
    analysis_path = tmp_path / "results" / "lr_u_analysis.v3.json"
    analysis_path.parent.mkdir()
    analysis_path.write_text(json.dumps({"response_observation_dataset": dataset}), encoding="utf-8")

    provenance = rebuild_campaign_occupation_provenance(analysis_path, campaign_root=tmp_path)
    sidecar = json.loads((tmp_path / "results" / "data" / "occupation_provenance.v1.json").read_text())

    assert provenance.status is OccupationProvenanceStatus.AVAILABLE
    assert sidecar["hash_policy"] == "WARN_ONLY"
    assert sidecar["records"]
    assert all(item["selected_block_line"] is not None for item in sidecar["records"])
