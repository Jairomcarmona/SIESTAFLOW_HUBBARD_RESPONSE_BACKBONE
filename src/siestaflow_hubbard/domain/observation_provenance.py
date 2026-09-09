"""Immutable identities and gates for observed LR-U data.

The module is intentionally independent of SIESTA and Slurm.  A backend must
derive the evidence hashes and semantic flags from real artifacts; a hash or a
boolean supplied by an untrusted caller is not proof of physical validity.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import math
import re
from typing import Mapping, Sequence


_HASH = re.compile(r"[0-9a-f]{64}")


def canonical_json_bytes(payload: object) -> bytes:
    """Encode a deliberately narrow, deterministic JSON profile."""

    def validate(value: object) -> None:
        if value is None or type(value) in (str, bool, int):
            return
        if type(value) is float and math.isfinite(value):
            return
        if isinstance(value, (list, tuple)):
            for item in value:
                validate(item)
            return
        if type(value) is dict and all(type(key) is str for key in value):
            for item in value.values():
                validate(item)
            return
        raise ValueError("value is outside the canonical provenance JSON profile")

    validate(payload)
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def content_sha256(payload: object) -> str:
    return sha256(canonical_json_bytes(payload)).hexdigest()


def _is_hash(value: object) -> bool:
    return isinstance(value, str) and _HASH.fullmatch(value) is not None


@dataclass(frozen=True)
class RunIdentity:
    campaign: str
    step: str
    mode: str
    alpha_ev: float
    observed_channel: str
    perturbed_channel: str
    fdf_sha256: str
    pseudos: tuple[tuple[str, str], ...]
    parent_dm_sha256: str
    subspace_sha256: str
    projector_sha256: str
    physical_model_sha256: str
    runtime_sha256: str
    magnetic_reference_sha256: str
    selector_policy_sha256: str


@dataclass(frozen=True)
class Observation:
    identity: RunIdentity
    occupation: float
    output_sha256: str
    scf_state: str
    scf_evidence_sha256: str
    dm_read_verified: bool
    complete: bool
    return_code: int


def validate_observation(observation: Observation, expected: RunIdentity) -> str:
    """Return an identity hash only for a complete, planned observation."""

    if observation.identity != expected:
        raise ValueError("observation identity differs from the approved plan")
    identity = observation.identity
    if identity.mode not in {"BARE", "SCREENED"} or not math.isfinite(identity.alpha_ev):
        raise ValueError("invalid mode or alpha")
    for name in ("campaign", "step", "observed_channel", "perturbed_channel"):
        if not isinstance(getattr(identity, name), str) or not getattr(identity, name).strip():
            raise ValueError(f"empty identity field: {name}")
    for name, value in asdict(identity).items():
        if name.endswith("sha256") and not _is_hash(value):
            raise ValueError(f"invalid required hash: {name}")
    if (
        not identity.pseudos
        or tuple(sorted(identity.pseudos)) != identity.pseudos
        or len({label for label, _ in identity.pseudos}) != len(identity.pseudos)
        or any(not isinstance(label, str) or not label or not _is_hash(digest) for label, digest in identity.pseudos)
    ):
        raise ValueError("pseudopotentials must be sorted unique label/hash pairs")
    required_state = {"BARE": "bare_selected_verified", "SCREENED": "converged_verified"}[identity.mode]
    if (
        observation.complete is not True
        or observation.dm_read_verified is not True
        or type(observation.return_code) is not int
        or observation.return_code != 0
        or observation.scf_state != required_state
        or not math.isfinite(observation.occupation)
        or not _is_hash(observation.output_sha256)
        or not _is_hash(observation.scf_evidence_sha256)
    ):
        raise ValueError("observation lacks positive semantic completion evidence")
    return content_sha256(asdict(observation))


def validate_response_lot(
    observations: Sequence[Observation],
    expected_by_step: Mapping[str, RunIdentity],
    required_alphas_ev: Sequence[float],
    required_modes: Sequence[str] = ("BARE", "SCREENED"),
) -> dict[str, object]:
    """Gate one observed/perturbed channel before it enters matrix assembly.

    It deliberately requires a full mode-by-alpha Cartesian grid and invariant
    physical model, parent DM, runtime, projector, subspace, pseudo and
    magnetic-reference identities.  Cross-channel assembly remains a separate
    gate because its channel map belongs to the matrix layer.
    """

    if not observations or not required_alphas_ev or not required_modes:
        raise ValueError("observations, alpha grid, and modes are required")
    if len(set(required_alphas_ev)) != len(required_alphas_ev) or any(not math.isfinite(alpha) for alpha in required_alphas_ev):
        raise ValueError("required alpha grid is invalid")
    if set(required_modes) - {"BARE", "SCREENED"} or len(set(required_modes)) != len(required_modes):
        raise ValueError("required modes are invalid")

    invariant_names = (
        "campaign", "observed_channel", "perturbed_channel", "pseudos", "parent_dm_sha256",
        "subspace_sha256", "projector_sha256", "physical_model_sha256", "runtime_sha256",
        "magnetic_reference_sha256", "selector_policy_sha256",
    )
    reference = observations[0].identity
    seen: set[tuple[str, float]] = set()
    seen_steps: set[str] = set()
    hashes: list[str] = []
    for observation in observations:
        identity = observation.identity
        if identity.step not in expected_by_step:
            raise ValueError("unplanned step")
        hashes.append(validate_observation(observation, expected_by_step[identity.step]))
        if any(getattr(identity, name) != getattr(reference, name) for name in invariant_names):
            raise ValueError("response lot mixes immutable physical identities")
        key = (identity.mode, identity.alpha_ev)
        if key in seen or identity.step in seen_steps:
            raise ValueError("duplicate mode/alpha or step; replicas need an explicit policy")
        seen.add(key)
        seen_steps.add(identity.step)
    expected_keys = {(mode, alpha) for mode in required_modes for alpha in required_alphas_ev}
    if seen != expected_keys:
        raise ValueError("response lot is incomplete or contains unplanned alpha/mode points")
    return {
        "status": "compatible_for_analysis",
        "observation_hashes": sorted(hashes),
        "analysis_input_sha256": content_sha256(sorted(hashes)),
        "parent_dm_sha256": reference.parent_dm_sha256,
    }
