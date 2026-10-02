"""Opt-in label splitting with exact, reference-bound input identity checks.

This backend stages aliases; it neither establishes site equivalence nor runs
SIESTA. Generated ion files must pass the same verification after execution.
Only the two audited .ion label fields are normalized; every physical byte is
compared exactly. Staging is explicitly pending generated-basis verification.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from tempfile import TemporaryDirectory

from hubbardflow.siesta_backend.fdf_model import (
    FdfModel,
    SpeciesIdentityStatus,
    parse_effective_fdf,
    species_identity,
)
from hubbardflow.siesta_backend.semantic_ion_identity import (
    IonIdentityError,
    canonical_ion_bytes,
    relabel_ion_bytes,
)
from hubbardflow.siesta_backend.semantic_split_models import (
    DISABLED_SEMANTIC_SPLIT_POLICY,
    SemanticSpeciesIdentityEvidence,
    SemanticSpeciesSplitError,
    SemanticSpeciesSplitPolicy,
    SemanticSpeciesSplitResult,
    SemanticSplitCode,
)


def _replace_block(content: str, name: str, rows: list[str]) -> str:
    pattern = rf"(?im)^\s*%block\s+{re.escape(name)}\s*$[\s\S]*?^\s*%endblock(?:\s+{re.escape(name)})?\s*$"
    replacement = f"%block {name}\n" + "\n".join(rows) + f"\n%endblock {name}"
    content, count = re.subn(pattern, lambda _: replacement, content)
    if count != 1:
        raise SemanticSpeciesSplitError(SemanticSplitCode.INVALID_SPLIT_INPUT, f"missing or duplicate {name}")
    return content


def _basis_records(model: FdfModel) -> tuple[tuple[str, tuple[str, ...]], ...]:
    match = re.search(
        r"(?im)^\s*%block\s+PAO\.Basis\s*$([\s\S]*?)^\s*%endblock(?:\s+PAO\.Basis)?\s*$", model.effective_text
    )
    if match is None:
        raise SemanticSpeciesSplitError(
            SemanticSplitCode.SPECIES_IDENTITY_NOT_ESTABLISHED, "PAO.Basis missing"
        )
    labels = {item.label for item in model.chemical_species_labels}
    records: list[tuple[str, tuple[str, ...]]] = []
    active: str | None = None
    rows: list[str] = []
    for raw in match.group(1).splitlines():
        fields = raw.split("#", 1)[0].split()
        if fields and fields[0] in labels:
            if active is not None:
                records.append((active, tuple(rows)))
            active, rows = fields[0], [raw]
        elif active is not None:
            rows.append(raw)
    if active is not None:
        records.append((active, tuple(rows)))
    if len({label for label, _ in records}) != len(records):
        raise SemanticSpeciesSplitError(SemanticSplitCode.INVALID_SPLIT_INPUT, "duplicate PAO.Basis species")
    return tuple(records)


def _split_geometry(model: FdfModel, target_species: str, labels: tuple[str, ...]) -> str:
    """Change species indices only; preserve every coordinate token and comment."""
    others = tuple(item for item in model.chemical_species_labels if item.label != target_species)
    by_label = {label: index for index, label in enumerate(labels, 1)}
    by_label.update({item.label: index for index, item in enumerate(others, len(labels) + 1)})
    target = next(item for item in model.chemical_species_labels if item.label == target_species)
    species_rows = [f"{by_label[label]} {target.atomic_number} {label}" for label in labels]
    species_rows.extend(f"{by_label[item.label]} {item.atomic_number} {item.label}" for item in others)
    content = _replace_block(model.effective_text, "ChemicalSpeciesLabel", species_rows)
    match = re.search(
        r"(?im)^\s*%block\s+AtomicCoordinatesAndAtomicSpecies\s*$([\s\S]*?)^\s*%endblock(?:\s+AtomicCoordinatesAndAtomicSpecies)?\s*$",
        model.effective_text,
    )
    assert match is not None  # Already validated by the audited FDF parser.
    coordinate_rows: list[str] = []
    atom_index = 0
    target_index = 0
    for raw in match.group(1).splitlines():
        fields = list(re.finditer(r"\S+", raw.split("#", 1)[0]))
        if fields:
            atom = model.atoms[atom_index]
            label = atom.species_label
            if label == target_species:
                label = labels[target_index]
                target_index += 1
            token = fields[3]
            raw = raw[: token.start()] + str(by_label[label]) + raw[token.end() :]
            atom_index += 1
        coordinate_rows.append(raw)
    content = _replace_block(content, "AtomicCoordinatesAndAtomicSpecies", coordinate_rows)
    return re.sub(
        r"(?im)^(\s*NumberOfSpecies\s+)\d+", lambda m: m[1] + str(len(labels) + len(others)), content
    )


def _source_blob(label: str, suffix: str, directories: tuple[Path, ...]) -> bytes:
    blobs = [
        (directory / f"{label}{suffix}").read_bytes()
        for directory in directories
        if (directory / f"{label}{suffix}").is_file()
    ]
    if not blobs or len(set(blobs)) != 1:
        raise SemanticSpeciesSplitError(
            SemanticSplitCode.SPECIES_IDENTITY_NOT_ESTABLISHED, f"missing or conflicting {label}{suffix}"
        )
    return blobs[0]


def _canonical_basis_record(model: FdfModel, label: str) -> tuple[str, ...]:
    rows = dict(_basis_records(model)).get(label)
    if not rows:
        raise SemanticSpeciesSplitError(
            SemanticSplitCode.SPECIES_IDENTITY_NOT_ESTABLISHED, f"missing {label} basis"
        )
    return (re.sub(r"\S+", "X", rows[0], count=1), *rows[1:])


def _basis_options(model: FdfModel) -> tuple[str, ...]:
    # Global PAO directives are preserved byte-for-byte, including units/comments.
    return tuple(
        line for line in model.effective_text.splitlines() if re.match(r"\s*PAO\.", line, re.IGNORECASE)
    )


def verify_semantic_split_identities(
    materialized_fdf_path: Path,
    labels: tuple[str, ...],
    source_fdf_path: Path,
    source_label: str,
    search_dirs: tuple[Path, ...],
    reference_search_dirs: tuple[Path, ...],
) -> SemanticSpeciesIdentityEvidence:
    """Verify staged or regenerated aliases against the immutable reference.

    Call after SIESTA regenerates .ion files as well as after staging. A missing
    reference ion cannot demonstrate preservation of the generated basis.
    """
    source = parse_effective_fdf(source_fdf_path)
    reference_identity = species_identity(source, reference_search_dirs).get(source_label)
    if (
        reference_identity is None
        or reference_identity.status != SpeciesIdentityStatus.ESTABLISHED
        or reference_identity.ion_sha256 is None
    ):
        raise SemanticSpeciesSplitError(
            SemanticSplitCode.SPECIES_IDENTITY_NOT_ESTABLISHED, "reference PP, basis and .ion are required"
        )
    model = parse_effective_fdf(materialized_fdf_path)
    identities = species_identity(model, search_dirs)
    if _basis_options(model) != _basis_options(source):
        raise SemanticSpeciesSplitError(
            SemanticSplitCode.SPECIES_IDENTITY_NOT_ESTABLISHED, "global basis options changed"
        )
    reference_ion = _source_blob(source_label, ".ion", reference_search_dirs)
    try:
        canonical_reference = canonical_ion_bytes(reference_ion, source_label)
    except IonIdentityError as exc:
        raise SemanticSpeciesSplitError(SemanticSplitCode.SPECIES_IDENTITY_NOT_ESTABLISHED, str(exc)) from exc
    semantic_digest = hashlib.sha256(
        json.dumps(
            {
                "atomic_number": reference_identity.atomic_number,
                "pseudopotential_sha256": reference_identity.pseudopotential_sha256,
                "basis_record": _canonical_basis_record(source, source_label),
                "basis_options": _basis_options(source),
                "canonical_ion_sha256": hashlib.sha256(canonical_reference).hexdigest(),
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()
    source_projector = next((record for record in source.dftu_records if record.label == source_label), None)
    if source_projector is None:
        raise SemanticSpeciesSplitError(
            SemanticSplitCode.INVALID_SPLIT_INPUT, "source label has no DFTU projector"
        )
    expected_projector = re.sub(r"\S+", "X", source_projector.canonical_text, count=1)
    projectors = {record.label: record for record in model.dftu_records}
    for label in labels:
        identity = identities.get(label)
        if (
            identity is None
            or identity.status != SpeciesIdentityStatus.ESTABLISHED
            or (identity.atomic_number, identity.pseudopotential_sha256, identity.pao_basis_sha256)
            != (
                reference_identity.atomic_number,
                reference_identity.pseudopotential_sha256,
                reference_identity.pao_basis_sha256,
            )
            or _canonical_basis_record(model, label) != _canonical_basis_record(source, source_label)
        ):
            raise SemanticSpeciesSplitError(
                SemanticSplitCode.SPECIES_IDENTITY_NOT_ESTABLISHED,
                f"alias {label} differs from reference identity",
            )
        if (
            label not in projectors
            or re.sub(r"\S+", "X", projectors[label].canonical_text, count=1) != expected_projector
        ):
            raise SemanticSpeciesSplitError(
                SemanticSplitCode.SPECIES_IDENTITY_NOT_ESTABLISHED, f"alias {label} projector differs"
            )
        for suffix in (".psml", ".psf", ".vps"):
            if any(
                (directory / f"{source_label}{suffix}").is_file() for directory in reference_search_dirs
            ) and _source_blob(label, suffix, search_dirs) != _source_blob(
                source_label, suffix, reference_search_dirs
            ):
                raise SemanticSpeciesSplitError(
                    SemanticSplitCode.SPECIES_IDENTITY_NOT_ESTABLISHED, f"alias {label}{suffix} differs"
                )
        try:
            ion = canonical_ion_bytes(_source_blob(label, ".ion", search_dirs), label)
        except IonIdentityError as exc:
            raise SemanticSpeciesSplitError(
                SemanticSplitCode.SPECIES_IDENTITY_NOT_ESTABLISHED, str(exc)
            ) from exc
        if ion != canonical_reference:
            raise SemanticSpeciesSplitError(
                SemanticSplitCode.SPECIES_IDENTITY_NOT_ESTABLISHED,
                f"alias {label} ion physical payload differs",
            )
    return SemanticSpeciesIdentityEvidence(semantic_digest, labels)


def materialize_semantic_split_species_fdf(
    source_fdf_path: Path,
    target_species: str,
    new_prefix: str,
    output_directory: Path,
    search_dirs: tuple[Path, ...],
    *,
    policy: SemanticSpeciesSplitPolicy = DISABLED_SEMANTIC_SPLIT_POLICY,
) -> SemanticSpeciesSplitResult:
    """Duplicate one shared DFTU species without changing its physics inputs.

    Input identity checks precede file writes. Existing output files are never
    overwritten; no reference DM or magnetic evidence is inferred or generated.
    The caller must freeze the returned policy digest before production use.
    """
    if not isinstance(policy, SemanticSpeciesSplitPolicy):
        raise SemanticSpeciesSplitError(
            SemanticSplitCode.INVALID_SPLIT_INPUT, "explicit split policy object required"
        )
    if not policy.auto_split_species:
        raise SemanticSpeciesSplitError(
            SemanticSplitCode.SHARED_LABEL_NEEDS_SPLIT, "automatic species splitting requires explicit opt-in"
        )
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", new_prefix):
        raise SemanticSpeciesSplitError(
            SemanticSplitCode.INVALID_SPLIT_INPUT, "alias prefix must be a safe species label"
        )
    model = parse_effective_fdf(source_fdf_path)
    allowed_blocks = {
        "chemicalspecieslabel",
        "atomiccoordinatesandatomicspecies",
        "latticevectors",
        "dftu.proj",
        "pao.basis",
        "dm.initspin",
        "kgrid_monkhorst_pack",
    }
    blocks = {match[1].casefold() for match in re.finditer(r"(?im)^\s*%block\s+(\S+)", model.effective_text)}
    if blocks - allowed_blocks or re.search(r"(?im)^\s*AtomicMass\b", model.effective_text):
        raise SemanticSpeciesSplitError(
            SemanticSplitCode.INVALID_SPLIT_INPUT,
            "unmodeled blocks/species-indexed controls cannot be preserved safely",
        )
    labels_in_model = {item.label for item in model.chemical_species_labels}
    for raw in _basis_options(model):
        fields = raw.split("#", 1)[0].split()
        if (
            fields[0].casefold() not in {"pao.basissize", "pao.basistype", "pao.energyshift", "pao.splitnorm"}
            or any(token in labels_in_model for token in fields[1:])
            or (fields[0].casefold() in {"pao.basissize", "pao.basistype"} and len(fields) != 2)
        ):
            raise SemanticSpeciesSplitError(
                SemanticSplitCode.INVALID_SPLIT_INPUT, "unmodeled or species-indexed PAO option"
            )
    targets = [atom for atom in model.atoms if atom.species_label == target_species]
    if len(targets) < 2 or target_species not in {record.label for record in model.dftu_records}:
        raise SemanticSpeciesSplitError(
            SemanticSplitCode.INVALID_SPLIT_INPUT, "target must be a shared DFTU label"
        )
    labels = tuple(f"{new_prefix}{index}" for index in range(len(targets)))
    if set(labels) & {item.label for item in model.chemical_species_labels}:
        raise SemanticSpeciesSplitError(
            SemanticSplitCode.INVALID_SPLIT_INPUT, "split labels collide with existing species"
        )
    reference = species_identity(model, search_dirs)[target_species]
    if reference.status != SpeciesIdentityStatus.ESTABLISHED or reference.ion_sha256 is None:
        raise SemanticSpeciesSplitError(
            SemanticSplitCode.SPECIES_IDENTITY_NOT_ESTABLISHED,
            "target requires PP, explicit basis and reference .ion",
        )
    basis_records = _basis_records(model)
    if not dict(basis_records).get(target_species) or not dict(model.pao_basis_blocks).get(target_species):
        raise SemanticSpeciesSplitError(
            SemanticSplitCode.SPECIES_IDENTITY_NOT_ESTABLISHED, "target basis must have explicit contents"
        )
    content = _split_geometry(model, target_species, labels)
    basis_rows: list[str] = []
    for label, rows in basis_records:
        for alias in labels if label == target_species else (label,):
            basis_rows.extend((re.sub(r"\S+", alias, rows[0], count=1), *rows[1:]))
    content = _replace_block(content, "PAO.Basis", basis_rows)
    dftu_rows: list[str] = []
    for record in model.dftu_records:
        projector_rows = record.canonical_text.splitlines()
        for alias in labels if record.label == target_species else (record.label,):
            dftu_rows.extend((re.sub(r"\S+", alias, projector_rows[0], count=1), *projector_rows[1:]))
    content = _replace_block(content, "DFTU.Proj", dftu_rows)
    staged: dict[Path, bytes] = {}
    for suffix in (".psml", ".psf", ".vps", ".ion"):
        sources = [
            directory / f"{target_species}{suffix}"
            for directory in search_dirs
            if (directory / f"{target_species}{suffix}").is_file()
        ]
        if not sources:
            continue
        blobs = [path.read_bytes() for path in sources]
        if len(set(blobs)) != 1:
            raise SemanticSpeciesSplitError(
                SemanticSplitCode.SPECIES_IDENTITY_NOT_ESTABLISHED, f"conflicting source {suffix} files"
            )
        for label in labels:
            try:
                staged[output_directory / f"{label}{suffix}"] = (
                    relabel_ion_bytes(blobs[0], target_species, label) if suffix == ".ion" else blobs[0]
                )
            except IonIdentityError as exc:
                raise SemanticSpeciesSplitError(
                    SemanticSplitCode.SPECIES_IDENTITY_NOT_ESTABLISHED, str(exc)
                ) from exc
    destination = output_directory / "split-species.fdf"
    staged[destination] = content.encode("utf-8")
    if any(path.exists() for path in staged):
        raise SemanticSpeciesSplitError(
            SemanticSplitCode.INVALID_SPLIT_INPUT,
            "output alias files already exist; choose a fresh directory",
        )
    with TemporaryDirectory(prefix="hubbardflow-split-check-") as temporary:
        check_directory = Path(temporary)
        for path, blob in sorted(staged.items()):
            (check_directory / path.name).write_bytes(blob)
        checked_fdf = check_directory / destination.name
        identities = verify_semantic_split_identities(
            checked_fdf, labels, source_fdf_path, target_species, (check_directory,), search_dirs
        )
        materialized = parse_effective_fdf(checked_fdf)
        if materialized.dm_init_spin != model.dm_init_spin:
            raise SemanticSpeciesSplitError(
                SemanticSplitCode.INVALID_SPLIT_INPUT, "DM.InitSpin changed during split"
            )
    output_directory.mkdir(parents=True, exist_ok=True)
    for path, blob in sorted(staged.items()):
        with path.open("xb") as stream:
            stream.write(blob)
    return SemanticSpeciesSplitResult(
        content,
        labels,
        identities.identity_digest,
        identities.identities,
        model.effective_fdf_sha256,
        hashlib.sha256(content.encode()).hexdigest(),
        policy.digest,
    )
