from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path

import pytest

from siestaflow_hubbard.siesta_backend.bare_semantics_evidence import (
    BareTraceExpectation,
    BareSemanticEvidenceError,
    verify_bare_semantics_evidence,
    write_bare_semantics_sidecar,
)
from siestaflow_hubbard.siesta_backend.observation_selector import Siesta542BarePolicyV1
from siestaflow_hubbard.siesta_backend.parser_models import HubbardPopulationEvent, ObservationContext, ObservationRole


def _digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _artifacts(tmp_path: Path):
    executable = tmp_path / "siesta"; executable.write_bytes(b"diagnostic-build")
    dm = tmp_path / "reference.DM"; dm.write_bytes(b"canonical-dm")
    fdf = tmp_path / "siesta.fdf"; fdf.write_text("SCF.MustConverge F\n")
    output = tmp_path / "siesta.out"; output.write_text(
        "one\nhubbard_term: recalculating local occupations\n>> End of run\n"
    )
    trace = tmp_path / "bare.trace"
    markers = {
        "reference_dm_loaded": "TRACE DM loaded",
        "perturbation_applied": "TRACE perturbation applied",
        "selected_population": "TRACE selected population",
        "hxc_rebuild_after_selected_population": "TRACE Hxc rebuild",
    }
    trace.write_text("\n".join(markers[key] for key in (
        "reference_dm_loaded", "selected_population", "perturbation_applied",
        "hxc_rebuild_after_selected_population",
    )) + "\n")
    sidecar = tmp_path / "bare_semantics.json"
    payload = {
        "schema_version": "siestaflow-bare-semantics-v2", "status": "PASS", "siesta_version": "5.4.2",
        "executable_sha256": _digest(executable), "source_revision": "audit-source-revision",
        "reference_dm_sha256": _digest(dm), "input_fdf_sha256": _digest(fdf),
        "bare_scf_must_converge_false": True, "output_sha256": _digest(output),
        "selected_event_lines": [2, 2], "hxc_rebuild_excluded_before_selected_event": True,
        "trace_reference": trace.name, "trace_sha256": _digest(trace), "trace_markers": markers,
    }
    sidecar.write_text(json.dumps(payload))
    return executable, dm, fdf, output, trace, sidecar, payload


def _context(dm: Path) -> ObservationContext:
    return ObservationContext("5.4.2", "BARE", _digest(dm), "projector", "density", "Linear", 1.0, 2, False, None, None)


def _expectation(payload: dict) -> BareTraceExpectation:
    return BareTraceExpectation(payload["source_revision"], payload["trace_markers"])


def test_verified_sidecar_binds_trace_output_dm_and_executable(tmp_path: Path):
    executable, dm, fdf, output, _, sidecar, payload = _artifacts(tmp_path)
    result = verify_bare_semantics_evidence(
        sidecar, siesta_version="5.4.2", executable_path=executable,
        reference_dm_path=dm, input_fdf_path=fdf, output_path=output, selected_event_lines=(2, 2),
        expectation=_expectation(payload),
    )
    assert result.evidence_reference.startswith("bare_semantics.json#")
    context = Siesta542BarePolicyV1.context_from_verified_bare_sidecar(
        _context(dm), sidecar_path=sidecar, executable_path=executable,
        reference_dm_path=dm, input_fdf_path=fdf, output_path=output, selected_event_lines=(2, 2),
        bare_trace_expectation=_expectation(payload),
    )
    assert context.bare_hxc_rebuild_excluded is True
    assert context.bare_semantics_evidence_ref == result.evidence_reference
    selection = Siesta542BarePolicyV1.get_verified_bare_observation(
        [HubbardPopulationEvent(1, 1, 1, ""), HubbardPopulationEvent(2, 2, 2, "")], context,
    )
    assert selection.role is ObservationRole.VERIFIED_BARE


def test_rejects_reordered_native_trace(tmp_path: Path):
    executable, dm, fdf, output, trace, sidecar, payload = _artifacts(tmp_path)
    trace.write_text("\n".join((payload["trace_markers"]["reference_dm_loaded"], payload["trace_markers"]["hxc_rebuild_after_selected_population"], payload["trace_markers"]["perturbation_applied"], payload["trace_markers"]["selected_population"])) + "\n")
    payload["trace_sha256"] = _digest(trace)
    sidecar.write_text(json.dumps(payload))
    with pytest.raises(BareSemanticEvidenceError, match="ordering"):
        verify_bare_semantics_evidence(sidecar, siesta_version="5.4.2", executable_path=executable, reference_dm_path=dm, input_fdf_path=fdf, output_path=output, selected_event_lines=(2, 2), expectation=_expectation(payload))


def test_rejects_output_substitution(tmp_path: Path):
    executable, dm, fdf, output, _, sidecar, payload = _artifacts(tmp_path)
    output.write_text("substituted output")
    with pytest.raises(BareSemanticEvidenceError, match="normal non-aborted|output_sha256"):
        verify_bare_semantics_evidence(sidecar, siesta_version="5.4.2", executable_path=executable, reference_dm_path=dm, input_fdf_path=fdf, output_path=output, selected_event_lines=(2, 2), expectation=_expectation(payload))


def test_writer_makes_a_verifiable_intentional_nonconverged_bare_certificate(tmp_path: Path):
    executable = tmp_path / "siesta"; executable.write_bytes(b"diagnostic-build")
    dm = tmp_path / "reference.DM"; dm.write_bytes(b"canonical-dm")
    fdf = tmp_path / "siesta.fdf"; fdf.write_text("SCF.MustConverge F\n")
    output = tmp_path / "siesta.out"
    output.write_text(
        "hubbard_term: recalculating local occupations\n"
        "TRACE: LR_BARE reference_dm_accepted\n"
        "TRACE: LR_BARE population_evaluated iscf=2 population_cycle=2\n"
        "TRACE: LR_BARE perturbation_hamiltonian_built iscf=2 population_cycle=2\n"
        "TRACE: LR_BARE hxc_rebuild_after_perturbation iscf=2\n"
        "SCF_NOT_CONV: expected fixed-Hxc BARE termination\n"
        ">> End of run\n"
    )
    sidecar = write_bare_semantics_sidecar(
        tmp_path / "bare_semantics.json", siesta_version="5.4.2",
        source_revision="official-5.4.2+diagnostic-patch", executable_path=executable,
        reference_dm_path=dm, input_fdf_path=fdf, output_path=output, trace_path=output,
        selected_event_lines=(1, 1), selected_iscf=2, population_cycle=2,
    )
    verified = verify_bare_semantics_evidence(
        sidecar, siesta_version="5.4.2", executable_path=executable,
        reference_dm_path=dm, input_fdf_path=fdf, output_path=output, selected_event_lines=(1, 1),
        expectation=BareTraceExpectation(
            "official-5.4.2+diagnostic-patch",
            {
                "reference_dm_loaded": "TRACE: LR_BARE reference_dm_accepted",
                "perturbation_applied": "TRACE: LR_BARE perturbation_hamiltonian_built iscf=2 population_cycle=2",
                "selected_population": "TRACE: LR_BARE population_evaluated iscf=2 population_cycle=2",
                "hxc_rebuild_after_selected_population": "TRACE: LR_BARE hxc_rebuild_after_perturbation iscf=2",
            },
        ),
    )
    assert verified.selected_event_lines == (1, 1)


def test_writer_rejects_unconverged_transcript(tmp_path: Path):
    executable = tmp_path / "siesta"; executable.write_bytes(b"diagnostic-build")
    dm = tmp_path / "reference.DM"; dm.write_bytes(b"canonical-dm")
    fdf = tmp_path / "siesta.fdf"; fdf.write_text("SCF.MustConverge F\n")
    output = tmp_path / "siesta.out"
    output.write_text("hubbard_term: recalculating local occupations\nSCF_NOT_CONV\n")
    with pytest.raises(BareSemanticEvidenceError, match="normal non-aborted"):
        write_bare_semantics_sidecar(
            tmp_path / "bare_semantics.json", siesta_version="5.4.2",
            source_revision="official-5.4.2+diagnostic-patch", executable_path=executable,
            reference_dm_path=dm, input_fdf_path=fdf, output_path=output, trace_path=output,
            selected_event_lines=(1, 1), selected_iscf=2, population_cycle=2,
        )
