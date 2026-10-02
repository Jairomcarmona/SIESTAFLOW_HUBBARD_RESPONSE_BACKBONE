"""Campaign-file reconstruction for response-grid evidence validation."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from hubbardflow.domain.adaptive_alpha_control import AdaptiveAlphaPolicy
from hubbardflow.domain.lr_analysis_v2 import LRAnalysisPolicy
from hubbardflow.domain.response_grid_reproducibility import (
    ResponseGridCalibrationError,
    response_grid_campaign_context_sha256,
)
from .campaign_v2 import load_campaign_v2, sha256_file, verify_campaign_inventory


def response_grid_source_campaign_context(manifest_path: Path) -> tuple[dict[str, Any], str]:
    """Reconstruct response context from a validated, pinned source campaign."""
    campaign = load_campaign_v2(manifest_path)
    verify_campaign_inventory(campaign)
    root = Path(str(campaign["_campaign_root"])).resolve(strict=True)
    config_relative = Path(str(campaign["lr_config_file"]))
    if config_relative.is_absolute() or ".." in config_relative.parts:
        raise ResponseGridCalibrationError("source LR config path is not campaign-relative")
    config_path = (root / config_relative).resolve(strict=True)
    try:
        config_path.relative_to(root)
    except ValueError as exc:
        raise ResponseGridCalibrationError("source LR config escapes campaign root") from exc
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ResponseGridCalibrationError("source LR config is unreadable") from exc
    if not isinstance(config, Mapping):
        raise ResponseGridCalibrationError("source LR config must be an object")
    pseudopotentials = config.get("pseudopotentials")
    if not isinstance(pseudopotentials, Mapping) or not pseudopotentials:
        raise ResponseGridCalibrationError("source LR config lacks pseudopotential paths")
    pseudo_hashes: dict[str, str] = {}
    for label, raw in sorted(pseudopotentials.items()):
        if not isinstance(raw, str):
            raise ResponseGridCalibrationError(f"source pseudopotential path for {label} is invalid")
        pseudo = Path(raw)
        if not pseudo.is_absolute():
            pseudo = root / pseudo
        pseudo = pseudo.resolve(strict=True)
        if not pseudo.is_file():
            raise ResponseGridCalibrationError(f"source pseudopotential for {label} is not a file")
        pseudo_hashes[str(label)] = sha256_file(pseudo)
    analysis_raw = config.get("analysis_policy", {})
    if not isinstance(analysis_raw, Mapping):
        raise ResponseGridCalibrationError("source analysis_policy must be an object")
    try:
        analysis_context = LRAnalysisPolicy(**analysis_raw).response_context()
    except (TypeError, ValueError) as exc:
        raise ResponseGridCalibrationError(f"source analysis policy is invalid: {exc}") from exc
    adaptive_raw = config.get("adaptive_alpha_policy")
    if adaptive_raw is None:
        adaptive_context = None
    else:
        try:
            adaptive_context = AdaptiveAlphaPolicy.from_mapping(adaptive_raw).to_mapping()
        except (TypeError, ValueError) as exc:
            raise ResponseGridCalibrationError(f"source adaptive alpha policy is invalid: {exc}") from exc
    reference_fdf_rel = Path(str(campaign["reference_fdf"]))
    profile_rel = Path(str(campaign["execution_profile_file"]))
    if (reference_fdf_rel.is_absolute() or profile_rel.is_absolute()
            or ".." in reference_fdf_rel.parts or ".." in profile_rel.parts):
        raise ResponseGridCalibrationError("source FDF/profile path is not campaign-relative")
    reference_fdf = (root / reference_fdf_rel).resolve(strict=True)
    profile = (root / profile_rel).resolve(strict=True)
    for path in (reference_fdf, profile):
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise ResponseGridCalibrationError("source FDF/profile path escapes campaign root") from exc
    context_hash = response_grid_campaign_context_sha256(
        material=campaign.get("material"),
        functional=str(campaign["functional"]),
        reference_fdf_sha256=sha256_file(reference_fdf),
        execution_profile_sha256=sha256_file(profile),
        pseudopotentials=pseudo_hashes,
        sites=campaign["sites"],
        alpha_grid_eV=[float(value) for value in campaign["alpha_grid_ev"]],
        analysis_policy=analysis_context,
        adaptive_alpha_policy=adaptive_context,
        magnetic_moment_tolerance_muB=campaign.get("magnetic_moment_tolerance_muB"),
    )
    return campaign, context_hash
