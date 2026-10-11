"""Installed QRAFT controller entrypoint for an already prepared HF campaign."""

from __future__ import annotations

import argparse
import os
import signal
import sys
from pathlib import Path, PurePosixPath
from threading import Event

from hubbardflow.api.controller_contracts import (
    ControllerContractError,
    load_controller_reservation,
)
from hubbardflow.api.controller_ledger import ControllerLedgerObserver
from hubbardflow.execution.campaign_runner import run_campaign_worker


def _run_relative_path(root: Path, value: str, label: str) -> Path:
    relative = PurePosixPath(value)
    if relative.is_absolute() or not value or any(part in {"", ".", ".."} for part in relative.parts):
        raise ControllerContractError(f"{label} must be a safe path relative to the QRAFT run directory")
    resolved = (root / Path(*relative.parts)).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise ControllerContractError(f"{label} escapes the QRAFT run directory") from exc
    return resolved


def main(argv: list[str] | None = None) -> int:
    """Run one fresh native campaign attempt under the QRAFT supervisor."""
    parser = argparse.ArgumentParser(prog="hubbardflow-controller")
    parser.add_argument("--qraft-reservation", required=True)
    parser.add_argument("--campaign", required=True)
    parser.add_argument("--prior-ledger", action="append", default=[])
    arguments = parser.parse_args(argv)
    run_root = Path.cwd().resolve()
    try:
        if os.name != "posix":
            raise ControllerContractError("CONTROLLER_REQUIRES_POSIX")
        descriptor_path = _run_relative_path(run_root, arguments.qraft_reservation, "reservation path")
        campaign_path = _run_relative_path(run_root, arguments.campaign, "campaign path")
        prior_ledger_paths = tuple(
            _run_relative_path(run_root, value, "prior ledger path") for value in arguments.prior_ledger
        )
        descriptor = load_controller_reservation(descriptor_path)
        details = descriptor.to_mapping()
        raw_attempt_number = details["attempt_number"]
        if not isinstance(raw_attempt_number, int) or isinstance(raw_attempt_number, bool):
            raise ControllerContractError("reservation attempt_number must be an integer")
        attempt_number = raw_attempt_number
        if len(prior_ledger_paths) != attempt_number - 1:
            raise ControllerContractError("one prior ledger path is required for each earlier attempt")
        observer = ControllerLedgerObserver(descriptor, run_root, prior_ledger_paths=prior_ledger_paths)
        all_book_paths = [path.resolve() for path in prior_ledger_paths] + [
            observer.inner_ledger_path.resolve()
        ]
        if len(set(all_book_paths)) != len(all_book_paths):
            raise ControllerContractError("each attempt must use a distinct immutable ledger path")
        observed_attempts: set[str] = set()
        for book in observer.prior_ledgers:
            book_attempts = {str(row.get("attempt_id", "")) for row in book.entries}
            if len(book_attempts) > 1:
                raise ControllerContractError("a prior ledger contains more than one attempt")
            if book_attempts:
                prior_id = next(iter(book_attempts))
                if not prior_id or prior_id == observer.attempt_id or prior_id in observed_attempts:
                    raise ControllerContractError("prior ledger attempts are duplicated or malformed")
                observed_attempts.add(prior_id)
            if any(str(row.get("task_id", "")) != observer.task_id for row in book.entries):
                raise ControllerContractError("prior ledger belongs to another QRAFT task")
        previous = details["previous_attempt"]
        if attempt_number > 1 and isinstance(previous, dict):
            last_prior = observer.prior_ledgers[-1].entries
            if last_prior and any(
                str(row.get("attempt_id", "")) != str(previous["attempt_id"]) for row in last_prior
            ):
                raise ControllerContractError("last prior ledger does not match previous_attempt")
        if campaign_path.resolve().parent != observer.state_dir_path.resolve(strict=True):
            raise ControllerContractError("campaign root must be the complete paths.state_dir directory")
        stop_event = Event()
        previous_handler = signal.getsignal(signal.SIGTERM)

        def request_cooperative_stop(_signum: int, _frame: object) -> None:
            stop_event.set()

        signal.signal(signal.SIGTERM, request_cooperative_stop)
        try:
            return run_campaign_worker(
                campaign_path,
                "run" if details["attempt_number"] == 1 else "resume",
                controller_observer=observer,
                controller_stop_event=stop_event,
                controller_stop_path=observer.stop_request_path,
            )
        finally:
            signal.signal(signal.SIGTERM, previous_handler)
    except (ControllerContractError, OSError, ValueError) as exc:
        print(f"hubbardflow-controller: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
