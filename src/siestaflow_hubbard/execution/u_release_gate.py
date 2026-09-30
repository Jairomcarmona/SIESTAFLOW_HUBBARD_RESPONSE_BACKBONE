"""Hash-bound operational release gate, distinct from physical acceptance."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping


class UReleaseError(ValueError):
    pass


def canonical_hash(value: object) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


@dataclass(frozen=True)
class UReleasePolicy:
    u_precision_tolerance_eV: str
    require_reproducibility: bool = False
    max_sensitivity_eV: str | None = None
    required_certificate_method: str = "exact_rational_2x2"
    allow_verified_fallback: bool = False
    require_scf_converged: bool = True
    require_magnetic_state_validated: bool = True

    def validate(self) -> None:
        from fractions import Fraction
        if Fraction(self.u_precision_tolerance_eV) < 0:
            raise UReleaseError("release precision tolerance must be nonnegative")
        if self.max_sensitivity_eV is not None and Fraction(self.max_sensitivity_eV) < 0:
            raise UReleaseError("sensitivity limit must be nonnegative")


def create_u_release(
    *, certificate: Mapping[str, Any], certificate_sha256: str,
    evidence: Mapping[str, Any], policy: UReleasePolicy, campaign_root: Path,
    execution_mode: str,
) -> dict[str, Any]:
    """Return a deterministic, immutable-by-contract release payload or fail closed."""
    policy.validate()
    if execution_mode != "PRODUCTION":
        raise UReleaseError("U release creation requires explicit PRODUCTION mode")
    if canonical_hash(certificate) != certificate_sha256:
        raise UReleaseError("certificate hash mismatch")
    try:
        from .u_certification_node import UCertificationNodeError, verify_certificate_source_chain
        verify_certificate_source_chain(certificate, campaign_root)
    except (UCertificationNodeError, OSError, ValueError) as exc:
        raise UReleaseError(f"SOURCE_EVIDENCE_CHANGED_AFTER_CERTIFICATION: {exc}") from exc
    if certificate.get("certificate_status") not in {"CERTIFIED", "CERTIFIED_WITH_FALLBACK"}:
        raise UReleaseError("certificate is not established")
    method = certificate.get("primary_method")
    fallback = certificate.get("certificate_status") == "CERTIFIED_WITH_FALLBACK"
    if fallback and not policy.allow_verified_fallback:
        raise UReleaseError("verified fallback is not permitted by release policy")
    if method != policy.required_certificate_method and not (policy.allow_verified_fallback and fallback):
        raise UReleaseError("certificate method is not permitted by release policy")
    if not evidence.get("all_required_nodes_validated") or not evidence.get("parent_dm_load_proven"):
        raise UReleaseError("required scientific evidence is not validated")
    if evidence.get("analysis_policy_sha256") != certificate.get("analysis_policy_sha256"):
        raise UReleaseError("analysis policy hash mismatch")
    if evidence.get("campaign_uuid") != certificate.get("campaign_uuid"):
        raise UReleaseError("campaign identity mismatch")
    if not isinstance(evidence.get("campaign_hash"), str) or len(evidence["campaign_hash"]) != 64:
        raise UReleaseError("campaign hash is missing or malformed")
    if evidence.get("sensitivity_gate") != "SENSITIVITY_WITHIN_PREDECLARED_POLICY":
        raise UReleaseError("sensitivity gate is missing or failed")
    if policy.max_sensitivity_eV is not None:
        from fractions import Fraction
        observed = evidence.get("sensitivity_max_eV")
        if observed is None or Fraction(str(observed)) > Fraction(policy.max_sensitivity_eV):
            raise UReleaseError("sensitivity exceeds or lacks the release policy limit")
    if policy.require_reproducibility and evidence.get("reproducibility_status") != "ESTABLISHED":
        raise UReleaseError("required reproducibility evidence is absent")
    if policy.require_scf_converged and evidence.get("scf_status") != "CONVERGED":
        raise UReleaseError("required SCF convergence evidence is absent")
    if policy.require_magnetic_state_validated and evidence.get("magnetic_state_status") != "VALIDATED":
        raise UReleaseError("required magnetic-state evidence is absent")
    if evidence.get("source_analysis_sha256") != certificate.get("source_analysis_sha256"):
        raise UReleaseError("source analysis hash mismatch")
    if evidence.get("response_dataset_sha256") != certificate.get("response_dataset_sha256"):
        raise UReleaseError("response dataset hash mismatch")
    if not evidence.get("projector_fingerprints"):
        raise UReleaseError("projector provenance fingerprints are absent")
    intervals = certificate.get("u_interval_by_site")
    nominal = certificate.get("nominal_u_by_site_eV")
    if not isinstance(intervals, list) or not isinstance(nominal, list) or len(intervals) != len(nominal):
        raise UReleaseError("certificate lacks nominal values or deterministic intervals")
    from fractions import Fraction
    from siestaflow_hubbard.domain.u_certification import interval_half_width
    tolerance = Fraction(policy.u_precision_tolerance_eV)
    for value, box in zip(nominal, intervals):
        # Nominal values may originate as JSON numbers; use their declared
        # decimal spelling for the release comparison, never Fraction(float).
        center = Fraction(str(value))
        lower, upper = Fraction(box["lower"]), Fraction(box["upper"])
        if not lower <= center <= upper:
            raise UReleaseError("nominal U is outside its deterministic certificate interval")
        half = interval_half_width(lower, upper)
        if half > tolerance:
            raise UReleaseError("deterministic interval exceeds release precision tolerance")
    payload: dict[str, Any] = {
        "schema_version": "u_release.v1", "release_status": "RELEASED",
        "execution_mode": execution_mode,
        "nominal_u_by_site_eV": nominal, "u_certificate_sha256": certificate_sha256,
        "campaign_uuid": certificate["campaign_uuid"],
        "campaign_hash": evidence.get("campaign_hash"),
        "analysis_policy_sha256": certificate["analysis_policy_sha256"],
        "certificate_method": method, "deterministic_interval_by_site": intervals,
        "sensitivity_gate_status": evidence["sensitivity_gate"],
        "reproducibility_status": evidence.get("reproducibility_status", "NOT_REQUIRED"),
        "source_executable_identity": evidence.get("source_executable_identity"),
        "projector_fingerprints": evidence.get("projector_fingerprints", []),
        "release_policy": asdict(policy), "physical_acceptance": "NOT_ESTABLISHED",
    }
    payload["release_sha256"] = canonical_hash(payload)
    return payload


def verify_u_release(payload: Mapping[str, Any]) -> None:
    claimed = payload.get("release_sha256")
    unsigned = dict(payload)
    unsigned.pop("release_sha256", None)
    if (payload.get("schema_version") != "u_release.v1" or payload.get("release_status") != "RELEASED"
            or payload.get("execution_mode") != "PRODUCTION"):
        raise UReleaseError("invalid release schema or status")
    if claimed != canonical_hash(unsigned):
        raise UReleaseError("release artifact hash mismatch")
    if payload.get("physical_acceptance") != "NOT_ESTABLISHED":
        raise UReleaseError("operational release cannot assert physical acceptance")


def write_u_release(root: Path, payload: Mapping[str, Any]) -> Path:
    """Write once inside the campaign root; do not overwrite an existing artifact."""
    root = root.resolve(strict=True)
    target = root / "u_release.v1.json"
    if target.exists():
        raise UReleaseError("release artifacts are immutable and already exist")
    verify_u_release(payload)
    target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target
