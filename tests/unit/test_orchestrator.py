import pytest

from siestaflow_hubbard.execution.orchestrator import (
    CampaignOrchestrator,
    LegacyCampaignOrchestrationDisabledError,
)


@pytest.mark.parametrize("method", ["run_reference", "run_perturbations", "compute_u", "execute_campaign"])
def test_legacy_orchestrator_cannot_launch_or_fit_unreceipted_siesta_output(method):
    with pytest.raises(LegacyCampaignOrchestrationDisabledError):
        getattr(CampaignOrchestrator(), method)()
