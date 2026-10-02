"""Typed identities for the scientifically validated XC configurations.

An XC name that can be recognized in an input file is not thereby a
scientifically validated Hubbard-response profile.  The only profile
qualified by the frozen V6 evidence is the explicit PBE reference profile.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Literal


class ScientificProfileError(ValueError):
    """A declared scientific configuration is missing or not qualified."""


QualificationStatus = Literal["V6_VALIDATED", "DECLARED_UNVALIDATED"]


@dataclass(frozen=True)
class XcScientificProfile:
    """Versioned scientific identity independent of campaign and backend."""

    profile_id: str
    version: int
    xc_functional: str
    qualification_status: QualificationStatus
    qualification_basis: str | None = None

    def __post_init__(self) -> None:
        if not self.profile_id.strip():
            raise ScientificProfileError("profile_id must be non-empty")
        if isinstance(self.version, bool) or not isinstance(self.version, int) or self.version < 1:
            raise ScientificProfileError("profile version must be a positive integer")
        if self.xc_functional not in _XC_MARKERS:
            raise ScientificProfileError(f"unsupported XC functional {self.xc_functional!r}")
        if self.qualification_status not in {"V6_VALIDATED", "DECLARED_UNVALIDATED"}:
            raise ScientificProfileError("unknown scientific profile qualification status")
        if self.qualification_status == "V6_VALIDATED" and not self.qualification_basis:
            raise ScientificProfileError("a validated profile must identify its qualification basis")
        if self.qualification_status == "V6_VALIDATED" and (
            self.profile_id, self.version, self.xc_functional, self.qualification_basis
        ) != ("hubbardflow.v6.pbe-reference", 1, "PBE", "scientific-v6-final"):
            raise ScientificProfileError("only the immutable V6 PBE reference profile is currently qualified")
        if self.qualification_status == "DECLARED_UNVALIDATED" and self.qualification_basis is not None:
            raise ScientificProfileError("an unvalidated profile cannot claim a qualification basis")

    @property
    def is_qualified_for_lr(self) -> bool:
        return self.qualification_status == "V6_VALIDATED"

    def to_mapping(self) -> dict[str, object]:
        """Return a JSON-compatible stable representation."""
        return asdict(self)

    @classmethod
    def from_mapping(cls, value: object) -> XcScientificProfile:
        if not isinstance(value, dict) or set(value) != {
            "profile_id", "version", "xc_functional", "qualification_status", "qualification_basis",
        }:
            raise ScientificProfileError("xc_profile has missing or unexpected fields")
        try:
            return cls(**value)
        except (TypeError, AttributeError) as exc:
            raise ScientificProfileError("xc_profile fields have invalid types") from exc


_XC_MARKERS: dict[str, tuple[str, tuple[tuple[str, ...], ...]]] = {
    "PBE": ("gga", (("pbe",), ("perdew", "burke", "ernzerhof"))),
    "PBEsol": ("gga", (("pbesol",), ("perdew", "burke", "ernzerhof", "solids"))),
    "RPBE": ("gga", (("rpbe",),)),
    "LDA_CA": ("lda", (("ca",), ("ceperley", "alder"))),
    "LDA_PZ": ("lda", (("pz",), ("perdew", "zunger"))),
    "SCAN": ("mgga", (("scan",),)),
}

_FUNCTIONAL_ALIASES = {
    "pbe": "PBE", "ggapbe": "PBE", "pbesol": "PBEsol", "rpbe": "RPBE",
    "ldaca": "LDA_CA", "ca-lda": "LDA_CA", "ldapz": "LDA_PZ", "pz-lda": "LDA_PZ",
    "scan": "SCAN",
}

V6_PBE_REFERENCE_PROFILE = XcScientificProfile(
    profile_id="hubbardflow.v6.pbe-reference",
    version=1,
    xc_functional="PBE",
    qualification_status="V6_VALIDATED",
    qualification_basis="scientific-v6-final",
)


def canonical_xc_functional(value: object) -> str:
    """Normalize an explicit legacy XC token; never supply a default."""
    if not isinstance(value, str) or not value.strip():
        raise ScientificProfileError("XC functional must be declared explicitly")
    normalized = re.sub(r"[^a-z0-9_]", "", value.casefold())
    for alias, canonical in _FUNCTIONAL_ALIASES.items():
        if re.sub(r"[^a-z0-9_]", "", alias.casefold()) == normalized:
            return canonical
    raise ScientificProfileError("unsupported declared XC functional")


def profile_from_explicit_functional(value: object) -> XcScientificProfile:
    """Map an explicit v2 functional into its typed profile identity.

    PBE maps to the qualified V6 reference. Other recognized family names are
    represented as declared-but-unvalidated, which prevents recognition from
    being mistaken for scientific qualification.
    """
    functional = canonical_xc_functional(value)
    if functional == "PBE":
        return V6_PBE_REFERENCE_PROFILE
    return XcScientificProfile(
        profile_id=f"hubbardflow.xc.{functional.casefold()}.declared",
        version=1,
        xc_functional=functional,
        qualification_status="DECLARED_UNVALIDATED",
    )


def resolve_scientific_profile(functional: object, declared_profile: object = None) -> XcScientificProfile:
    """Resolve a typed profile or explicitly migrate a v2 functional field.

    Existing v2 campaign/config records carry an explicit ``functional`` and
    may omit ``xc_profile``. This is the sole legacy migration path;
    absence of both is an error. If both are present, they must agree exactly.
    """
    migrated = profile_from_explicit_functional(functional)
    if declared_profile is None:
        return migrated
    declared = XcScientificProfile.from_mapping(declared_profile)
    if declared != migrated:
        raise ScientificProfileError("xc_profile differs from the explicitly declared v2 functional")
    return declared


def validate_xc_text(text: str, functional: str, source: str) -> None:
    """Check that backend-provided XC text agrees with an explicit profile."""
    family, marker_groups = _XC_MARKERS[functional]
    folded = text.casefold()
    if family not in folded or not any(
        all(marker.casefold() in folded for marker in group) for group in marker_groups
    ):
        raise ScientificProfileError(f"{source} is inconsistent with declared functional {functional}")


def require_lr_qualified(profile: XcScientificProfile) -> XcScientificProfile:
    """Refuse to execute LR with an XC family lacking a qualified profile."""
    if not profile.is_qualified_for_lr:
        raise ScientificProfileError(
            f"scientific profile {profile.profile_id!r} is declared but not validated for Hubbard-response use"
        )
    return profile
