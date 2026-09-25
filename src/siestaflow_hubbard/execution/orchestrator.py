"""Retired direct campaign orchestrator.

It formerly coupled generic fitting with a SIESTA adapter that could launch
and extract unreceipted output. Production campaigns must instead execute the
admitted SIESTA runtime through the generic DAG and consume its validated
receipts at the application boundary.
"""
from __future__ import annotations


class LegacyCampaignOrchestrationDisabledError(RuntimeError):
    """A legacy orchestration entry point was invoked."""


class CampaignOrchestrator:
    """Compatibility object whose former execution API is fail-closed."""

    def __init__(self, *args: object, **kwargs: object):
        del args, kwargs

    @staticmethod
    def _disabled() -> None:
        raise LegacyCampaignOrchestrationDisabledError(
            "CampaignOrchestrator is disabled for production; use the admitted SIESTA DAG runtime"
        )

    def run_reference(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        self._disabled()

    def run_perturbations(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        self._disabled()

    def compute_u(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        self._disabled()

    def execute_campaign(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        self._disabled()
