"""Render projector applicability reports for human review."""

from __future__ import annotations

from hubbardflow.siesta_backend.projector_compatibility import ProjectorCompatibilityReport


def render_projector_compatibility_report(report: ProjectorCompatibilityReport) -> str:
    """Render decisions, declared differences, and traceability data as ASCII.

    Hashes are shown as provenance only. The comparison status is determined
    exclusively by projector and PAO declarations.
    """
    lines = [
        "HUBBARDFLOW  |  PROJECTOR APPLICABILITY",
        "=" * 52,
        f"Campaign : {report.campaign_path}",
        f"Target   : {report.target_fdf_path}",
        f"Result   : {report.status.value}",
    ]
    if report.force_requested:
        lines.extend(
            (
                "Override : --force was explicitly requested.",
                "           Structural status remains unchanged.",
            )
        )
    lines.append("")
    for comparison in report.results:
        lines.append(f"{comparison.lr_label} -> {comparison.dftu_label}  [{comparison.status.value}]")
        if comparison.differences:
            rows = [
                (item.field, _value(item.lr_value), _value(item.dftu_value))
                for item in comparison.differences
            ]
            lines.extend(_ascii_table(("FIELD", "LR", "DFT+U"), rows))
        else:
            lines.append("  No declared parameter differences.")
        if comparison.incomplete_reasons:
            lines.append(
                "  Evidence incomplete: " + ", ".join(item.value for item in comparison.incomplete_reasons)
            )
        if comparison.digest_warnings:
            for warning in comparison.digest_warnings:
                lines.append(
                    f"  WARNING: {warning.role} digest differs (traceability only): "
                    f"LR={_hashes(warning.lr_sha256)} DFT+U={_hashes(warning.dftu_sha256)}"
                )
        for side, issues in (
            ("LR", comparison.lr_artifact_digest_issues),
            ("DFT+U", comparison.dftu_artifact_digest_issues),
        ):
            for issue in issues:
                lines.append(f"  WARNING: {side} digest unavailable (traceability only): {issue}")
        for side, digests in (
            ("LR", comparison.lr_artifact_digests),
            ("DFT+U", comparison.dftu_artifact_digests),
        ):
            for digest in digests:
                lines.append(f"  {side} {digest.role}: sha256={digest.sha256} ({digest.path})")
        lines.append("")
    lines.append("File digests are recorded as provenance and never decide MATCH/MISMATCH.")
    if report.force_requested and not report.application_permitted:
        lines.append("The override was recorded but is not applicable to this report.")
    return "\n".join(lines).rstrip()


def _ascii_table(headers: tuple[str, ...], rows: list[tuple[str, str, str]]) -> list[str]:
    widths = [max(len(header), *(len(row[index]) for row in rows)) for index, header in enumerate(headers)]
    border = "+" + "+".join("-" * (width + 2) for width in widths) + "+"

    def render_row(row: tuple[str, ...]) -> str:
        cells = [f" {value:<{widths[index]}} " for index, value in enumerate(row)]
        return "|" + "|".join(cells) + "|"

    return [border, render_row(headers), border, *(render_row(row) for row in rows), border]


def _value(value: object) -> str:
    if isinstance(value, tuple):
        return "(" + ", ".join(_value(item) for item in value) + ")"
    return "<missing>" if value is None else str(value)


def _hashes(values: tuple[str, ...]) -> str:
    return ",".join(values) if values else "<none>"
