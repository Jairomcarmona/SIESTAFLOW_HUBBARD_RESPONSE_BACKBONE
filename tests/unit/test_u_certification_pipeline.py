import json
import re
from fractions import Fraction
from hashlib import sha256
from pathlib import Path
from decimal import Decimal

import pytest

from siestaflow_hubbard.domain.u_certification import inverse
from siestaflow_hubbard.execution.downstream_u_admission import (
    DownstreamUAdmissionError, load_verified_u_release,
)
from siestaflow_hubbard.execution.source_evidence import (
    extract_verified_response_tokens, scientific_tokens_sha256,
    source_manifest_identity_sha256,
)
from siestaflow_hubbard.execution.u_certification_node import (
    UCertificationNodeError, _derive_boxes, certify_campaign, verify_certificate_source_chain, write_certificate,
)
from siestaflow_hubbard.execution.u_release_gate import (
    UReleasePolicy, create_u_release, canonical_hash, write_u_release,
)


def _hash(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def test_exact_u_boxes_follow_committed_active_grid_not_full_token_grid():
    """Regression: the nominal matrices use six active alphas from ten tokens."""
    from siestaflow_hubbard.domain.u_certification import Interval

    full_grid = ["-0.05", "-0.04", "-0.03", "-0.02", "-0.01", "0.01", "0.02", "0.03", "0.04", "0.05"]
    active_grid = ["-0.03", "-0.02", "-0.01", "0.01", "0.02", "0.03"]
    nominal_by_mode = {
        "BARE": [["4", "0.1"], ["0.1", "5"]],
        "SCREENED": [["2", "0.05"], ["0.05", "2.5"]],
    }
    cubic_by_cell = [[1000, -700], [500, 900]]
    active_values = [float(alpha) for alpha in active_grid]
    active_cubic_slope = sum(alpha**4 for alpha in active_values) / sum(alpha**2 for alpha in active_values)
    observations = []
    for mode, nominal in nominal_by_mode.items():
        for j in range(2):
            for alpha in full_grid:
                x = float(alpha)
                row_tokens = []
                for i in range(2):
                    cubic = cubic_by_cell[i][j]
                    linear = float(nominal[i][j]) - cubic * active_cubic_slope
                    row_tokens.append([f"{10 + linear * x + cubic * x**3:.6f}"])
                observations.append({
                    "mode": mode, "perturbed_site_index": j, "alpha_token": alpha,
                    "occupation_tokens": row_tokens,
                })
    full_dataset = {
        "schema_version": "response_tokens.v1", "status": "AVAILABLE",
        "matrix_dimension": 2, "polynomial_degree": 1, "observations": observations,
    }
    active_dataset = {
        **full_dataset,
        "observations": [row for row in observations if row["alpha_token"] in active_grid],
    }
    # Independently reconstruct the active-grid point estimate represented by
    # the analysis artifact; the exact decimal intervals must enclose it.
    active_bare, active_screened = _derive_boxes(active_dataset, active_grid)
    full_bare, full_screened = _derive_boxes(full_dataset, active_grid)
    for mode, actual, active_box, full_box in (
        ("BARE", nominal_by_mode["BARE"], active_bare, full_bare),
        ("SCREENED", nominal_by_mode["SCREENED"], active_screened, full_screened),
    ):
        for i in range(2):
            for j in range(2):
                nominal_cell = Interval.around(actual[i][j], "0")
                assert active_box[i][j].contains(nominal_cell.lo)
                assert full_box[i][j] == active_box[i][j]


def test_exact_u_boxes_require_exact_active_grid_coverage():
    full_grid = ["-0.05", "-0.04", "-0.03", "-0.02", "-0.01", "0.01", "0.02", "0.03", "0.04", "0.05"]
    active_grid = ["-0.03", "-0.02", "-0.01", "0.01", "0.02", "0.03"]
    rows = [{
        "mode": mode, "perturbed_site_index": j, "alpha_token": alpha,
        "occupation_tokens": [["10"], ["10"]],
    } for mode in ("BARE", "SCREENED") for j in range(2) for alpha in full_grid]
    dataset = {
        "schema_version": "response_tokens.v1", "status": "AVAILABLE",
        "matrix_dimension": 2, "polynomial_degree": 1, "observations": rows,
    }
    missing = {**dataset, "observations": [row for row in rows if not (
        row["mode"] == "BARE" and row["perturbed_site_index"] == 1 and row["alpha_token"] == "0.03"
    )]}
    with pytest.raises(UCertificationNodeError, match="active analysis alpha coverage is incomplete"):
        _derive_boxes(missing, active_grid)
    duplicate = {**dataset, "observations": [*rows, dict(rows[0])]}
    with pytest.raises(UCertificationNodeError, match="duplicate response alpha coverage"):
        _derive_boxes(duplicate, active_grid)


def test_n3_tokens_to_certificate_artifact(tmp_path: Path):
    _, _, _, certificate_path, certificate, _ = _full_n3_source_chain(tmp_path)
    assert certificate["certificate_status"] == "CERTIFIED"
    assert certificate["matrix_dimension"] == 3
    assert certificate["certification_alpha_grid_eV"] == [-0.037, -0.014, -0.006, 0.006, 0.014, 0.037]
    for interval, declared_half in zip(certificate["u_interval_by_site"], certificate["half_width_by_site"]):
        assert Fraction(declared_half) == (Fraction(interval["upper"]) - Fraction(interval["lower"])) / 2
    assert certificate["primary_method"] in {"verified_krawczyk", "verified_neumann_fallback"}
    assert json.loads(certificate_path.read_text(encoding="utf-8"))["schema_version"] == "u_certificate.v1"


def test_n3_certificate_ignores_committedly_external_alpha_points(tmp_path: Path):
    active = ("-0.037", "-0.014", "-0.006", "0.006", "0.014", "0.037")
    clean_root, extra_root = tmp_path / "clean", tmp_path / "with-extra"
    *_, clean_certificate, _ = _full_n3_source_chain(clean_root, active_alpha_grid=active)
    *_, extra_certificate, _ = _full_n3_source_chain(
        extra_root, active_alpha_grid=active, extra_alpha_grid=("-0.123", "-0.077", "0.077", "0.123"),
    )
    for key in ("chi0_interval", "chi_interval", "u_interval_by_site", "half_width_by_site",
                "certificate_status", "regularity_certificates", "primary_method"):
        assert extra_certificate[key] == clean_certificate[key]


@pytest.mark.parametrize("mutation", ["active_grid", "campaign_uuid", "analysis_commitment", "token_digest"])
def test_n3_committed_source_chain_rejects_individual_uncommitted_mutations(tmp_path: Path, mutation: str):
    from siestaflow_hubbard.execution.u_certification_node import verify_certificate_source_chain

    _, _, _, _, certificate, _ = _full_n3_source_chain(tmp_path)
    if mutation == "active_grid":
        path = tmp_path / certificate["analysis_artifact_path"]
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["analysis_alpha_grid_eV"].append(0.077)
    elif mutation == "campaign_uuid":
        path = tmp_path / certificate["analysis_artifact_path"]
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["campaign"]["campaign_id"] = "uncommitted-campaign"
    elif mutation == "analysis_commitment":
        path = tmp_path / certificate["matrix_analysis_commitment_path"]
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["campaign_uuid"] = "uncommitted-campaign"
    else:
        path = tmp_path / certificate["response_tokens_path"]
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["response_tokens_scientific_sha256"] = "0" * 64
    path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    with pytest.raises(UCertificationNodeError, match="SOURCE_EVIDENCE_CHANGED_AFTER_CERTIFICATION"):
        verify_certificate_source_chain(certificate, tmp_path)


def test_legacy_full_grid_certificate_remains_reconstructable(tmp_path: Path):
    from siestaflow_hubbard.execution.u_certification_node import verify_certificate_source_chain

    _, _, _, _, certificate, _ = _full_n3_source_chain(tmp_path)
    historical = dict(certificate)
    historical.pop("certification_alpha_grid_eV")
    historical["implementation_version"] = "u-certification-rational-v1"
    # Frozen v1 certificates used the nominal-to-endpoint maximum under the
    # historical half-width label. Recreate that exact legacy field so this
    # test exercises source-chain compatibility rather than v3 output.
    historical["half_width_by_site"] = [
        str(max(Fraction(str(nominal)) - Fraction(box["lower"]),
                 Fraction(box["upper"]) - Fraction(str(nominal))))
        for nominal, box in zip(historical["nominal_u_by_site_eV"], historical["u_interval_by_site"])
    ]
    historical.pop("certificate_scientific_sha256")
    historical["certificate_scientific_sha256"] = canonical_hash(historical)
    verify_certificate_source_chain(historical, tmp_path)


def _synthetic_population_event(values: list[str]) -> list[str]:
    lines = ["hubbard_term: recalculating local occupations    1", "hubbard_term: projector occupations"]
    for atom_index, total in enumerate(values, 1):
        spin = Decimal(total) / 2
        lines.extend([
            f"hubbard_term: atom, species:            {atom_index}           1",
            f"  1  1  {spin:.6f}  {spin:.6f}",
            f"hubbard_term: Total projector shell",
            f"Occupations:     {spin:.6f}    {spin:.6f}    {Decimal(total):.6f}",
        ])
    return lines


def _full_n3_source_chain(
    root: Path, *, bare_matrix: list[list[str]] | None = None,
    screened_matrix: list[list[str]] | None = None, parent_loaded: bool = True,
    active_alpha_grid: tuple[str, ...] = ("-0.037", "-0.014", "-0.006", "0.006", "0.014", "0.037"),
    extra_alpha_grid: tuple[str, ...] = (),
) -> tuple[Path, Path, Path, Path, dict, dict]:
    """Build a source-backed synthetic 3x3 chain without invoking SIESTA."""
    import json
    from siestaflow_hubbard.execution.u_release_gate import canonical_hash

    root.mkdir(parents=True, exist_ok=True)
    campaign = "synthetic-source-n3"
    parent = root / "reference.DM"
    parent.write_bytes(b"synthetic validated parent DM\n")
    parent_hash = _hash(parent)
    reference_receipt = {
        "campaign_uuid": campaign, "node_id": "reference", "state": "VALIDATED",
        "node_evidence_sha256": "f" * 64, "reference_dm_sha256": parent_hash,
    }
    reference_receipt_path = root / "reference-receipt.json"
    reference_receipt_path.write_text(json.dumps(reference_receipt, sort_keys=True, separators=(",", ":")))
    bare = bare_matrix or [["4", "0", "0"], ["0", "5", "0"], ["0", "0", "6"]]
    screened = screened_matrix or [["2", "0", "0"], ["0", "2.5", "0"], ["0", "0", "3"]]
    policy = {"polynomial_degree": 1, "source_fixture": "synthetic"}
    policy_hash = canonical_hash(policy)
    rows, evidence = [], []
    token_grid = tuple(sorted(set((*active_alpha_grid, *extra_alpha_grid)), key=Fraction))
    for mode, matrix in (("BARE", bare), ("SCREENED", screened)):
        for j in range(3):
            for alpha in token_grid:
                totals = [f"{Decimal(10) + Decimal(matrix[i][j]) * Decimal(alpha):.6f}" for i in range(3)]
                if mode == "BARE":
                    out_lines = ["redata: SCF mix quantity = Hamiltonian"]
                    out_lines += _synthetic_population_event(["10", "10", "10"])
                    out_lines += ["hubbard_term: recalculating Hamiltonian", "stepf: Fermi-Dirac step function"]
                    out_lines += _synthetic_population_event(totals)
                    out_lines += ["hubbard_term: recalculating Hamiltonian", "scf: 1"]
                else:
                    out_lines = ["SCF Convergence by synthetic fixture criterion", "Using DM_out to compute the final energy and forces"]
                    out_lines += _synthetic_population_event(totals)
                    out_lines += ["hubbard_term: recalculating Hamiltonian", "Job completed"]
                out_path = root / f"{mode.lower()}-{j}-{alpha}.out"
                out_path.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
                out_hash = _hash(out_path)
                node_id = f"{mode.lower()}:{j}:{alpha}"
                node_digest = sha256(node_id.encode()).hexdigest()
                receipt = {
                    "campaign_uuid": campaign, "node_id": node_id, "state": "VALIDATED",
                    "node_evidence_sha256": node_digest, "out_sha256": out_hash,
                    "parent_dm_sha256": parent_hash, "parent_dm_loaded": parent_loaded,
                    "mode": mode, "perturbed_site_index": j, "perturbed_site_id": f"s{j}",
                    "alpha_token": alpha, "parser_id": "siesta-5.4.2-bare-first-iteration-v1" if mode == "BARE" else "siesta-5.4.2-screened-dmout-v1",
                    "scientific_profile_id": "siesta-5.4.2-potential-shift-hamiltonian-v1" if mode == "BARE" else "siesta-5.4.2-screened-dmout-v1",
                    "backend_identity": "e" * 64, "atom_indices": [1, 2, 3],
                }
                receipt_path = root / f"{node_digest}.receipt.json"
                receipt_path.write_text(json.dumps(receipt, sort_keys=True, separators=(",", ":")), encoding="utf-8")
                rows.append({
                    "node_id": node_id, "perturbed_site_index": j, "perturbed_site_id": f"s{j}",
                    "alpha_token": alpha, "mode": mode, "out_path": out_path.name, "out_sha256": out_hash,
                    "receipt_path": receipt_path.name, "receipt_sha256": _hash(receipt_path),
                    "node_evidence_sha256": node_digest, "node_state": "VALIDATED",
                    "parent_dm_path": parent.name, "parent_dm_sha256": parent_hash,
                    "backend_identity": "e" * 64, "scientific_profile_id": receipt["scientific_profile_id"],
                    "parser_id": receipt["parser_id"], "atom_indices": [1, 2, 3],
                })
                evidence.append({"path": receipt_path.name, "sha256": _hash(receipt_path),
                                 "state": "VALIDATED", "evidence_digest": node_digest, "parent_dm_loaded": parent_loaded})
    manifest = {
        "schema_version": "source_evidence_manifest.v1", "campaign_uuid": campaign,
        "generation_version": "test-source-evidence-v1", "matrix_dimension": 3, "polynomial_degree": 1,
        "analysis_policy_sha256": policy_hash,
        "reference_calculation": {
            "campaign_uuid": campaign, "node_id": "reference", "node_evidence_sha256": "f" * 64,
            "receipt_path": reference_receipt_path.name, "receipt_sha256": _hash(reference_receipt_path),
            "reference_dm_path": parent.name, "reference_dm_sha256": parent_hash,
        }, "observations": rows,
    }
    manifest["source_manifest_identity_sha256"] = source_manifest_identity_sha256(manifest)
    manifest_path = root / "source_evidence_manifest.v1.json"
    manifest_path.write_text(json.dumps(manifest, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    token_payload = extract_verified_response_tokens(manifest, root)
    token_payload["response_tokens_scientific_sha256"] = scientific_tokens_sha256(token_payload)
    token_path = root / "response_tokens.v1.json"
    token_path.write_text(json.dumps(token_payload, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    analysis_payload = {
        "campaign": {"campaign_id": campaign}, "site_labels": ["s0", "s1", "s2"],
        "analysis_alpha_grid_eV": [float(alpha) for alpha in active_alpha_grid],
        "primary": {"matrix_used_chi0": [[float(v) for v in row] for row in bare],
                    "matrix_used_chi": [[float(v) for v in row] for row in screened],
                    "U_by_site_eV": {
                        f"s{i}": str(
                            inverse([[Fraction(v) for v in row] for row in bare])[i][i]
                            - inverse([[Fraction(v) for v in row] for row in screened])[i][i]
                        ) for i in range(3)
                    }},
        "estimator_policy": policy,
        "sensitivity_gate": {"status": "SENSITIVITY_WITHIN_PREDECLARED_POLICY",
                             "estimator_sensitivity_eV": {f"s{i}": 0.001 for i in range(3)},
                             "window_sensitivity_eV": {f"s{i}": 0.001 for i in range(3)}},
        "response_grid_reproducibility_calibration": {"status": "MISSING"},
        "scf_and_magnetic_diagnostics": {"scf_validated": True, "state_continuity_confirmed": True},
        "provenance": {"projector_fingerprints": ["synthetic-source-fixture"]},
    }
    analysis_path = root / "analysis.v1.json"
    analysis_path.write_text(json.dumps(analysis_payload, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    commitment = {
        "schema_version": "matrix_analysis_commitment.v1", "campaign_uuid": campaign,
        "analysis_artifact_path": analysis_path.name, "analysis_artifact_sha256": _hash(analysis_path),
        "analysis_policy_sha256": policy_hash, "source_evidence_manifest_path": manifest_path.name,
        "source_evidence_manifest_sha256": canonical_hash(manifest), "source_evidence_manifest_file_sha256": _hash(manifest_path),
        "source_manifest_identity_sha256": manifest["source_manifest_identity_sha256"],
        "response_tokens_path": token_path.name, "response_tokens_file_sha256": _hash(token_path),
        "response_tokens_scientific_sha256": scientific_tokens_sha256(token_payload),
    }
    commitment_path = root / "matrix_analysis_commitment.v1.json"
    commitment_path.write_text(json.dumps(commitment, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    analysis_input = {
        "state": "VALIDATED", "campaign_uuid": campaign,
        "chi0_nominal": analysis_payload["primary"]["matrix_used_chi0"],
        "chi_nominal": analysis_payload["primary"]["matrix_used_chi"],
        "nominal_u_by_site_eV": [str(v) for v in (
            inverse([[Fraction(v) for v in row] for row in bare])[i][i]
            - inverse([[Fraction(v) for v in row] for row in screened])[i][i] for i in range(3))],
    }
    certificate, digest = certify_campaign(
        root, analysis=analysis_input, response_dataset_path=token_path.name,
        response_dataset_sha256=_hash(token_path), analysis_path=analysis_path.name,
        analysis_sha256=_hash(analysis_path), node_evidence=evidence, analysis_policy=policy,
        source_manifest_path=manifest_path.name, source_manifest_sha256=canonical_hash(manifest),
        source_manifest_file_sha256=_hash(manifest_path),
        source_manifest_identity_sha256=manifest["source_manifest_identity_sha256"],
        response_tokens_scientific_sha256=scientific_tokens_sha256(token_payload),
        matrix_analysis_receipt_sha256=canonical_hash(commitment),
        matrix_analysis_commitment_path=commitment_path.name,
        matrix_analysis_commitment_file_sha256=_hash(commitment_path),
    )
    certificate_path = write_certificate(root, certificate, digest)
    return manifest_path, token_path, analysis_path, certificate_path, certificate, policy


def test_n3_primary_evidence_certificate_release_chain_and_mutations(tmp_path: Path):
    from siestaflow_hubbard.execution.u_certification_node import verify_certificate_source_chain

    manifest_path, tokens_path, analysis_path, certificate_path, certificate, policy = _full_n3_source_chain(tmp_path)
    verify_certificate_source_chain(certificate, tmp_path)
    evidence = {
        "all_required_nodes_validated": True, "parent_dm_load_proven": True,
        "analysis_policy_sha256": canonical_hash(policy), "campaign_uuid": certificate["campaign_uuid"],
        "campaign_hash": "a" * 64, "sensitivity_gate": "SENSITIVITY_WITHIN_PREDECLARED_POLICY",
        "scf_status": "CONVERGED", "magnetic_state_status": "VALIDATED",
        "source_analysis_sha256": certificate["source_analysis_sha256"],
        "response_dataset_sha256": certificate["response_dataset_sha256"],
        "projector_fingerprints": ["synthetic"],
    }
    release = create_u_release(
        certificate=certificate, certificate_sha256=canonical_hash(certificate), evidence=evidence,
        policy=UReleasePolicy("1000000", required_certificate_method=certificate["primary_method"],
                              allow_verified_fallback=True), campaign_root=tmp_path, execution_mode="PRODUCTION",
    )
    release_path = write_u_release(tmp_path, release)
    capability = load_verified_u_release(release_path, certificate_path, execution_mode="PRODUCTION")
    assert capability.nominal_u_by_site_eV == tuple(str(value) for value in certificate["nominal_u_by_site_eV"])

    # Self-consistently rehash a forged mathematical certificate and matching
    # release. Transitively reconstructed intervals must still be authoritative.
    original_certificate = certificate_path.read_bytes()
    original_release = release_path.read_bytes()
    try:
        forged_certificate = json.loads(original_certificate)
        forged_certificate["u_interval_by_site"][0]["upper"] = str(
            Fraction(forged_certificate["u_interval_by_site"][0]["upper"]) + Fraction(1, 10)
        )
        forged_certificate["certificate_scientific_sha256"] = canonical_hash({
            key: value for key, value in forged_certificate.items() if key != "certificate_scientific_sha256"
        })
        certificate_path.write_text(json.dumps(forged_certificate, sort_keys=True, separators=(",", ":")), encoding="utf-8")
        forged_release = json.loads(original_release)
        forged_release["u_certificate_sha256"] = canonical_hash(forged_certificate)
        forged_release["deterministic_interval_by_site"] = forged_certificate["u_interval_by_site"]
        forged_release.pop("release_sha256", None)
        forged_release["release_sha256"] = canonical_hash(forged_release)
        release_path.write_text(json.dumps(forged_release, sort_keys=True, separators=(",", ":")), encoding="utf-8")
        with pytest.raises(DownstreamUAdmissionError, match="certificate scientific fields"):
            load_verified_u_release(release_path, certificate_path, execution_mode="PRODUCTION")
    finally:
        certificate_path.write_bytes(original_certificate)
        release_path.write_bytes(original_release)

    # Exercise the primary consumer directly: the analysis/DAG commitment
    # remains A while a separately rehashed token payload claims B.
    commitment_path = tmp_path / certificate["matrix_analysis_commitment_path"]
    commitment = json.loads(commitment_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    analysis_payload = json.loads(analysis_path.read_text(encoding="utf-8"))
    normalized_analysis = {
        "state": "VALIDATED", "campaign_uuid": certificate["campaign_uuid"],
        "chi0_nominal": analysis_payload["primary"]["matrix_used_chi0"],
        "chi_nominal": analysis_payload["primary"]["matrix_used_chi"],
        "nominal_u_by_site_eV": certificate["nominal_u_by_site_eV"],
    }
    node_evidence = [{
        "path": row["receipt_path"], "sha256": row["receipt_sha256"],
        "state": "VALIDATED", "evidence_digest": row["node_evidence_sha256"],
        "parent_dm_loaded": True,
    } for row in manifest["observations"]]
    original_tokens = tokens_path.read_bytes()
    try:
        forged = json.loads(original_tokens)
        forged["observations"][0]["occupation_tokens"][0][0] = "1.234568"
        forged["response_tokens_scientific_sha256"] = scientific_tokens_sha256(forged)
        tokens_path.write_text(json.dumps(forged, sort_keys=True, separators=(",", ":")), encoding="utf-8")
        with pytest.raises(UCertificationNodeError, match="hash mismatch"):
            certify_campaign(
                tmp_path, analysis=normalized_analysis, response_dataset_path=tokens_path.name,
                response_dataset_sha256=commitment["response_tokens_file_sha256"],
                analysis_path=analysis_path.name, analysis_sha256=commitment["analysis_artifact_sha256"],
                node_evidence=node_evidence, analysis_policy=policy,
                source_manifest_path=manifest_path.name,
                source_manifest_sha256=commitment["source_evidence_manifest_sha256"],
                source_manifest_file_sha256=commitment["source_evidence_manifest_file_sha256"],
                source_manifest_identity_sha256=commitment["source_manifest_identity_sha256"],
                response_tokens_scientific_sha256=commitment["response_tokens_scientific_sha256"],
                matrix_analysis_receipt_sha256=canonical_hash(commitment),
                matrix_analysis_commitment_path=commitment_path.name,
                matrix_analysis_commitment_file_sha256=_hash(commitment_path),
            )
    finally:
        tokens_path.write_bytes(original_tokens)

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    first_out = tmp_path / manifest["observations"][0]["out_path"]
    paths = [manifest_path, first_out, tokens_path, analysis_path, certificate_path, release_path]
    for path in paths:
        original = path.read_bytes()
        if path == tokens_path:
            forged = json.loads(original)
            forged["observations"][0]["occupation_tokens"][0][0] = "1.234568"
            forged["response_tokens_scientific_sha256"] = scientific_tokens_sha256(forged)
            path.write_text(json.dumps(forged, sort_keys=True, separators=(",", ":")), encoding="utf-8")
        else:
            path.write_bytes(original + b"tampered")
        with pytest.raises((ValueError, OSError)):
            load_verified_u_release(release_path, certificate_path, execution_mode="PRODUCTION")
        path.write_bytes(original)

    # Rehash a forged OUT -> receipt -> manifest -> tokens -> commitment chain.
    # The OUT prints 1.234567 while the forged token file claims 1.234568;
    # the prior certificate/DAG commitment must still reject that new branch.
    commitment_path = tmp_path / certificate["matrix_analysis_commitment_path"]
    target_row = manifest["observations"][0]
    target_out = tmp_path / target_row["out_path"]
    target_receipt = tmp_path / target_row["receipt_path"]
    originals = {path: path.read_bytes() for path in (target_out, target_receipt, manifest_path, tokens_path, commitment_path)}
    try:
        text = target_out.read_text(encoding="utf-8")
        head, separator, tail = text.partition("stepf: Fermi-Dirac step function")
        assert separator
        tail, matrix_count = re.subn(
            r"(?m)^\s*1\s+1\s+-?\d+\.\d+\s+-?\d+\.\d+\s*$",
            "  1  1  0.617283  0.617283", tail, count=1,
        )
        assert matrix_count == 1
        tail, count = re.subn(
            r"Occupations:\s+\d+\.\d+\s+\d+\.\d+\s+\d+\.\d+",
            "Occupations:     0.617283    0.617283    1.234567", tail, count=1,
        )
        assert count == 1
        target_out.write_text(head + separator + tail, encoding="utf-8")
        forged_out_hash = _hash(target_out)
        receipt = json.loads(target_receipt.read_text(encoding="utf-8"))
        receipt["out_sha256"] = forged_out_hash
        target_receipt.write_text(json.dumps(receipt, sort_keys=True, separators=(",", ":")), encoding="utf-8")
        target_row["out_sha256"] = forged_out_hash
        target_row["receipt_sha256"] = _hash(target_receipt)
        manifest["source_manifest_identity_sha256"] = source_manifest_identity_sha256(manifest)
        manifest_path.write_text(json.dumps(manifest, sort_keys=True, separators=(",", ":")), encoding="utf-8")
        rebuilt = extract_verified_response_tokens(manifest, tmp_path)
        source_row = next(row for row in rebuilt["observations"] if row["node_id"] == target_row["node_id"])
        assert source_row["occupation_tokens"][0][0] == "1.234567"
        rebuilt["observations"] = [dict(row) for row in rebuilt["observations"]]
        forged_row = next(row for row in rebuilt["observations"] if row["node_id"] == target_row["node_id"])
        forged_row["occupation_tokens"] = [list(values) for values in forged_row["occupation_tokens"]]
        forged_row["occupation_tokens"][0][0] = "1.234568"
        rebuilt["response_tokens_scientific_sha256"] = scientific_tokens_sha256(rebuilt)
        tokens_path.write_text(json.dumps(rebuilt, sort_keys=True, separators=(",", ":")), encoding="utf-8")
        commitment = json.loads(commitment_path.read_text(encoding="utf-8"))
        commitment.update({
            "source_evidence_manifest_sha256": canonical_hash(manifest),
            "source_evidence_manifest_file_sha256": _hash(manifest_path),
            "source_manifest_identity_sha256": manifest["source_manifest_identity_sha256"],
            "response_tokens_file_sha256": _hash(tokens_path),
            "response_tokens_scientific_sha256": scientific_tokens_sha256(rebuilt),
        })
        commitment_path.write_text(json.dumps(commitment, sort_keys=True, separators=(",", ":")), encoding="utf-8")
        with pytest.raises(DownstreamUAdmissionError, match="SOURCE_EVIDENCE_CHANGED_AFTER_CERTIFICATION"):
            load_verified_u_release(release_path, certificate_path, execution_mode="PRODUCTION")
    finally:
        for path, raw in originals.items():
            path.write_bytes(raw)
