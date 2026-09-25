import json
from pathlib import Path

import pytest

from siestaflow_hubbard.domain.symmetry_reduction import (
    SymmetryEvidenceBundle,
    SymmetryPlanError,
    SymmetryReductionPolicy,
    build_symmetry_reduction_plan,
    filter_evidence_compatible_operations,
)
from siestaflow_hubbard.siesta_backend.symmetry_evidence import (
    SymmetryEvidenceFormatError,
    load_symmetry_evidence,
)
from tests.support import certificate


def _hash(char: str) -> str:
    return char * 64


def _bundle(cert, fingerprints=("d", "d", "d", "d")):
    return SymmetryEvidenceBundle(
        certificate_input_hash=cert.input_hash,
        reference_fdf_sha256=_hash("a"),
        reference_output_sha256=_hash("b"),
        magnetic_evidence_sha256=_hash("c"),
        subspace_fingerprints=fingerprints,
    )


def test_strict_evidence_keeps_only_subspace_compatible_magnetic_operations():
    cert = certificate(4)
    allowed = filter_evidence_compatible_operations(cert, _bundle(cert), ["a", "b", "c", "d"])
    assert allowed
    incompatible = filter_evidence_compatible_operations(
        cert, _bundle(cert, ("d0", "d1", "d2", "d3")), ["a", "b", "c", "d"]
    )
    assert all(operation.permutation == tuple(range(4)) for operation in incompatible)


def test_wrong_certificate_binding_fails_closed():
    cert = certificate(4)
    bundle = _bundle(cert)
    object.__setattr__(bundle, "certificate_input_hash", _hash("f"))
    with pytest.raises(SymmetryPlanError, match="different certificate"):
        filter_evidence_compatible_operations(cert, bundle, ["a", "b", "c", "d"])


def test_incomplete_magnetic_evidence_blocks_new_strict_route():
    cert = certificate(4)
    bundle = SymmetryEvidenceBundle(
        certificate_input_hash=cert.input_hash,
        reference_fdf_sha256=_hash("a"), reference_output_sha256=_hash("b"),
        magnetic_evidence_sha256=_hash("c"), subspace_fingerprints=("d",) * 4,
        magnetic_evidence_complete=False,
    )
    with pytest.raises(SymmetryPlanError, match="incomplete"):
        build_symmetry_reduction_plan(["a", "b", "c", "d"], ["a", "b", "c", "d"], cert,
                                      SymmetryReductionPolicy(alpha_ev=0.05), bundle)


def test_loader_rejects_unknown_schema_and_non_sha256_fields():
    path = Path("tests/unit/_symmetry_evidence_temp.json")
    try:
        path.write_text(json.dumps({"schema_version": 2}), encoding="utf-8")
        with pytest.raises(SymmetryEvidenceFormatError, match="unsupported"):
            load_symmetry_evidence(path)
        path.write_text(json.dumps({
            "schema_version": 1,
            "certificate_input_hash": "x",
            "reference_fdf_sha256": _hash("a"),
            "reference_output_sha256": _hash("b"),
            "magnetic_evidence_sha256": _hash("c"),
            "subspace_fingerprints": ["d"] * 4,
            "magnetic_evidence_complete": True,
            "reference_output_normal": True,
            "source_format": "versioned_reference_evidence_v1",
        }), encoding="utf-8")
        with pytest.raises(SymmetryPlanError, match="lowercase SHA-256"):
            load_symmetry_evidence(path).validate(certificate=certificate(4), site_count=4)
    finally:
        path.unlink(missing_ok=True)
