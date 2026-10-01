"""Site-neutral state machine that prevents invalid scientific descendants."""
from __future__ import annotations

from enum import Enum


class NodeState(str, Enum):
    MATERIALIZED = "MATERIALIZED"
    RUNNING = "RUNNING"
    VALIDATED = "VALIDATED"
    FAILED_EXECUTION = "FAILED_EXECUTION"
    FAILED_OUTPUT_VALIDATION = "FAILED_OUTPUT_VALIDATION"
    FAILED_SCIENCE = "FAILED_SCIENCE"
    BLOCKED = "BLOCKED"


TERMINAL_FAILURES = {NodeState.FAILED_EXECUTION, NodeState.FAILED_OUTPUT_VALIDATION, NodeState.FAILED_SCIENCE, NodeState.BLOCKED}


def may_start(parent_states: list[NodeState]) -> bool:
    """A node starts only after every declared parent is scientifically valid."""
    return all(state is NodeState.VALIDATED for state in parent_states)


def may_analyze(required_response_states: list[NodeState]) -> bool:
    """Analysis has no partial or fallback path."""
    return bool(required_response_states) and may_start(required_response_states)
