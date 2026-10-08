"""Formatting primitives shared by the plain-text HubbardFlow report."""

from __future__ import annotations

import math
import textwrap
import unicodedata
from collections.abc import Mapping
from pathlib import PurePosixPath
from typing import Any

WIDTH = 80


def ascii_text(value: Any) -> str:
    """Convert arbitrary report evidence to printable ASCII without losing it silently."""
    decomposed = unicodedata.normalize("NFKD", str(value))
    return decomposed.encode("ascii", errors="replace").decode("ascii")


def report_value(value: Any) -> str:
    """Format a single saved value, preserving absence as NOT_ASSESSED."""
    if value is None:
        return "NOT_ASSESSED"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, float):
        return f"{value:.8g}" if math.isfinite(value) else "NOT_ASSESSED"
    return ascii_text(value)


def section_header(title: str) -> list[str]:
    """Use the title length as the shared underline rule for report sections."""
    return ["", title, "-" * len(title)]


def fixed_decimal(value: Any) -> str:
    """Render matrix values with one fixed decimal precision and field width."""
    if value is None:
        return "NOT_ASSESSED".rjust(14)
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "NOT_ASSESSED".rjust(14)
    if not math.isfinite(number):
        return "NOT_ASSESSED".rjust(14)
    return f"{number:14.8f}"


def _path_chunks(path: str, width: int) -> list[str]:
    """Split a POSIX path only between complete slash-delimited components."""
    chunks: list[str] = []
    current = ""
    components = path.split("/")
    for index, component in enumerate(components):
        part = component + ("/" if index < len(components) - 1 else "")
        if len(current) + len(part) <= width:
            current += part
            continue
        if current:
            chunks.append(current)
        current = part
    if current or not chunks:
        chunks.append(current)
    return chunks


def path_lines(path: str) -> list[str]:
    """Render a run folder on indented lines, wrapping only at path separators."""
    path = path.replace("\\", "/")
    prefix = "    PATH: "
    continuation = "          "
    chunks = _path_chunks(path, WIDTH - len(prefix))
    if chunks and len(chunks[0]) > WIDTH - len(prefix):
        # A long single component can still fit if the label is omitted for that row.
        chunks = _path_chunks(path, WIDTH - len(continuation))
        prefix = continuation
    lines = [prefix + chunks[0]]
    lines.extend(continuation + chunk for chunk in chunks[1:])
    return lines


def report_list(value: Any) -> str:
    if not isinstance(value, (list, tuple)) or not value:
        return "NOT_ASSESSED"
    return ", ".join(report_value(item) for item in value)


def mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def site_names(analysis: Mapping[str, Any], dataset: Mapping[str, Any]) -> dict[int, str]:
    result: dict[int, str] = {}
    rows = dataset.get("site_index_map")
    if isinstance(rows, list):
        for row in rows:
            if isinstance(row, Mapping) and isinstance(row.get("index"), int):
                result[int(row["index"])] = ascii_text(row.get("site_id", row["index"]))
    if not result:
        sites = mapping(analysis.get("campaign")).get("sites")
        if isinstance(sites, list):
            for index, item in enumerate(sites):
                if isinstance(item, Mapping):
                    result[int(item.get("index", index))] = ascii_text(item.get("site_id", index))
    return result


def alpha_key(value: Any) -> str:
    try:
        return format(float(value), ".12g")
    except (TypeError, ValueError):
        return ""


def source_records(provenance: Mapping[str, Any]) -> dict[tuple[str, str, str, int], Mapping[str, Any]]:
    indexed: dict[tuple[str, str, str, int], Mapping[str, Any]] = {}
    rows = provenance.get("records")
    if not isinstance(rows, list):
        return indexed
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        key = (
            str(row.get("mode", "")),
            str(row.get("perturbed_site_id") or ""),
            alpha_key(row.get("alpha_eV")),
            int(row.get("observed_site_index", -1)),
        )
        indexed[key] = row
    return indexed


def run_inventory(dataset: Mapping[str, Any]) -> list[tuple[str, str, str, str, str]]:
    result: list[tuple[str, str, str, str, str]] = []
    reference = dataset.get("reference_source")
    if isinstance(reference, Mapping):
        path = str(reference.get("out_path") or "NOT_ASSESSED").replace("\\", "/")
        result.append(
            (
                str(reference.get("node_id") or "reference"),
                PurePosixPath(path).parent.as_posix(),
                "REFERENCE_SCREENED",
                "NOT_APPLICABLE",
                str(reference.get("state") or "NOT_ASSESSED"),
            )
        )
    rows = dataset.get("rows")
    if not isinstance(rows, list):
        return result
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        sources = mapping(row.get("sources"))
        for key, mode in (("bare", "BARE"), ("screened", "SCREENED")):
            source = sources.get(key)
            if not isinstance(source, Mapping):
                continue
            path = str(source.get("out_path") or "NOT_ASSESSED").replace("\\", "/")
            result.append(
                (
                    str(source.get("node_id") or "NOT_ASSESSED"),
                    PurePosixPath(path).parent.as_posix(),
                    mode,
                    report_value(row.get("alpha_eV")),
                    str(source.get("state") or "NOT_ASSESSED"),
                )
            )
    return result


def matrix_lines(title: str, matrix: Any, names: Mapping[int, str]) -> list[str]:
    lines = [title]
    if not isinstance(matrix, list) or not matrix:
        return [*lines, "  NOT_ASSESSED: matrix is absent from the saved analysis."]
    size = len(matrix)
    block_size = 4
    for start in range(0, size, block_size):
        stop = min(size, start + block_size)
        labels = ", ".join(f"{index}={names.get(index, str(index))}" for index in range(start, stop))
        lines.append(f"  COLUMNS {start}-{stop - 1}: {labels}")
        lines.append("  ROW  |" + "".join(f"{index:>14}" for index in range(start, stop)))
        for row_index, row in enumerate(matrix):
            values = row if isinstance(row, list) else []
            rendered = []
            for column in range(start, stop):
                value = values[column] if column < len(values) else None
                rendered.append(fixed_decimal(value))
            lines.append(f"  {row_index:>3}  |" + "".join(rendered))
    return lines


def wrap_lines(lines: list[str]) -> list[str]:
    wrapped: list[str] = []
    for raw in lines:
        line = ascii_text(raw)
        if len(line) <= WIDTH:
            wrapped.append(line)
            continue
        indent = len(line) - len(line.lstrip(" "))
        wrapped_lines = textwrap.wrap(
            line,
            width=WIDTH,
            subsequent_indent=" " * indent,
            break_long_words=False,
            break_on_hyphens=False,
        ) or [""]
        for wrapped_line in wrapped_lines:
            if len(wrapped_line) <= WIDTH:
                wrapped.append(wrapped_line)
                continue
            long_path = next(
                (
                    token
                    for token in wrapped_line.split()
                    if token.count("/") + token.count("\\") >= 2 and len(token) > WIDTH - indent
                ),
                None,
            )
            if long_path is None:
                wrapped.append(wrapped_line)
                continue
            before, _, after = wrapped_line.partition(long_path)
            if before.strip():
                wrapped.append(before.rstrip())
            continuation = " " * indent
            normalized_path = long_path.replace("\\", "/")
            wrapped.extend(continuation + chunk for chunk in _path_chunks(normalized_path, WIDTH - indent))
            if after.strip():
                wrapped.extend(
                    textwrap.wrap(
                        after.strip(),
                        width=WIDTH,
                        subsequent_indent=continuation,
                        break_long_words=False,
                        break_on_hyphens=False,
                    )
                )
    return wrapped


def quality_check_lines(source: Mapping[str, Any], state_gate: Mapping[str, Any]) -> list[str]:
    """Render saved quality evidence without creating acceptance thresholds."""
    lines = section_header("QUALITY CHECKS")
    quality = mapping(source.get("quality_checks"))
    for label in (
        "linearity",
        "chi0_rank_condition",
        "chi_rank_condition",
        "common_parent_state",
        "charge_conservation",
        "intra_orbit_symmetry_dispersion",
        "scf_convergence",
        "magnetic_moment_consistency",
    ):
        item = mapping(quality.get(label))
        value = item.get("value")
        if isinstance(value, Mapping):
            value_text = ", ".join(f"{key}={report_value(entry)}" for key, entry in sorted(value.items()))
        else:
            value_text = report_value(value)
        units = f" {item.get('units')}" if item.get("units") else ""
        lines.append(f"  {label}: value={value_text}{units}; status={report_value(item.get('status'))}")
    pairs = state_gate.get("pairs")
    if isinstance(pairs, list) and pairs:
        verdicts: dict[str, int] = {}
        for pair in pairs:
            if isinstance(pair, Mapping):
                verdict = str(pair.get("verdict") or "NOT_ASSESSED")
                verdicts[verdict] = verdicts.get(verdict, 0) + 1
        gate_summary = ", ".join(f"{key}={count}" for key, count in sorted(verdicts.items()))
        lines.append(f"  Pointwise state gate: {gate_summary}; RECORD_ONLY")
    else:
        lines.append("  Pointwise state gate: NOT_ASSESSED")
    return lines


def dftu_block(context: Mapping[str, Any], analysis: Mapping[str, Any]) -> list[str]:
    """Build a pasteable DFTU.Proj block only when every value is evidenced."""
    projector = mapping(context.get("projector"))
    records = projector.get("records")
    u_by_site = mapping(mapping(analysis.get("primary")).get("U_by_site_eV"))
    sites = mapping(analysis.get("response_observation_dataset")).get("site_index_map")
    site_ids: dict[str, int] = {}
    if isinstance(sites, list):
        for row in sites:
            if isinstance(row, Mapping) and row.get("site_id") is not None:
                site_ids[str(row["site_id"])] = int(row.get("index", -1))
    if not isinstance(records, list) or not records:
        return ["NOT_ASSESSED: projector records are absent."]
    rendered_records: list[str] = []
    for record in records:
        if not isinstance(record, Mapping):
            continue
        label = str(record.get("label") or "")
        index = site_ids.get(label)
        u_value = u_by_site.get(str(index)) if index is not None else None
        canonical = record.get("canonical_text")
        rows = canonical.splitlines() if isinstance(canonical, str) else []
        if u_value is None or len(rows) != 4:
            return ["NOT_ASSESSED: a complete site-to-projector mapping is unavailable."]
        fields = rows[2].split()
        if len(fields) < 2:
            return ["NOT_ASSESSED: a saved DFTU.Proj record is incomplete."]
        try:
            fields[0] = format(float(u_value), ".17g")
        except (TypeError, ValueError):
            return ["NOT_ASSESSED: a calculated U value is unavailable for a projector record."]
        rows[2] = " ".join(fields)
        rendered_records.extend(rows)
    if any(len(row) + 4 > WIDTH for row in rendered_records):
        return ["NOT_ASSESSED: a complete DFTU.Proj row exceeds the report width."]
    return ["%block DFTU.Proj", *(f"  {row}" for row in rendered_records), "%endblock DFTU.Proj"]


def additional_report_sections(
    source: Mapping[str, Any],
    context: Mapping[str, Any],
    analysis: Mapping[str, Any],
    geometry: Mapping[str, Any],
    system: Mapping[str, Any],
    basis: Mapping[str, Any],
    k_grid: Mapping[str, Any],
) -> list[str]:
    """Render researcher notes that supplement the fixed thirteen sections."""
    lines = section_header("HOW TO USE THIS U")
    lines.append("  Apply this value only with the same projector definition and geometry.")
    lines.extend("  " + item for item in dftu_block(context, analysis))
    reproduction = mapping(context.get("reproducibility"))
    lines.append(
        "  Check command template: hubbardflow check-projector --campaign "
        "campaign.v2.json --target-fdf production.fdf --map LR_LABEL=DFTU_LABEL"
    )
    lines.append(f"  Reproduce command: {report_value(reproduction.get('command'))}")
    lines.extend(section_header("APPLICABILITY"))
    lines.append(f"  Geometry: {report_value(geometry.get('summary'))}")
    lines.append(
        f"  Functional: {report_value(system.get('functional'))}; "
        f"pseudos: {report_value(system.get('pseudopotential_summary'))}"
    )
    lines.append(f"  Basis: {report_value(basis.get('summary'))}; k-grid: {report_list(k_grid.get('block'))}")

    lines.extend(section_header("NOT ASSESSED / NOT CLAIMED"))
    claims = source.get("not_assessed_or_not_claimed")
    if isinstance(claims, list):
        lines.extend(f"  {report_value(item)}" for item in claims)
    else:
        lines.extend(
            [
                "  Cell-size, vacuum, and k-grid sensitivity: NOT_ASSESSED unless measured separately.",
                "  This is not a self-consistent DFT+U result.",
                "  This is not a structure relaxed with the reported U.",
            ]
        )

    version = mapping(context.get("hubbardflow"))
    siesta = mapping(context.get("siesta"))
    lines.extend(section_header("REPRODUCIBILITY"))
    lines.append(
        f"  HubbardFlow version/commit: {report_value(version.get('version'))} / "
        f"{report_value(version.get('commit'))}"
    )
    lines.append(
        f"  SIESTA version/binary SHA-256: {report_value(siesta.get('version'))} / "
        f"{report_value(siesta.get('binary_sha256'))}"
    )
    lines.append(f"  BARE profile: {report_value(siesta.get('bare_profile'))}")
    lines.append(f"  Environment modules: {report_value(reproduction.get('modules'))}")
    lines.append(f"  Command: {report_value(reproduction.get('command'))}")
    lines.extend(
        [
            *section_header("CONVENTIONS"),
            "  CHI_IJ = d n_I / d alpha_J at alpha=0; CHI0 is BARE and CHI is SCREENED.",
            "  Positive alpha raises the declared DFTU.Proj potential on site J.",
            "  n is in electrons; alpha and U are in eV; CHI is in electrons/eV.",
            "  U = inverse(CHI0) - inverse(CHI); U_i is the diagonal element for site i.",
            "  NOT_ASSESSED means the saved evidence does not support the statement.",
            *section_header("REFERENCES AND CITATION"),
            "  Cococcioni and de Gironcoli, Phys. Rev. B 71, 035105 (2005).",
            "  Timrov, Marzari, and Cococcioni, arXiv:2203.15684 (2022).",
            "  Cite HubbardFlow with the recorded version, commit, and repository release.",
        ]
    )
    return lines
