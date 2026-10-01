"""Campaign-root-confined U_CERTIFICATION artifact writer."""
from __future__ import annotations

from hashlib import sha256
import json
from fractions import Fraction
from pathlib import Path
from typing import Any, Mapping, Sequence

from hubbardflow.domain.u_certification import (
    CertificationError, Interval, certify_u_matrices, exact_slope_weights, interval_half_width, inverse,
    propagate_linear_occupation_tokens,
)
from .u_release_gate import canonical_hash
from .source_evidence import (
    SourceEvidenceError, _safe_relative_file, extract_verified_response_tokens,
    scientific_tokens_sha256, source_manifest_identity_sha256 as calculate_source_manifest_identity_sha256,
)


class UCertificationNodeError(ValueError):
    pass


def _bound_file(root: Path, relpath: str, expected_hash: str) -> tuple[Path, str]:
    candidate = Path(relpath)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise UCertificationNodeError("evidence path must be relative to the campaign root")
    path = (root / candidate).resolve(strict=True)
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise UCertificationNodeError("evidence path escapes the campaign root") from exc
    if not path.is_file():
        raise UCertificationNodeError("evidence path is not a regular file")
    digest = sha256(path.read_bytes()).hexdigest()
    if digest != expected_hash:
        raise UCertificationNodeError("INVALID_SOURCE_EVIDENCE: hash mismatch")
    return path, digest


def _derive_boxes(
    dataset: Mapping[str, Any], active_alpha_grid_eV: Sequence[Any],
) -> tuple[list[list[Interval]], list[list[Interval]]]:
    """Rebuild boxes using exactly the alpha vector committed by the analysis."""
    if dataset.get("schema_version") != "response_tokens.v1":
        raise UCertificationNodeError("INVALID_SOURCE_EVIDENCE: exact lexical response dataset is required")
    if dataset.get("status") != "AVAILABLE":
        raise UCertificationNodeError("INVALID_SOURCE_EVIDENCE: exact response tokens are unavailable")
    dimension = dataset.get("matrix_dimension")
    degree = dataset.get("polynomial_degree")
    if not isinstance(dimension, int) or dimension < 1 or not isinstance(degree, int):
        raise UCertificationNodeError("INVALID_SOURCE_EVIDENCE: malformed exact response dataset")
    if not isinstance(active_alpha_grid_eV, (list, tuple)) or not active_alpha_grid_eV:
        raise UCertificationNodeError("INVALID_SOURCE_EVIDENCE: analysis active alpha grid is missing")
    try:
        active_values = [Fraction(str(value)) for value in active_alpha_grid_eV]
        if any(isinstance(value, bool) for value in active_alpha_grid_eV):
            raise ValueError("boolean alpha")
        if any(value == 0 for value in active_values) or len(set(active_values)) != len(active_values):
            raise ValueError("zero or duplicate active alpha")
    except (ValueError, TypeError, ZeroDivisionError) as exc:
        raise UCertificationNodeError("INVALID_SOURCE_EVIDENCE: malformed analysis active alpha grid") from exc
    boxes: dict[str, list[list[Interval | None]]] = {
        "BARE": [[None for _ in range(dimension)] for _ in range(dimension)],
        "SCREENED": [[None for _ in range(dimension)] for _ in range(dimension)],
    }
    groups: dict[tuple[str, int], list[Mapping[str, Any]]] = {}
    for row in dataset.get("observations", []):
        if row.get("mode") not in boxes:
            raise UCertificationNodeError("INVALID_SOURCE_EVIDENCE: unsupported response mode")
        try:
            site_index = row["perturbed_site_index"]
            if not isinstance(site_index, int) or not 0 <= site_index < dimension:
                raise ValueError("invalid site index")
            Fraction(str(row["alpha_token"]))
        except (KeyError, TypeError, ValueError, ZeroDivisionError) as exc:
            raise UCertificationNodeError("INVALID_SOURCE_EVIDENCE: malformed response alpha coverage") from exc
        key = (row["mode"], site_index)
        groups.setdefault(key, []).append(row)
    if len(groups) != 2 * dimension:
        raise UCertificationNodeError("INVALID_SOURCE_EVIDENCE: incomplete response matrix token grid")
    try:
        for (mode, j), rows in groups.items():
            by_alpha: dict[Fraction, Mapping[str, Any]] = {}
            for row in rows:
                alpha_value = Fraction(str(row["alpha_token"]))
                if alpha_value in by_alpha:
                    raise UCertificationNodeError("INVALID_SOURCE_EVIDENCE: duplicate response alpha coverage")
                by_alpha[alpha_value] = row
            if not set(active_values).issubset(by_alpha):
                raise UCertificationNodeError("INVALID_SOURCE_EVIDENCE: active analysis alpha coverage is incomplete")
            rows = [by_alpha[alpha] for alpha in active_values]
            alphas = [str(row["alpha_token"]) for row in rows]
            weights = exact_slope_weights(alphas, degree)
            if any(len(row["occupation_tokens"]) != dimension for row in rows):
                raise UCertificationNodeError("INVALID_SOURCE_EVIDENCE: occupation vector dimension mismatch")
            for i in range(dimension):
                boxes[mode][i][j] = propagate_linear_occupation_tokens(
                    weights, [row["occupation_tokens"][i] for row in rows],
                )
    except UCertificationNodeError:
        raise
    except (KeyError, TypeError, ValueError, CertificationError) as exc:
        raise UCertificationNodeError("INVALID_SOURCE_EVIDENCE: exact token fit could not be reconstructed") from exc
    if any(value is None for matrix in boxes.values() for row in matrix for value in row):
        raise UCertificationNodeError("INVALID_SOURCE_EVIDENCE: incomplete response matrix")
    return boxes["BARE"], boxes["SCREENED"]  # type: ignore[return-value]


def certify_campaign(
    campaign_root: Path, *, analysis: Mapping[str, Any], response_dataset_path: str,
    response_dataset_sha256: str, analysis_path: str, analysis_sha256: str,
    node_evidence: list[Mapping[str, Any]], analysis_policy: Mapping[str, Any],
    source_manifest_path: str, source_manifest_sha256: str, source_manifest_file_sha256: str,
    source_manifest_identity_sha256: str,
    response_tokens_scientific_sha256: str, matrix_analysis_receipt_sha256: str,
    matrix_analysis_commitment_path: str, matrix_analysis_commitment_file_sha256: str,
    _legacy_full_grid: bool = False,
    _legacy_nominal_deviation_half_width: bool = False,
) -> tuple[dict[str, Any], str]:
    """Consume only validated, hash-bound evidence under the campaign root."""
    root = campaign_root.resolve(strict=True)
    if analysis.get("state") != "VALIDATED":
        raise UCertificationNodeError("INVALID_SOURCE_EVIDENCE: MATRIX_ANALYSIS is not VALIDATED")
    analysis_file, analysis_digest = _bound_file(root, analysis_path, analysis_sha256)
    try:
        analysis_bytes = analysis_file.read_bytes()
        if sha256(analysis_bytes).hexdigest() != analysis_digest:
            raise UCertificationNodeError("INVALID_SOURCE_EVIDENCE: analysis changed while being read")
        source_analysis = json.loads(analysis_bytes)
    except (OSError, json.JSONDecodeError) as exc:
        raise UCertificationNodeError("INVALID_SOURCE_EVIDENCE: analysis artifact is unreadable") from exc
    source_campaign = source_analysis.get("campaign", {}).get("campaign_id")
    source_primary = source_analysis.get("primary", {})
    if source_campaign != analysis.get("campaign_uuid"):
        raise UCertificationNodeError("INVALID_SOURCE_EVIDENCE: analysis campaign UUID mismatch")
    from fractions import Fraction
    for supplied, saved in ((analysis.get("chi0_nominal"), source_primary.get("matrix_used_chi0")),
                            (analysis.get("chi_nominal"), source_primary.get("matrix_used_chi"))):
        if not isinstance(supplied, list) or not isinstance(saved, list) or len(supplied) != len(saved):
            raise UCertificationNodeError("INVALID_SOURCE_EVIDENCE: nominal matrices differ from source analysis")
        try:
            if [[Fraction(str(v)) for v in row] for row in supplied] != [[Fraction(str(v)) for v in row] for row in saved]:
                raise UCertificationNodeError("INVALID_SOURCE_EVIDENCE: nominal matrices differ from source analysis")
        except (ValueError, TypeError, ZeroDivisionError) as exc:
            raise UCertificationNodeError("INVALID_SOURCE_EVIDENCE: malformed nominal matrix") from exc
    manifest_path, manifest_digest = _bound_file(root, source_manifest_path, source_manifest_file_sha256)
    try:
        manifest_bytes = manifest_path.read_bytes()
        if sha256(manifest_bytes).hexdigest() != source_manifest_file_sha256:
            raise UCertificationNodeError("INVALID_SOURCE_EVIDENCE: source manifest changed while being read")
        manifest_payload = json.loads(manifest_bytes)
        rebuilt_dataset = extract_verified_response_tokens(manifest_payload, root)
    except (OSError, json.JSONDecodeError, SourceEvidenceError) as exc:
        raise UCertificationNodeError(f"INVALID_SOURCE_EVIDENCE: {exc}") from exc
    if canonical_hash(manifest_payload) != source_manifest_sha256:
        raise UCertificationNodeError("INVALID_SOURCE_EVIDENCE: source manifest commitment mismatch")
    if calculate_source_manifest_identity_sha256(manifest_payload) != source_manifest_identity_sha256:
        raise UCertificationNodeError("INVALID_SOURCE_EVIDENCE: semantic source identity commitment mismatch")
    rebuilt_scientific_hash = scientific_tokens_sha256(rebuilt_dataset)
    if rebuilt_scientific_hash != response_tokens_scientific_sha256:
        raise UCertificationNodeError("INVALID_SOURCE_EVIDENCE: OUT-derived response tokens differ from MATRIX_ANALYSIS commitment")
    dataset_path, dataset_digest = _bound_file(root, response_dataset_path, response_dataset_sha256)
    try:
        dataset_bytes = dataset_path.read_bytes()
        if sha256(dataset_bytes).hexdigest() != dataset_digest:
            raise UCertificationNodeError("INVALID_SOURCE_EVIDENCE: response token file changed while being read")
        dataset_payload = json.loads(dataset_bytes)
    except (OSError, json.JSONDecodeError) as exc:
        raise UCertificationNodeError("INVALID_SOURCE_EVIDENCE: response token dataset is unreadable") from exc
    campaign_uuid = analysis.get("campaign_uuid") or analysis.get("campaign", {}).get("campaign_id")
    if dataset_payload.get("campaign_uuid") != campaign_uuid:
        raise UCertificationNodeError("INVALID_SOURCE_EVIDENCE: response token campaign UUID mismatch")
    if scientific_tokens_sha256(dataset_payload) != rebuilt_scientific_hash:
        raise UCertificationNodeError("INVALID_SOURCE_EVIDENCE: response_tokens.v1 differs from primary OUT re-extraction")
    if dataset_payload.get("response_tokens_scientific_sha256") != rebuilt_scientific_hash:
        raise UCertificationNodeError("INVALID_SOURCE_EVIDENCE: response_tokens scientific digest claim is wrong")
    dataset_payload = rebuilt_dataset
    for observation in dataset_payload.get("observations", []):
        try:
            _bound_file(root, str(observation["source_out_path"]), str(observation["source_out_sha256"]))
        except (KeyError, TypeError) as exc:
            raise UCertificationNodeError("INVALID_SOURCE_EVIDENCE: response observation lacks hash-bound OUT") from exc
    active_alpha_grid = source_analysis.get("analysis_alpha_grid_eV")
    if _legacy_full_grid:
        active_alpha_grid = sorted({str(row["alpha_token"]) for row in dataset_payload.get("observations", [])}, key=Fraction)
    elif not isinstance(active_alpha_grid, list):
        raise UCertificationNodeError("INVALID_SOURCE_EVIDENCE: committed analysis active alpha grid is missing")
    chi0_box, chi_box = _derive_boxes(dataset_payload, active_alpha_grid)
    evidence_hashes: list[str] = []
    receipt_digests: set[str] = set()
    for item in node_evidence:
        if item.get("state") != "VALIDATED":
            raise UCertificationNodeError("INVALID_SOURCE_EVIDENCE: scientific node is not VALIDATED")
        _, digest = _bound_file(root, str(item["path"]), str(item["sha256"]))
        evidence_hashes.append(digest)
        receipt_digest = item.get("evidence_digest")
        if not isinstance(receipt_digest, str) or len(receipt_digest) != 64:
            raise UCertificationNodeError("INVALID_SOURCE_EVIDENCE: node receipt digest is missing")
        receipt_digests.add(receipt_digest)
        if item.get("parent_dm_loaded") is not True:
            raise UCertificationNodeError("INVALID_SOURCE_EVIDENCE: required parent DM load is unproven")
    if any(row.get("node_evidence_sha256") not in receipt_digests
           for row in dataset_payload.get("observations", [])):
        raise UCertificationNodeError("INVALID_SOURCE_EVIDENCE: token row is not bound to validated node evidence")
    dimension = len(chi0_box)
    nominal_u_by_site = analysis.get("nominal_u_by_site_eV")
    if not isinstance(nominal_u_by_site, list):
        raise UCertificationNodeError("INVALID_SOURCE_EVIDENCE: nominal U missing from validated analysis")
    for field, box in (("chi0_nominal", chi0_box), ("chi_nominal", chi_box)):
        nominal_matrix = analysis.get(field)
        if not isinstance(nominal_matrix, list) or len(nominal_matrix) != len(box):
            raise UCertificationNodeError("INCONSISTENT_NOMINAL_AND_CERTIFICATE_INPUTS")
        for i, row in enumerate(box):
            if len(nominal_matrix[i]) != len(row):
                raise UCertificationNodeError("INCONSISTENT_NOMINAL_AND_CERTIFICATE_INPUTS")
            for j, cell in enumerate(row):
                try:
                    # JSON floats are converted through their decimal spelling;
                    # no binary float enters a certification comparison.
                    value = Fraction(str(nominal_matrix[i][j]))
                except (ValueError, TypeError, ZeroDivisionError) as exc:
                    raise UCertificationNodeError("INCONSISTENT_NOMINAL_AND_CERTIFICATE_INPUTS") from exc
                if not cell.contains(value):
                    raise UCertificationNodeError("INCONSISTENT_NOMINAL_AND_CERTIFICATE_INPUTS")
    try:
        nominal_chi0 = [[Fraction(str(value)) for value in row] for row in analysis["chi0_nominal"]]
        nominal_chi = [[Fraction(str(value)) for value in row] for row in analysis["chi_nominal"]]
        inverse0, inverse_screened = inverse(nominal_chi0), inverse(nominal_chi)
        if len(nominal_chi0) != dimension or len(nominal_chi) != dimension:
            raise ValueError("matrix dimension mismatch")
        nominal_u_from_matrices = [inverse0[i][i] - inverse_screened[i][i] for i in range(dimension)]
    except (KeyError, TypeError, ValueError, CertificationError) as exc:
        raise UCertificationNodeError("INCONSISTENT_NOMINAL_AND_CERTIFICATE_INPUTS") from exc
    for declared_u, reconstructed_u in zip(nominal_u_by_site, nominal_u_from_matrices):
        if abs(Fraction(str(declared_u)) - reconstructed_u) > Fraction(1, 10**10):
            raise UCertificationNodeError("INCONSISTENT_NOMINAL_AND_CERTIFICATE_INPUTS")
    try:
        certified = certify_u_matrices(chi0_box, chi_box)
    except CertificationError as exc:
        raise UCertificationNodeError(str(exc)) from exc
    intervals = certified["u_interval_by_site"]
    if intervals is None:
        certificate_status = "CERTIFICATE_NOT_ESTABLISHED"
    else:
        certificate_status = str(certified.get("status", "CERTIFIED"))
    if len(nominal_u_by_site) != dimension or (intervals is not None and len(nominal_u_by_site) != len(intervals)):
        raise UCertificationNodeError("INCONSISTENT_NOMINAL_AND_CERTIFICATE_INPUTS")
    if intervals is not None:
        for nominal, interval in zip(nominal_u_by_site, intervals):
            n = Fraction(str(nominal))
            if not Fraction(interval["lower"]) <= n <= Fraction(interval["upper"]):
                raise UCertificationNodeError("INCONSISTENT_NOMINAL_AND_CERTIFICATE_INPUTS")
        half_widths = []
        for nominal, interval in zip(nominal_u_by_site, intervals):
            lower, upper = Fraction(interval["lower"]), Fraction(interval["upper"])
            if _legacy_nominal_deviation_half_width:
                # Reproduce frozen v1/v2 certificate bytes during chain audit;
                # new certificates use the mathematical interval radius below.
                center = Fraction(str(nominal))
                half_widths.append(str(max(center - lower, upper - center)))
            else:
                half_widths.append(str(interval_half_width(lower, upper)))
        conservative_half_widths = half_widths
    else:
        conservative_half_widths = None
    if dimension == 2:
        regularity = {"chi0": certified["chi0_regular"], "chi": certified["chi_regular"]}
        cross_checks = certified["cross_checks"]
        consistency = certified["consistency_status"]
    else:
        regularity = {"chi0": certified.get("chi0_inverse"), "chi": certified.get("chi_inverse")}
        cross_checks = []
        consistency = "CONSISTENT" if certificate_status != "CERTIFICATE_NOT_ESTABLISHED" else "NOT_ESTABLISHED"
    result: dict[str, Any] = {
        "schema_version": "u_certificate.v1", "certificate_status": certificate_status,
        "campaign_uuid": str(campaign_uuid),
        "source_analysis_sha256": analysis_digest, "response_dataset_sha256": dataset_digest,
        "source_evidence_manifest_sha256": manifest_digest,
        "source_evidence_manifest_canonical_sha256": source_manifest_sha256,
        "source_manifest_identity_sha256": source_manifest_identity_sha256,
        "source_evidence_manifest_path": source_manifest_path,
        "response_tokens_scientific_sha256": rebuilt_scientific_hash,
        "response_tokens_file_sha256": dataset_digest,
        "response_tokens_path": response_dataset_path,
        "matrix_analysis_receipt_sha256": matrix_analysis_receipt_sha256,
        "matrix_analysis_commitment_path": matrix_analysis_commitment_path,
        "matrix_analysis_commitment_file_sha256": matrix_analysis_commitment_file_sha256,
        "analysis_artifact_sha256": analysis_digest,
        "analysis_artifact_path": analysis_path,
        "node_evidence_sha256": evidence_hashes,
        "occupation_source": "reextracted_from_hash_verified_primary_OUT",
        "exact_token_precision_contract": "decimal lexical token ± half printed unit; all certified operations use fractions.Fraction",
        "analysis_policy_sha256": canonical_hash(analysis_policy),
        "nominal_u_by_site_eV": nominal_u_by_site, "matrix_dimension": dimension,
        "chi0_interval": [[x.as_json() for x in row] for row in chi0_box],
        "chi_interval": [[x.as_json() for x in row] for row in chi_box],
        "regularity_certificates": regularity,
        "primary_method": certified.get("method") or certified.get("primary_method"), "u_interval_by_site": intervals,
        "half_width_by_site": conservative_half_widths,
        "cross_checks": cross_checks, "consistency_status": consistency,
        "assumptions": certified["assumptions"],
        "implementation_version": (
            "u-certification-rational-v1" if _legacy_full_grid else
            "u-certification-rational-active-grid-v2" if _legacy_nominal_deviation_half_width else
            "u-certification-rational-active-grid-v3"
        ),
        "physical_acceptance": "NOT_ESTABLISHED", "response_dataset_file": dataset_path.name,
    }
    if not _legacy_full_grid:
        result["certification_alpha_grid_eV"] = list(active_alpha_grid)
    result["certificate_scientific_sha256"] = canonical_hash(result)
    return result, canonical_hash(result)


def verify_certificate_source_chain(certificate: Mapping[str, Any], campaign_root: Path) -> None:
    """Revalidate every content commitment from a certificate to primary OUT bytes."""
    root = campaign_root.resolve(strict=True)
    def bound(key: str, expected: str) -> tuple[Path, bytes]:
        path, raw = _safe_relative_file(root, str(certificate[key]))
        if sha256(raw).hexdigest() != expected:
            raise UCertificationNodeError("SOURCE_EVIDENCE_CHANGED_AFTER_CERTIFICATION: artifact changed while read")
        return path, raw
    try:
        commitment_path, commitment_bytes = bound(
            "matrix_analysis_commitment_path", str(certificate["matrix_analysis_commitment_file_sha256"]),
        )
        commitment = json.loads(commitment_bytes)
        if canonical_hash(commitment) != certificate["matrix_analysis_receipt_sha256"]:
            raise UCertificationNodeError("SOURCE_EVIDENCE_CHANGED_AFTER_CERTIFICATION: MATRIX_ANALYSIS commitment changed")
        analysis_path, analysis_bytes = bound("analysis_artifact_path", str(certificate["analysis_artifact_sha256"]))
        analysis = json.loads(analysis_bytes)
        manifest_path, manifest_bytes = bound(
            "source_evidence_manifest_path", str(certificate["source_evidence_manifest_sha256"]),
        )
        manifest = json.loads(manifest_bytes)
        if canonical_hash(manifest) != certificate.get("source_evidence_manifest_canonical_sha256"):
            raise UCertificationNodeError("SOURCE_EVIDENCE_CHANGED_AFTER_CERTIFICATION: source manifest changed")
        if calculate_source_manifest_identity_sha256(manifest) != certificate.get("source_manifest_identity_sha256"):
            raise UCertificationNodeError("SOURCE_EVIDENCE_CHANGED_AFTER_CERTIFICATION: semantic source identity changed")
        rebuilt = extract_verified_response_tokens(manifest, root)
        if scientific_tokens_sha256(rebuilt) != certificate.get("response_tokens_scientific_sha256"):
            raise UCertificationNodeError("SOURCE_EVIDENCE_CHANGED_AFTER_CERTIFICATION: primary OUT tokens changed")
        tokens_path, tokens_bytes = bound("response_tokens_path", str(certificate["response_tokens_file_sha256"]))
        tokens = json.loads(tokens_bytes)
        if scientific_tokens_sha256(tokens) != scientific_tokens_sha256(rebuilt):
            raise UCertificationNodeError("SOURCE_EVIDENCE_CHANGED_AFTER_CERTIFICATION: response token file changed")
        policy = analysis.get("estimator_policy", {})
        if (canonical_hash(commitment) != certificate.get("matrix_analysis_receipt_sha256")
                or commitment.get("analysis_artifact_sha256") != sha256(analysis_bytes).hexdigest()
                or certificate.get("source_analysis_sha256") != sha256(analysis_bytes).hexdigest()
                or commitment.get("analysis_artifact_path") != certificate.get("analysis_artifact_path")
                or commitment.get("source_evidence_manifest_sha256") != certificate.get("source_evidence_manifest_canonical_sha256")
                or commitment.get("source_evidence_manifest_file_sha256") != sha256(manifest_bytes).hexdigest()
                or commitment.get("source_manifest_identity_sha256") != certificate.get("source_manifest_identity_sha256")
                or commitment.get("source_evidence_manifest_path") != certificate.get("source_evidence_manifest_path")
                or commitment.get("response_tokens_file_sha256") != sha256(tokens_bytes).hexdigest()
                or commitment.get("response_tokens_path") != certificate.get("response_tokens_path")
                or commitment.get("response_tokens_scientific_sha256") != certificate.get("response_tokens_scientific_sha256")
                or commitment.get("analysis_policy_sha256") != canonical_hash(policy)
                or canonical_hash(policy) != certificate.get("analysis_policy_sha256")
                or manifest.get("analysis_policy_sha256") != canonical_hash(policy)
                or commitment.get("campaign_uuid") != certificate.get("campaign_uuid")
                or manifest.get("matrix_dimension") != certificate.get("matrix_dimension")
                or rebuilt.get("campaign_uuid") != certificate.get("campaign_uuid")
                or rebuilt.get("matrix_dimension") != certificate.get("matrix_dimension")
                or certificate.get("response_dataset_sha256") != certificate.get("response_tokens_file_sha256")
                or analysis.get("campaign", {}).get("campaign_id") != certificate.get("campaign_uuid")
                or manifest.get("campaign_uuid") != certificate.get("campaign_uuid")):
            raise UCertificationNodeError("SOURCE_EVIDENCE_CHANGED_AFTER_CERTIFICATION: transitive commitment mismatch")

        # Re-run the same certifier from the committed analysis and OUT-derived
        # tokens. A certificate's self-digest only proves internal consistency;
        # this comparison proves its mathematical claims still follow from the
        # validated inputs, even if an attacker rehashes certificate and release.
        primary = analysis.get("primary", {})
        labels = analysis.get("site_labels", [])
        nominal_by_label = primary.get("U_by_site_eV")
        if (not isinstance(labels, list) or not labels or not isinstance(nominal_by_label, Mapping)
                or not isinstance(primary.get("matrix_used_chi0"), list)
                or not isinstance(primary.get("matrix_used_chi"), list)):
            raise UCertificationNodeError("SOURCE_EVIDENCE_CHANGED_AFTER_CERTIFICATION: analysis lacks reconstructable U inputs")
        normalized_analysis = {
            "state": "VALIDATED", "campaign_uuid": certificate["campaign_uuid"],
            "chi0_nominal": primary["matrix_used_chi0"],
            "chi_nominal": primary["matrix_used_chi"],
            "nominal_u_by_site_eV": [nominal_by_label.get(str(label)) for label in labels],
        }
        committed_nodes = [{
            "path": row["receipt_path"], "sha256": row["receipt_sha256"],
            "state": "VALIDATED", "evidence_digest": row["node_evidence_sha256"],
            "parent_dm_loaded": True,
        } for row in manifest.get("observations", [])]
        rebuilt_certificate, _ = certify_campaign(
            root, analysis=normalized_analysis,
            response_dataset_path=str(certificate["response_tokens_path"]),
            response_dataset_sha256=str(certificate["response_tokens_file_sha256"]),
            analysis_path=str(certificate["analysis_artifact_path"]),
            analysis_sha256=str(certificate["analysis_artifact_sha256"]),
            node_evidence=committed_nodes, analysis_policy=policy,
            source_manifest_path=str(certificate["source_evidence_manifest_path"]),
            source_manifest_sha256=str(certificate["source_evidence_manifest_canonical_sha256"]),
            source_manifest_file_sha256=str(certificate["source_evidence_manifest_sha256"]),
            source_manifest_identity_sha256=str(certificate["source_manifest_identity_sha256"]),
            response_tokens_scientific_sha256=str(certificate["response_tokens_scientific_sha256"]),
            matrix_analysis_receipt_sha256=str(certificate["matrix_analysis_receipt_sha256"]),
            matrix_analysis_commitment_path=str(certificate["matrix_analysis_commitment_path"]),
            matrix_analysis_commitment_file_sha256=str(certificate["matrix_analysis_commitment_file_sha256"]),
            _legacy_full_grid=certificate.get("implementation_version") == "u-certification-rational-v1",
            _legacy_nominal_deviation_half_width=certificate.get("implementation_version") in {
                "u-certification-rational-v1", "u-certification-rational-active-grid-v2",
            },
        )
        if rebuilt_certificate != dict(certificate):
            raise UCertificationNodeError(
                "SOURCE_EVIDENCE_CHANGED_AFTER_CERTIFICATION: certificate scientific fields do not match reconstructed inputs"
            )
        if certificate.get("certificate_scientific_sha256") != canonical_hash({
            key: value for key, value in certificate.items() if key != "certificate_scientific_sha256"
        }):
            raise UCertificationNodeError("SOURCE_EVIDENCE_CHANGED_AFTER_CERTIFICATION: certificate scientific digest mismatch")
    except UCertificationNodeError as exc:
        if "SOURCE_EVIDENCE_CHANGED_AFTER_CERTIFICATION" in str(exc):
            raise
        raise UCertificationNodeError(
            f"SOURCE_EVIDENCE_CHANGED_AFTER_CERTIFICATION: mathematical reconstruction failed: {exc}"
        ) from exc
    except (OSError, KeyError, TypeError, json.JSONDecodeError, SourceEvidenceError) as exc:
        raise UCertificationNodeError(f"SOURCE_EVIDENCE_CHANGED_AFTER_CERTIFICATION: {exc}") from exc


# Retain the original internal symbol for callers created during the v1
# 2x2 implementation; the writer now supports the general N x N route.
certify_campaign_2x2 = certify_campaign


def write_certificate(campaign_root: Path, certificate: Mapping[str, Any], digest: str) -> Path:
    root = campaign_root.resolve(strict=True)
    target = root / "u_certificate.v1.json"
    if target.exists():
        raise UCertificationNodeError("certificate artifact is immutable and already exists")
    if canonical_hash(certificate) != digest:
        raise UCertificationNodeError("certificate receipt hash mismatch")
    target.write_text(json.dumps(certificate, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target
