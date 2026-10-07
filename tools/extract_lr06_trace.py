"""Rebuild the minimal LR-06 fixture from the verified full SIESTA output.

The full output is intentionally not stored in the repository. Its SHA-256
guards this extraction so line ranges cannot silently drift to another run.
Section digests cover the exact extracted UTF-8 text normalized to LF endings.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import sys
import zlib
from collections.abc import Sequence
from pathlib import Path

TRACE_SHA256 = "3c909d4e94a34c7685cb31f89ca1193098a4eb7ba5b50396fd5266d41b186028"
FULL_OUTPUT_SHA256 = "f28dbe35ff17734f9291676dccf9592e4cc0d09049d6192237be82ea4786eb20"
SIESTA_EXECUTABLE_SHA256 = "c69519dc7296ca8f9e454303947084ee246efd609be4bc05244a31a91b82e37e"
FULL_OUTPUT_LINE_COUNT = 5871
REQUIRED_FINAL_LINE = 4579

FIXTURE_PATH = (
    Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "lr06_siesta542_yoltla_extract.txt"
)


def _section_digest(lines: Sequence[str]) -> str:
    section_text = "\n".join(lines) + "\n"
    return hashlib.sha256(section_text.encode("utf-8")).hexdigest()


def render_fixture_from_lines(lines: Sequence[str]) -> str:
    """Render the three documented native-output ranges without altering text."""
    if len(lines) < REQUIRED_FINAL_LINE:
        raise ValueError(f"source has {len(lines)} lines; native line {REQUIRED_FINAL_LINE} is required")

    signature = list(lines[4336:4337])
    parent = list(lines[4482:4514])
    response = list(lines[4514:4579])
    sections = (
        ("native line 4337", signature),
        ("native lines 4483-4514", parent),
        ("native lines 4515-4579", response),
    )

    output = [
        "# Minimal verbatim excerpts from the verified Yoltla SIESTA output.",
        "# Regenerate/check: python tools/extract_lr06_trace.py FULL_OUTPUT.out.gz --check",
        f"# Source trace SHA-256: {TRACE_SHA256}",
        f"# Original full siesta.out SHA-256 (citation only): {FULL_OUTPUT_SHA256}",
        f"# SIESTA 5.4.2 executable SHA-256: {SIESTA_EXECUTABLE_SHA256}",
        "# Section digests use UTF-8 text, LF line endings, and a trailing LF.",
        f"# Extracted section {sections[0][0]} SHA-256: {_section_digest(signature)}",
        "# Native output line 4337; production profile signature:",
        *signature,
        f"# Extracted section {sections[1][0]} SHA-256: {_section_digest(parent)}",
        "# Native output lines 4483-4514; complete pre-perturbation population event:",
        *parent,
        f"# Extracted section {sections[2][0]} SHA-256: {_section_digest(response)}",
        "# Native output lines 4515-4579; verbatim trace lines 70-134:",
        *response,
    ]
    return "\n".join(output) + "\n"


def render_fixture_from_source(source_path: Path) -> str:
    """Read a plain or gzip-compressed full output and enforce its identity."""
    try:
        source_bytes = source_path.read_bytes()
    except OSError as exc:
        raise ValueError(f"cannot read full SIESTA output {source_path}: {exc}") from exc

    try:
        output_bytes = gzip.decompress(source_bytes) if source_bytes.startswith(b"\x1f\x8b") else source_bytes
    except (OSError, EOFError, zlib.error) as exc:
        raise ValueError(f"cannot decompress full SIESTA output {source_path}: {exc}") from exc

    actual_sha256 = hashlib.sha256(output_bytes).hexdigest()
    if actual_sha256 != FULL_OUTPUT_SHA256:
        raise ValueError(
            f"full SIESTA output SHA-256 mismatch: expected {FULL_OUTPUT_SHA256}, got {actual_sha256}"
        )

    try:
        text = output_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("full SIESTA output is not valid UTF-8") from exc
    lines = text.splitlines()
    if len(lines) != FULL_OUTPUT_LINE_COUNT:
        raise ValueError(
            f"full SIESTA output line count mismatch: expected {FULL_OUTPUT_LINE_COUNT}, got {len(lines)}"
        )
    return render_fixture_from_lines(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="verified full siesta.out or its .gz")
    parser.add_argument("--output", type=Path, default=FIXTURE_PATH, help="fixture path")
    parser.add_argument(
        "--check",
        action="store_true",
        help="compare regenerated text with the existing fixture without writing it",
    )
    args = parser.parse_args(argv)

    try:
        rendered = render_fixture_from_source(args.source)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.check:
        try:
            existing = args.output.read_text(encoding="utf-8")
        except OSError as exc:
            print(f"error: cannot read fixture {args.output}: {exc}", file=sys.stderr)
            return 2
        if existing != rendered:
            print(f"fixture differs from extracted source: {args.output}", file=sys.stderr)
            return 1
        print(f"verified {args.output} against full-output SHA-256 {FULL_OUTPUT_SHA256}")
        return 0

    try:
        args.output.write_text(rendered, encoding="utf-8", newline="\n")
    except OSError as exc:
        print(f"error: cannot write fixture {args.output}: {exc}", file=sys.stderr)
        return 2
    print(f"wrote {args.output} from full-output SHA-256 {FULL_OUTPUT_SHA256}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
