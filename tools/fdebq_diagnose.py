"""Read-only FD-EBQ diagnostic sidecar for existing linear-response analyses."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tomllib
from collections.abc import Mapping, Sequence
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import cast

from hubbardflow.domain.response_budget_models import (
    ElementBudgetReport,
    ElementSeries,
    NoiseModel,
    PointObservation,
    ResponseBudgetError,
)
from hubbardflow.domain.response_error_budget import element_report, reciprocity
from hubbardflow.domain.response_protocol import (
    EstimatorKind,
    PerturbationStrategy,
    ResolvedResponseProtocol,
    ResponseProtocolError,
    protocol_from_fixed_grid,
)
from hubbardflow.domain.symmetry_reduction import ResponseMode
from hubbardflow.domain.validation import ValidationError, require_finite, require_positive_finite

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPO_ROOT
OUTPUT_SCHEMA = "hubbardflow.fdebq_diagnostic.v1"
SCOPE = "diagnostic, print-quantization bounds only; SCF component not assessed"
OUTPUT_JSON = "fdebq_diagnostic.v1.json"
OUTPUT_MARKDOWN = "FDEBQ_DIAGNOSTIC.md"


class DiagnosticToolError(ValueError):
    """Input or output paths cannot safely produce a deterministic sidecar."""


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or any(not isinstance(key, str) for key in value):
        raise DiagnosticToolError(f"{label} must be a JSON object with string keys")
    return cast(Mapping[str, object], value)


def _sequence(value: object, label: str) -> Sequence[object]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise DiagnosticToolError(f"{label} must be a JSON array")
    return value


def _string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise DiagnosticToolError(f"{label} must be a nonempty string")
    return value


def _number(value: object, label: str) -> float:
    try:
        return require_finite(value, label)
    except ValidationError as exc:
        raise DiagnosticToolError(str(exc)) from exc


def _path_is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _reject_unsafe_output(input_path: Path, output_dir: Path) -> None:
    """Refuse protected repository locations and every location beside the input."""
    repo_root = REPO_ROOT.resolve()
    protected = (
        repo_root / "results",
        repo_root / "benchmarks",
        repo_root / "validation_observables_v6",
        repo_root / "FEO_SCF_DIAGNOSTIC_EXPORT_20261001",
    )
    for protected_root in protected:
        if _path_is_within(output_dir, protected_root.resolve()):
            raise DiagnosticToolError(f"--out is inside protected directory {protected_root.name}/")

    try:
        relative_output = output_dir.relative_to(repo_root)
    except ValueError:
        relative_output = None
    if relative_output is not None:
        parts = relative_output.parts
        if len(parts) >= 3 and parts[0] == "campaigns" and parts[2] == "results":
            raise DiagnosticToolError("--out is inside a campaigns/*/results/ directory")

    input_parent = input_path.parent
    if (
        _path_is_within(input_path, output_dir)
        or _path_is_within(output_dir, input_parent)
        or _path_is_within(input_parent, output_dir)
    ):
        raise DiagnosticToolError("--out must be separate from the input file and its containing directory")

    if output_dir.exists():
        if not output_dir.is_dir():
            raise DiagnosticToolError("--out exists and is not a directory")
        try:
            next(output_dir.iterdir())
        except StopIteration:
            return
        raise DiagnosticToolError("--out exists and is not empty")


def _package_version() -> str:
    try:
        return version("hubbardflow")
    except PackageNotFoundError:
        project_file = SOURCE_ROOT / "pyproject.toml"
        try:
            with project_file.open("rb") as handle:
                project = tomllib.load(handle)
            return _string(_mapping(project.get("project"), "pyproject project").get("version"), "version")
        except (OSError, tomllib.TOMLDecodeError, DiagnosticToolError) as exc:
            raise DiagnosticToolError("could not determine the HubbardFlow package version") from exc


def _git_commit() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    commit = result.stdout.strip()
    return commit or None


def _estimator_policy(analysis: Mapping[str, object]) -> tuple[EstimatorKind, int | None]:
    policy = _mapping(analysis.get("estimator_policy"), "estimator_policy")
    method = _string(policy.get("estimator"), "estimator_policy.estimator")
    if method == "auto":
        selected = _mapping(analysis.get("selected_estimator"), "selected_estimator")
        method = _string(selected.get("method"), "selected_estimator.method")
    if method == "polynomial":
        raw_degree = policy.get("polynomial_degree")
        if isinstance(raw_degree, bool) or not isinstance(raw_degree, int):
            raise DiagnosticToolError("estimator_policy.polynomial_degree must be an integer")
        return EstimatorKind.POLYNOMIAL_LSQ, raw_degree
    if method == "linear":
        return EstimatorKind.LINEAR_LSQ, None
    raise DiagnosticToolError(f"unsupported estimator policy {method!r}")


def _protocol_and_series(
    analysis: Mapping[str, object],
) -> tuple[ResolvedResponseProtocol, list[ElementSeries]]:
    schema_version = _string(analysis.get("schema_version"), "schema_version")
    if schema_version not in {"siestaflow.lr_u_analysis.v3", "hubbardflow.lr_u_analysis.v3"}:
        raise DiagnosticToolError("analysis input must use the lr_u_analysis.v3 schema")
    raw_dataset = _mapping(analysis.get("response_observation_dataset"), "response_observation_dataset")
    raw_grid = _sequence(analysis.get("alpha_grid_eV"), "alpha_grid_eV")
    alpha_grid = tuple(_number(value, "alpha_grid_eV entry") for value in raw_grid)
    raw_rows = _sequence(raw_dataset.get("rows"), "response_observation_dataset.rows")
    if not raw_rows:
        raise DiagnosticToolError("response_observation_dataset.rows must not be empty")
    reference_source = _mapping(raw_dataset.get("reference_source"), "reference_source")
    reference_node_id = _string(reference_source.get("node_id"), "reference_source.node_id")
    observable_id = _string(raw_dataset.get("occupation_source"), "occupation_source")
    matrix_sites_raw = _mapping(
        raw_dataset.get("matrix_index_to_site_id"), "response_observation_dataset.matrix_index_to_site_id"
    )
    matrix_sites = tuple(
        _string(matrix_sites_raw[key], f"matrix_index_to_site_id[{key}]") for key in sorted(matrix_sites_raw)
    )
    if not matrix_sites or len(set(matrix_sites)) != len(matrix_sites):
        raise DiagnosticToolError("matrix_index_to_site_id must declare distinct site identifiers")
    estimator_kind, polynomial_degree = _estimator_policy(analysis)

    grouped: dict[tuple[str, ResponseMode, str], dict[float, tuple[float, float, float, float]]] = {}
    perturbed_sites: set[str] = set()
    for row_index, raw_row in enumerate(raw_rows):
        row_label = f"response_observation_dataset.rows[{row_index}]"
        row = _mapping(raw_row, row_label)
        alpha = _number(row.get("alpha_eV"), f"{row_label}.alpha_eV")
        perturbed_site = _string(row.get("perturbed_site_id"), f"{row_label}.perturbed_site_id")
        perturbed_sites.add(perturbed_site)
        observed_sites = _sequence(row.get("observed_sites"), f"{row_label}.observed_sites")
        for observed_index, raw_observed in enumerate(observed_sites):
            observed_label = f"{row_label}.observed_sites[{observed_index}]"
            observed = _mapping(raw_observed, observed_label)
            observed_site = _string(observed.get("observed_site_id"), f"{observed_label}.observed_site_id")
            occupations = _mapping(
                observed.get("occupations_electron"), f"{observed_label}.occupations_electron"
            )
            widths = _mapping(
                observed.get("occupation_half_widths_electron"),
                f"{observed_label}.occupation_half_widths_electron",
            )
            reference_occupation = _number(occupations.get("reference"), f"{observed_label}.reference")
            reference_width = _number(widths.get("reference"), f"{observed_label}.reference half width")
            if reference_width < 0.0:
                raise DiagnosticToolError(f"{observed_label}.reference half width must be nonnegative")
            for mode, key in ((ResponseMode.BARE, "bare"), (ResponseMode.SCREENED, "screened")):
                occupation = _number(occupations.get(key), f"{observed_label}.{key} occupation")
                half_width = _number(widths.get(key), f"{observed_label}.{key} half width")
                if half_width < 0.0:
                    raise DiagnosticToolError(f"{observed_label}.{key} half width must be nonnegative")
                series_key = (perturbed_site, mode, observed_site)
                point_values = grouped.setdefault(series_key, {})
                if alpha in point_values:
                    raise DiagnosticToolError(f"duplicate alpha {alpha} for response series {series_key}")
                point_values[alpha] = (occupation, half_width, reference_occupation, reference_width)

    if not perturbed_sites:
        raise DiagnosticToolError("response dataset has no perturbed sites")
    if not perturbed_sites.issubset(matrix_sites):
        raise DiagnosticToolError("perturbed site identifiers must appear in matrix_index_to_site_id")
    source_scf_level = raw_dataset.get("scf_level_id", analysis.get("scf_level_id"))
    scf_level_id = (
        _string(source_scf_level, "scf_level_id")
        if source_scf_level is not None
        else "not-recorded-in-analysis-v3"
    )
    protocol = protocol_from_fixed_grid(
        tuple(sorted(perturbed_sites)),
        alpha_grid,
        estimator=estimator_kind,
        polynomial_degree=polynomial_degree,
        scf_level_id=scf_level_id,
        reference_node_id=reference_node_id,
        observable_id=observable_id,
        strategy=PerturbationStrategy.FIXED_PROTOCOL_GRID,
        protocol_version="fdebq-diagnostic-sidecar-v1",
    )

    expected_signed = set(alpha_grid)
    series_results: list[ElementSeries] = []
    for series_key in sorted(grouped, key=lambda item: (item[0], item[1].value, item[2])):
        values_by_alpha = grouped[series_key]
        if set(values_by_alpha) != expected_signed:
            raise DiagnosticToolError(
                f"response series {series_key} does not contain the declared alpha grid"
            )
        references = {(item[2], item[3]) for item in values_by_alpha.values()}
        if len(references) != 1:
            raise DiagnosticToolError(f"response series {series_key} has inconsistent reference observations")
        reference_occupation, reference_width = next(iter(references))
        points = tuple(
            PointObservation(alpha, values_by_alpha[alpha][0], values_by_alpha[alpha][1])
            for alpha in sorted(values_by_alpha)
        )
        series_results.append(
            ElementSeries(
                site_perturbed=series_key[0],
                mode=series_key[1],
                site_observed=series_key[2],
                reference_occupation_e=reference_occupation,
                reference_half_width_e=reference_width,
                points=points,
            )
        )
    # Ensure every generated column has a matching observed series for each site pair.
    expected_series = {
        (perturbed, mode, observed)
        for perturbed in perturbed_sites
        for mode in (ResponseMode.BARE, ResponseMode.SCREENED)
        for observed in matrix_sites
    }
    if set(grouped) != expected_series:
        raise DiagnosticToolError("response dataset is missing a declared site/mode/observable series")
    return protocol, series_results


def _report_mapping(report: ElementBudgetReport) -> dict[str, object]:
    """Expose diagnostic evidence without later qualification terminology."""
    record = report.to_mapping()
    return {key: value for key, value in record.items() if key not in {"qualification_cap", "reasons"}} | {
        "reasons": record.get("reasons", [])
    }


def _render_markdown(payload: Mapping[str, object]) -> str:
    series = cast(Sequence[object], payload["series"])
    reciprocity_items = cast(Sequence[object], payload["reciprocity"])
    return "\n".join(
        (
            "# FD-EBQ diagnostic",
            "",
            SCOPE,
            "",
            f"- Element series: {len(series)}",
            f"- Reciprocity pairs reported: {len(reciprocity_items)}",
            f"- Protocol digest: `{payload['protocol_digest']}`",
            f"- Input SHA-256: `{payload['input_sha256']}`",
            "",
        )
    )


def _diagnostic_payload(
    input_bytes: bytes, analysis: Mapping[str, object], kappa: float
) -> dict[str, object]:
    try:
        factor = require_positive_finite(kappa, "kappa")
    except ValidationError as exc:
        raise DiagnosticToolError(str(exc)) from exc
    protocol, series = _protocol_and_series(analysis)
    noise = NoiseModel()
    reports = [
        element_report(
            item,
            noise,
            protocol_estimator=next(
                column.estimator
                for column in protocol.columns
                if column.site_id == item.site_perturbed and column.mode is item.mode
            ),
            kappa=factor,
        )
        for item in series
    ]
    reciprocal = reciprocity(reports, kappa=factor)
    return {
        "schema": OUTPUT_SCHEMA,
        "scope": SCOPE,
        "input_sha256": hashlib.sha256(input_bytes).hexdigest(),
        "protocol_digest": protocol.digest(),
        "protocol": protocol.to_mapping(),
        "kappa": factor,
        "package_version": _package_version(),
        "git_commit": _git_commit(),
        "series": [_report_mapping(report) for report in reports],
        "reciprocity": [item.to_mapping() for item in reciprocal],
    }


def run_diagnostic(input_path: Path, output_dir: Path, kappa: float) -> None:
    """Write deterministic sidecar files after all read-only and safety checks pass."""
    try:
        resolved_input = input_path.resolve(strict=True)
    except OSError as exc:
        raise DiagnosticToolError(f"input file cannot be resolved: {input_path}") from exc
    if not resolved_input.is_file():
        raise DiagnosticToolError("input path must be a file")
    try:
        resolved_output = output_dir.resolve(strict=False)
    except (OSError, RuntimeError) as exc:
        raise DiagnosticToolError(f"output directory cannot be resolved: {output_dir}") from exc
    _reject_unsafe_output(resolved_input, resolved_output)
    try:
        input_bytes = resolved_input.read_bytes()
        analysis = _mapping(json.loads(input_bytes), "analysis input")
    except (OSError, json.JSONDecodeError) as exc:
        raise DiagnosticToolError(f"could not read analysis JSON: {resolved_input}") from exc
    try:
        payload = _diagnostic_payload(input_bytes, analysis, kappa)
    except (ResponseBudgetError, ResponseProtocolError) as exc:
        raise DiagnosticToolError(str(exc)) from exc
    json_text = json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    markdown_text = _render_markdown(payload)
    resolved_output.mkdir(parents=True, exist_ok=True)
    (resolved_output / OUTPUT_JSON).write_text(json_text, encoding="utf-8", newline="\n")
    (resolved_output / OUTPUT_MARKDOWN).write_text(markdown_text, encoding="utf-8", newline="\n")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write an FD-EBQ diagnostic sidecar for an analysis JSON.")
    parser.add_argument("analysis", type=Path, help="path to lr_u_analysis.v3.json")
    parser.add_argument(
        "--out", required=True, type=Path, help="empty output directory outside protected data"
    )
    parser.add_argument("--kappa", required=True, type=float, help="positive reciprocity factor")
    args = parser.parse_args(argv)
    try:
        run_diagnostic(args.analysis, args.out, args.kappa)
    except (DiagnosticToolError, OSError, ResponseBudgetError, ResponseProtocolError) as exc:
        print(f"fdebq_diagnose: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
