"""Validate generated Method-2 profiles against effective FDF and PSML identity."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np

from audit_method2_projector import parse_projector
from psml_selection import pseudo_atomic_number, read_fdf_species, select_psml_sources
from siesta_dftu_fdf import projector_specs_from_text


def species(path: Path) -> dict[str, int]:
    return read_fdf_species(path)


def fdf_sha256(fdf: Path) -> str:
    return hashlib.sha256(fdf.read_bytes()).hexdigest()


def projector_specs(fdf: Path) -> dict[str, dict[str, Any]]:
    return projector_specs_from_text(fdf.read_text(encoding="utf-8"), str(fdf))


def projector_configuration_fingerprint(fdf: Path) -> str:
    """Hash every effective projector target and setting, excluding U/J values."""
    specs = projector_specs(fdf)
    active_block = next(iter(specs.values()))["effective_block"]
    payload = {
        "method": 2,
        "effective_block": active_block,
        "projectors": {
            label: list(spec["structure"])
            for label, spec in sorted(specs.items())
        },
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _sha256(path: Path) -> str:
    content = path.read_bytes()
    if not content:
        raise ValueError(f"file is empty: {path}")
    return hashlib.sha256(content).hexdigest()


def pseudo_key(run_dir: Path, label: str, expected_z: int) -> str:
    path = run_dir / f"{label}.psml"
    if not path.is_file():
        raise ValueError(f"missing staged pseudopotential {path}")
    actual_z = pseudo_atomic_number(path)
    if actual_z != expected_z:
        raise ValueError(f"{path}: PSML atomic number Z={actual_z} does not match FDF Z={expected_z}")
    return _sha256(path)


def selected_psml_hashes(fdf: Path, pseudo_directory: Path) -> dict[str, str]:
    species_map = species(fdf)
    sources = select_psml_sources(species_map, sorted(pseudo_directory.glob("*.psml")))
    return {label: _sha256(path) for label, path in sorted(sources.items())}


def _profile(path: Path) -> tuple[int, int, np.ndarray, np.ndarray, float]:
    if not path.is_file():
        raise ValueError(f"generated projector missing: {path}")
    return parse_projector(path)


def _profile_signature(path: Path, spec: dict[str, Any], context: str) -> tuple[Any, ...]:
    l_value, n_value, grid, radial, cutoff = _profile(path)
    # The second value in SIESTA's .dftu_proj header is a sequence number,
    # not the principal quantum number supplied in the FDF.
    if l_value != spec["l"]:
        raise ValueError(f"{context} projector l={l_value} disagrees with FDF l={spec['l']}")
    return (l_value, n_value, cutoff, tuple(grid.tolist()), tuple(radial.tolist()))


def verify(reference_fdf: Path, reference_dir: Path, candidate_fdf: Path, candidate_dir: Path) -> None:
    ref_species, cand_species = species(reference_fdf), species(candidate_fdf)
    ref_specs, cand_specs = projector_specs(reference_fdf), projector_specs(candidate_fdf)
    ref_labels, cand_labels = set(ref_specs), set(cand_specs)
    if ref_labels != cand_labels:
        missing = sorted(ref_labels - cand_labels)
        extra = sorted(cand_labels - ref_labels)
        raise ValueError(
            "projected alias label sets differ between accepted reference and candidate "
            f"(missing={missing}, extra={extra})"
        )

    def collect(species_map: dict[str, int], specs: dict[str, dict[str, Any]], run_dir: Path):
        targets: dict[str, tuple[tuple[Any, ...], tuple[Any, ...]]] = {}
        profiles_by_group: dict[tuple[Any, ...], dict[str, tuple[Any, ...]]] = {}
        for label, spec in specs.items():
            if label not in species_map:
                raise ValueError(f"projected label {label} is missing from ChemicalSpeciesLabel")
            z = species_map[label]
            key = pseudo_key(run_dir, label, z)
            profile = _profile_signature(run_dir / f"{label}.dftu_proj", spec, f"{run_dir}/{label}")
            group_key = (z, key, spec["structure"])
            targets[label] = (group_key, profile)
            profiles_by_group.setdefault(group_key, {})[label] = profile
        return targets, profiles_by_group

    reference_targets, reference_profiles_by_group = collect(ref_species, ref_specs, reference_dir)
    candidate_targets, _ = collect(cand_species, cand_specs, candidate_dir)
    for group_key, aliases in reference_profiles_by_group.items():
        if len(set(aliases.values())) != 1:
            labels = sorted(aliases)
            raise ValueError(
                f"reference aliases have distinct radial profiles for {group_key}: {labels}"
            )
    for label in sorted(ref_labels):
        reference_group, reference_profile = reference_targets[label]
        candidate_group, candidate_profile = candidate_targets[label]
        if candidate_group != reference_group:
            raise ValueError(
                f"candidate projected alias {label} has different species/PSML/configuration "
                "from the accepted reference"
            )
        if candidate_profile != reference_profile:
            raise ValueError(f"candidate alias projector differs from frozen reference for {label}")


def verify_preflight(
    fdf: Path,
    reference_dir: Path | None,
    preflight_dir: Path,
    label: str,
    pseudo_directory: Path | None = None,
) -> None:
    """Validate Gate-0 materialization, optionally against a completed reference run."""
    specs = projector_specs(fdf)
    if label not in specs:
        raise ValueError(f"preflight label {label} is not declared in the effective projector block")
    manifest_path = preflight_dir / "materialization.json"
    if not manifest_path.is_file():
        raise ValueError(f"preflight materialization manifest missing: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 2 or manifest.get("status") != "PROJECTOR_MATERIALIZED_ONLY":
        raise ValueError("preflight materialization manifest is not a complete schema-v2 materialization")
    if manifest.get("fdf_sha256") != fdf_sha256(fdf):
        raise ValueError("preflight FDF fingerprint differs from the current FDF")
    if manifest.get("projector_configuration_sha256") != projector_configuration_fingerprint(fdf):
        raise ValueError("preflight effective projector configuration differs from the current FDF")

    species_map = species(fdf)
    expected_psml_hashes = manifest.get("pseudopotential_sha256")
    if not isinstance(expected_psml_hashes, dict) or set(expected_psml_hashes) != set(species_map):
        raise ValueError("preflight manifest does not contain a PSML identity for every FDF species label")
    if pseudo_directory is not None:
        current_psml_hashes = selected_psml_hashes(fdf, pseudo_directory)
        if current_psml_hashes != expected_psml_hashes:
            raise ValueError("preflight PSML identities differ from the currently selected pseudopotentials")
    if reference_dir is not None:
        ref_input = reference_dir / "siesta.fdf"
        if ref_input.is_file() and fdf_sha256(ref_input) != manifest["fdf_sha256"]:
            raise ValueError("reference run FDF differs from the preflight FDF fingerprint")
        reference_psml_hashes = {
            species_label: pseudo_key(reference_dir, species_label, atomic_number)
            for species_label, atomic_number in species_map.items()
        }
        if reference_psml_hashes != expected_psml_hashes:
            raise ValueError("reference-run PSML identities differ from preflight")
    elif pseudo_directory is None:
        raise ValueError("preflight validation requires --reference-dir or --pseudo-directory")

    projected_labels = sorted(specs)
    if manifest.get("projected_labels") != projected_labels:
        raise ValueError("preflight manifest projected-label set differs from the current FDF")
    profile_names = {f"{projected_label}.dftu_proj" for projected_label in projected_labels}
    if manifest.get("projector_files") != sorted(profile_names):
        raise ValueError("preflight manifest projector-file set differs from the current FDF")
    if not profile_names.issubset(set(manifest.get("files", []))):
        raise ValueError("preflight manifest does not list every projected profile")

    for projected_label in projected_labels:
        preflight_profile = _profile_signature(
            preflight_dir / f"{projected_label}.dftu_proj", specs[projected_label], f"preflight {projected_label}"
        )
        if reference_dir is not None:
            if pseudo_key(reference_dir, projected_label, species_map[projected_label]) != expected_psml_hashes[projected_label]:
                raise ValueError(f"preflight PSML identity differs from accepted reference for {projected_label}")
            reference_profile = _profile_signature(
                reference_dir / f"{projected_label}.dftu_proj",
                specs[projected_label],
                f"reference {projected_label}",
            )
            if preflight_profile != reference_profile:
                raise ValueError(f"accepted reference projector differs from preflight materialization for {projected_label}")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--reference-fdf", type=Path, required=True, help="FDF whose effective projector configuration is checked")
    p.add_argument("--reference-dir", type=Path, help="completed reference-run directory; optional for Gate-0 cache validation")
    p.add_argument("--candidate-fdf", type=Path)
    p.add_argument("--candidate-dir", type=Path)
    p.add_argument("--preflight-dir", type=Path)
    p.add_argument("--pseudo-directory", type=Path, help="source PSML directory to re-resolve during preflight validation")
    p.add_argument("--label", help="central label when validating preflight materialization")
    a = p.parse_args()
    if a.preflight_dir:
        if not a.label:
            p.error("--label is required with --preflight-dir")
        verify_preflight(a.reference_fdf, a.reference_dir, a.preflight_dir, a.label, a.pseudo_directory)
    else:
        if not a.reference_dir or not a.candidate_fdf or not a.candidate_dir:
            p.error("--reference-dir, --candidate-fdf and --candidate-dir are required without --preflight-dir")
        verify(a.reference_fdf, a.reference_dir, a.candidate_fdf, a.candidate_dir)
    print("PROJECTOR_IDENTITY_OK")


if __name__ == "__main__":
    main()
