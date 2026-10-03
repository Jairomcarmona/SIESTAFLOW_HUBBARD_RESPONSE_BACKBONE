"""Compare user-generated alias ions; prints an exact-byte receipt and never runs SIESTA."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from hubbardflow.siesta_backend.split_generated_identity import (
    SplitIdentityError,
    SplitIdentityStatus,
    verify_generated_split_identity,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_directory", type=Path)
    parser.add_argument("--original-label", required=True)
    parser.add_argument("--aliases", nargs="+", required=True)
    parser.add_argument("--reference-directory", type=Path)
    args = parser.parse_args(argv)
    try:
        receipt = verify_generated_split_identity(
            args.run_directory,
            args.original_label,
            args.aliases,
            reference_directory=args.reference_directory,
        )
    except SplitIdentityError as exc:
        print(
            json.dumps(
                {"status": SplitIdentityStatus.SPECIES_IDENTITY_NOT_ESTABLISHED.value, "error": str(exc)}
            )
        )
        return 2
    print(json.dumps({**receipt.to_mapping(), "receipt_sha256": receipt.digest}, indent=2, sort_keys=True))
    return 0 if receipt.status is SplitIdentityStatus.MATCH else 2


if __name__ == "__main__":
    raise SystemExit(main())
