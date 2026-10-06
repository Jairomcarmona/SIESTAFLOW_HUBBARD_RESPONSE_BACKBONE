"""Assemble receipt-bound observations from the current campaign graph.

The assembler is stateless. Callers pass the live DAG, specs, records and
checkpoint for each operation so graph replacement cannot leave stale state.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from fractions import Fraction
from hashlib import sha256
from pathlib import Path
from typing import Any

from hubbardflow.domain.matrix_lr import ResponseObservation
from hubbardflow.domain.symmetry_reduction import PerturbationSpec
from hubbardflow.execution.campaign_files import (
    build_verified_dataset,
    campaign_relative_path,
    dataset_half_width,
    dataset_half_widths,
    source_record,
    verify_record_artifacts,
)
from hubbardflow.execution.dag_contract import NodeState
from hubbardflow.execution.generic_executor import NodeReceipt
from hubbardflow.execution.lr_dag import LRDag, LRDagNode, LRNodeKind
from hubbardflow.siesta_backend.occupation_precision import read_printed_occupation_precision
from hubbardflow.siesta_backend.parser_models import HubbardPopulationEvent
from hubbardflow.siesta_backend.reference_magnetic_evidence import reference_moments_from_fdf_and_output
from hubbardflow.siesta_backend.siesta542_screened_selection import select_converged_screened_event

__all__ = [
    "ObservationAssembler",
    "build_verified_dataset",
    "campaign_relative_path",
    "dataset_half_width",
    "dataset_half_widths",
    "source_record",
    "verify_record_artifacts",
]


class ObservationAssembler:
    """Build response observations from explicitly supplied live campaign state."""

    @staticmethod
    def event_occupations(
        output_content: str,
        event: HubbardPopulationEvent,
        sites: list[dict[str, Any]],
        *,
        minimum_decimal_places: int | None,
    ) -> list[float]:
        printed = read_printed_occupation_precision(
            output_content, event, minimum_decimal_places=minimum_decimal_places
        )
        expected = [int(site["atom_index"]) for site in sites]
        if len(printed) != len(event.atoms) or any(index not in printed for index in expected):
            raise ValueError("selected Hubbard event lacks one or more declared correlated atom indices")
        return [float(printed[index].total) for index in expected]

    @staticmethod
    def event_trace_half_widths(
        output_content: str,
        event: HubbardPopulationEvent,
        sites: list[dict[str, Any]],
        *,
        minimum_decimal_places: int | None,
    ) -> list[float] | None:
        """Enclose printing plus conversion/summation of Occupations tokens.

        Two printed spin tokens can be converted separately and then summed;
        half a ULP of the total alone does not enclose that error. Retain the
        numerical center and add its exact error against the lexical sum.
        """
        try:
            precision = read_printed_occupation_precision(
                output_content, event, minimum_decimal_places=minimum_decimal_places
            )
        except (ValueError, KeyError, IndexError):
            return None
        expected = [int(site["atom_index"]) for site in sites]
        if any(index not in precision for index in expected):
            return None
        widths = []
        for index in expected:
            measured = precision[index]
            if len(measured.certification_tokens) == 1:
                # A single token needs only the conversion cell already
                # enclosed by fitted_print_interval, preserving legacy widths.
                widths.append(float(measured.half_width))
                continue
            lexical_total = sum((Fraction(token) for token in measured.certification_tokens), Fraction(0))
            conversion_error = abs(Fraction.from_float(float(measured.total)) - lexical_total)
            width_exact = Fraction(measured.half_width_exact) + conversion_error
            width = float(width_exact)
            if Fraction.from_float(width) < width_exact:
                width = math.nextafter(width, math.inf)
            widths.append(width)
        return widths

    @staticmethod
    def projector_fingerprint(
        site_id: str,
        fdf_text: str,
        *,
        root: Path,
        config: Mapping[str, Any],
        input_sha256_by_path: Mapping[str, str],
    ) -> str:
        match = re.search(
            r"^\s*%block\s+DFTU\.Proj\s*$([\s\S]*?)^\s*%endblock(?:\s+DFTU\.Proj)?\s*$",
            fdf_text,
            re.IGNORECASE | re.MULTILINE,
        )
        if match is None:
            raise ValueError("reference FDF lost its DFTU.Proj block after validation")
        rows = [line.split("#", 1)[0].strip() for line in match.group(1).splitlines() if line.split("#", 1)[0].strip()]
        for offset in range(0, len(rows), 4):
            if rows[offset].split()[0] == site_id:
                potential = config["pseudopotentials"].get(site_id)
                if not potential:
                    raise ValueError(f"no PSML is declared for correlated site {site_id}")
                relative_path = campaign_relative_path(root, potential)
                digest = input_sha256_by_path.get(str(relative_path))
                if digest is None:
                    raise ValueError(f"PSML for correlated site {site_id} is absent from the verified input inventory")
                return sha256(("\n".join(rows[offset : offset + 4]) + "\0" + digest).encode()).hexdigest()
        raise ValueError(f"correlated site {site_id} has no DFTU.Proj record")

    @staticmethod
    def reference_node(dag: LRDag, scf_level_id: str = "base") -> LRDagNode:
        matches = [
            node for node in dag.nodes
            if node.kind is LRNodeKind.REFERENCE and (node.scf_level_id or "base") == scf_level_id
        ]
        if len(matches) != 1:
            raise ValueError(f"expected one shared reference node for SCF level {scf_level_id!r}")
        return matches[0]

    def verified_observations(
        self,
        *,
        root: Path,
        campaign: Mapping[str, Any],
        config: Mapping[str, Any],
        sites: list[dict[str, Any]],
        dag: LRDag,
        specs: Mapping[str, PerturbationSpec],
        records: Mapping[str, Any],
        checkpoint: Mapping[str, NodeReceipt],
        admitted: Any,
        input_sha256_by_path: Mapping[str, str],
        minimum_decimal_places: int | None,
        adaptive: bool,
        alpha_grid: list[float],
        scf_level_id: str = "base",
        site_indices: tuple[int, ...] | None = None,
    ) -> tuple[
        list[ResponseObservation],
        dict[float, str] | None,
        dict[str, Any],
        dict[tuple[int, float, str], list[float]],
        list[float] | None,
    ]:
        reference_node = self.reference_node(dag, scf_level_id) if adaptive else next(
            node for node in dag.nodes if node.kind is LRNodeKind.REFERENCE
        )
        reference_id = reference_node.node_id
        selected_grid = list(alpha_grid)
        reference = records.get(reference_id, {})
        if reference_id not in checkpoint or checkpoint[reference_id].state is not NodeState.VALIDATED:
            raise ValueError("validated reference receipt is missing")
        command = reference.get("command", {})
        reference_output = Path(command.get("stdout_path", ""))
        reference_fdf = Path(command.get("stdin_path", ""))
        if not reference_output.is_file() or not reference_fdf.is_file():
            raise ValueError("validated reference FDF/output artifacts are missing")
        reference_hashes = verify_record_artifacts(reference, reference_id)
        output_text = reference_output.read_text(encoding="utf-8", errors="replace")
        fdf_text = reference_fdf.read_text(encoding="utf-8", errors="replace")
        reference_event = select_converged_screened_event(output_text)
        reference_occ = self.event_occupations(
            output_text, reference_event, sites, minimum_decimal_places=minimum_decimal_places
        )
        reference_trace_half_widths = self.event_trace_half_widths(
            output_text, reference_event, sites, minimum_decimal_places=minimum_decimal_places
        )
        reference_moments, magnetic_parser = reference_moments_from_fdf_and_output(fdf_text, output_text)

        indexed: dict[tuple[int, float, str], tuple[LRDagNode, dict[str, Any]]] = {}
        nodes_by_id = {node.node_id: node for node in dag.nodes}
        for node_id, spec in specs.items():
            node = nodes_by_id[node_id]
            if (node.scf_level_id or "base") != scf_level_id:
                continue
            if not any(abs(float(spec.alpha_ev) - alpha) <= 1e-14 for alpha in selected_grid):
                continue
            receipt = checkpoint.get(node_id)
            record = records.get(node_id)
            if receipt is None or receipt.state is not NodeState.VALIDATED or not isinstance(record, dict):
                raise ValueError(f"validated receipt/evidence missing for {node_id}")
            indexed[(spec.site_index, float(spec.alpha_ev), spec.mode.value)] = (node, record)

        observations: list[ResponseObservation] = []
        trace_half_widths_electron: dict[tuple[int, float, str], list[float]] = {}
        tolerance = campaign.get("magnetic_moment_tolerance_muB")
        alpha_state: dict[float, str] | None = {} if tolerance is not None else None
        magnetic_rows: dict[str, Any] = {
            "reference_parser": magnetic_parser,
            "reference_moments_muB": reference_moments.tolist(),
            "by_alpha": {},
        }
        reference_dm_hash = reference_hashes["dm"]
        projector_fingerprints = {
            site_index: self.projector_fingerprint(
                site["site_id"],
                fdf_text,
                root=root,
                config=config,
                input_sha256_by_path=input_sha256_by_path,
            )
            for site_index, site in enumerate(sites)
        }
        for alpha in selected_grid:
            branch_differences: list[float] = []
            magnetic_per_site: dict[str, Any] = {}
            for site_index, site in enumerate(sites):
                if site_indices is not None and site_index not in site_indices:
                    continue
                try:
                    bare_node, bare_record = indexed[(site_index, alpha, "BARE")]
                    screened_node, screened_record = indexed[(site_index, alpha, "SCREENED")]
                except KeyError as exc:
                    raise ValueError(
                        f"incomplete mode/site/alpha pair for site {site['site_id']} at alpha={alpha}"
                    ) from exc
                bare_output = Path(bare_record["command"]["stdout_path"])
                screened_output = Path(screened_record["command"]["stdout_path"])
                bare_hashes = verify_record_artifacts(bare_record, bare_node.node_id)
                screened_hashes = verify_record_artifacts(screened_record, screened_node.node_id)
                bare_text = bare_output.read_text(encoding="utf-8", errors="replace")
                bare_event = admitted.factory.bare_profile.select_response(bare_text).response_event
                screened_text = screened_output.read_text(encoding="utf-8", errors="replace")
                screened_event = select_converged_screened_event(screened_text)
                bare_occ = self.event_occupations(
                    bare_text, bare_event, sites, minimum_decimal_places=minimum_decimal_places
                )
                screened_occ = self.event_occupations(
                    screened_text, screened_event, sites, minimum_decimal_places=minimum_decimal_places
                )
                bare_half_widths = self.event_trace_half_widths(
                    bare_text, bare_event, sites, minimum_decimal_places=minimum_decimal_places
                )
                screened_half_widths = self.event_trace_half_widths(
                    screened_text, screened_event, sites, minimum_decimal_places=minimum_decimal_places
                )
                if bare_half_widths is not None:
                    trace_half_widths_electron[(site_index, float(alpha), "bare")] = bare_half_widths
                if screened_half_widths is not None:
                    trace_half_widths_electron[(site_index, float(alpha), "screened")] = screened_half_widths
                screened_fdf = Path(screened_record["command"]["stdin_path"])
                moments, screened_magnetic_parser = reference_moments_from_fdf_and_output(
                    screened_fdf.read_text(encoding="utf-8", errors="replace"), screened_text
                )
                difference = float(abs(moments - reference_moments).max())
                branch_differences.append(difference)
                magnetic_per_site[str(site["site_id"])] = {
                    "moments_muB": moments.tolist(),
                    "max_abs_difference_from_reference_muB": difference,
                    "parser": screened_magnetic_parser,
                }
                observations.append(
                    ResponseObservation(
                        perturbation_site=site_index,
                        alpha=float(alpha),
                        site_labels=list(range(len(sites))),
                        occupations_ref=reference_occ,
                        occupations_bare=bare_occ,
                        occupations_screened=screened_occ,
                        parent_dm_sha256=reference_dm_hash,
                        projector_fingerprints=projector_fingerprints,
                        bare_fdf_sha256=bare_hashes["fdf"],
                        bare_out_sha256=bare_hashes["output"],
                        screened_fdf_sha256=screened_hashes["fdf"],
                        screened_out_sha256=screened_hashes["output"],
                    )
                )
            max_difference = max(branch_differences, default=float("inf"))
            state_label = None
            if tolerance is not None:
                state_label = (
                    "reference_branch"
                    if max_difference <= float(tolerance)
                    else f"changed_branch_at_alpha_{alpha}"
                )
                assert alpha_state is not None
                alpha_state[alpha] = state_label
            magnetic_rows["by_alpha"][str(alpha)] = {
                "state_label": state_label,
                "continuity_known": tolerance is not None,
                "tolerance_muB": tolerance,
                "max_abs_difference_from_reference_muB": max_difference,
                "per_perturbed_site": magnetic_per_site,
            }
        return observations, alpha_state, magnetic_rows, trace_half_widths_electron, reference_trace_half_widths

    def response_observation_dataset(
        self,
        *,
        root: Path,
        sites: list[dict[str, Any]],
        dag: LRDag,
        specs: Mapping[str, PerturbationSpec],
        records: Mapping[str, Any],
        checkpoint: Mapping[str, NodeReceipt],
        observations: list[ResponseObservation],
        scf_level_id: str = "base",
        trace_half_widths_electron: Mapping[tuple[int, float, str], list[float]] | None = None,
        reference_trace_half_widths_electron: list[float] | None = None,
        occupation_source: str = "matrix_trace_total",
    ) -> dict[str, Any]:
        reference_node = self.reference_node(dag, scf_level_id)
        reference_id = reference_node.node_id
        reference_receipt = checkpoint.get(reference_id)
        reference_record = records.get(reference_id)
        if reference_receipt is None or not isinstance(reference_record, Mapping):
            raise ValueError("validated reference evidence is unavailable for the report dataset")
        reference_source = source_record(
            root, reference_id, reference_record, reference_receipt, mode="REFERENCE_SCREENED"
        )
        sources_by_perturbation: dict[tuple[int, float], dict[str, Mapping[str, Any]]] = {}
        traceability_warnings: list[dict[str, str]] = []
        for observation in observations:
            if observation.parent_dm_sha256 != reference_source.get("dm_sha256"):
                traceability_warnings.append({
                    "reason_code": "PARENT_DM_DIGEST_MISMATCH",
                    "detail": f"column={observation.perturbation_site},alpha={observation.alpha}",
                })
        for node_id, spec in specs.items():
            node = next(node for node in dag.nodes if node.node_id == node_id)
            if (node.scf_level_id or "base") != scf_level_id:
                continue
            if not any(abs(float(spec.alpha_ev) - float(item.alpha)) <= 1e-14 for item in observations):
                continue
            receipt = checkpoint.get(node_id)
            record = records.get(node_id)
            if receipt is None or not isinstance(record, Mapping):
                raise ValueError(f"validated source evidence is unavailable for {node_id}")
            if record.get("evidence_digest") != receipt.evidence_digest:
                traceability_warnings.append({"reason_code": "NODE_EVIDENCE_DIGEST_MISMATCH", "detail": node_id})
            artifact_warnings = verify_record_artifacts(record, node_id).get("hash_warnings", [])
            traceability_warnings.extend(
                {"reason_code": item.split(":", 1)[0], "detail": item}
                for item in artifact_warnings
            )
            if record.get("reference_dm_sha256") != reference_source.get("dm_sha256"):
                traceability_warnings.append({
                    "reason_code": "PARENT_DM_IDENTITY_MISMATCH",
                    "detail": node_id,
                })
            key = (int(spec.site_index), float(spec.alpha_ev))
            sources_by_perturbation.setdefault(key, {})[spec.mode.value.casefold()] = source_record(
                root, node_id, record, receipt, mode=spec.mode.value
            )
        dataset = build_verified_dataset(
            observations,
            sites,
            reference_source=reference_source,
            response_sources=sources_by_perturbation,
            trace_half_widths_electron=trace_half_widths_electron,
            reference_trace_half_widths_electron=reference_trace_half_widths_electron,
            occupation_source=occupation_source,
            traceability_warnings=traceability_warnings,
        )
        return dataset
