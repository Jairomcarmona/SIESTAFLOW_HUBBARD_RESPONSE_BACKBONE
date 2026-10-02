"""Check user-produced T0–T4 metrics; never invoke SIESTA or fabricate results."""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import cast

from hubbardflow.domain.scf_validation import (
    ValidationMetrics,
    ValidationProtocol,
    ValidationStatus,
    validate_t0_t4,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("protocol", type=Path)
    parser.add_argument("metrics", type=Path)
    args = parser.parse_args(argv)
    protocol = ValidationProtocol.from_mapping(
        cast(Mapping[str, object], json.loads(args.protocol.read_text(encoding="utf-8")))
    )
    rows = json.loads(args.metrics.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        parser.error("metrics must be a JSON array of ValidationMetrics records")
    metrics = tuple(ValidationMetrics.from_mapping(row) for row in rows)
    result = validate_t0_t4(protocol, metrics)
    print(
        json.dumps(
            {"result": result.to_mapping(), "result_sha256": result.digest}, sort_keys=True, allow_nan=False
        )
    )
    return 0 if result.status is ValidationStatus.PASSED else 2


if __name__ == "__main__":
    raise SystemExit(main())
