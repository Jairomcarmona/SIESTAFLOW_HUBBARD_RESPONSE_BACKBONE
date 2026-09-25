"""Adversarial regression tests for the versioned BARE trace contract.

These tests deliberately mutate synthetic evidence.  They are not SIESTA
evidence and must never be used as a physical result.  Their purpose is to
prove that a certificate cannot remain PASS after its provenance or semantic
trace has been tampered with.
"""

from hashlib import sha256
import json
from pathlib import Path

import pytest

from siestaflow_hubbard.siesta_backend.bare_semantics_evidence import (
    BareTraceExpectation,
    BareSemanticEvidenceError,
    verify_bare_semantics_evidence,
)


def _digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _fixture(tmp_path: Path):
    executable = tmp_path / "siesta"
    dm = tmp_path / "reference.DM"
    fdf = tmp_path / "perturbed.fdf"
    output = tmp_path / "siesta.out"
    trace = tmp_path / "bare.trace"
    sidecar = tmp_path / "bare_semantics.json"

    executable.write_bytes(b"diagnostic executable")
    dm.write_bytes(b"parent density matrix")
    fdf.write_text("SCF.MustConverge F\n", encoding="utf-8")
    output.write_text(
        "hubbard_term: selected population\n>> End of run\n",
        encoding="utf-8",
    )
    markers = {
        "reference_dm_loaded": "TRACE DM accepted",
        "selected_population": "TRACE population selected",
        "perturbation_applied": "TRACE perturbation Hamiltonian built",
        "hxc_rebuild_after_selected_population": "TRACE Hxc rebuilt",
    }
    trace.write_text(
        "\n".join(markers[name] for name in (
            "reference_dm_loaded",
            "selected_population",
            "perturbation_applied",
            "hxc_rebuild_after_selected_population",
        )) + "\n",
        encoding="utf-8",
    )
    payload = {
        "schema_version": "siestaflow-bare-semantics-v2",
        "status": "PASS",
        "siesta_version": "5.4.2",
        "executable_sha256": _digest(executable),
        "source_revision": "audited-diagnostic-revision",
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
    sidecar.write_text(json.dumps(payload), encoding="utf-8")
    return {
        "executable": executable,
        "dm": dm,
        "fdf": fdf,
        "output": output,
        "trace": trace,
        "sidecar": sidecar,
        "payload": payload,
        "trusted_expectation": BareTraceExpectation(
            "audited-diagnostic-revision", dict(markers)
        ),
    }


def _verify(fixture, **overrides):
    args = {
        "sidecar_path": fixture["sidecar"],
        "siesta_version": "5.4.2",
        "executable_path": fixture["executable"],
        "reference_dm_path": fixture["dm"],
        "input_fdf_path": fixture["fdf"],
        "output_path": fixture["output"],
        "selected_event_lines": (1, 1),
        "expectation": fixture["trusted_expectation"],
    }
    args.update(overrides)
    return verify_bare_semantics_evidence(**args)


def _rewrite_sidecar(fixture, mutate):
    payload = json.loads(fixture["sidecar"].read_text(encoding="utf-8"))
    mutate(payload)
    fixture["sidecar"].write_text(json.dumps(payload), encoding="utf-8")


@pytest.mark.parametrize(
    "name, mutate",
    [
        (
            "duplicate_marker",
            lambda f: f["trace"].write_text(
                f["trace"].read_text(encoding="utf-8")
                + "TRACE population selected\n",
                encoding="utf-8",
            ),
        ),
        (
            "missing_marker",
            lambda f: f["trace"].write_text(
                "TRACE DM accepted\nTRACE population selected\n",
                encoding="utf-8",
            ),
        ),
        (
            "out_of_order",
            lambda f: f["trace"].write_text(
                "\n".join((
                    "TRACE DM accepted",
                    "TRACE Hxc rebuilt",
                    "TRACE perturbation Hamiltonian built",
                    "TRACE population selected",
                )) + "\n",
                encoding="utf-8",
            ),
        ),
    ],
)
def test_trace_event_integrity_never_passes(tmp_path: Path, name, mutate):
    fixture = _fixture(tmp_path)
    mutate(fixture)
    fixture["payload"]["trace_sha256"] = _digest(fixture["trace"])
    fixture["sidecar"].write_text(json.dumps(fixture["payload"]), encoding="utf-8")
    with pytest.raises(BareSemanticEvidenceError):
        _verify(fixture)


@pytest.mark.parametrize("artifact", ["executable", "dm", "fdf", "output"])
def test_provenance_artifact_mutation_never_passes(tmp_path: Path, artifact):
    fixture = _fixture(tmp_path)
    fixture[artifact].write_bytes(fixture[artifact].read_bytes() + b"tampered")
    with pytest.raises(BareSemanticEvidenceError, match="sha256"):
        _verify(fixture)


def test_trace_hash_mutation_never_passes(tmp_path: Path):
    fixture = _fixture(tmp_path)
    fixture["trace"].write_text(
        fixture["trace"].read_text(encoding="utf-8") + "unbound text\n",
        encoding="utf-8",
    )
    with pytest.raises(BareSemanticEvidenceError, match="trace_sha256"):
        _verify(fixture)


def test_abnormal_output_never_passes_even_if_hash_is_rebound(tmp_path: Path):
    fixture = _fixture(tmp_path)
    fixture["output"].write_text(
        "hubbard_term: selected population\nMPI_Abort\n",
        encoding="utf-8",
    )
    fixture["payload"]["output_sha256"] = _digest(fixture["output"])
    fixture["sidecar"].write_text(json.dumps(fixture["payload"]), encoding="utf-8")
    with pytest.raises(BareSemanticEvidenceError):
        _verify(fixture)


def test_unknown_or_different_version_never_passes(tmp_path: Path):
    fixture = _fixture(tmp_path)
    with pytest.raises(BareSemanticEvidenceError, match="version"):
        _verify(fixture, siesta_version="5.5.0")

    source_revision_root = tmp_path / "source_revision"
    source_revision_root.mkdir()
    fixture = _fixture(source_revision_root)
    _rewrite_sidecar(fixture, lambda p: p.update({"source_revision": "different-build"}))
    with pytest.raises(BareSemanticEvidenceError, match="source_revision"):
        _verify(
            fixture,
            expectation=BareTraceExpectation(
                "audited-diagnostic-revision", fixture["payload"]["trace_markers"]
            ),
        )


def test_forged_marker_vocabulary_never_passes(tmp_path: Path):
    fixture = _fixture(tmp_path)
    forged = {
        "reference_dm_loaded": "FORGED_A",
        "selected_population": "FORGED_B",
        "perturbation_applied": "FORGED_C",
        "hxc_rebuild_after_selected_population": "FORGED_D",
    }
    fixture["trace"].write_text("FORGED_A\nFORGED_B\nFORGED_C\nFORGED_D\n", encoding="utf-8")
    fixture["payload"]["trace_markers"] = forged
    fixture["payload"]["trace_sha256"] = _digest(fixture["trace"])
    fixture["sidecar"].write_text(json.dumps(fixture["payload"]), encoding="utf-8")
    with pytest.raises(BareSemanticEvidenceError):
        _verify(fixture)


def test_partial_sidecar_schema_never_passes(tmp_path: Path):
    fixture = _fixture(tmp_path)
    _rewrite_sidecar(fixture, lambda p: p.pop("trace_markers"))
    with pytest.raises(BareSemanticEvidenceError, match="schema"):
        _verify(fixture)
