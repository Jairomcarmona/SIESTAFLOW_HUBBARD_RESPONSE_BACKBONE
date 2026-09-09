from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path

import pytest

from siestaflow_hubbard.siesta_backend.bare_semantics_evidence import (
    BareSemanticEvidenceError,
    verify_bare_semantics_evidence,
)
from siestaflow_hubbard.siesta_backend.observation_selector import Siesta542BarePolicyV1
from siestaflow_hubbard.siesta_backend.parser_models import HubbardPopulationEvent, ObservationContext, ObservationRole


def _digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _artifacts(tmp_path: Path):
    executable = tmp_path / "siesta"; executable.write_bytes(b"diagnostic-build")
    dm = tmp_path / "reference.DM"; dm.write_bytes(b"canonical-dm")
    output = tmp_path / "siesta.out"; output.write_text("one\nhubbard_term: recalculating local occupations\nthree\n")
    trace = tmp_path / "bare.trace"
    markers = {
        "reference_dm_loaded": "TRACE DM loaded",
        "perturbation_applied": "TRACE perturbation applied",
        "selected_population": "TRACE selected population",
        "hxc_rebuild_after_selected_population": "TRACE Hxc rebuild",
    }
    trace.write_text("\n".join(markers.values()) + "\n")
    sidecar = tmp_path / "bare_semantics.json"
    payload = {
        "schema_version": "siestaflow-bare-semantics-v1", "status": "PASS", "siesta_version": "5.4.2",
        "executable_sha256": _digest(executable), "source_revision": "audit-source-revision",
        "reference_dm_sha256": _digest(dm), "output_sha256": _digest(output),
        "selected_event_lines": [2, 2], "hxc_rebuild_excluded_before_selected_event": True,
        "trace_reference": trace.name, "trace_sha256": _digest(trace), "trace_markers": markers,
    }
    sidecar.write_text(json.dumps(payload))
    return executable, dm, output, trace, sidecar, payload


def _context(dm: Path) -> ObservationContext:
    return ObservationContext("5.4.2", "BARE", _digest(dm), "projector", "density", "Linear", 1.0, 2, False, None, None)


def test_verified_sidecar_binds_trace_output_dm_and_executable(tmp_path: Path):
    executable, dm, output, _, sidecar, _ = _artifacts(tmp_path)
    result = verify_bare_semantics_evidence(
        sidecar, siesta_version="5.4.2", executable_path=executable,
        reference_dm_path=dm, output_path=output, selected_event_lines=(2, 2),
    )
    assert result.evidence_reference.startswith("bare_semantics.json#")
    context = Siesta542BarePolicyV1.context_from_verified_bare_sidecar(
        _context(dm), sidecar_path=sidecar, executable_path=executable,
        reference_dm_path=dm, output_path=output, selected_event_lines=(2, 2),
    )
    assert context.bare_hxc_rebuild_excluded is True
    assert context.bare_semantics_evidence_ref == result.evidence_reference
    selection = Siesta542BarePolicyV1.get_verified_bare_observation(
        [HubbardPopulationEvent(1, 1, 1, ""), HubbardPopulationEvent(2, 2, 2, "")], context,
    )
    assert selection.role is ObservationRole.VERIFIED_BARE


def test_rejects_reordered_native_trace(tmp_path: Path):
    executable, dm, output, trace, sidecar, payload = _artifacts(tmp_path)
    trace.write_text("\n".join((payload["trace_markers"]["reference_dm_loaded"], payload["trace_markers"]["hxc_rebuild_after_selected_population"], payload["trace_markers"]["perturbation_applied"], payload["trace_markers"]["selected_population"])) + "\n")
    payload["trace_sha256"] = _digest(trace)
    sidecar.write_text(json.dumps(payload))
    with pytest.raises(BareSemanticEvidenceError, match="ordering"):
        verify_bare_semantics_evidence(sidecar, siesta_version="5.4.2", executable_path=executable, reference_dm_path=dm, output_path=output, selected_event_lines=(2, 2))


def test_rejects_output_substitution(tmp_path: Path):
    executable, dm, output, _, sidecar, _ = _artifacts(tmp_path)
    output.write_text("substituted output")
    with pytest.raises(BareSemanticEvidenceError, match="output_sha256"):
        verify_bare_semantics_evidence(sidecar, siesta_version="5.4.2", executable_path=executable, reference_dm_path=dm, output_path=output, selected_event_lines=(2, 2))
