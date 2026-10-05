"""Build the I.5 diagnostic from validated campaign node records."""

from __future__ import annotations

import re
from collections.abc import Collection, Mapping, Sequence
from pathlib import Path
from typing import Any, cast

from hubbardflow.domain.state_gate import (
    PointState,
    StateGatePoint,
    qualify_state_gate,
)
from hubbardflow.domain.state_gate_results import (
    CheckOutcome,
    StateCheck,
    StateCheckResult,
    StateGateMode,
    StateGateReason,
    StateGateResult,
    StateGateVerdict,
)
from hubbardflow.domain.symmetry_reduction import PerturbationSpec, ResponseMode
from hubbardflow.execution.campaign_store import atomic_json
from hubbardflow.execution.dag_contract import NodeState
from hubbardflow.execution.generic_executor import NodeReceipt
from hubbardflow.execution.lr_dag import LRDag, LRNodeKind
from hubbardflow.siesta_backend.parser_models import HubbardPopulationEvent
from hubbardflow.siesta_backend.point_state_evidence import build_point_state
from hubbardflow.siesta_backend.siesta542_screened_selection import select_converged_screened_event

_SYSTEM_LABEL = re.compile(r"^\s*SystemLabel\s+(\S+)", re.IGNORECASE | re.MULTILINE)
_SCHEMA_VERSION = "hubbardflow.i5_state_gate.v1"
_POLICY_ID = "i5-state-policy-v1"


def _event_for(
    output_text: str,
    mode: ResponseMode,
    bare_profile: Any,
) -> HubbardPopulationEvent:
    if mode is ResponseMode.BARE:
        return cast(HubbardPopulationEvent, bare_profile.select_response(output_text).response_event)
    return select_converged_screened_event(output_text)


def _point_state(record: Mapping[str, Any], mode: ResponseMode, bare_profile: Any) -> PointState:
    command = record["command"]
    if not isinstance(command, Mapping):
        raise TypeError("node command record is missing")
    stdout_path = Path(str(command["stdout_path"]))
    output_text = stdout_path.read_text(encoding="utf-8", errors="replace")
    event = _event_for(output_text, mode, bare_profile)
    cwd = Path(str(command["cwd"]))
    fdf_value = command.get("stdin_path")
    fdf_path = Path(str(fdf_value)) if fdf_value else cwd / str(record["artifact_spec"]["fdf"])
    fdf_text = fdf_path.read_text(encoding="utf-8", errors="replace")
    label_match = _SYSTEM_LABEL.search(fdf_text)
    eig_path = cwd / f"{label_match.group(1)}.EIG" if label_match else None
    eig_text = (
        eig_path.read_text(encoding="utf-8", errors="replace") if eig_path and eig_path.is_file() else None
    )
    return build_point_state(event, output_text, eig_text)


def _not_established(column_id: str, mode: StateGateMode, reason: StateGateReason) -> StateGateResult:
    smoothness = StateCheckResult(
        check=StateCheck.G3,
        outcome=CheckOutcome.NOT_ESTABLISHED,
        reasons=(StateGateReason.SMOOTHNESS_REQUIRES_SCF_LADDER,),
    )
    return StateGateResult(
        policy_id=_POLICY_ID,
        column_id=column_id,
        mode=mode,
        verdict=StateGateVerdict.NOT_ESTABLISHED,
        amplitudes=(),
        admissible_amplitudes_ev=(),
        excluded_amplitudes_ev=(),
        reasons=(reason,),
        smoothness=smoothness,
    )


def _response_node(
    dag: LRDag,
    specs: Mapping[str, PerturbationSpec],
    site_index: int,
    alpha_ev: float,
    mode: ResponseMode,
) -> str | None:
    for node in dag.nodes:
        spec = specs.get(node.node_id)
        if (
            node.kind is LRNodeKind.PERTURBATION
            and node.scf_level_id in (None, "base")
            and spec is not None
            and spec.site_index == site_index
            and spec.mode is mode
            and abs(float(spec.alpha_ev) - alpha_ev) <= 1e-14
        ):
            return node.node_id
    return None


def state_gate_mapping(
    *,
    dag: LRDag,
    specs: Mapping[str, PerturbationSpec],
    records: Mapping[str, Any],
    checkpoint: Mapping[str, NodeReceipt],
    sites: Sequence[Mapping[str, Any]],
    alpha_grid_ev: Sequence[float],
    bare_profile: Any,
    covered: bool,
    site_indices: Collection[int] | None = None,
) -> dict[str, object]:
    """Return one deterministic state-gate diagnostic for all column/mode pairs."""
    pairs: list[StateGateResult] = []
    reference_nodes = [node for node in dag.nodes if node.kind is LRNodeKind.REFERENCE]
    reference: PointState | None = None
    reference_error = StateGateReason.MISSING_REQUIRED_EVIDENCE
    if covered and len(reference_nodes) == 1:
        reference_node_id = reference_nodes[0].node_id
        record = records.get(reference_node_id)
        receipt = checkpoint.get(reference_node_id)
        if isinstance(record, Mapping) and receipt is not None and receipt.state is NodeState.VALIDATED:
            try:
                reference = _point_state(record, ResponseMode.SCREENED, bare_profile)
                reference_error = StateGateReason.MISSING_REQUIRED_EVIDENCE
            except Exception:  # noqa: BLE001 - malformed state evidence must be diagnostic only.
                reference = None
                reference_error = StateGateReason.INVALID_STATE_EVIDENCE

    for site_index, site in enumerate(sites):
        column_id = str(site["site_id"])
        for mode in (ResponseMode.BARE, ResponseMode.SCREENED):
            result_mode = StateGateMode(mode.value)
            if site_indices is not None and site_index not in site_indices:
                pairs.append(
                    _not_established(
                        column_id,
                        result_mode,
                        StateGateReason.RECONSTRUCTED_FROM_REPRESENTATIVE,
                    )
                )
                continue
            if not covered:
                pairs.append(_not_established(column_id, result_mode, StateGateReason.PATH_NOT_COVERED))
                continue
            if reference is None:
                pairs.append(_not_established(column_id, result_mode, reference_error))
                continue
            points: list[StateGatePoint] = []
            point_error = False
            for amplitude in sorted({abs(float(value)) for value in alpha_grid_ev}):
                for signed_alpha in (-amplitude, amplitude):
                    response_node_id = _response_node(dag, specs, site_index, signed_alpha, mode)
                    receipt = checkpoint.get(response_node_id) if response_node_id is not None else None
                    record = records.get(response_node_id) if response_node_id is not None else None
                    validated = receipt is not None and receipt.state is NodeState.VALIDATED
                    state: PointState | None = None
                    if validated and isinstance(record, Mapping):
                        try:
                            state = _point_state(record, mode, bare_profile)
                        except Exception:  # noqa: BLE001 - malformed state evidence must be diagnostic only.
                            state = None
                            point_error = True
                    elif validated:
                        point_error = True
                    points.append(StateGatePoint(signed_alpha, bool(validated), state))
            if point_error:
                pairs.append(_not_established(column_id, result_mode, StateGateReason.INVALID_STATE_EVIDENCE))
                continue
            try:
                pairs.append(qualify_state_gate(reference, column_id, result_mode, tuple(points)))
            except Exception:  # noqa: BLE001 - the diagnostic must never block matrix analysis.
                pairs.append(_not_established(column_id, result_mode, StateGateReason.INVALID_STATE_EVIDENCE))

    return {
        "schema_version": _SCHEMA_VERSION,
        "policy_id": _POLICY_ID,
        "pairs": [result.to_mapping() for result in pairs],
    }


def shadow_state_gate_passed(mapping: Mapping[str, object], site_ids: Collection[str]) -> bool:
    """Require complete pointwise I.5 evidence for every directly computed shadow column.

    The shadow comparison validates translation equivalence, so its gate requires
    measured point evidence including available band-gap evidence. The separate
    G3 smoothness diagnostic is deliberately excluded because it is not pointwise.
    """
    try:
        raw_pairs = mapping["pairs"]
        if not isinstance(raw_pairs, list) or not site_ids or len(set(site_ids)) != len(site_ids):
            return False
        indexed: dict[tuple[str, StateGateMode], StateGateResult] = {}
        for raw in raw_pairs:
            result = StateGateResult.from_mapping(raw)
            key = (result.column_id, result.mode)
            if key in indexed:
                return False
            indexed[key] = result
        for site_id in site_ids:
            for mode in StateGateMode:
                pair_result = indexed.get((site_id, mode))
                if (
                    pair_result is None
                    or pair_result.verdict is not StateGateVerdict.PASS
                    or not pair_result.amplitudes
                ):
                    return False
                for amplitude in pair_result.amplitudes:
                    for point in (amplitude.positive, amplitude.negative):
                        if (
                            point is None
                            or not point.checks
                            or any(
                                check.outcome
                                in {
                                    CheckOutcome.FAIL,
                                    CheckOutcome.NOT_AVAILABLE,
                                    CheckOutcome.NOT_ESTABLISHED,
                                }
                                for check in point.checks
                            )
                        ):
                            return False
        return True
    except (KeyError, TypeError, ValueError):
        return False


def failed_state_gate_mapping(
    sites: Sequence[Mapping[str, Any]], reason: StateGateReason
) -> dict[str, object]:
    """Represent an unexpected diagnostic error without blocking analysis."""
    pairs = [
        _not_established(str(site["site_id"]), StateGateMode(mode.value), reason)
        for site in sites
        for mode in (ResponseMode.BARE, ResponseMode.SCREENED)
    ]
    return {
        "schema_version": _SCHEMA_VERSION,
        "policy_id": _POLICY_ID,
        "pairs": [result.to_mapping() for result in pairs],
    }


def write_state_gate_file(path: Path, state_gate: Mapping[str, object]) -> None:
    """Persist the diagnostic separately from analysis and node evidence."""
    atomic_json(path, state_gate)
