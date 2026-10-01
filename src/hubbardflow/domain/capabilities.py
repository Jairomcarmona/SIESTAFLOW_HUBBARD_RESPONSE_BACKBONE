"""Explicit physics capabilities for an LR-U backend.

The capability declaration is a safety boundary, not a marketing statement.
An unsupported request must stop before FDF materialisation or submission;
silently treating a spinor or U+V request as scalar collinear U would make a
numerically successful campaign scientifically invalid.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class CapabilityError(ValueError):
    """The requested physics is outside the validated backend contract."""


class SpinTreatment(str, Enum):
    COLLINEAR_SCALAR = "collinear_scalar"
    NONCOLLINEAR_SPINOR = "noncollinear_spinor"
    SOC_SPINOR = "soc_spinor"


class InteractionModel(str, Enum):
    ON_SITE_U = "on_site_u"
    ON_SITE_U_AND_V = "on_site_u_and_v"


@dataclass(frozen=True)
class LRPhysicsRequest:
    """Physics requested by a campaign before any scheduler is involved."""

    spin_treatment: SpinTreatment
    interaction_model: InteractionModel
    manifolds_per_site: int = 1
    requires_orbital_covariance: bool = False

    def validate(self) -> None:
        if isinstance(self.manifolds_per_site, bool) or self.manifolds_per_site < 1:
            raise CapabilityError("manifolds_per_site must be a positive integer")


@dataclass(frozen=True)
class BackendCapabilities:
    """Versioned, validated capability set provided by a backend adapter."""

    backend_id: str
    supported_spin_treatments: frozenset[SpinTreatment]
    supported_interaction_models: frozenset[InteractionModel]
    maximum_manifolds_per_site: int
    orbital_covariance_certified: bool

    def require(self, request: LRPhysicsRequest) -> None:
        request.validate()
        missing: list[str] = []
        if request.spin_treatment not in self.supported_spin_treatments:
            missing.append(f"spin treatment {request.spin_treatment.value}")
        if request.interaction_model not in self.supported_interaction_models:
            missing.append(f"interaction model {request.interaction_model.value}")
        if request.manifolds_per_site > self.maximum_manifolds_per_site:
            missing.append("multiple correlated manifolds per site")
        if request.requires_orbital_covariance and not self.orbital_covariance_certified:
            missing.append("orbital-covariant symmetry transformation")
        if missing:
            raise CapabilityError(
                f"{self.backend_id} is not validated for " + ", ".join(missing)
            )


# This is deliberately narrow.  It documents what the present parser,
# materializer, and evidence model can actually certify, rather than what a
# particular SIESTA executable might theoretically be able to calculate.
SIESTA_SCALAR_LR_CAPABILITIES = BackendCapabilities(
    backend_id="siesta_finite_difference_lr_v1",
    supported_spin_treatments=frozenset({SpinTreatment.COLLINEAR_SCALAR}),
    supported_interaction_models=frozenset({InteractionModel.ON_SITE_U}),
    maximum_manifolds_per_site=1,
    orbital_covariance_certified=False,
)
