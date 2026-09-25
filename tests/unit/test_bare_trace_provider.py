import json
from hashlib import sha256
from pathlib import Path

import pytest

from siestaflow_hubbard.siesta_backend.bare_trace_provider import (
    BareTraceProviderError,
    BareTraceRequest,
    NativeBareTraceProvider,
)
from siestaflow_hubbard.siesta_backend.bare_semantics_evidence import BareTraceExpectation


def _digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _request(tmp_path: Path) -> BareTraceRequest:
    executable = tmp_path / "siesta"
    dm = tmp_path / "reference.DM"
    fdf = tmp_path / "bare.fdf"
    output = tmp_path / "bare.out"
    trace = tmp_path / "bare.trace"
    executable.write_bytes(b"audited executable")
    dm.write_bytes(b"parent dm")
    fdf.write_text("SCF.MustConverge F\n", encoding="utf-8")
    output.write_text(
        "hubbard_term: recalculating local occupations\n>> End of run\n",
        encoding="utf-8",
    )
    markers = {
        "reference_dm_loaded": "TRACE: LR_BARE reference_dm_accepted",
        "selected_population": "TRACE: LR_BARE population_evaluated iscf=2 population_cycle=2",
        "perturbation_applied": "TRACE: LR_BARE perturbation_hamiltonian_built iscf=2 population_cycle=2",
        "hxc_rebuild_after_selected_population": "TRACE: LR_BARE hxc_rebuild_after_perturbation iscf=2",
    }
    trace.write_text("\n".join(markers.values()) + "\n", encoding="utf-8")
    sidecar = tmp_path / "bare_semantics.json"
    sidecar.write_text(
        json.dumps(
            {
                "schema_version": "siestaflow-bare-semantics-v2",
                "status": "PASS",
                "siesta_version": "5.4.2",
                "executable_sha256": _digest(executable),
                "source_revision": "audited-revision",
                "reference_dm_sha256": _digest(dm),
                "input_fdf_sha256": _digest(fdf),
                "bare_scf_must_converge_false": True,
                "output_sha256": _digest(output),
                "selected_event_lines": [1, 1],
                "hxc_rebuild_excluded_before_selected_event": True,
                "trace_reference": trace.name,
                "trace_sha256": _digest(trace),
                "trace_markers": markers,
            }
        ),
        encoding="utf-8",
    )
    return BareTraceRequest(
        sidecar, "5.4.2", executable, dm, fdf, output, (1, 1),
        BareTraceExpectation("audited-revision", markers),
    )


def test_provider_returns_receipt_only_for_hash_bound_native_trace(tmp_path: Path):
    receipt = NativeBareTraceProvider().validate(_request(tmp_path))
    assert receipt.status == "VERIFIED"
    assert len(receipt.evidence_sha256) == 64
    assert receipt.selected_event_lines == (1, 1)


def test_provider_rejects_artifact_substitution(tmp_path: Path):
    request = _request(tmp_path)
    request.executable_path.write_bytes(b"different executable")
    with pytest.raises(BareTraceProviderError, match="rejected"):
        NativeBareTraceProvider().validate(request)


def test_provider_rejects_missing_sidecar(tmp_path: Path):
    request = _request(tmp_path)
    request.sidecar_path.unlink()
    with pytest.raises(BareTraceProviderError, match="rejected"):
        NativeBareTraceProvider().validate(request)


def test_provider_never_fabricates_a_trace(tmp_path: Path):
    with pytest.raises(BareTraceProviderError, match="collection is unavailable"):
        NativeBareTraceProvider().collect(tmp_path / "would-be-evidence.json")
    assert not (tmp_path / "would-be-evidence.json").exists()
