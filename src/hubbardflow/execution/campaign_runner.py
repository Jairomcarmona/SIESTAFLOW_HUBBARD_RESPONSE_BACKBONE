"""Fixed-grid v2 campaign dispatcher built on the admitted production runtime."""
from __future__ import annotations

from dataclasses import asdict, replace
from hashlib import sha256
try:
    import fcntl
except ImportError:  # Windows clients may import analysis/report helpers only.
    fcntl = None  # type: ignore[assignment]
import json
import os
from importlib.metadata import PackageNotFoundError, version as installed_package_version
from pathlib import Path
import shutil
import threading
import time
import traceback
import uuid
from subprocess import CompletedProcess, run as subprocess_run
from typing import Any, Mapping

from hubbardflow.domain.backend_compatibility import ScientificProfile
from hubbardflow.domain.adaptive_alpha_control import (
    AdaptiveAlphaPolicy, AdaptiveDecision, decide_round, initial_siesta_node_cost,
)
from hubbardflow.domain.lr_analysis_v2 import (
    LRAnalysisPolicy, analyze_verified_lr, write_lr_analysis_v2,
)
from hubbardflow.domain.response_grid_reproducibility import (
    ValidatedResponseGridCalibration, _execution_attempt, response_grid_campaign_context_sha256,
    validate_response_grid_calibration,
)
from hubbardflow.domain.lr_campaign_contract import LinearResponseBareCampaignContract
from hubbardflow.domain.matrix_lr import ResponseObservation
from hubbardflow.domain.state_gate_results import StateGateReason
from hubbardflow.domain.symmetry_reduction import PerturbationSpec, ResponseMode
from hubbardflow.execution.campaign_v2 import (
    CampaignV2Error, load_campaign_v2, sha256_file, validate_lr_config,
    validate_psml, validate_reference_fdf, verify_campaign_inventory,
)
from hubbardflow.execution.campaign_plan import campaign_inventory
from hubbardflow.execution.campaign_shadow import CampaignShadow
from hubbardflow.execution.campaign_files import (
    build_verified_dataset as _build_verified_dataset,
    campaign_relative_path as _campaign_relative_path,
    dataset_half_width as _dataset_half_width,
    dataset_half_widths as _dataset_half_widths,
    source_record as _source_record,
    verify_record_artifacts as _verify_record_artifacts,
)
from hubbardflow.execution.campaign_store import CampaignStore, atomic_json as _atomic_json
from hubbardflow.execution.dag_contract import NodeState
from hubbardflow.execution.execution_profile import ExecutionProfile
from hubbardflow.execution.observation_assembly import ObservationAssembler
from hubbardflow.execution.response_grid_context import response_grid_source_campaign_context
from hubbardflow.execution.state_gate_step import (
    failed_state_gate_mapping,
    state_gate_mapping,
    write_state_gate_file,
)
from hubbardflow.siesta_backend.response_grid_semantics import extract_siesta_response_cell
from hubbardflow.execution.generic_executor import (
    ExecutionContractError, GenericDagExecutor, NodeReceipt, dag_digest,
)
from hubbardflow.execution.lr_dag import (
    LRDag, LRDagNode, LRNodeKind, build_adaptive_campaign_dag,
)
from hubbardflow.reporting.lr_u_report import render_lr_u_report, write_lr_u_report
from hubbardflow.siesta_backend.backend_admission_plugin import admit_siesta542_from_campaign_contract
from hubbardflow.siesta_backend.command_factory import SiestaCampaignLayout
from hubbardflow.siesta_backend.event_parser import parse_hubbard_population_events
from hubbardflow.siesta_backend.occupation_precision import (
    read_printed_occupation_precision,
)
from hubbardflow.siesta_backend.output_validator import SiestaArtifactSpec
from hubbardflow.siesta_backend.parser_models import HubbardPopulationEvent
from hubbardflow.siesta_backend.production_runtime import build_admitted_siesta542_runtime
from hubbardflow.siesta_backend.reference_magnetic_evidence import (
    parse_final_collinear_mulliken_sz, reference_moments_from_fdf_and_output,
)
from hubbardflow.siesta_backend.siesta542_bare_profile import Siesta542PotentialShiftHamiltonianProfile
from hubbardflow.siesta_backend.siesta542_screened_selection import select_converged_screened_event


HEARTBEAT_SECONDS = 15
_F20_12_PATCH_SHA256 = "3539150217903b2665102a44396a9d84281fc91e1170819dc79e413af15d0116"


def _validate_resume_config(
    config: Mapping[str, Any],
    fdf_path: Path,
    fdf_species: Mapping[str, int],
    projector_sites: list[str],
    atom_count: int,
    perturbation_plan: Any,
) -> dict[str, Any]:
    """Use the pre-plan validator for legacy manifests and strict inventory for frozen plans.

    Campaigns initialized before Phase 2 have no frozen perturbation plan and
    must retain their original FDF acceptance rules on resume. The strict
    effective-FDF parser is part of inventory construction, so it applies only
    when the manifest carries the Phase-2 plan that was validated at init.
    """
    if perturbation_plan is None:
        return validate_lr_config(config, fdf_species, projector_sites, atom_count)
    inventory = campaign_inventory(
        fdf_path,
        tuple(sorted({Path(p).parent for p in config["pseudopotentials"].values()}, key=str)),
    )
    return validate_lr_config(
        config, fdf_species, projector_sites, atom_count, inventory=inventory,
    )


def _digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    return sha256(raw).hexdigest()


def _plain_json_value(value: Any) -> Any:
    """Thaw registry metadata containers before canonical JSON hashing."""
    if isinstance(value, Mapping):
        return {str(key): _plain_json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain_json_value(item) for item in value]
    return value


def _alpha_token(value: float) -> str:
    return ("p" if value > 0 else "m") + f"{abs(value):.12g}".replace(".", "p")


def _build_dag(sites: list[dict[str, Any]], alpha_grid: list[float]) -> tuple[LRDag, dict[str, PerturbationSpec]]:
    reference = LRDagNode("reference", LRNodeKind.REFERENCE, ())
    responses: list[LRDagNode] = []
    specs: dict[str, PerturbationSpec] = {}
    for site_index, site in enumerate(sites):
        for alpha in alpha_grid:
            for mode in (ResponseMode.BARE, ResponseMode.SCREENED):
                run_id = f"lr_s{site_index:03d}_{_alpha_token(alpha)}_{mode.value.lower()}"
                spec = PerturbationSpec(
                    run_id=run_id, orbit_id=str(site.get("orbit_id", site["site_id"])),
                    site_index=site_index, site_id=site["site_id"], mode=mode,
                    alpha_ev=float(alpha), purpose="explicit_fixed_grid",
                )
                node_id = f"response:{run_id}"
                specs[node_id] = spec
                responses.append(LRDagNode(node_id, LRNodeKind.PERTURBATION, ("reference",), spec))
    response_ids = tuple(node.node_id for node in responses)
    # This is a diagnostic completion gate: it records a declared fixed-grid
    # route and never vetoes an otherwise diagnosable polynomial analysis.
    alpha_gate = LRDagNode("alpha-diagnostic-gate", LRNodeKind.ALPHA_GATE, response_ids)
    analysis = LRDagNode("matrix-analysis", LRNodeKind.MATRIX_ANALYSIS, (alpha_gate.node_id,))
    return LRDag((reference, *responses, alpha_gate, analysis), False, False), specs


class _Heartbeat:
    def __init__(self, path: Path, *, campaign_id: str):
        self.path = path
        self.state: dict[str, Any] = {
            "campaign_id": campaign_id, "status": "RUNNING", "heartbeat_interval_seconds": HEARTBEAT_SECONDS,
            "started_epoch": time.time(), "completed_nodes": [], "active_node": None,
        }
        self.lock = threading.Lock()
        self.write_lock = threading.Lock()
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._loop, name="hubbardflow-heartbeat", daemon=True)

    def start(self) -> None:
        self._write()
        self.thread.start()

    def update(self, **changes: Any) -> None:
        with self.lock:
            self.state.update(changes)
            self.state["heartbeat_epoch"] = time.time()
            self.state["heartbeat_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            snapshot = dict(self.state)
        with self.write_lock:
            _atomic_json(self.path, snapshot)

    def finish(self, status: str, **changes: Any) -> None:
        self.update(status=status, finished_epoch=time.time(), active_node=None, **changes)
        self.stop_event.set()
        self.thread.join(timeout=HEARTBEAT_SECONDS + 1)

    def _write(self) -> None:
        with self.lock:
            self.state["heartbeat_epoch"] = time.time()
            self.state["heartbeat_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            snapshot = dict(self.state)
        with self.write_lock:
            _atomic_json(self.path, snapshot)

    def _loop(self) -> None:
        while not self.stop_event.wait(HEARTBEAT_SECONDS):
            self._write()


class _AttemptingFactory:
    """Reuse the production factory while assigning a unique attempt root."""

    def __init__(self, factory: Any, control: Path, state: _Heartbeat):
        self.factory, self.control, self.state = factory, control, state
        self.base_layout = factory.layout
        self.active_attempt_root: Path | None = None
        self.reference_dms: dict[str, Path] = {}

    def prepare(self, node: LRDagNode) -> None:
        node_key = sha256(node.node_id.encode()).hexdigest()[:20]
        node_root = self.control / "attempts" / node_key
        node_root.mkdir(parents=True, exist_ok=True)
        attempt_root = node_root / f"attempt-{time.time_ns()}-{uuid.uuid4().hex[:8]}"
        attempt_root.mkdir()
        self.active_attempt_root = attempt_root
        level_id = node.scf_level_id or "base"
        reference_dm = self.reference_dms.get(level_id)
        self.factory.layout = replace(
            self.base_layout, run_root=attempt_root, reference_dm=reference_dm,
        )
        self.state.update(active_attempt_root=str(attempt_root), active_node=node.node_id)

    def command_for(self, node: LRDagNode):
        if self.active_attempt_root is None:
            raise RuntimeError("attempt root was not prepared before materialization")
        return self.factory.command_for(node)

    def reference_completed(self, dm_path: Path, level_id: str = "base") -> None:
        self.reference_dms[level_id] = dm_path


class CampaignRunner:
    @property
    def input_sha256_by_path(self) -> Mapping[str, str]:
        """Read-only inventory hashes consumed by observation assembly."""
        return self._input_sha256_by_path

    @property
    def minimum_occupation_decimal_places(self) -> int | None:
        """Current output precision requirement for occupation extraction."""
        return self._minimum_occupation_decimal_places

    def __init__(self, manifest_path: str | Path):
        self.campaign = load_campaign_v2(manifest_path)
        verify_campaign_inventory(self.campaign)
        self.root = Path(self.campaign["_campaign_root"])
        self._input_sha256_by_path = {
            str(item["path"]): str(item["sha256"])
            for item in self.campaign["input_files"]
        }
        self.control = self.root / ".siestaflow"
        self.control.mkdir(parents=True, exist_ok=True)
        self.results = self.root / "results"
        self.profile: ExecutionProfile = self.campaign["_profile"]
        self.profile.require_submission_evidence()
        if self.profile.target == "local_wsl" and self.profile.wsl is None:
            raise CampaignV2Error("campaign runner requires WSL execution settings")
        requested_ranks = self.profile.runtime.launcher.processes_per_node
        visible_cpus = (
            len(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else os.cpu_count()
        )
        if self.profile.target == "local_wsl" and visible_cpus is not None and requested_ranks > visible_cpus:
            raise CampaignV2Error(
                f"profile requests {requested_ranks} MPI ranks, but this runtime exposes only {visible_cpus} CPUs"
            )
        # local_wsl serializes all campaigns in its workspace. A direct Linux
        # campaign is already serialized by its worker lock; Slurm grants are
        # validated and use the allocation adapter below.
        lock_root = Path(self.profile.wsl.workspace_root) if self.profile.wsl else self.root
        self.resource_lock_path = lock_root / ".siestaflow" / "single-siesta.lock"
        self.environment = {**os.environ, **self.profile.runtime.environment}

        self.config = json.loads((self.root / self.campaign["lr_config_file"]).read_text(encoding="utf-8"))
        fdf_path = self.root / self.campaign["reference_fdf"]
        fdf_text = fdf_path.read_text(encoding="utf-8")
        functional, fdf_species, projector_sites = validate_reference_fdf(fdf_text, self.config.get("functional"))
        atoms_match = __import__("re").search(r"^\s*NumberOfAtoms\s+(\d+)\s*$", fdf_text, __import__("re").IGNORECASE | __import__("re").MULTILINE)
        if atoms_match is None:
            raise CampaignV2Error("reference FDF lacks NumberOfAtoms")
        self.atom_count = int(atoms_match.group(1))
        self.perturbation_plan = self.campaign["_perturbation_plan"]
        self.config = _validate_resume_config(
            self.config, fdf_path, fdf_species, projector_sites, self.atom_count,
            self.perturbation_plan,
        )
        if functional != self.campaign["functional"] or self.config["functional"] != functional:
            raise CampaignV2Error("campaign functional differs from effective reference FDF/config")
        if self.config["xc_profile"] != self.campaign["_xc_profile"]:
            raise CampaignV2Error("campaign scientific profile differs from the validated LR config profile")
        for label, source in self.config["pseudopotentials"].items():
            validate_psml(Path(source), label, fdf_species[label], functional)
        self.contract = LinearResponseBareCampaignContract.from_json(
            (self.root / self.campaign["contract_file"]).read_text(encoding="utf-8")
        )
        self.sites = self.campaign["sites"]
        self.shadow = None
        if self.config["coverage"] == "TRANSLATION_SHADOWED":
            if self.perturbation_plan is None:
                raise CampaignV2Error("TRANSLATION_SHADOWED requires a frozen perturbation plan")
            by_label = {s["site_id"]: s for s in self.sites}
            self.sites = [
                {**by_label[subspace.species_label], "index": i}
                for i, subspace in enumerate(self.perturbation_plan.inventory.subspaces)
            ]
            self.shadow = CampaignShadow(self.perturbation_plan, self.control, self.campaign["input_identity"])
        self.alpha_grid = [float(value) for value in self.campaign["alpha_grid_ev"]]
        if any(abs(value - float(f"{value:+.4f}")) > 1.0e-12 for value in self.alpha_grid):
            raise CampaignV2Error(
                "alpha amplitudes must be representable to 1e-4 eV; the admitted FDF materializer writes four decimals"
            )
        self.response_grid_calibration = self._load_response_grid_calibration(fdf_path)
        self.checkpoint_path = self.control / "dag-checkpoint.json"
        self.adaptive_policy: AdaptiveAlphaPolicy | None = self.campaign.get("_adaptive_alpha_policy")
        self.adaptive_state_path = self.control / "adaptive-alpha-state.json"
        self.adaptive_policy_digest: str | None = None
        self.adaptive_state: dict[str, Any] | None = None
        if self.adaptive_policy is not None:
            if self.shadow is not None:
                raise CampaignV2Error("NOT_ESTABLISHED: translation shadows with legacy adaptive rounds")
            self.adaptive_policy_digest = _digest(self.adaptive_policy.to_mapping())
            self.adaptive_state = self._load_or_initialize_adaptive_state()
            self._build_adaptive_graph()
            checkpoint_identity = f"adaptive:{_digest({
                "input_identity": self.campaign["input_identity"],
                "policy_digest": self.adaptive_policy_digest,
            })}"
            self.executor = GenericDagExecutor(
                self.dag, self.checkpoint_path, checkpoint_identity=checkpoint_identity,
            )
            self.checkpoint_identity = checkpoint_identity
        else:
            self.dag, self.specs = _build_dag(self.sites, self.alpha_grid)
            self.executor = GenericDagExecutor(self.dag, self.checkpoint_path)
            self.checkpoint_identity = None
            if self.shadow is not None:
                self.shadow.install(self)
        self.records_path = self.control / "node-evidence.json"
        self.store = CampaignStore(self.records_path, lambda: self.executor.checkpoint)
        self.observations = ObservationAssembler()
        self.records = self._load_records()
        self.reference_fdf = fdf_path
        self.reference_dm_name = self.config["reference_dm_name"]
        static_artifacts = {f"{label}.psml": Path(path) for label, path in self.config["pseudopotentials"].items()}
        for destination, path in self.config["static_artifacts"].items():
            if destination in static_artifacts:
                raise CampaignV2Error(f"static artifact collides with pseudopotential filename {destination}")
            static_artifacts[destination] = Path(path)
        self.layout = SiestaCampaignLayout(
            reference_fdf=self.reference_fdf, run_root=self.control / "attempts" / "initial",
            reference_dm=None, reference_dm_name=self.reference_dm_name, static_artifacts=static_artifacts,
            scf_level_overrides=(
                {str(self.adaptive_policy.scf_probe_level["level_id"]): self.adaptive_policy.scf_probe_level["fdf_overrides"]}
                if self.adaptive_policy is not None and self.adaptive_policy.scf_probe_level is not None else {}
            ),
        )
        self.hosts = self._slurm_hosts() if self.profile.target == "slurm" else ("localhost",)
        self.admitted = build_admitted_siesta542_runtime(
            campaign_root=self.root, contract=self.contract,
            executable_path=self.profile.runtime.siesta_executable, profile=self.profile,
            hosts=self.hosts, layout=self.layout,
        )
        self.factory = _AttemptingFactory(self.admitted.factory, self.control, _Heartbeat(self.control / "worker-state.json", campaign_id=self.campaign["campaign_id"]))
        self.analysis_policy = LRAnalysisPolicy(**self.config["analysis_policy"])
        self.analysis_policy.validate()
        self._minimum_occupation_decimal_places = None
        if self.analysis_policy.occupation_precision_requirement == "f20.12":
            metadata = self.admitted.admission.registry_record.profile.metadata
            build_receipt = metadata.get("occupation_build_receipt")
            canonical_receipt = (
                json.dumps(_plain_json_value(build_receipt), sort_keys=True, separators=(",", ":"), ensure_ascii=True)
                if isinstance(build_receipt, Mapping) else None
            )
            receipt_digest = (
                sha256(canonical_receipt.encode("utf-8")).hexdigest()
                if canonical_receipt is not None else None
            )
            receipt_matches = (
                isinstance(build_receipt, Mapping)
                and build_receipt.get("schema") == "siestaflow.siesta_occupation_build_receipt.v1"
                and build_receipt.get("occupation_output_format") == "extended-f20.12"
                and build_receipt.get("occupation_decimal_places") == 12
                and build_receipt.get("source_patch_sha256") == _F20_12_PATCH_SHA256
                and build_receipt.get("executable_sha256") == self.admitted.admission.observed.executable_sha256
                and isinstance(build_receipt.get("build_id"), str)
                and bool(build_receipt.get("build_id", "").strip())
                and isinstance(build_receipt.get("build_process"), Mapping)
                and bool(build_receipt.get("build_process"))
                and metadata.get("occupation_build_receipt_sha256") == receipt_digest
            )
            if (
                metadata.get("occupation_output_format") != "extended-f20.12"
                or metadata.get("occupation_decimal_places") != 12
                or metadata.get("occupation_patch_sha256") != _F20_12_PATCH_SHA256
                or metadata.get("occupation_build_receipt_status") != "BUILD_RECEIPT_LINKED"
                or not receipt_matches
            ):
                raise CampaignV2Error(
                    "occupation_precision_requirement=f20.12 requires a matching SIESTA build receipt linking the "
                    "canonical Occupations f20.12 patch hash to the admitted executable hash; "
                    "declared/unverified format metadata is insufficient"
                )
            self._minimum_occupation_decimal_places = 12

    def _slurm_hosts(self) -> tuple[str, ...]:
        """Resolve hosts in the already granted allocation; never submit jobs."""
        from hubbardflow.execution.slurm_environment import SlurmEnvironment
        slurm = SlurmEnvironment.from_environ(self.environment)
        completed = subprocess_run(
            ["scontrol", "show", "hostnames", slurm.nodelist],
            check=False, capture_output=True, text=True, shell=False, env=self.environment,
        )
        if completed.returncode != 0:
            raise CampaignV2Error("cannot resolve hosts in the granted Slurm allocation")
        hosts = tuple(line.strip() for line in completed.stdout.splitlines() if line.strip())
        if not hosts:
            raise CampaignV2Error("granted Slurm allocation resolved to no hosts")
        return hosts

    def _load_or_initialize_adaptive_state(self) -> dict[str, Any]:
        assert self.adaptive_policy is not None and self.adaptive_policy_digest is not None
        identity = {
            "input_identity": str(self.campaign["input_identity"]),
            "campaign_id": str(self.campaign["campaign_id"]),
            "policy_digest": self.adaptive_policy_digest,
        }
        if self.adaptive_state_path.exists():
            try:
                state = json.loads(self.adaptive_state_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise ExecutionContractError(f"adaptive alpha state is unreadable: {exc}") from exc
            if not isinstance(state, dict) or state.get("identity") != identity:
                raise ExecutionContractError("adaptive alpha state belongs to a different input or frozen policy")
            if state.get("policy") != self.adaptive_policy.to_mapping():
                raise ExecutionContractError("adaptive alpha policy changed after its first durable decision")
            return state
        initial_cost = initial_siesta_node_cost(len(self.sites), len(self.adaptive_policy.seed_grid_ev))
        if initial_cost > self.adaptive_policy.total_siesta_node_budget:
            raise CampaignV2Error("adaptive alpha budget cannot cover the shared reference and initial seed grid")
        first_round = {
            "round_index": 0, "direction": "initial",
            "alpha_grid_ev": list(self.adaptive_policy.seed_grid_ev),
            "active_window_eV": self.adaptive_policy.analysis_for_round(0)["active_window_eV"],
            "fit_policy": dict(self.adaptive_policy.analysis_for_round(0)),
            "scf_level_id": "base", "status": "PENDING",
        }
        state = {
            "schema": "siestaflow.adaptive_alpha_state.v1", "identity": identity,
            "policy": self.adaptive_policy.to_mapping(), "rounds": [first_round],
            "decisions": [], "reserved_nodes": {}, "stable_comparisons": 0,
            "probed_site_ids": [], "probe_plan": None, "scf_reruns": [],
            "candidate_status": "PENDING", "campaign_status": "RUNNING",
            "budget": {"total_siesta_node_budget": self.adaptive_policy.total_siesta_node_budget,
                       "reserved_nodes": 0, "remaining_nodes": self.adaptive_policy.total_siesta_node_budget},
        }
        _atomic_json(self.adaptive_state_path, state)
        return state

    def _persist_adaptive_state(self) -> None:
        if self.adaptive_state is None:
            return
        reserved = self.adaptive_state.get("reserved_nodes", {})
        spent = len(reserved) if isinstance(reserved, Mapping) else 0
        total = int(self.adaptive_policy.total_siesta_node_budget) if self.adaptive_policy else 0
        self.adaptive_state["budget"] = {
            "total_siesta_node_budget": total,
            "reserved_nodes": spent,
            "remaining_nodes": max(0, total - spent),
        }
        _atomic_json(self.adaptive_state_path, self.adaptive_state)

    def _build_adaptive_graph(self) -> None:
        assert self.adaptive_state is not None and self.adaptive_policy_digest is not None
        self.dag, self.specs, _metadata = build_adaptive_campaign_dag(
            self.sites, self.adaptive_state["rounds"],
            probe_plan=self.adaptive_state.get("probe_plan"),
            scf_reruns=self.adaptive_state.get("scf_reruns", ()),
            campaign_id=self.campaign["campaign_id"], policy_digest=self.adaptive_policy_digest,
        )

    def _rebuild_adaptive_graph(self) -> None:
        self._build_adaptive_graph()
        assert self.checkpoint_identity is not None
        self.executor = GenericDagExecutor(
            self.dag, self.checkpoint_path, checkpoint_identity=self.checkpoint_identity,
        )

    def _load_records(self) -> dict[str, Any]:
        return self.store.load_records(self._identity())

    def _identity(self) -> dict[str, str]:
        if getattr(self, "shadow", None) is not None:
            return {
                "campaign_id": self.campaign["campaign_id"],
                "input_identity": self.campaign["input_identity"],
                "perturbation_plan_digest": self.shadow.plan.digest,
            }
        if self.adaptive_policy_digest is not None:
            return {
                "campaign_id": self.campaign["campaign_id"],
                "input_identity": self.campaign["input_identity"],
                "adaptive_policy_digest": self.adaptive_policy_digest,
            }
        return {
            "campaign_id": self.campaign["campaign_id"],
            "input_identity": self.campaign["input_identity"],
            "dag_digest": dag_digest(self.dag),
        }

    def _save_records(self) -> None:
        self.save_records()

    def save_records(self) -> None:
        self.store.records = self.records
        self.store.save_records(self._identity())

    def _checkpoint(self) -> dict[str, NodeReceipt]:
        return self.checkpoint()

    def checkpoint(self) -> dict[str, NodeReceipt]:
        return self.store.checkpoint()

    def _reserve_adaptive_node(self, node: LRDagNode) -> bool:
        if self.adaptive_policy is None or self.adaptive_state is None:
            return True
        if node.kind not in {LRNodeKind.REFERENCE, LRNodeKind.PERTURBATION}:
            return True
        reservations = self.adaptive_state.setdefault("reserved_nodes", {})
        existing = reservations.get(node.node_id)
        if existing is not None:
            expected = {
                "node_id": node.node_id,
                "policy_digest": self.adaptive_policy_digest,
                "round_index": self._node_round_index(node.node_id),
                "kind": node.kind.value,
                "scf_level_id": node.scf_level_id or "base",
                "parent_dm_node_id": node.parent_dm_node_id,
                "alpha_eV": None if node.perturbation is None else float(node.perturbation.alpha_ev),
                "site_id": None if node.perturbation is None else str(node.perturbation.site_id),
                "mode": None if node.perturbation is None else node.perturbation.mode.value,
            }
            if any(existing.get(key) != value for key, value in expected.items()):
                raise ExecutionContractError(f"adaptive node reservation identity changed for {node.node_id}")
            return True
        if len(reservations) >= self.adaptive_policy.total_siesta_node_budget:
            return False
        reservations[node.node_id] = {
            "node_id": node.node_id,
            "policy_digest": self.adaptive_policy_digest,
            "round_index": self._node_round_index(node.node_id),
            "kind": node.kind.value,
            "scf_level_id": node.scf_level_id or "base",
            "parent_dm_node_id": node.parent_dm_node_id,
            "alpha_eV": None if node.perturbation is None else float(node.perturbation.alpha_ev),
            "site_id": None if node.perturbation is None else str(node.perturbation.site_id),
            "mode": None if node.perturbation is None else node.perturbation.mode.value,
            "reserved_epoch": time.time(),
        }
        self._persist_adaptive_state()
        return True

    def _stop_for_unreserved_node(self, node: LRDagNode) -> None:
        assert self.adaptive_state is not None
        decision = {
            "schema": "siestaflow.adaptive_alpha_decision.v1",
            "decision": AdaptiveDecision.STOP_LIMIT_SENSITIVE.value,
            "reason": "unplanned_node_exceeds_remaining_budget",
            "node_id": node.node_id,
            "policy_digest": self.adaptive_policy_digest,
            "budget_reserved_nodes": len(self.adaptive_state.get("reserved_nodes", {})),
            "candidate_status": self.adaptive_state.get("candidate_status", "NO_NUMERICAL_U"),
        }
        self.adaptive_state["campaign_status"] = decision["decision"]
        self.adaptive_state["decisions"].append(decision)
        self._persist_adaptive_state()
        for round_state in reversed(self.adaptive_state["rounds"]):
            path = round_state.get("effective_analysis_path") or round_state.get("analysis_path")
            if path:
                try:
                    self._adaptive_final_artifacts(self._analysis_metrics(path), decision)
                except (OSError, ValueError, KeyError):
                    pass
                break

    def _descendants(self, seeds: set[str]) -> set[str]:
        affected = set(seeds)
        changed = True
        while changed:
            changed = False
            for node in self.dag.nodes:
                if node.node_id not in affected and any(dep in affected for dep in node.dependencies):
                    affected.add(node.node_id)
                    changed = True
        return affected

    def _rollback_adaptive_after_invalidation(self, invalid: set[str]) -> None:
        """Drop decisions downstream of invalid receipts while keeping spent reservations."""
        if self.adaptive_state is None:
            return
        decision_nodes = [
            node.node_id for node in self.dag.nodes
            if node.node_id in invalid and node.kind is LRNodeKind.ALPHA_GATE
            and node.node_id.startswith("adaptive:")
        ]
        if not decision_nodes:
            return
        invalid_gate = decision_nodes[0]
        round_index = self._node_round_index(invalid_gate)
        if round_index is None:
            return
        decisions = self.adaptive_state.get("decisions", [])
        keep: list[dict[str, Any]] = []
        found = False
        for decision in decisions:
            if not isinstance(decision, dict):
                continue
            if decision.get("node_id") == invalid_gate:
                found = True
                break
            keep.append(decision)
        self.adaptive_state["decisions"] = keep
        self.adaptive_state["rounds"] = [
            item for item in self.adaptive_state.get("rounds", [])
            if int(item.get("round_index", -1)) <= round_index
        ]
        is_rerun = ":scf-rerun:" in invalid_gate
        is_after_probe = invalid_gate.endswith(":decision-after-probe")
        current = next(
            (item for item in self.adaptive_state["rounds"] if int(item["round_index"]) == round_index), None,
        )
        if current is not None:
            current.pop("decision", None)
            if is_rerun:
                current.pop("scf_rerun_analysis_path", None)
                current.pop("scf_rerun_candidate_status", None)
                current["status"] = "ANALYZED"
            elif is_after_probe:
                prior_probe = next(
                    (item for item in reversed(keep)
                     if item.get("decision") == AdaptiveDecision.PROBE_SCF.value
                     and self._node_round_index(str(item.get("node_id", ""))) == round_index),
                    None,
                )
                if prior_probe is not None:
                    current["decision"] = dict(prior_probe)
                current["status"] = "PROBE_SCHEDULED"
            else:
                current.pop("analysis_path", None)
                current.pop("effective_analysis_path", None)
                current.pop("effective_scf_level_id", None)
                current.pop("candidate_status", None)
                current["status"] = "PENDING"
        self.adaptive_state["scf_reruns"] = [
            item for item in self.adaptive_state.get("scf_reruns", [])
            if int(item.get("round_index", -1)) < round_index or (is_rerun and int(item.get("round_index", -1)) == round_index)
        ]
        if not is_after_probe and not is_rerun:
            plan = self.adaptive_state.get("probe_plan")
            if isinstance(plan, Mapping) and int(plan.get("round_index", -1)) >= round_index:
                self.adaptive_state["probe_plan"] = None
        self.adaptive_state["stable_comparisons"] = int(keep[-1].get("stable_comparisons", 0)) if keep else 0
        self.adaptive_state["candidate_status"] = keep[-1].get("candidate_status", "PENDING") if keep else "PENDING"
        self.adaptive_state["campaign_status"] = "RUNNING"
        self.adaptive_state["rollback"] = {
            "invalidated_decision_node": invalid_gate,
            "round_index": round_index,
            "decision_replayed": found,
            "reserved_nodes_retained_as_spent_or_retryable": True,
        }
        self._persist_adaptive_state()

    def _revalidate_reuse(self) -> None:
        receipts = self._checkpoint()
        invalid: set[str] = set()
        for node in self.dag.nodes:
            receipt = receipts.get(node.node_id)
            if receipt is None:
                continue
            record = self.records.get(node.node_id)
            if receipt.state is not NodeState.VALIDATED or not isinstance(record, dict):
                invalid.add(node.node_id)
                continue
            if node.kind in {LRNodeKind.REFERENCE, LRNodeKind.PERTURBATION}:
                try:
                    spec_payload = record["artifact_spec"]
                    spec = SiestaArtifactSpec(**spec_payload)
                    raw_command = record["command"]
                    from hubbardflow.execution.runtime_adapters import NodeCommand
                    command = NodeCommand(
                        tuple(raw_command["argv"]), Path(raw_command["cwd"]),
                        Path(raw_command["stdin_path"]) if raw_command.get("stdin_path") else None,
                        Path(raw_command["stdout_path"]) if raw_command.get("stdout_path") else None,
                        Path(raw_command["stderr_path"]) if raw_command.get("stderr_path") else None,
                    )
                    self.admitted.factory.artifacts[node.node_id] = spec
                    fresh = self.admitted.validator.validate(
                        node, command, CompletedProcess(command.argv, 0, "", ""),
                    )
                    if fresh.state is not NodeState.VALIDATED or fresh.evidence_digest != receipt.evidence_digest:
                        invalid.add(node.node_id)
                        continue
                    if node.kind is LRNodeKind.REFERENCE:
                        dm = command.cwd / spec.dm
                        if not dm.is_file():
                            invalid.add(node.node_id)
                        else:
                            self.factory.reference_completed(dm, node.scf_level_id or "base")
                except Exception:
                    invalid.add(node.node_id)
            else:
                evidence_path = Path(record.get("evidence_path", ""))
                if (record.get("evidence_digest") != receipt.evidence_digest
                        or not evidence_path.is_file()
                        or sha256_file(evidence_path) != record.get("evidence_sha256")
                        or record.get("evidence_sha256") != receipt.evidence_digest):
                    invalid.add(node.node_id)
        if invalid:
            invalid = self._descendants(invalid)
            self._rollback_adaptive_after_invalidation(invalid)
            receipts = {node_id: receipt for node_id, receipt in receipts.items() if node_id not in invalid}
            for node_id in invalid:
                self.records.pop(node_id, None)
            self.executor.checkpoint.save(receipts)
            self._save_records()
            self._archive_unvalidated_attempts(invalid)
        self._archive_orphaned_attempts(receipts)

        if self.adaptive_policy is not None:
            self._rebuild_adaptive_graph()

        # A reference receipt may have been revalidated earlier than a newly
        # scheduled response. Reconstruct its DM source after every resume.
        for reference_node in (node for node in self.dag.nodes if node.kind is LRNodeKind.REFERENCE):
            record = self.records.get(reference_node.node_id)
            if reference_node.node_id not in receipts or not isinstance(record, dict):
                continue
            raw_command, spec_payload = record.get("command", {}), record.get("artifact_spec", {})
            dm = Path(raw_command.get("cwd", ".")) / spec_payload.get("dm", self.reference_dm_name)
            if dm.is_file():
                self.factory.reference_completed(dm, reference_node.scf_level_id or "base")

    def _archive_unvalidated_attempts(self, node_ids: set[str]) -> None:
        self.store.archive_unvalidated_attempts(self.control, node_ids)

    def _archive_orphaned_attempts(self, receipts: Mapping[str, NodeReceipt]) -> None:
        self.store.records = self.records
        self.store.archive_orphaned_attempts(self.control, receipts)

    def _record_receipt(self, node: LRDagNode, receipt: NodeReceipt, extra: Mapping[str, Any] | None = None) -> None:
        self.store.records = self.records
        self.store.record_receipt(self._identity(), node, receipt, extra)

    def _command_record(self, node: LRDagNode, command: Any, receipt: NodeReceipt) -> dict[str, Any]:
        spec = self.admitted.factory.artifacts[node.node_id]
        provenance = self.admitted.validator.last_provenance or {}
        return {
            "kind": "siesta",
            "scf_level_id": node.scf_level_id or "base",
            "parent_dm_node_id": node.parent_dm_node_id,
            "adaptive_policy_digest": self.adaptive_policy_digest,
            "adaptive_round": self._node_round_index(node.node_id),
            "artifact_spec": asdict(spec),
            "command": {
                "argv": list(command.argv), "cwd": str(command.cwd),
                "stdin_path": str(command.stdin_path) if command.stdin_path else None,
                "stdout_path": str(command.stdout_path) if command.stdout_path else None,
                "stderr_path": str(command.stderr_path) if command.stderr_path else None,
            },
            "provenance": provenance,
            "reference_dm_sha256": provenance.get("semantic", {}).get("reference_dm_sha256"),
        }

    def _execute_siesta(self, node: LRDagNode, heartbeat: _Heartbeat) -> NodeReceipt:
        from hubbardflow.execution.runtime_adapters import LocalSubprocessExecutor, SlurmAllocationExecutor

        command_holder: dict[str, Any] = {}
        base_factory = self.factory

        class CapturingFactory:
            def command_for(inner_self, requested: LRDagNode):
                command = base_factory.command_for(requested)
                command_holder["command"] = command
                heartbeat.update(active_node=node.node_id, active_working_directory=str(command.cwd))
                return command

        factory = CapturingFactory()
        if self.profile.target == "slurm":
            adapter = SlurmAllocationExecutor(
                self.profile, self.hosts, factory, self.admitted.validator, environment=self.environment,
            )
        else:
            adapter = LocalSubprocessExecutor(factory, self.admitted.validator, env=self.environment)
        if fcntl is None:
            raise ExecutionContractError("SIESTA resource locking requires Linux/WSL fcntl")
        self.resource_lock_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            heartbeat.update(current_node_state=("RUNNING_IN_GRANTED_SLURM_ALLOCATION" if self.profile.target == "slurm" else "WAITING_FOR_LOCAL_SIESTA_SLOT"))
            with self.resource_lock_path.open("a+b") as resource_lock:
                fcntl.flock(resource_lock.fileno(), fcntl.LOCK_EX)
                try:
                    self.factory.prepare(node)
                    receipt = adapter.execute(node)
                finally:
                    fcntl.flock(resource_lock.fileno(), fcntl.LOCK_UN)
        except Exception as exc:
            digest = _digest({"node": node.node_id, "error": f"{type(exc).__name__}: {exc}"})
            receipt = NodeReceipt(node.node_id, NodeState.FAILED_OUTPUT_VALIDATION, digest)
            self._record_receipt(node, receipt, {"kind": "siesta_failure", "reason": f"{type(exc).__name__}: {exc}"})
            return receipt
        command = command_holder.get("command")
        if command is None:
            self._record_receipt(node, receipt, {"kind": "execution_failure", "reason": "no materialized command"})
            return receipt
        record = self._command_record(node, command, receipt)
        if receipt.state is NodeState.FAILED_EXECUTION:
            failure = json.loads((command.cwd / "failure.json").read_text(encoding="utf-8"))
            record["returncode"] = failure["returncode"]
            record["returncode_meaning"] = failure["returncode_meaning"]
        self._record_receipt(node, receipt, record)
        if receipt.state is NodeState.VALIDATED and node.kind is LRNodeKind.REFERENCE:
            dm_path = command.cwd / record["artifact_spec"]["dm"]
            if not dm_path.is_file():
                failed = NodeReceipt(node.node_id, NodeState.FAILED_OUTPUT_VALIDATION, _digest("reference DM missing after validation"))
                self._record_receipt(node, failed, {"kind": "siesta_failure", "reason": "reference DM missing"})
                return failed
            self.factory.reference_completed(dm_path, node.scf_level_id or "base")
        return receipt

    def _execute_gate(self, node: LRDagNode) -> NodeReceipt:
        if self.adaptive_policy is not None:
            return self._execute_adaptive_gate(node)
        evidence_path = self.control / "gates" / "alpha-diagnostic.json"
        payload = {
            "schema": "siestaflow.alpha_diagnostic.v1",
            "campaign_id": self.campaign["campaign_id"],
            "alpha_grid_ev": self.alpha_grid,
            "decision": "FIXED_GRID_ANALYSIS_REQUIRED",
            "linear_window": "diagnosed_in_analysis",
            "automatic_alpha_refinement": False,
            "note": "No alpha-window intersection veto; estimator/window sensitivity is reported after matrix analysis.",
        }
        _atomic_json(evidence_path, payload)
        digest = sha256_file(evidence_path)
        receipt = NodeReceipt(node.node_id, NodeState.VALIDATED, digest)
        self._record_receipt(node, receipt, {"kind": "gate", "evidence_path": str(evidence_path), "evidence_sha256": digest})
        return receipt

    def _read_response_vector(self, node: LRDagNode) -> tuple[list[float], list[float]]:
        receipt = self._checkpoint().get(node.node_id)
        record = self.records.get(node.node_id)
        if receipt is None or receipt.state is not NodeState.VALIDATED or not isinstance(record, Mapping):
            raise ValueError(f"validated response is unavailable for {node.node_id}")
        output_path = Path(record["command"]["stdout_path"])
        output_text = output_path.read_text(encoding="utf-8", errors="replace")
        if node.perturbation is not None and node.perturbation.mode is ResponseMode.BARE:
            event = self.admitted.factory.bare_profile.select_response(output_text).response_event
        else:
            event = select_converged_screened_event(output_text)
        vector = self._event_occupations(output_text, event, self.sites)
        precision = read_printed_occupation_precision(
            output_text, event, minimum_decimal_places=self._minimum_occupation_decimal_places,
        )
        widths = [float(precision[int(site["atom_index"])].half_width) for site in self.sites]
        return vector, widths

    def _matching_response_node(
        self, site_index: int, alpha: float, mode: ResponseMode, scf_level_id: str,
    ) -> LRDagNode | None:
        for node_id, spec in self.specs.items():
            node = next(item for item in self.dag.nodes if item.node_id == node_id)
            if ((node.scf_level_id or "base") == scf_level_id
                    and spec.site_index == site_index and spec.mode is mode
                    and abs(float(spec.alpha_ev) - alpha) <= 1e-14):
                return node
        return None

    def _signal_vectors(self, scf_level_id: str = "base") -> dict[str, dict[str, Any]]:
        assert self.adaptive_policy is not None
        h = float(self.adaptive_policy.h_ev)
        result: dict[str, dict[str, Any]] = {}
        for site_index, site in enumerate(self.sites):
            for mode in (ResponseMode.BARE, ResponseMode.SCREENED):
                plus = self._matching_response_node(site_index, h, mode, scf_level_id)
                minus = self._matching_response_node(site_index, -h, mode, scf_level_id)
                if plus is None or minus is None:
                    continue
                try:
                    plus_vector, plus_rounding = self._read_response_vector(plus)
                    minus_vector, minus_rounding = self._read_response_vector(minus)
                except (OSError, ValueError, KeyError):
                    continue
                result[f"{site['site_id']}|{mode.value}"] = {
                    "perturbed_site_id": str(site["site_id"]),
                    "signal_vector_electron": [a - b for a, b in zip(plus_vector, minus_vector)],
                    "rounding_bound_vector_electron": [a + b for a, b in zip(plus_rounding, minus_rounding)],
                }
        return result

    def _scf_probe_evidence(
        self, signal_vectors: Mapping[str, Mapping[str, Any]],
    ) -> dict[str, Any] | None:
        if self.adaptive_state is None:
            return None
        plan = self.adaptive_state.get("probe_plan")
        if not isinstance(plan, Mapping):
            return None
        level_id = str(plan["scf_level_id"])
        h = float(plan["h_eV"])
        receipts = self._checkpoint()
        reference = self._reference_node(level_id)
        reference_record = self.records.get(reference.node_id, {})
        reference_receipt = receipts.get(reference.node_id)
        by_mode_column: dict[str, Any] = {}
        tolerance = self.campaign.get("magnetic_moment_tolerance_muB")
        reference_moments = None
        if reference_receipt is not None and isinstance(reference_record, Mapping):
            try:
                command = reference_record["command"]
                reference_moments, _ = reference_moments_from_fdf_and_output(
                    Path(command["stdin_path"]).read_text(encoding="utf-8", errors="replace"),
                    Path(command["stdout_path"]).read_text(encoding="utf-8", errors="replace"),
                )
            except (OSError, KeyError, ValueError):
                reference_moments = None
        for site_index in sorted({int(item) for item in plan["site_indices"]}):
            site_id = str(self.sites[site_index]["site_id"])
            for mode in (ResponseMode.BARE, ResponseMode.SCREENED):
                plus = self._matching_response_node(site_index, h, mode, level_id)
                minus = self._matching_response_node(site_index, -h, mode, level_id)
                key = f"{site_id}|{mode.value}"
                base = signal_vectors.get(key)
                if plus is None or minus is None or not isinstance(base, Mapping):
                    continue
                if any(
                    receipts.get(item.node_id) is None
                    or receipts[item.node_id].state is not NodeState.VALIDATED
                    for item in (plus, minus)
                ):
                    continue
                try:
                    plus_vector, plus_rounding = self._read_response_vector(plus)
                    minus_vector, minus_rounding = self._read_response_vector(minus)
                    strict_vector = [a - b for a, b in zip(plus_vector, minus_vector)]
                    strict_rounding = [a + b for a, b in zip(plus_rounding, minus_rounding)]
                    base_vector = [float(value) for value in base["signal_vector_electron"]]
                    base_rounding = [float(value) for value in base["rounding_bound_vector_electron"]]
                except (OSError, ValueError, KeyError, TypeError):
                    continue
                branch_consistent = bool(
                    mode is ResponseMode.BARE and reference_receipt is not None
                    and reference_receipt.state is NodeState.VALIDATED
                )
                branch_evidence = "shared_validated_strict_reference_dm" if branch_consistent else None
                if tolerance is not None and reference_moments is not None and mode is ResponseMode.SCREENED:
                    differences: list[float] = []
                    try:
                        for response_node in (plus, minus):
                            response_record = self.records[response_node.node_id]
                            output_text = Path(response_record["command"]["stdout_path"]).read_text(
                                encoding="utf-8", errors="replace",
                            )
                            fdf_text = Path(response_record["command"]["stdin_path"]).read_text(
                                encoding="utf-8", errors="replace",
                            )
                            moments, _ = reference_moments_from_fdf_and_output(fdf_text, output_text)
                            differences.append(float(abs(moments - reference_moments).max()))
                        branch_consistent = max(differences, default=float("inf")) <= float(tolerance)
                        branch_evidence = "strict_reference_magnetic_continuity"
                    except (OSError, ValueError, KeyError):
                        branch_consistent = False
                        branch_evidence = "strict_reference_magnetic_continuity_unavailable"
                by_mode_column[key] = {
                    "v_base_electron": base_vector,
                    "v_strict_electron": strict_vector,
                    "q_rounding_bound_electron": [a + b for a, b in zip(base_rounding, strict_rounding)],
                    "branch_consistent": branch_consistent,
                    "branch_evidence": branch_evidence or "screened_branch_tolerance_not_configured",
                }
        expected = {
            f"{self.sites[index]['site_id']}|{mode.value}"
            for index in sorted({int(item) for item in plan["site_indices"]})
            for mode in (ResponseMode.BARE, ResponseMode.SCREENED)
        }
        reserved = self.adaptive_state.get("reserved_nodes", {})
        grid = [float(value) for value in plan.get("rerun_alpha_grid_ev", plan.get("alpha_grid_ev", []))]
        if not grid:
            current = next(item for item in self.adaptive_state["rounds"] if int(item["round_index"]) == int(plan["round_index"]))
            grid = [float(value) for value in current["alpha_grid_ev"]]
        pre_reserved = sum(
            node.node_id in reserved and (
                (node.kind is LRNodeKind.REFERENCE and (node.scf_level_id or "base") == level_id)
                or (node.kind is LRNodeKind.PERTURBATION
                    and (node.scf_level_id or "base") == level_id
                    and node.perturbation is not None
                    and any(abs(float(node.perturbation.alpha_ev) - alpha) <= 1e-14 for alpha in grid))
            )
            for node in self.dag.nodes
        )
        return {
            "validated": expected.issubset(by_mode_column), "by_mode_column": by_mode_column,
            "pre_reserved_rerun_node_count": pre_reserved,
            "quantity": "empirical_scf_sensitivity_not_error_bound",
        }

    def _analysis_metrics(self, path: str | Path) -> dict[str, Any]:
        candidate_path = Path(path)
        if not candidate_path.is_absolute():
            candidate_path = self.root / candidate_path
        return json.loads(candidate_path.read_text(encoding="utf-8"))

    @staticmethod
    def _analysis_u(analysis: Mapping[str, Any]) -> dict[str, float] | None:
        primary = analysis.get("primary")
        values = primary.get("U_by_site_eV") if isinstance(primary, Mapping) else None
        if not isinstance(values, Mapping) or not values:
            return None
        try:
            return {str(key): float(value) for key, value in values.items()}
        except (TypeError, ValueError):
            return None

    def _fit_signature(self, fit: Mapping[str, Any], scf_level_id: str) -> dict[str, Any]:
        return {
            "estimator": fit.get("estimator"),
            "polynomial_degree": fit.get("polynomial_degree"),
            "minimum_residual_dof": fit.get("minimum_residual_dof"),
            "matrix_for_inversion": fit.get("matrix_for_inversion"),
            "window_selection_rule": "policy_declared_active_window_by_round",
            "scf_level_id": scf_level_id,
            "policy_digest": self.adaptive_policy_digest,
            "active_window_eV": fit.get("active_window_eV"),
        }

    def _adaptive_final_artifacts(self, analysis: Mapping[str, Any], decision: Mapping[str, Any]) -> None:
        assert self.adaptive_state is not None and self.adaptive_policy is not None
        result = dict(analysis)
        rounds = []
        for item in self.adaptive_state["rounds"]:
            rounds.append({
                key: item.get(key) for key in (
                    "round_index", "direction", "alpha_grid_ev", "active_window_eV",
                    "fit_policy", "scf_level_id", "effective_scf_level_id",
                    "candidate_status", "analysis_path", "scf_rerun_analysis_path", "status",
                ) if key in item
            })
        result["campaign_status"] = decision["decision"]
        result["candidate_status"] = analysis.get("numerical_status", "NO_NUMERICAL_U")
        result["alpha_rounds"] = rounds
        result["refinement_policy"] = self.adaptive_policy.to_mapping()
        result["refinement_decision"] = dict(decision)
        result["adaptive_budget"] = dict(self.adaptive_state.get("budget", {}))
        result["campaign"]["fixed_grid"] = False
        result["campaign"]["automatic_alpha_refinement"] = True
        result["dag_action"] = "ADAPTIVE_STOP"
        result["scf_probe_interpretation"] = "empirical SCF sensitivity; not a rigorous error bound for U"
        result["noise_not_quantified"] = not bool(decision.get("scf_probe_metrics"))
        is_v3 = result.get("schema_version") == "siestaflow.lr_u_analysis.v3"
        final_path = self.results / ("lr_u_analysis.v3.json" if is_v3 else "lr_u_analysis.v2.json")
        report_path = self.results / ("LR_U_REPORT.v3.md" if is_v3 else "LR_U_REPORT.md")
        write_lr_analysis_v2(final_path, result)
        state_gate = self._read_state_gate_for_report()
        write_lr_u_report(report_path, result, state_gate=state_gate)

    def _read_state_gate_for_report(self) -> Mapping[str, Any] | None:
        path = self.results / "i5_state_gate.json"
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return value if isinstance(value, Mapping) else None

    def _execute_adaptive_gate(self, node: LRDagNode) -> NodeReceipt:
        assert self.adaptive_policy is not None and self.adaptive_state is not None
        is_rerun = ":scf-rerun:" in node.node_id
        is_after_probe = node.node_id.endswith(":decision-after-probe")
        round_index = self._node_round_index(node.node_id)
        if round_index is None:
            raise ExecutionContractError(f"adaptive decision gate has no round key: {node.node_id}")
        round_state = next(item for item in self.adaptive_state["rounds"] if int(item["round_index"]) == round_index)
        analysis_rel = (
            round_state.get("scf_rerun_analysis_path") if is_rerun
            else round_state.get("analysis_path")
        )
        if not analysis_rel:
            raise ExecutionContractError(f"analysis evidence was not persisted before decision gate {node.node_id}")
        analysis = self._analysis_metrics(analysis_rel)
        prior_decision = next(
            (item for item in reversed(self.adaptive_state.get("decisions", []))
             if isinstance(item, Mapping) and item.get("node_id") == node.node_id),
            None,
        )
        if isinstance(prior_decision, Mapping):
            decision = dict(prior_decision)
            evidence_path = self.control / "gates" / f"{node.node_id.replace(':', '-')}.json"
            _atomic_json(evidence_path, decision)
            if decision.get("decision") in {
                AdaptiveDecision.STOP_STABLE.value,
                AdaptiveDecision.STOP_LIMIT_SENSITIVE.value,
                AdaptiveDecision.STOP_INVALID.value,
            }:
                self._adaptive_final_artifacts(analysis, decision)
            digest = sha256_file(evidence_path)
            receipt = NodeReceipt(node.node_id, NodeState.VALIDATED, digest)
            self._record_receipt(node, receipt, {
                "kind": "adaptive_decision", "decision": decision.get("decision"),
                "evidence_path": str(evidence_path), "evidence_sha256": digest,
            })
            if decision.get("decision") in {
                AdaptiveDecision.REFINE.value, AdaptiveDecision.PROBE_SCF.value,
                AdaptiveDecision.IMPROVE_SCF_FIRST.value,
            }:
                self._rebuild_adaptive_graph()
            return receipt
        level_id = str(node.scf_level_id or round_state.get("scf_level_id", "base"))
        analysis_level_id = level_id if is_rerun else str(round_state.get("scf_level_id", "base"))
        fit = dict(round_state.get("fit_policy", {}))
        current_signature = self._fit_signature(fit, analysis_level_id)
        previous_analysis: dict[str, Any] | None = None
        previous_signature: dict[str, Any] | None = None
        if round_index > 0:
            previous_round = self.adaptive_state["rounds"][round_index - 1]
            previous_path = previous_round.get("effective_analysis_path") or previous_round.get("scf_rerun_analysis_path") or previous_round.get("analysis_path")
            if previous_path:
                previous_analysis = self._analysis_metrics(previous_path)
                previous_fit = dict(previous_round.get("fit_policy", {}))
                previous_level = str(previous_round.get("effective_scf_level_id", previous_round.get("scf_level_id", "base")))
                previous_signature = self._fit_signature(previous_fit, previous_level)
        current_u = self._analysis_u(analysis)
        previous_u = None if previous_analysis is None else self._analysis_u(previous_analysis)
        primary = analysis.get("primary", {})
        matrix_usable = isinstance(primary, Mapping) and primary.get("matrix_status") == "FULL_RANK" and current_u is not None
        diagnostics = analysis.get("scf_and_magnetic_diagnostics", {})
        branch_consistent = diagnostics.get("state_continuity_confirmed") if isinstance(diagnostics, Mapping) else None
        sensitivity = (analysis.get("sensitivity_summary") or {}).get("max_abs_u_difference_eV")
        numeric_window_values = [
            float(value) for value in (analysis.get("window_sensitivity_eV") or {}).values()
            if isinstance(value, (int, float)) and not isinstance(value, bool)
        ]
        truncation_metric = max(numeric_window_values) if numeric_window_values else None
        signal_vectors = {} if is_rerun else self._signal_vectors("base")
        probe_evidence = self._scf_probe_evidence(signal_vectors)
        if probe_evidence is None and self.adaptive_state.get("probe_plan") is not None:
            probe_evidence = {"validated": False, "by_mode_column": {}}
        previous_sensitivity = None
        if previous_analysis is not None:
            previous_sensitivity = (previous_analysis.get("sensitivity_summary") or {}).get("max_abs_u_difference_eV")
        result = decide_round(
            self.adaptive_policy,
            round_index=round_index,
            current_grid_ev=round_state["alpha_grid_ev"],
            completed_node_count=len(self.adaptive_state.get("reserved_nodes", {})),
            site_count=len(self.sites), candidate_u_by_site_ev=current_u,
            previous_u_by_site_ev=previous_u,
            stable_comparisons=int(self.adaptive_state.get("stable_comparisons", 0)),
            matrix_usable=bool(matrix_usable), branch_consistent=branch_consistent,
            scf_converged=bool(diagnostics.get("scf_validated")) if isinstance(diagnostics, Mapping) else False,
            truncation_metric_ev=truncation_metric,
            sensitivity_metric_ev=float(sensitivity) if isinstance(sensitivity, (int, float)) else None,
            previous_sensitivity_metric_ev=float(previous_sensitivity) if isinstance(previous_sensitivity, (int, float)) else None,
            signal_vectors_by_mode_column=signal_vectors or None,
            current_fit_signature=current_signature, previous_fit_signature=previous_signature,
            scf_probe=probe_evidence,
        )
        if is_after_probe and result["decision"] == AdaptiveDecision.PROBE_SCF.value:
            result = {
                **result, "decision": AdaptiveDecision.STOP_LIMIT_SENSITIVE.value,
                "reason": "probe_already_scheduled_but_required_vectors_missing",
            }
        if is_rerun and result["decision"] == AdaptiveDecision.IMPROVE_SCF_FIRST.value:
            result = {
                **result, "decision": AdaptiveDecision.STOP_LIMIT_SENSITIVE.value,
                "reason": "strict_scf_level_already_used_for_consistent_rerun",
            }
        result.update({
            "node_id": node.node_id, "policy_digest": self.adaptive_policy_digest,
            "fit_signature": current_signature,
            "candidate_status": analysis.get("numerical_status", "NO_NUMERICAL_U"),
            "candidate_U_by_site_eV": current_u,
            "truncation_metric_eV": truncation_metric,
            "truncation_metric_basis": (
                "range_of_eligible_linear_fit_windows; excludes resolution_limited_two_point_central_differences; "
                "empirical_estimator_diagnostic_not_an_error_bound"
            ),
            "sensitivity_metric_eV": sensitivity,
            "budget_reserved_nodes": len(self.adaptive_state.get("reserved_nodes", {})),
        })
        decision_index = next(
            (index for index, item in enumerate(self.adaptive_state["decisions"])
             if isinstance(item, Mapping) and item.get("node_id") == node.node_id),
            None,
        )
        if decision_index is None:
            self.adaptive_state["decisions"].append(dict(result))
            decision_index = len(self.adaptive_state["decisions"]) - 1
        self.adaptive_state["candidate_status"] = result["candidate_status"]
        if "stable_comparisons" in result:
            self.adaptive_state["stable_comparisons"] = int(result["stable_comparisons"])
        round_state["decision"] = dict(result)
        round_state["status"] = "DECIDED"
        decision_type = result["decision"]
        if decision_type == AdaptiveDecision.PROBE_SCF.value:
            strict = self.adaptive_policy.scf_probe_level
            if strict is None:
                result["decision"] = AdaptiveDecision.STOP_LIMIT_SENSITIVE.value
                result["reason"] = "scf_probe_level_not_configured"
                decision_type = result["decision"]
            else:
                ids = set(result.get("affected_site_ids", []))
                probe_ids = set(result.get("probe_site_ids", ids))
                site_indices = [index for index, site in enumerate(self.sites) if site["site_id"] in probe_ids]
                old_probe = self.adaptive_state.get("probe_plan")
                if old_probe is not None:
                    result["decision"] = AdaptiveDecision.STOP_LIMIT_SENSITIVE.value
                    result["reason"] = "probe_activation_limit_reached_for_existing_campaign_probe"
                    decision_type = result["decision"]
                elif not site_indices:
                    result["decision"] = AdaptiveDecision.STOP_LIMIT_SENSITIVE.value
                    result["reason"] = "scf_probe_affected_columns_not_identified"
                    decision_type = result["decision"]
                else:
                    self.adaptive_state["probe_plan"] = {
                        "round_index": round_index, "site_indices": site_indices,
                        "trigger_site_ids": sorted(ids),
                        "probe_site_ids": [str(self.sites[index]["site_id"]) for index in site_indices],
                        "scope": result.get("probe_scope", "weak_sites"),
                        "h_eV": float(self.adaptive_policy.h_ev),
                        "scf_level_id": str(strict["level_id"]),
                        "alpha_grid_ev": list(round_state["alpha_grid_ev"]),
                    }
                    self.adaptive_state["probed_site_ids"] = sorted(
                        set(self.adaptive_state.get("probed_site_ids", []))
                        | {str(self.sites[index]["site_id"]) for index in site_indices}
                    )
                    round_state["status"] = "PROBE_SCHEDULED"
        if decision_type == AdaptiveDecision.IMPROVE_SCF_FIRST.value:
            strict = self.adaptive_policy.scf_probe_level
            if strict is None:
                result["decision"] = AdaptiveDecision.STOP_LIMIT_SENSITIVE.value
                result["reason"] = "strict_scf_rerun_level_not_configured"
                decision_type = result["decision"]
            elif not any(int(item["round_index"]) == round_index for item in self.adaptive_state.get("scf_reruns", [])):
                self.adaptive_state["scf_reruns"].append({
                    "round_index": round_index, "alpha_grid_ev": list(round_state["alpha_grid_ev"]),
                    "scf_level_id": str(strict["level_id"]),
                    "fit_policy": dict(round_state["fit_policy"]),
                    "active_window_eV": round_state["active_window_eV"],
                    "status": "PENDING",
                })
                round_state["status"] = "STRICT_SCF_RERUN_SCHEDULED"
        if decision_type == AdaptiveDecision.REFINE.value:
            additions = [float(value) for value in result.get("add_alpha_ev", [])]
            direction = str(result["direction"])
            new_index = round_index + 1
            new_grid = sorted({float(value) for value in (*round_state["alpha_grid_ev"], *additions)})
            next_fit = dict(self.adaptive_policy.analysis_for_round(new_index, direction))
            next_round = {
                "round_index": new_index, "direction": direction,
                "alpha_grid_ev": new_grid,
                "active_window_eV": next_fit["active_window_eV"],
                "fit_policy": next_fit,
                "scf_level_id": analysis_level_id,
                "status": "PENDING",
            }
            existing_round = next(
                (item for item in self.adaptive_state["rounds"] if int(item["round_index"]) == new_index),
                None,
            )
            if existing_round is not None:
                if existing_round.get("direction") != direction or existing_round.get("alpha_grid_ev") != new_grid:
                    raise ExecutionContractError("persisted refinement decision conflicts with an existing round")
            else:
                self.adaptive_state["rounds"].append(next_round)
            round_state["status"] = "REFINED"
            round_state["effective_analysis_path"] = analysis_rel
            round_state["effective_scf_level_id"] = level_id
        terminal = decision_type in {
            AdaptiveDecision.STOP_STABLE.value,
            AdaptiveDecision.STOP_LIMIT_SENSITIVE.value,
            AdaptiveDecision.STOP_INVALID.value,
        }
        self.adaptive_state["campaign_status"] = decision_type if terminal else "RUNNING"
        result["decision"] = decision_type
        self.adaptive_state["decisions"][decision_index] = dict(result)
        round_state["decision"] = dict(result)
        self._persist_adaptive_state()

        evidence_path = self.control / "gates" / f"{node.node_id.replace(':', '-')}.json"
        _atomic_json(evidence_path, result)
        if terminal:
            self._adaptive_final_artifacts(analysis, result)
        digest = sha256_file(evidence_path)
        receipt = NodeReceipt(node.node_id, NodeState.VALIDATED, digest)
        self._record_receipt(node, receipt, {
            "kind": "adaptive_decision", "decision": decision_type,
            "evidence_path": str(evidence_path), "evidence_sha256": digest,
        })
        if decision_type in {AdaptiveDecision.REFINE.value, AdaptiveDecision.PROBE_SCF.value,
                             AdaptiveDecision.IMPROVE_SCF_FIRST.value}:
            self._rebuild_adaptive_graph()
        return receipt

    def _no_numerical_result(self, reason: str, *, magnetic_diagnostics: Mapping[str, Any] | None = None) -> dict[str, Any]:
        site_index_map = [
            {"index": index, "site_id": str(site["site_id"]),
             "atom_index": site.get("atom_index"), "orbit_id": site.get("orbit_id")}
            for index, site in enumerate(self.sites)
        ]
        return {
            "schema_version": "siestaflow.lr_u_analysis.v3",
            "occupation_source": "siesta_occupations_total",
            "campaign": {
                "campaign_id": self.campaign["campaign_id"], "name": self.campaign.get("name"),
                "material": self.campaign.get("material"), "functional": self.campaign["functional"],
                "xc_profile": self.campaign["_xc_profile"],
                "sites": self.sites, "observables": self.campaign.get("observables", []),
                "fixed_grid": True, "automatic_alpha_refinement": False,
            },
            "quantity": "U_scalar_charge", "units": "eV",
            "site_labels": list(range(len(self.sites))), "alpha_grid_eV": self.alpha_grid,
            "estimator_policy": self.config.get("analysis_policy", {}),
            "selected_estimator": None,
            "primary": {"method": None, "degree": None, "U_by_site_eV": None, "U_matrix_eV": None, "matrix_status": "NO_NUMERICAL_U"},
            "same_grid_linear": None, "window_results": [], "window_sensitivity_eV": None,
            "model_sensitivity_eV": None, "printing_rounding_bound_eV": None,
            "printing_rounding_bound_reason": "analysis inputs unavailable or invalid",
            "scf_and_magnetic_diagnostics": {"scf_validated": None, "magnetic": dict(magnetic_diagnostics or {})},
            "response_observation_dataset": {
                "schema_version": "siestaflow.lr_u_verified_dataset.v2",
                "occupation_source": "siesta_occupations_total",
                "status": "UNAVAILABLE",
                "reason": reason,
                "units": {"alpha": "eV", "occupations": "electron"},
                "site_index_map": site_index_map,
                "matrix_index_to_site_id": {str(item["index"]): item["site_id"] for item in site_index_map},
                "site_id_to_matrix_index": {item["site_id"]: item["index"] for item in site_index_map},
                "reference_source": None,
                "rows": [],
            },
            "numerical_status": "NO_NUMERICAL_U", "physical_acceptance": "NOT_ESTABLISHED",
            "dag_action": "RECORDED_ONLY", "reasons": ["NO_NUMERICAL_U", reason],
            "provenance": {"input_identity": self.campaign["input_identity"], "campaign_inputs": self._analysis_input_provenance()},
        }

    def _event_occupations(
        self, output_content: str, event: HubbardPopulationEvent, sites: list[dict[str, Any]],
    ) -> list[float]:
        return self.observations.event_occupations(
            output_content, event, sites,
            minimum_decimal_places=self._minimum_occupation_decimal_places,
        )

    def _event_trace_half_widths(
        self, output_content: str, event: HubbardPopulationEvent, sites: list[dict[str, Any]],
    ) -> list[float] | None:
        return self.observations.event_trace_half_widths(
            output_content, event, sites,
            minimum_decimal_places=self._minimum_occupation_decimal_places,
        )

    @staticmethod
    def _verify_record_artifacts(record: Mapping[str, Any], node_id: str) -> dict[str, str]:
        return _verify_record_artifacts(record, node_id)

    def _projector_fingerprint(self, site_id: str, fdf_text: str) -> str:
        return self.observations.projector_fingerprint(
            site_id, fdf_text, root=self.root, config=self.config,
            input_sha256_by_path=self._input_sha256_by_path,
        )
    def _analysis_input_provenance(self) -> dict[str, Any]:
        """Expose the campaign's declared inputs and runtime identity in the report."""
        def input_record(path: str | Path) -> dict[str, Any]:
            relative = _campaign_relative_path(self.root, path)
            return {
                "path": relative,
                "sha256": self._input_sha256_by_path.get(str(relative)),
                "hash_source": "verified_campaign_input_inventory",
            }

        declared_files: dict[str, Any] = {}
        for label, field in (
            ("reference_fdf", "reference_fdf"),
            ("lr_config", "lr_config_file"),
            ("campaign_contract", "contract_file"),
            ("execution_profile", "execution_profile_file"),
        ):
            path = self.root / self.campaign[field]
            declared_files[label] = input_record(path)
        pseudopotentials = {
            str(label): input_record(path)
            for label, path in sorted(self.config["pseudopotentials"].items())
        }
        version_path = Path(str(self.config["version_text_source"]))
        version_record = input_record(version_path)
        admission = getattr(self.admitted, "admission", None)
        observed_runtime = getattr(admission, "observed", None)
        try:
            package_version = installed_package_version("hubbardflow")
        except PackageNotFoundError:
            package_version = "uninstalled-source-tree"
        return {
            "input_identity": self.campaign["input_identity"],
            "declared_inputs": declared_files,
            "pseudopotentials": pseudopotentials,
            "siesta_runtime": {
                "declared_executable": self.config.get("declared_executable"),
                "runtime_executable": self.profile.runtime.siesta_executable,
                "version": getattr(observed_runtime, "version", None),
                "version_text_path": version_record["path"],
                "version_text_sha256": version_record["sha256"],
                "version_hash_source": version_record["hash_source"],
            },
            "analysis_implementation": {
                "module": "hubbardflow.domain.lr_analysis_v2",
                "package": "hubbardflow",
                "package_version": package_version,
                "schema": "siestaflow.lr_u_analysis.v3",
            },
        }

    def _load_response_grid_calibration(self, reference_fdf: Path) -> dict[str, Any] | None:
        """Load a preregistered grid replica receipt before any campaign work.

        Its context digest binds the material, functional, ordered projectors,
        exact response mesh, SCF-defining input/profile, and numerical policy.
        Only response-defining analysis policy fields enter that digest;
        acceptance tolerances are frozen separately by campaign resume identity
        and cannot change which replica measurements are scientifically applicable.
        """
        specification = self.config.get("response_grid_reproducibility_calibration")
        if specification is None:
            return None
        try:
            lock_key = specification["lock_static_artifact"]
            result_key = specification["result_static_artifact"]
            response_policy = LRAnalysisPolicy(**self.config.get("analysis_policy", {}))
            response_policy.validate()
            context_hash = response_grid_campaign_context_sha256(
                material=self.campaign.get("material"),
                functional=self.campaign["functional"],
                reference_fdf_sha256=sha256_file(reference_fdf),
                execution_profile_sha256=sha256_file(self.root / self.campaign["execution_profile_file"]),
                pseudopotentials={
                    str(label): sha256_file(Path(path))
                    for label, path in sorted(self.config["pseudopotentials"].items())
                },
                sites=self.sites,
                alpha_grid_eV=self.alpha_grid,
                analysis_policy=response_policy.response_context(),
                adaptive_alpha_policy=self.config.get("adaptive_alpha_policy"),
                magnetic_moment_tolerance_muB=self.campaign.get("magnetic_moment_tolerance_muB"),
            )
            return validate_response_grid_calibration(
                self.root,
                Path(self.config["static_artifacts"][lock_key]),
                Path(self.config["static_artifacts"][result_key]),
                expected_context_sha256=context_hash,
                expected_sites=[int(site["index"]) for site in self.sites],
                expected_site_ids={int(site["index"]): str(site["site_id"]) for site in self.sites},
                expected_atom_indices={int(site["index"]): int(site["atom_index"]) for site in self.sites},
                expected_alphas_eV=self.alpha_grid,
                source_context_resolver=response_grid_source_campaign_context,
                response_cell_extractor=extract_siesta_response_cell,
                expected_primary_campaign_id=str(self.campaign["campaign_id"]),
                expected_primary_source_root=self.root.resolve(strict=True),
            )
        except Exception as exc:
            reason = f"{type(exc).__name__}: {exc}"
            return {
                "validation_status": (
                    "UNVERIFIED_MEASUREMENT_VALUES" if "UNVERIFIED_MEASUREMENT_VALUES" in str(exc)
                    else "INVALID_RESPONSE_GRID_CALIBRATION"
                ),
                "reason": reason,
            }

    def _reference_node(self, scf_level_id: str = "base") -> LRDagNode:
        return self.observations.reference_node(self.dag, scf_level_id)

    def _verified_observations(
        self, *, alpha_grid: list[float] | None = None, scf_level_id: str = "base",
        site_indices: tuple[int, ...] | None = None,
    ) -> tuple[
        list[ResponseObservation], dict[float, str] | None, dict[str, Any],
        dict[tuple[int, float, str], list[float]], list[float] | None,
    ]:
        return self.observations.verified_observations(
            root=self.root,
            campaign=self.campaign,
            config=self.config,
            sites=self.sites,
            dag=self.dag,
            specs=self.specs,
            records=self.records,
            checkpoint=self.checkpoint(),
            admitted=self.admitted,
            input_sha256_by_path=self._input_sha256_by_path,
            minimum_decimal_places=self._minimum_occupation_decimal_places,
            adaptive=self.adaptive_policy is not None,
            alpha_grid=list(alpha_grid if alpha_grid is not None else self.alpha_grid),
            scf_level_id=scf_level_id,
            site_indices=site_indices,
        )

    def _response_observation_dataset(
        self, observations: list[ResponseObservation], *, scf_level_id: str = "base",
        trace_half_widths_electron: Mapping[tuple[int, float, str], list[float]] | None = None,
        reference_trace_half_widths_electron: list[float] | None = None,
        occupation_source: str = "matrix_trace_total",
    ) -> dict[str, Any]:
        return self.observations.response_observation_dataset(
            root=self.root,
            sites=self.sites,
            dag=self.dag,
            specs=self.specs,
            records=self.records,
            checkpoint=self.checkpoint(),
            observations=observations,
            scf_level_id=scf_level_id,
            trace_half_widths_electron=trace_half_widths_electron,
            reference_trace_half_widths_electron=reference_trace_half_widths_electron,
            occupation_source=occupation_source,
        )
    def _analysis_execution_identity(
        self, dataset: Mapping[str, Any], *, scf_level_id: str, alpha_grid: list[float],
    ) -> dict[str, Any]:
        """Return attempt IDs bound to the exact verified dataset used for analysis."""
        root = self.root.resolve(strict=True)
        receipts = self._checkpoint()
        nodes: dict[str, str] = {}
        attempts: set[str] = set()

        def bind_source(source: Any, label: str, *, expected_mode: str | None = None) -> None:
            if not isinstance(source, Mapping) or source.get("state") != NodeState.VALIDATED.value:
                raise ValueError(f"{label} dataset source lacks a validated execution receipt")
            node_id, digest = source.get("node_id"), source.get("evidence_digest")
            if not isinstance(node_id, str) or not node_id or not isinstance(digest, str):
                raise ValueError(f"{label} dataset source lacks node identity/digest")
            if expected_mode is not None and source.get("mode") != expected_mode:
                raise ValueError(f"{label} dataset mode differs from the selected analysis grid")
            record = self.records.get(node_id)
            receipt = receipts.get(node_id)
            if (not isinstance(record, Mapping) or record.get("state") != NodeState.VALIDATED.value
                    or record.get("kind") != "siesta" or record.get("evidence_digest") != digest
                    or receipt is None or receipt.state is not NodeState.VALIDATED
                    or receipt.evidence_digest != digest):
                raise ValueError(f"{label} source is not bound to the validated campaign node receipt")
            if str(record.get("scf_level_id", "base")) != scf_level_id:
                raise ValueError(f"{label} source belongs to another SCF level")
            actual = self._verify_record_artifacts(record, node_id)
            for key, source_key in (("fdf", "fdf"), ("output", "out"), ("dm", "dm")):
                declared_hash = source.get(f"{source_key}_sha256")
                if declared_hash != actual[key]:
                    raise ValueError(f"{label} {key} hash differs from its validated node receipt")
                raw_path = source.get(f"{source_key}_path")
                if not isinstance(raw_path, str):
                    raise ValueError(f"{label} {key} path is missing from the verified dataset")
                candidate = Path(raw_path)
                candidate = candidate if candidate.is_absolute() else root / candidate
                try:
                    resolved = candidate.resolve(strict=True)
                    resolved.relative_to(root)
                except (OSError, ValueError) as exc:
                    raise ValueError(f"{label} {key} path escapes the campaign root") from exc
                command = record.get("command")
                spec = record.get("artifact_spec")
                if not isinstance(command, Mapping) or not isinstance(spec, Mapping):
                    raise ValueError(f"{label} receipt lacks command/artifact specification")
                cwd = Path(str(command.get("cwd", ""))).resolve(strict=True)
                attempt_id, attempt_root = _execution_attempt(root, cwd)
                expected_path = (
                    Path(str(command.get("stdin_path", ""))) if key == "fdf"
                    else Path(str(command.get("stdout_path", ""))) if key == "output"
                    else cwd / str(spec.get("dm", ""))
                ).resolve(strict=True)
                if resolved != expected_path:
                    raise ValueError(f"{label} {key} path differs from command/artifact receipt")
                try:
                    resolved.relative_to(attempt_root)
                except ValueError as exc:
                    raise ValueError(f"{label} {key} artifact is outside its recorded attempt") from exc
                if key == "fdf":
                    attempt_for_node = attempt_id
                elif attempt_for_node != attempt_id:
                    raise ValueError(f"{label} artifacts span multiple execution attempts")
            if node_id in nodes and nodes[node_id] != attempt_for_node:
                raise ValueError(f"{label} node is associated with inconsistent attempts")
            if attempt_for_node in attempts and nodes.get(node_id) != attempt_for_node:
                raise ValueError(f"distinct dataset nodes reuse the same execution attempt")
            nodes[node_id] = attempt_for_node
            attempts.add(attempt_for_node)

        reference = dataset.get("reference_source")
        bind_source(reference, "reference", expected_mode="REFERENCE_SCREENED")
        rows = dataset.get("rows")
        if not isinstance(rows, list):
            raise ValueError("verified response dataset has no rows")
        expected_coordinates = {
            (int(site["index"]), float(alpha), mode)
            for site in self.sites for alpha in alpha_grid for mode in ("BARE", "SCREENED")
        }
        observed_coordinates: set[tuple[int, float, str]] = set()
        for row in rows:
            if not isinstance(row, Mapping):
                raise ValueError("verified response dataset row is malformed")
            coordinate = (int(row["perturbed_site_index"]), float(row["alpha_eV"]))
            sources = row.get("sources")
            if not isinstance(sources, Mapping):
                raise ValueError("verified response row lacks its mode source receipts")
            for mode, key in (("BARE", "bare"), ("SCREENED", "screened")):
                source = sources.get(key)
                observed_coordinates.add((*coordinate, mode))
                bind_source(source, f"response {coordinate}/{mode}", expected_mode=mode)
        if observed_coordinates != expected_coordinates:
            raise ValueError("verified response dataset does not cover this analysis grid and SCF level")
        return {"source_root": str(root), "execution_attempt_ids": sorted(attempts)}

    @staticmethod
    def _node_round_index(node_id: str) -> int | None:
        import re
        match = re.search(r"(?:round:|scf-rerun:)(\d+)", node_id)
        if match is None:
            match = re.search(r":r(\d+):", node_id)
        return None if match is None else int(match.group(1))

    def _adaptive_analysis_context(
        self, node: LRDagNode,
    ) -> tuple[dict[str, Any], dict[str, Any], int, str, bool]:
        if self.adaptive_state is None:
            raise ExecutionContractError("adaptive analysis context requested for fixed-grid campaign")
        round_index = self._node_round_index(node.node_id)
        if round_index is None:
            raise ExecutionContractError(f"adaptive analysis node has no round key: {node.node_id}")
        round_state = next(
            (item for item in self.adaptive_state["rounds"] if int(item["round_index"]) == round_index), None,
        )
        is_rerun = ":scf-rerun:" in node.node_id
        if is_rerun:
            rerun = next(
                (item for item in self.adaptive_state.get("scf_reruns", [])
                 if int(item["round_index"]) == round_index), None,
            )
            if rerun is None or round_state is None:
                raise ExecutionContractError(f"SCF rerun state for round {round_index} is missing")
            return round_state, rerun, round_index, str(rerun["scf_level_id"]), True
        if round_state is None:
            raise ExecutionContractError(f"adaptive round state {round_index} is missing")
        return round_state, round_state, round_index, str(round_state.get("scf_level_id", "base")), False

    def _execute_analysis(self, node: LRDagNode) -> NodeReceipt:
        adaptive = self.adaptive_policy is not None
        if adaptive:
            round_state, fit_state, round_index, level_id, is_rerun = self._adaptive_analysis_context(node)
            evidence_path = self.results / "alpha_rounds" / f"round-{round_index:02d}" / (
                "scf-rerun-analysis.v3.json" if is_rerun else "analysis.v3.json"
            )
            report_path = evidence_path.with_suffix(".md")
            fit = fit_state.get("fit_policy", fit_state.get("analysis_policy", {}))
            round_policy = replace(
                self.analysis_policy,
                estimator=str(fit["estimator"]),
                polynomial_degree=int(fit["polynomial_degree"]),
                minimum_residual_dof=int(fit["minimum_residual_dof"]),
                matrix_for_inversion=str(fit["matrix_for_inversion"]),
            )
            round_policy.validate()
            alpha_grid = [float(value) for value in fit_state["alpha_grid_ev"]]
            active_window = float(fit["active_window_eV"])
        else:
            round_state = None
            round_index = -1
            level_id = "base"
            is_rerun = False
            evidence_path = self.results / "lr_u_analysis.v3.json"
            report_path = self.results / "LR_U_REPORT.v3.md"
            round_policy = self.analysis_policy
            alpha_grid = self.alpha_grid
            active_window = None
        magnetic: dict[str, Any] = {}
        try:
            if getattr(self, "shadow", None) is not None:
                observations, states, magnetic, trace_half_widths_electron, reference_trace_half_widths_electron, verified_dataset = self.shadow.analysis_data(self)
            else:
                observations, states, magnetic, trace_half_widths_electron, reference_trace_half_widths_electron = self._verified_observations(
                    alpha_grid=alpha_grid, scf_level_id=level_id,
                )
                verified_dataset = self._response_observation_dataset(
                    observations, scf_level_id=level_id,
                    trace_half_widths_electron=trace_half_widths_electron,
                    reference_trace_half_widths_electron=reference_trace_half_widths_electron,
                    occupation_source="siesta_occupations_total",
                )
            execution_identity = (
                self._analysis_execution_identity(
                    verified_dataset, scf_level_id=level_id, alpha_grid=alpha_grid,
                )
                if isinstance(self.response_grid_calibration, ValidatedResponseGridCalibration)
                else {}
            )
            analysis = analyze_verified_lr(
                observations, round_policy,
                campaign={
                    "campaign_id": self.campaign["campaign_id"], "name": self.campaign.get("name"),
                    "reference_dm_sha256": verified_dataset["reference_source"]["dm_sha256"],
                    **execution_identity,
                    "material": self.campaign.get("material"), "functional": self.campaign["functional"],
                    "xc_profile": self.campaign["_xc_profile"],
                    "sites": self.sites, "observables": self.campaign.get("observables", []),
                    "fixed_grid": not adaptive, "automatic_alpha_refinement": adaptive,
                },
                magnetic_state_labels=states,
                scf_validated=True,
                active_window_ev=active_window,
                trace_half_widths_electron=trace_half_widths_electron,
                occupation_source="siesta_occupations_total",
                response_grid_reproducibility_calibration=self.response_grid_calibration,
            )
            analysis["dag_action"] = "ADAPTIVE_ROUND_ANALYSIS" if adaptive else "RECORDED_ONLY"
            if not adaptive:
                analysis["alpha_diagnostic"] = {
                    "grid_mode": "fixed_grid", "automatic_refinement": False,
                    "decision": "SENSITIVITY_REPORTED_BY_ANALYSIS",
                }
            analysis["scf_and_magnetic_diagnostics"]["magnetic_branch_evidence"] = magnetic
            analysis["provenance"]["campaign_inputs"] = self._analysis_input_provenance()
            analysis["response_observation_dataset"] = verified_dataset
            if adaptive:
                analysis["adaptive_round"] = {
                    "round_index": round_index, "direction": round_state.get("direction"),
                    "scf_level_id": level_id, "active_window_eV": active_window,
                    "fit_policy": dict(fit), "is_scf_consistent_rerun": is_rerun,
                    "alpha_grid_eV": alpha_grid,
                    "full_grid_is_diagnostic_only": True,
                }
        except Exception as exc:
            analysis = self._no_numerical_result(
                f"analysis_or_observation_extraction_failed:{type(exc).__name__}:{exc}",
                magnetic_diagnostics=magnetic,
            )
        write_lr_analysis_v2(evidence_path, analysis)
        state_gate_path = self.results / "i5_state_gate.json"
        try:
            state_gate = state_gate_mapping(
                dag=self.dag,
                specs=self.specs,
                records=self.records,
                checkpoint=self._checkpoint(),
                sites=self.sites,
                alpha_grid_ev=alpha_grid,
                bare_profile=self.admitted.factory.bare_profile,
                covered=not adaptive,
                **(
                    {
                        "site_indices": tuple(
                            i
                            for i, subspace in enumerate(self.shadow.plan.inventory.subspaces)
                            if subspace.site_id
                            in (set(self.shadow.plan.computed_columns) | set(self.shadow.expanded))
                        )
                    }
                    if self.shadow is not None
                    else {}
                ),
            )
        except Exception:
            state_gate = failed_state_gate_mapping(self.sites, StateGateReason.INVALID_STATE_EVIDENCE)
        try:
            write_state_gate_file(state_gate_path, state_gate)
            report_state_gate = json.loads(state_gate_path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001 - I.5 persistence must not fail the U analysis.
            report_state_gate = failed_state_gate_mapping(
                self.sites, StateGateReason.INVALID_STATE_EVIDENCE
            )
        write_lr_u_report(report_path, analysis, state_gate=report_state_gate)
        digest = sha256_file(evidence_path)
        # Keep the analysis-node record tied to the canonical LR-U report. The
        # separate I.5 diagnostic section must not change node-evidence.json.
        canonical_report_digest = sha256(render_lr_u_report(analysis).encode("utf-8")).hexdigest()
        receipt = NodeReceipt(node.node_id, NodeState.VALIDATED, digest)
        if adaptive:
            assert self.adaptive_state is not None and round_state is not None
            persisted_path = str(evidence_path.relative_to(self.root).as_posix())
            if is_rerun:
                round_state["scf_rerun_analysis_path"] = persisted_path
                round_state["scf_rerun_candidate_status"] = analysis.get("numerical_status", "NO_NUMERICAL_U")
                round_state["effective_analysis_path"] = persisted_path
                round_state["effective_scf_level_id"] = level_id
            else:
                round_state["analysis_path"] = persisted_path
                round_state["candidate_status"] = analysis.get("numerical_status", "NO_NUMERICAL_U")
                round_state["effective_analysis_path"] = persisted_path
                round_state["effective_scf_level_id"] = level_id
            round_state["status"] = "ANALYZED"
            self._persist_adaptive_state()
        self._record_receipt(node, receipt, {
            "kind": "analysis", "evidence_path": str(evidence_path),
            "evidence_sha256": digest, "report_path": str(report_path),
            "report_sha256": canonical_report_digest,
            "numerical_status": analysis.get("numerical_status"),
        })
        return receipt

    def advance(self, mode: str, heartbeat: _Heartbeat) -> int:
        if mode == "run" and self.checkpoint_path.exists():
            existing = self._checkpoint()
            if existing:
                raise ExecutionContractError("campaign already has DAG receipts; use resume")
        if mode == "resume":
            self._revalidate_reuse()
            if getattr(self, "shadow", None) is not None:
                self.shadow.replay_barrier(self)
        while True:
            ready = self.executor.runnable()
            if not ready:
                receipts = self._checkpoint()
                if all(node.node_id in receipts and receipts[node.node_id].state is NodeState.VALIDATED for node in self.dag.nodes):
                    heartbeat.finish("COMPLETED", completed_nodes=sorted(receipts))
                    return 0
                blocked = [node.node_id for node in self.dag.nodes if node.node_id not in receipts]
                raise ExecutionContractError(f"no runnable node; unresolved DAG nodes: {blocked[:8]}")
            if (self.control / "stop-request.json").exists():
                heartbeat.finish("STOPPED", stop_reason="safe_stop_requested", completed_nodes=sorted(self._checkpoint()))
                return 0
            node = ready[0]
            if not self._reserve_adaptive_node(node):
                self._stop_for_unreserved_node(node)
                heartbeat.finish(
                    "COMPLETED", stop_reason="unplanned_node_exceeds_remaining_budget",
                    campaign_status=AdaptiveDecision.STOP_LIMIT_SENSITIVE.value,
                )
                return 0
            heartbeat.update(active_node=node.node_id, current_node_state="RUNNING")
            if node.kind in {LRNodeKind.REFERENCE, LRNodeKind.PERTURBATION}:
                receipt = self._execute_siesta(node, heartbeat)
            elif node.kind is LRNodeKind.ALPHA_GATE:
                if getattr(self, "shadow", None) is not None and not self.shadow.prepare(self):
                    continue
                receipt = self._execute_gate(node)
            elif node.kind is LRNodeKind.MATRIX_ANALYSIS:
                receipt = self._execute_analysis(node)
            else:  # pragma: no cover - closed enum guard
                raise ExecutionContractError(f"unsupported DAG node kind {node.kind.value}")
            completed = sorted(self._checkpoint())
            heartbeat.update(active_node=None, current_node_state=receipt.state.value, completed_nodes=completed)
            if receipt.state is not NodeState.VALIDATED:
                if getattr(self, "shadow", None) is not None and self.shadow.failed_shadow(self, node):
                    continue
                failure_record = self.store.records.get(node.node_id, {})
                failure_details = {
                    name: failure_record[name]
                    for name in ("returncode", "returncode_meaning")
                    if name in failure_record
                }
                heartbeat.finish(
                    "FAILED", failed_node=node.node_id, failure_state=receipt.state.value, **failure_details,
                )
                return 1


def run_campaign_worker(manifest_path: str | Path, mode: str) -> int:
    if fcntl is None:
        raise RuntimeError("campaign worker execution requires Linux/WSL fcntl locking")
    campaign = load_campaign_v2(manifest_path)
    control = Path(campaign["_campaign_root"]) / ".siestaflow"
    control.mkdir(parents=True, exist_ok=True)
    with (control / "worker.lock").open("a+b") as worker_lock:
        try:
            fcntl.flock(worker_lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return 2
        heartbeat = _Heartbeat(control / "worker-state.json", campaign_id=campaign["campaign_id"])
        (control / "stop-request.json").unlink(missing_ok=True)
        heartbeat.start()
        try:
            runner = CampaignRunner(manifest_path)
            runner.factory.state = heartbeat
            return runner.advance(mode, heartbeat)
        except Exception as exc:
            _atomic_json(control / "worker-error.json", {
                "type": type(exc).__name__, "message": str(exc), "traceback": traceback.format_exc(),
                "epoch": time.time(),
            })
            heartbeat.finish("FAILED", error_type=type(exc).__name__, error=str(exc))
        return 1


def campaign_status(manifest_path: str | Path) -> dict[str, Any]:
    campaign = load_campaign_v2(manifest_path)
    state_path = Path(campaign["_campaign_root"]) / ".siestaflow" / "worker-state.json"
    try:
        value = json.loads(state_path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {"status": "UNKNOWN"}
    except (OSError, json.JSONDecodeError):
        return {"campaign_id": campaign["campaign_id"], "status": "NOT_STARTED"}


def request_campaign_stop(manifest_path: str | Path) -> dict[str, Any]:
    campaign = load_campaign_v2(manifest_path)
    control = Path(campaign["_campaign_root"]) / ".siestaflow"
    control.mkdir(parents=True, exist_ok=True)
    _atomic_json(control / "stop-request.json", {"campaign_id": campaign["campaign_id"], "requested_epoch": time.time()})
    return {"campaign_id": campaign["campaign_id"], "stop_requested": True}


def render_campaign_report(manifest_path: str | Path) -> str:
    campaign = load_campaign_v2(manifest_path)
    root = Path(campaign["_campaign_root"])
    analysis_path = root / "results" / "lr_u_analysis.v3.json"
    if not analysis_path.is_file():
        analysis_path = root / "results" / "lr_u_analysis.v2.json"
    if analysis_path.is_file():
        analysis = json.loads(analysis_path.read_text(encoding="utf-8"))
        state_gate_path = root / "results" / "i5_state_gate.json"
        try:
            state_gate = json.loads(state_gate_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            state_gate = None
        report_path = root / "results" / (
            "LR_U_REPORT.v3.md" if analysis.get("schema_version") == "siestaflow.lr_u_analysis.v3"
            else "LR_U_REPORT.md"
        )
        report = render_lr_u_report(analysis, state_gate=state_gate)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(report, encoding="utf-8", newline="\n")
        return report
    try:
        status = json.loads((root / ".siestaflow" / "worker-state.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        status = {"status": "NOT_STARTED"}
    try:
        adaptive = json.loads((root / ".siestaflow" / "adaptive-alpha-state.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        adaptive = None
    lines = [
        "# Estado de campaña HubbardFlow",
        "",
        f"- Campaña: {campaign.get('name', campaign['campaign_id'])}",
        f"- Estado: **{status.get('status', 'NOT_STARTED')}**",
        f"- Nodo activo: {status.get('active_node') or '—'}",
        "- Análisis U: todavía no hay JSON v2; report se actualizará al terminar MATRIX_ANALYSIS.",
    ]
    if isinstance(adaptive, Mapping):
        rounds = adaptive.get("rounds", [])
        current = rounds[-1] if isinstance(rounds, list) and rounds else {}
        decisions = adaptive.get("decisions", [])
        decision = decisions[-1] if isinstance(decisions, list) and decisions else {}
        budget = adaptive.get("budget", {})
        lines.extend([
            "",
            "## Refinamiento adaptativo de α",
            "",
            f"- Estado de campaña: **{adaptive.get('campaign_status', 'RUNNING')}**.",
            f"- Estado del candidato: **{adaptive.get('candidate_status', 'PENDING')}**.",
            f"- Ronda actual/final: {current.get('round_index', '—')} ({current.get('status', '—')}); ventana activa: {current.get('active_window_eV', '—')} eV.",
            f"- Decisión más reciente: `{decision.get('decision', 'PENDING')}` — {str(decision.get('reason') or '—').replace(chr(10), ' ')}.",
            f"- Nodos SIESTA reservados: {budget.get('reserved_nodes', 0)}/{budget.get('total_siesta_node_budget', '—')}; quedan {budget.get('remaining_nodes', '—')}.",
        ])
    lines.append("")
    return "\n".join(lines)


__all__ = ["CampaignRunner", "campaign_status", "render_campaign_report", "request_campaign_stop", "run_campaign_worker"]
