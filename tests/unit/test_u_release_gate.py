from copy import deepcopy
import json
from pathlib import Path

import pytest

from hubbardflow.execution.u_release_gate import (
    UReleaseError, UReleasePolicy, canonical_hash, create_u_release, verify_u_release,
)
from hubbardflow.execution.lr_dag import LRDag, LRDagNode, LRNodeKind, append_u_release_nodes
from hubbardflow.execution.downstream_u_admission import (
    DownstreamUAdmissionError, ValidatedURelease, load_verified_u_release,
)
from hubbardflow.execution import u_certification_node, downstream_u_admission


@pytest.fixture(autouse=True)
def _policy_unit_tests_isolate_chain_verifier(monkeypatch):
    # These tests isolate release policy decisions. Full source-chain checks
    # are exercised by source-evidence tests and the campaign integration path.
    monkeypatch.setattr(u_certification_node, "verify_certificate_source_chain", lambda *_args: None)
    monkeypatch.setattr(downstream_u_admission, "verify_certificate_source_chain", lambda *_args: None)


def _release(certificate, evidence, policy):
    return create_u_release(
        certificate=certificate, certificate_sha256=canonical_hash(certificate), evidence=evidence,
        policy=policy, campaign_root=Path.cwd(), execution_mode="PRODUCTION",
    )


def _inputs(status="CERTIFIED", method="exact_rational_2x2"):
    certificate = {
        "certificate_status": status, "primary_method": method,
        "campaign_uuid": "campaign-123", "analysis_policy_sha256": "a" * 64,
        "source_analysis_sha256": "d" * 64, "response_dataset_sha256": "e" * 64,
        "nominal_u_by_site_eV": ["6.864", "6.865"],
        "u_interval_by_site": [
            {"lower": "685/100", "upper": "6869/1000"},
            {"lower": "6864/1000", "upper": "6866/1000"},
        ],
    }
    evidence = {
        "all_required_nodes_validated": True, "parent_dm_load_proven": True,
        "analysis_policy_sha256": "a" * 64, "campaign_uuid": "campaign-123",
        "sensitivity_gate": "SENSITIVITY_WITHIN_PREDECLARED_POLICY",
        "reproducibility_status": "ESTABLISHED", "campaign_hash": "b" * 64,
        "projector_fingerprints": ["c" * 64],
        "source_analysis_sha256": "d" * 64, "response_dataset_sha256": "e" * 64,
        "scf_status": "CONVERGED", "magnetic_state_status": "VALIDATED",
    }
    return certificate, evidence


def test_release_synthetic_validated_pipeline_and_hash_check():
    certificate, evidence = _inputs()
    artifact = _release(certificate, evidence, UReleasePolicy("0.02", require_reproducibility=True))
    verify_u_release(artifact)
    assert artifact["release_status"] == "RELEASED"
    assert artifact["physical_acceptance"] == "NOT_ESTABLISHED"
    changed = deepcopy(artifact); changed["nominal_u_by_site_eV"][0] = "6.8641"
    with pytest.raises(UReleaseError, match="hash mismatch"):
        verify_u_release(changed)


def test_precision_gate_uses_interval_half_width_not_nominal_deviation():
    certificate, evidence = _inputs()
    # Site zero's exact interval has half-width 0.0095 eV, although the
    # declared nominal is 0.014 eV from its lower endpoint.
    artifact = _release(certificate, evidence, UReleasePolicy("0.01"))
    assert artifact["release_status"] == "RELEASED"


@pytest.mark.parametrize(("tolerance", "expected"), [("0.010", "RELEASED"), ("0.020", "RELEASED"), ("0.050", "RELEASED")])
def test_precision_gate_is_injected_from_each_supplied_policy(tolerance, expected):
    certificate, evidence = _inputs()
    artifact = _release(certificate, evidence, UReleasePolicy(tolerance))
    assert artifact["release_status"] == expected


def test_precision_gate_fails_when_supplied_policy_is_tighter_than_interval():
    certificate, evidence = _inputs()
    with pytest.raises(UReleaseError, match="deterministic interval"):
        _release(certificate, evidence, UReleasePolicy("0.009"))


def test_dag_certification_and_release_follow_matrix_analysis_without_siesta():
    analysis = LRDagNode("matrix-analysis", LRNodeKind.MATRIX_ANALYSIS, ("validated-responses",))
    dag = append_u_release_nodes(LRDag((analysis,), False))
    certificate = dag.node("u-certification")
    release = dag.node("u-release-gate")
    assert certificate.kind is LRNodeKind.U_CERTIFICATION
    assert certificate.dependencies == ("matrix-analysis",)
    assert release.kind is LRNodeKind.U_RELEASE_GATE
    assert release.dependencies == ("u-certification",)


def test_certificate_not_established_cannot_release():
    certificate, evidence = _inputs("CERTIFICATE_NOT_ESTABLISHED")
    with pytest.raises(UReleaseError, match="not established"):
        _release(certificate, evidence, UReleasePolicy("0.01"))


def test_verified_fallback_requires_prospective_policy_permission():
    certificate, evidence = _inputs("CERTIFIED_WITH_FALLBACK", "verified_neumann_fallback")
    digest = canonical_hash(certificate)
    with pytest.raises(UReleaseError, match="not permitted"):
        create_u_release(certificate=certificate, certificate_sha256=digest, evidence=evidence,
                         policy=UReleasePolicy("0.02"), campaign_root=Path.cwd(), execution_mode="PRODUCTION")
    released = create_u_release(certificate=certificate, certificate_sha256=digest, evidence=evidence,
                                policy=UReleasePolicy("0.02", allow_verified_fallback=True),
                                campaign_root=Path.cwd(), execution_mode="PRODUCTION")
    assert released["certificate_method"] == "verified_neumann_fallback"


@pytest.mark.parametrize("change,message", [
    ("sensitivity", "sensitivity gate"), ("reproducibility", "reproducibility"),
    ("hash", "hash mismatch"), ("parent", "scientific evidence"),
])
def test_release_gate_fails_closed_on_missing_or_inconsistent_operational_evidence(change, message):
    certificate, evidence = _inputs()
    policy = UReleasePolicy("0.02", require_reproducibility=True)
    if change == "sensitivity": evidence["sensitivity_gate"] = "SENSITIVITY_EXCEEDS_POLICY"
    if change == "reproducibility": evidence["reproducibility_status"] = "MISSING"
    if change == "hash": evidence["analysis_policy_sha256"] = "d" * 64
    if change == "parent": evidence["parent_dm_load_proven"] = False
    with pytest.raises(UReleaseError, match=message):
        create_u_release(certificate=certificate, certificate_sha256=canonical_hash(certificate),
                         evidence=evidence, policy=policy, campaign_root=Path.cwd(), execution_mode="PRODUCTION")


def test_downstream_admission_requires_hash_bound_release_and_certificate(tmp_path):
    certificate, evidence = _inputs()
    certificate.update({"schema_version": "u_certificate.v1", "physical_acceptance": "NOT_ESTABLISHED"})
    certificate_path = tmp_path / "u_certificate.v1.json"
    certificate_path.write_text(json.dumps(certificate, sort_keys=True), encoding="utf-8")
    cert_sha = canonical_hash(certificate)
    release = create_u_release(
        certificate=certificate, certificate_sha256=cert_sha, evidence=evidence,
        policy=UReleasePolicy("0.02"), campaign_root=tmp_path, execution_mode="PRODUCTION",
    )
    release_path = tmp_path / "u_release.v1.json"
    release_path.write_text(json.dumps(release, sort_keys=True), encoding="utf-8")
    validated = load_verified_u_release(release_path, certificate_path, require_preregistered=True,
                                        registered_release_sha256=release["release_sha256"],
                                        execution_mode="PRODUCTION")
    assert isinstance(validated, ValidatedURelease)
    assert validated.nominal_u_by_site_eV == ("6.864", "6.865")
    with pytest.raises(DownstreamUAdmissionError, match="source certificate hash"):
        load_verified_u_release(release_path, tmp_path / "u_release.v1.json", execution_mode="PRODUCTION")
    with pytest.raises(DownstreamUAdmissionError, match="not preregistered"):
        load_verified_u_release(release_path, certificate_path, require_preregistered=True,
                                execution_mode="PRODUCTION")
    tampered_certificate = deepcopy(certificate)
    tampered_certificate["campaign_uuid"] = "another-campaign"
    certificate_path.write_text(json.dumps(tampered_certificate, sort_keys=True), encoding="utf-8")
    with pytest.raises(DownstreamUAdmissionError, match="source certificate hash mismatch"):
        load_verified_u_release(release_path, certificate_path, execution_mode="PRODUCTION")
    with pytest.raises(TypeError, match="verifier"):
        ValidatedURelease({"nominal_u_by_site_eV": [6.8], "release_sha256": "x"}, "x", object())
