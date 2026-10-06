"""Freeze and verify product inputs using the existing TASK 7–13 adapters.

These commands reach the production admission boundary. The upstream runtime
does not yet produce the complete I.5 state gate, so execution remains explicitly
NOT_ESTABLISHED even when a static plan is READY or an override is recorded.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, replace
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import cast

from hubbardflow.domain.coverage import UserCoveragePolicy, qualify_coverage
from hubbardflow.domain.perturbation_plan import AlphaStrategy, PlanStatus, ResolvedPerturbationPlan
from hubbardflow.domain.subspace_inventory import InventoryStatus, build_inventory
from hubbardflow.domain.symmetry_operation_models import bind_symmetry_model
from hubbardflow.domain.validation import require_nonnegative_finite
from hubbardflow.execution.campaign_coverage_policy import campaign_coverage_policy
from hubbardflow.execution.campaign_plan import (
    CampaignCoverage,
    planning_config_digest,
    resolve_campaign_planning,
)
from hubbardflow.execution.campaign_split import stage_campaign_split, verify_campaign_split_staging
from hubbardflow.execution.campaign_v2 import resolve_fdf_includes, validate_lr_config, validate_reference_fdf
from hubbardflow.execution.product_admission import (
    ExecutionAdmission,
    ExecutionAdmissionStatus,
)
from hubbardflow.execution.product_models import (
    LOCK_SCHEMA,
    ProductBoundary,
    ProductCommand,
    ProductError,
    ProductReason,
    ProductSnapshot,
    V6ProtectionStatus,
    canonical,
    json_object,
)
from hubbardflow.execution.product_paths import PRODUCT_SIDECARS
from hubbardflow.execution.product_paths import protect_product_destination as _protect_product_destination
from hubbardflow.siesta_backend.coverage_reference import build_coverage_reference_evidence
from hubbardflow.siesta_backend.fdf_model import parse_effective_fdf, species_identity


@dataclass(frozen=True)
class ProductRequest:
    fdf: str
    lr_config: str | None
    reference_output: str | None
    reference_dm: str | None
    coverage: CampaignCoverage | None
    alpha_strategy: AlphaStrategy | None
    identity_dirs: tuple[str, ...]
    allow_spin_flip: bool | None
    allow_rotations: bool | None
    tol_fermi_ev: float | None = None

    def __post_init__(self) -> None:
        for value in (
            self.fdf,
            self.lr_config,
            self.reference_output,
            self.reference_dm,
            *self.identity_dirs,
        ):
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise ProductError("request paths must be explicit nonempty strings")
        if self.coverage is not None and not isinstance(self.coverage, CampaignCoverage):
            raise ProductError("request coverage must be a CampaignCoverage")
        if self.alpha_strategy is not None and not isinstance(self.alpha_strategy, AlphaStrategy):
            raise ProductError("request strategy must be an AlphaStrategy")
        if any(
            value is not None and type(value) is not bool
            for value in (self.allow_spin_flip, self.allow_rotations)
        ):
            raise ProductError("request flags must be explicit booleans")
        if self.tol_fermi_ev is not None:
            try:
                require_nonnegative_finite(self.tol_fermi_ev, "tol_Fermi_eV")
            except ValueError as exc:
                raise ProductError(str(exc)) from exc

    def to_mapping(self) -> dict[str, object]:
        return asdict(self)

    @classmethod
    def from_mapping(cls, row: Mapping[str, object]) -> ProductRequest:
        return cls(
            cast(str, row["fdf"]),
            cast(str | None, row["lr_config"]),
            cast(str | None, row["reference_output"]),
            cast(str | None, row["reference_dm"]),
            None if row["coverage"] is None else CampaignCoverage(cast(str, row["coverage"])),
            None if row["alpha_strategy"] is None else AlphaStrategy(cast(str, row["alpha_strategy"])),
            tuple(cast(Sequence[str], row["identity_dirs"])),
            cast(bool | None, row["allow_spin_flip"]),
            cast(bool | None, row["allow_rotations"]),
            cast(float | None, row.get("tol_fermi_ev")),
        )


def _file(value: object, base: Path) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ProductError("input paths must be explicit nonempty strings")
    path = Path(value)
    return str((path if path.is_absolute() else base / path).resolve(strict=True))


def _config(request: ProductRequest) -> dict[str, object] | None:
    if request.lr_config is None:
        if request.tol_fermi_ev is not None:
            raise ProductError("--tol-fermi-ev requires --lr-config to freeze the declared policy")
        return None
    path = Path(request.lr_config)
    raw = json_object(path.read_text(encoding="utf-8"))
    for field in ("pseudopotentials", "static_artifacts"):
        if field in raw:
            entries = raw[field]
            if not isinstance(entries, dict):
                raise ProductError(f"{field} must be an object")
            raw[field] = {key: _file(value, path.parent) for key, value in sorted(entries.items())}
    for field in (
        "compatibility_registry",
        "version_text_source",
        "planning_reference_output",
        "planning_reference_dm",
    ):
        if raw.get(field) is not None:
            raw[field] = _file(raw[field], path.parent)
    for field, value in (
        ("planning_reference_output", request.reference_output),
        ("planning_reference_dm", request.reference_dm),
        ("coverage", None if request.coverage is None else request.coverage.value),
        ("alpha_strategy", None if request.alpha_strategy is None else request.alpha_strategy.value),
        ("allow_spin_flip", request.allow_spin_flip),
        ("allow_rotations", request.allow_rotations),
    ):
        if value is not None:
            raw[field] = value
    if raw.get("coverage", "DIAGNOSTIC") == "TRANSLATION_SHADOWED":
        raw.setdefault("shadow_rejection_policy", "STOP")
        raw.setdefault("parent_reproduction", "PRINT_EQUIVALENT")
    if request.tol_fermi_ev is not None:
        raw["tol_Fermi_eV"] = request.tol_fermi_ev
        raw["tol_Fermi_eV_source"] = "cli"
    return raw


def resolve_product_snapshot(request: ProductRequest) -> ProductSnapshot:
    """Expose exact domain plan states; absent protocol never gains an invented grid."""
    fdf = Path(request.fdf)
    model = parse_effective_fdf(fdf)
    raw = _config(request)
    frozen_config = None if raw is None else dict(raw)
    if frozen_config is not None and isinstance(frozen_config.get("alpha_grid_ev"), list):
        frozen_config["alpha_grid_ev"] = sorted(cast(list[float], frozen_config["alpha_grid_ev"]))
    frozen_lr_config_json = None if frozen_config is None else canonical(frozen_config)
    split_staging = None
    if raw is not None and raw.get("auto_split_species") is True:
        with TemporaryDirectory(prefix="hubbardflow-product-split-") as temporary:
            split_staging = stage_campaign_split(
                fdf, raw, Path(temporary), identity_dirs=tuple(Path(d) for d in request.identity_dirs)
            )
    dirs = {Path(d) for d in request.identity_dirs}
    if raw is not None:
        dirs.update(Path(p).parent for p in cast(Mapping[str, str], raw.get("pseudopotentials", {})).values())
    pseudopotentials = {} if raw is None else cast(Mapping[str, str], raw.get("pseudopotentials", {}))
    identities = species_identity(
        model,
        tuple(sorted(dirs, key=str)),
        pseudopotentials={label: Path(path) for label, path in pseudopotentials.items()},
    )
    inventory = build_inventory(model, identities)
    source = sha256(fdf.read_bytes()).hexdigest()
    config_digest = (
        _raw_config_digest(
            {
                "planning_reference_output": request.reference_output,
                "planning_reference_dm": request.reference_dm,
            }
        )
        if raw is None
        else _raw_config_digest(raw)
    )
    reason: ProductReason | None = None
    detail = ""
    planning = None
    diagnostic_coverage = None
    output = (
        request.reference_output if raw is None else cast(str | None, raw.get("planning_reference_output"))
    )
    if output is not None:
        reference = build_coverage_reference_evidence(fdf, output, inventory.subspaces)
        parent = request.reference_dm if raw is None else cast(str | None, raw.get("planning_reference_dm"))
        if parent is not None:
            reference = replace(reference, parent_dm_sha256=sha256(Path(parent).read_bytes()).hexdigest())
        policy_input: dict[str, object] = dict(raw or {})
        if raw is None:
            for field in ("allow_spin_flip", "allow_rotations"):
                flag = getattr(request, field)
                if flag is not None:
                    policy_input[field] = flag
        mode = (
            request.coverage
            if raw is None
            else CampaignCoverage(cast(str, raw.get("coverage", "DIAGNOSTIC")))
        )
        diagnostic_coverage = qualify_coverage(
            inventory,
            reference,
            bind_symmetry_model(model, identities),
            campaign_coverage_policy(policy_input),
            UserCoveragePolicy("campaign-coverage-v1", mode is not CampaignCoverage.DISABLED, ()),
        )
    if raw is None:
        reason = ProductReason.LR_CONFIG_REQUIRED
        detail = "Supply --lr-config with a declared alpha grid, estimator policy and backend identities."
    else:
        try:
            _, species, labels = validate_reference_fdf(
                model.effective_text, cast(str, raw.get("functional"))
            )
            normalized = validate_lr_config(raw, species, labels, model.number_of_atoms, inventory=inventory)
            planning = resolve_campaign_planning(fdf, normalized)
            inventory = planning.plan.inventory
            diagnostic_coverage = planning.diagnostic_coverage
            config_digest = planning_config_digest(normalized)
        except ValueError as exc:
            message = str(exc)
            if "STAGED_PENDING_GENERATED_IDENTITY" in message:
                reason = ProductReason.STAGED_PENDING_GENERATED_IDENTITY
            elif "SHARED_LABEL_NEEDS_SPLIT" in message:
                reason = ProductReason.SHARED_LABEL_NEEDS_SPLIT
            elif "NOT_ESTABLISHED: SCIENTIFIC_STATE_NOT_ESTABLISHED" in message:
                reason = ProductReason.CALIBRATED_VALIDATION_NOT_ESTABLISHED
            elif "CALIBRATED requires an explicit calibration_protocol" in message:
                reason = ProductReason.CALIBRATION_PROTOCOL_REQUIRED
            else:
                raise ProductError(f"invalid product planning inputs: {message}") from exc
            detail = message
    if planning is None and inventory.status is InventoryStatus.NOT_SUPPORTED:
        status = PlanStatus.FAIL
    else:
        status = PlanStatus.NOT_ESTABLISHED if planning is None else planning.plan.status
    input_sha256_json = _input_file_hashes(request, raw)
    return ProductSnapshot(
        canonical(request.to_mapping()),
        inventory,
        planning,
        config_digest,
        source,
        status,
        () if reason is None else (reason,),
        detail,
        diagnostic_coverage,
        split_staging,
        frozen_lr_config_json,
        input_sha256_json,
    )


def _input_file_hashes(request: ProductRequest, raw: Mapping[str, object] | None) -> str:
    """Bind every source file used by the frozen plan, including FDF includes."""
    paths: set[Path] = {Path(request.fdf).resolve(strict=True)}
    for value in (request.reference_output, request.reference_dm):
        if value is not None:
            paths.add(Path(value).resolve(strict=True))
    _, includes = resolve_fdf_includes(Path(request.fdf))
    paths.update(path.resolve(strict=True) for path in includes)
    if raw is not None:
        for field in ("pseudopotentials", "static_artifacts"):
            paths.update(
                Path(value).resolve(strict=True)
                for value in cast(Mapping[str, str], raw.get(field, {})).values()
            )
        for field in (
            "compatibility_registry",
            "version_text_source",
            "planning_reference_output",
            "planning_reference_dm",
        ):
            configured_path = raw.get(field)
            if configured_path is not None:
                paths.add(Path(cast(str, configured_path)).resolve(strict=True))
    return canonical({str(path): sha256(path.read_bytes()).hexdigest() for path in sorted(paths, key=str)})


def _raw_config_digest(raw: Mapping[str, object]) -> str:
    """Pending admission still binds every declared input byte, including parent DM."""
    hashes: dict[str, object] = dict(raw)
    for field in ("pseudopotentials", "static_artifacts"):
        hashes[field] = {
            label: sha256(Path(path).read_bytes()).hexdigest()
            for label, path in sorted(cast(Mapping[str, str], raw.get(field, {})).items())
        }
    for field in (
        "compatibility_registry",
        "version_text_source",
        "planning_reference_output",
        "planning_reference_dm",
    ):
        path = raw.get(field)
        hashes[field] = None if path is None else sha256(Path(cast(str, path)).read_bytes()).hexdigest()
    return sha256(canonical(hashes).encode()).hexdigest()


def protect_product_destination(root: Path) -> V6ProtectionStatus:
    """Preserve the public adapter while protecting the complete V6 inventory."""
    return _protect_product_destination(root)


def freeze_product_snapshot(root: Path, snapshot: ProductSnapshot) -> None:
    """Create immutable artifacts; repeat requests verify them before reusing them."""
    protect_product_destination(root)
    _protect_source_files(root, ProductRequest.from_mapping(json_object(snapshot.request_json)))
    values: dict[str, object] = {
        "product_plan.json": snapshot.to_mapping(),
        "product_campaign.lock": {
            "schema": LOCK_SCHEMA,
            "campaign_identity": snapshot.campaign_identity,
            "plan_digest": None if snapshot.planning is None else snapshot.planning.plan.digest,
        },
    }
    if snapshot.planning is not None:
        values["resolved_perturbation_plan.json"] = snapshot.planning.plan.to_mapping()
    if any((root / name).exists() for name in values):
        frozen = load_product_snapshot(root)
        if frozen.to_mapping() != snapshot.to_mapping():
            raise ProductError("frozen product plan invalidated: inputs, policy or provenance changed")
        return
    root.mkdir(parents=True, exist_ok=True)
    if snapshot.split_staging is not None:
        request = ProductRequest.from_mapping(json_object(snapshot.request_json))
        staging = stage_campaign_split(
            Path(request.fdf),
            _config(request) or {},
            root,
            identity_dirs=tuple(Path(d) for d in request.identity_dirs),
        )
        if staging != snapshot.split_staging:
            raise ProductError("split input identity changed before freezing")
    for name, row in values.items():
        with (root / name).open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(canonical(row) + "\n")


def load_product_snapshot(root: Path) -> ProductSnapshot:
    """Load TASK 12 serialization and verify both plan and campaign identity."""
    try:
        snapshot = ProductSnapshot.from_mapping(
            json_object((root / "product_plan.json").read_text(encoding="utf-8"))
        )
        lock = json_object((root / "product_campaign.lock").read_text(encoding="utf-8"))
        digest = None if snapshot.planning is None else snapshot.planning.plan.digest
        if lock != {
            "schema": LOCK_SCHEMA,
            "campaign_identity": snapshot.campaign_identity,
            "plan_digest": digest,
        }:
            raise ProductError("campaign identity or plan digest disagrees with the frozen lock")
        path = root / "resolved_perturbation_plan.json"
        if snapshot.planning is not None:
            plan = ResolvedPerturbationPlan.from_mapping(json_object(path.read_text(encoding="utf-8")))
            if plan.to_mapping() != snapshot.planning.plan.to_mapping():
                raise ProductError("frozen resolved plan disagrees with campaign identity")
        elif path.exists():
            raise ProductError("unexpected resolved plan for diagnostic-only product snapshot")
        request = ProductRequest.from_mapping(json_object(snapshot.request_json))
        _protect_source_files(root, request)
        if resolve_product_snapshot(request).to_mapping() != snapshot.to_mapping():
            raise ProductError("frozen product plan invalidated: inputs, parent DM, bands or policy changed")
        if snapshot.split_staging is not None:
            verify_campaign_split_staging(root, snapshot.split_staging)
        return snapshot
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise ProductError(f"cannot consume frozen product plan: {exc}") from exc


def _protect_source_files(root: Path, request: ProductRequest) -> None:
    """Reports and locks must not overwrite any declared scientific input."""
    _, included = resolve_fdf_includes(Path(request.fdf))
    sources = {p.resolve() for p in included}
    sources.update(
        Path(p).resolve()
        for p in (
            request.fdf,
            request.lr_config,
            request.reference_output,
            request.reference_dm,
        )
        if p is not None
    )
    raw = _config(request)
    if raw is not None:
        for field in ("pseudopotentials", "static_artifacts"):
            sources.update(Path(p).resolve() for p in cast(Mapping[str, str], raw.get(field, {})).values())
        for field in (
            "compatibility_registry",
            "version_text_source",
            "planning_reference_output",
            "planning_reference_dm",
        ):
            if raw.get(field) is not None:
                sources.add(Path(cast(str, raw[field])).resolve())
    targets = {root / name for name in PRODUCT_SIDECARS}
    if sources & targets:
        raise ProductError("product output would overwrite a declared input; choose another output directory")


def product_execution_boundary(
    root: Path,
    snapshot: ProductSnapshot,
    command: ProductCommand,
    *,
    override_reason: str | None,
    partition: str | None,
    account: str | None,
    admission: ExecutionAdmission | None = None,
) -> ProductBoundary:
    """Record the admission request without bypassing missing scientific producers.

    Pilot reuse remains unavailable and no file-name based reuse is attempted.
    I.5 blocks this product route before materialization, local/MPI or SLURM
    launch. The legacy explicit campaign commands retain their existing runner.
    """
    admissible = admission is not None and admission.status in {
        ExecutionAdmissionStatus.ADMISSIBLE_LEGACY_EQUIVALENT,
        ExecutionAdmissionStatus.ADMISSIBLE_TRANSLATION_SHADOWED,
    }
    if admissible:
        reasons = list(snapshot.reasons)
    else:
        reasons = [ProductReason.SCIENTIFIC_STATE_NOT_ESTABLISHED, ProductReason.PILOT_REUSE_NOT_ESTABLISHED]
        reasons.extend(snapshot.reasons)
        if snapshot.status is not PlanStatus.READY and override_reason is None:
            reasons.append(ProductReason.PLAN_NOT_READY)
    v6_protection = protect_product_destination(root)
    receipt = ProductBoundary(
        command,
        snapshot.campaign_identity,
        None if snapshot.planning is None else snapshot.planning.plan.digest,
        snapshot.status,
        tuple(sorted(set(reasons), key=lambda r: r.value)),
        override_reason,
        partition,
        account,
        v6_protection,
        None if admission is None else canonical(admission.to_mapping()),
    )
    text = canonical(receipt.to_mapping()) + "\n"
    path = root / f"{command.value}.{sha256(text.encode()).hexdigest()}.receipt.json"
    if path.exists():
        if path.read_text(encoding="utf-8") != text:
            raise ProductError("execution receipt identity mismatch")
    else:
        with path.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
    return receipt
