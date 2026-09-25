import pytest

from siestaflow_hubbard.domain.capabilities import (
    CapabilityError,
    InteractionModel,
    LRPhysicsRequest,
    SIESTA_SCALAR_LR_CAPABILITIES,
    SpinTreatment,
)


def test_current_backend_accepts_only_its_certified_scalar_on_site_u_scope():
    SIESTA_SCALAR_LR_CAPABILITIES.require(
        LRPhysicsRequest(SpinTreatment.COLLINEAR_SCALAR, InteractionModel.ON_SITE_U)
    )


@pytest.mark.parametrize(
    "physics_request",
    [
        LRPhysicsRequest(SpinTreatment.NONCOLLINEAR_SPINOR, InteractionModel.ON_SITE_U),
        LRPhysicsRequest(SpinTreatment.SOC_SPINOR, InteractionModel.ON_SITE_U),
        LRPhysicsRequest(SpinTreatment.COLLINEAR_SCALAR, InteractionModel.ON_SITE_U_AND_V),
        LRPhysicsRequest(SpinTreatment.COLLINEAR_SCALAR, InteractionModel.ON_SITE_U, manifolds_per_site=2),
        LRPhysicsRequest(SpinTreatment.COLLINEAR_SCALAR, InteractionModel.ON_SITE_U, requires_orbital_covariance=True),
    ],
)
def test_unsupported_physics_fails_before_execution(physics_request):
    with pytest.raises(CapabilityError):
        SIESTA_SCALAR_LR_CAPABILITIES.require(physics_request)
