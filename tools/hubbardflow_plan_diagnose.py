"""Read-only coverage diagnostic: report candidates without scheduling runs."""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, replace
from hashlib import sha256
from pathlib import Path
from typing import cast

from hubbardflow.domain.coverage import (
    CoverageQualification,
    CoverageReason,
    CoverageStrategy,
    UserCoveragePolicy,
    qualify_coverage,
)
from hubbardflow.domain.state_evidence import EvidenceStatus
from hubbardflow.domain.subspace_inventory import build_inventory
from hubbardflow.domain.symmetry_operation_models import bind_symmetry_model, coverage_policy_v1
from hubbardflow.execution.product_paths import protect_product_destination
from hubbardflow.siesta_backend.coverage_reference import build_coverage_reference_evidence
from hubbardflow.siesta_backend.fdf_model import FdfModelError, parse_effective_fdf, species_identity


@dataclass(frozen=True)
class DiagnosticSite:
    site_id: str
    atom_index: int
    species_label: str
    n: int
    l: int
    identity_digest: str

    def to_mapping(self) -> dict[str, object]:
        return asdict(self)

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> DiagnosticSite:
        return cls(
            cast(str, value["site_id"]),
            cast(int, value["atom_index"]),
            cast(str, value["species_label"]),
            cast(int, value["n"]),
            cast(int, value["l"]),
            cast(str, value["identity_digest"]),
        )


@dataclass(frozen=True)
class CoverageDiagnostic:
    input_file_sha256: str
    output_sha256: str
    inventory: tuple[DiagnosticSite, ...]
    qualification: CoverageQualification | None
    error: str | None

    def to_mapping(self) -> dict[str, object]:
        return {
            "schema": "hubbardflow.coverage_diagnostic.v1",
            "diagnostic_only": True,
            "input_file_sha256": self.input_file_sha256,
            "output_sha256": self.output_sha256,
            "inventory": [site.to_mapping() for site in self.inventory],
            "qualification": None if self.qualification is None else self.qualification.to_mapping(),
            "qualification_digest": None if self.qualification is None else self.qualification.digest,
            "error": self.error,
            "reference_status": EvidenceStatus.REFERENCE_NOT_ADMISSIBLE.value
            if self.qualification is None
            else self.qualification.reference.status.value,
            "strategy": CoverageStrategy.ALL_SUBSPACES.value
            if self.qualification is None
            else self.qualification.strategy.value,
            "reasons": [CoverageReason.UNSUPPORTED_SYNTAX.value]
            if self.qualification is None
            else [r.value for r in self.qualification.reasons],
            "would_reduce_to": len(self.inventory)
            if self.qualification is None
            else self.qualification.would_reduce_to,
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> CoverageDiagnostic:
        if (
            value.get("schema") != "hubbardflow.coverage_diagnostic.v1"
            or value.get("diagnostic_only") is not True
        ):
            raise ValueError("unsupported diagnostic schema or non-diagnostic report")
        raw = value["qualification"]
        return cls(
            cast(str, value["input_file_sha256"]),
            cast(str, value["output_sha256"]),
            tuple(
                DiagnosticSite.from_mapping(s)
                for s in cast(Sequence[Mapping[str, object]], value["inventory"])
            ),
            None if raw is None else CoverageQualification.from_mapping(cast(Mapping[str, object], raw)),
            cast(str | None, value["error"]),
        )

    def json_text(self) -> str:
        return json.dumps(self.to_mapping(), indent=2, sort_keys=True, allow_nan=False) + "\n"

    def markdown_text(self) -> str:
        lines = [
            "# Coverage diagnostic",
            "",
            "Diagnostic only; no runs are omitted or scheduled.",
            "",
            f"Input SHA256: `{self.input_file_sha256}`",
            f"Output SHA256: `{self.output_sha256}`",
            "",
            "| Site | Atom index | Species | n | l | Identity digest |",
            "|---|---:|---|---:|---:|---|",
        ]
        for s in self.inventory:
            lines.append(
                f"| {s.site_id} | {s.atom_index} | {s.species_label} | {s.n} | {s.l} | {s.identity_digest} |"
            )
        payload = self.to_mapping()
        lines += [
            "",
            f"Reference: {payload['reference_status']}",
            f"Strategy: {payload['strategy']}",
            f"would_reduce_to {payload['would_reduce_to']} representatives",
            "",
            "Reasons: " + ", ".join(str(r) for r in payload["reasons"])
            if isinstance(payload["reasons"], list)
            else "",
        ]
        if self.error:
            lines += ["", self.error]
        if self.qualification is not None:
            q = self.qualification
            lines += [
                "",
                f"Qualification digest: `{q.digest}`",
                f"Input/output consistent: {q.reference.input_output_consistent}",
                f"Non-polarized verified: {q.reference.nonpolarized_verified}",
                f"Perturbation detected: {q.reference.perturbation_detected}",
                f"Parent DM SHA256: {q.reference.parent_dm_sha256 or 'NOT_ESTABLISHED'}",
                "",
                "| Members | Representative | Shadow | Status | Reasons |",
                "|---|---|---|---|---|",
            ]
            for c in q.classes:
                lines.append(
                    f"| {', '.join(c.members)} | {c.representative} | {c.shadow or 'none'} | {c.status.value} | {', '.join(r.value for r in c.reasons)} |"
                )
            lines += [
                "",
                "| Operation | eps | Exactness | F1–F8 (status, measured, bands) | Accepted candidate |",
                "|---:|---:|---|---|---|",
            ]
            for i, op in enumerate(q.operations):
                conditions = "; ".join(
                    f"{c.condition}={c.status.value} ({c.measured_value}; {c.tau_eq}, {c.tau_neq}); pairs={c.pair_measurements}"
                    for c in op.conditions
                )
                lines.append(
                    f"| {i} | {op.operation.eps} | {op.operation.exactness_class.value} | {conditions} | {op.accepted} |"
                )
            lines += ["", "Search reasons: " + ", ".join(r.value for r in q.search_reasons)]
        return "\n".join(lines) + "\n"


def diagnose(
    fdf: Path,
    reference_output: Path,
    identity_dirs: tuple[Path, ...],
    user_policy: UserCoveragePolicy,
    *,
    allow_spin_flip: bool,
    allow_rotations: bool,
) -> CoverageDiagnostic:
    """Bind one reference pair; unknown syntax yields explicit diagnostic fallback."""
    input_digest = sha256(fdf.read_bytes()).hexdigest()
    output_digest = sha256(reference_output.read_bytes()).hexdigest()
    try:
        model = parse_effective_fdf(fdf)
    except FdfModelError as exc:
        return CoverageDiagnostic(input_digest, output_digest, (), None, f"{exc.code.value}: {exc}")
    identities = species_identity(model, identity_dirs)
    inventory = build_inventory(model, identities)
    state = build_coverage_reference_evidence(fdf, reference_output, inventory.subspaces)
    policy = replace(coverage_policy_v1(), allow_spin_flip=allow_spin_flip, allow_rotations=allow_rotations)
    qualification = qualify_coverage(
        inventory, state, bind_symmetry_model(model, identities), policy, user_policy
    )
    sites = tuple(
        DiagnosticSite(
            s.site_id, s.atom_index, s.species_label, s.dftu_record.n, s.dftu_record.l, s.identity_digest
        )
        for s in inventory.subspaces
    )
    return CoverageDiagnostic(input_digest, output_digest, sites, qualification, None)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fdf", type=Path)
    parser.add_argument("--reference-output", type=Path, required=True)
    parser.add_argument("--identity-dir", type=Path, action="append")
    parser.add_argument("--coverage", choices=("DISABLED", "DIAGNOSTIC"), default="DIAGNOSTIC")
    parser.add_argument("--allow-spin-flip", action="store_true")
    parser.add_argument("--allow-rotations", action="store_true")
    parser.add_argument("--json", type=Path, required=True)
    parser.add_argument("--markdown", type=Path, required=True)
    args = parser.parse_args()
    sources = {args.fdf.resolve(), args.reference_output.resolve()}
    destinations = {args.json.resolve(), args.markdown.resolve()}
    if len(destinations) != 2 or sources & destinations:
        parser.error("diagnostic destinations must be distinct and must not overwrite either source")
    for destination in sorted(destinations, key=str):
        protect_product_destination(destination.parent)
        protect_product_destination(destination)
    report = diagnose(
        args.fdf,
        args.reference_output,
        tuple(args.identity_dir or (args.fdf.parent,)),
        UserCoveragePolicy("coverage-user-policy-v1", args.coverage != "DISABLED", ()),
        allow_spin_flip=args.allow_spin_flip,
        allow_rotations=args.allow_rotations,
    )
    with args.json.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(report.json_text())
    with args.markdown.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(report.markdown_text())


if __name__ == "__main__":
    main()
