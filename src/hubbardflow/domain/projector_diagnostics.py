"""Record-only diagnostics for SIESTA's atomic Method 2 Hubbard projectors.

The comparisons in this module describe the reference projector occupation and
the dimensionless ``U * abs(chi0)`` regime indicator. They never accept or
reject a calculated Hubbard parameter. Electron-count references must be
declared for each site; chemistry and labels are not used to infer them.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum

from .validation import ValidationError, require_finite, require_nonnegative_finite


class ProjectorDiagnosticError(ValueError):
    """Raised when declared projector diagnostic evidence is malformed."""


class ComparisonStatus(str, Enum):
    """Whether a record-only comparison has the inputs it needs."""

    RECORDED = "RECORDED"
    NOT_ASSESSED = "NOT_ASSESSED"


class ProjectorDiagnosticStatus(str, Enum):
    """Projector diagnostics never participate in scientific acceptance."""

    RECORD_ONLY = "RECORD_ONLY"


class DiagnosticSeverity(str, Enum):
    WARNING = "WARNING"


class LigandChargeCaptureStatus(str, Enum):
    """Record-only comparison with a declared free-atom d occupation."""

    CAPTURE_INDICATED = "CAPTURE_INDICATED"
    NOT_INDICATED = "NOT_INDICATED"
    NOT_ASSESSED = "NOT_ASSESSED"


@dataclass(frozen=True)
class SiteElectronReference:
    """User-declared d-electron references for one correlated site."""

    formal_d_electrons: float | None = None
    free_atom_d_electrons: float | None = None

    def validate(self) -> None:
        try:
            if self.formal_d_electrons is not None:
                require_nonnegative_finite(self.formal_d_electrons, "formal_d_electrons")
            if self.free_atom_d_electrons is not None:
                require_nonnegative_finite(self.free_atom_d_electrons, "free_atom_d_electrons")
        except ValidationError as exc:
            raise ProjectorDiagnosticError(str(exc)) from exc
        if self.formal_d_electrons is None and self.free_atom_d_electrons is None:
            raise ProjectorDiagnosticError(
                "a site electron reference must declare at least one d-electron count"
            )

    def to_mapping(self) -> dict[str, float | None]:
        return {
            "formal_d_electrons": self.formal_d_electrons,
            "free_atom_d_electrons": self.free_atom_d_electrons,
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> SiteElectronReference:
        if set(value) - {"formal_d_electrons", "free_atom_d_electrons"}:
            raise ProjectorDiagnosticError("site electron reference has unsupported fields")
        formal = value.get("formal_d_electrons")
        free_atom = value.get("free_atom_d_electrons")
        result = cls(
            formal_d_electrons=None
            if formal is None
            else _validated_nonnegative(formal, "formal_d_electrons"),
            free_atom_d_electrons=None
            if free_atom is None
            else _validated_nonnegative(free_atom, "free_atom_d_electrons"),
        )
        result.validate()
        return result


@dataclass(frozen=True)
class ProjectorDiagnosticInput:
    """Validated per-site values supplied by campaign analysis."""

    site_id: str
    reference_occupation_e: float | None
    u_ev: float | None
    chi0_diagonal_per_ev: float | None
    electron_reference: SiteElectronReference | None = None


@dataclass(frozen=True)
class ProjectorSiteDiagnostic:
    """Record-only comparisons and response-regime indicator for one site."""

    site_id: str
    reference_occupation_e: float | None
    formal_d_electrons: float | None
    difference_from_formal_d_e: float | None
    formal_comparison: ComparisonStatus
    free_atom_d_electrons: float | None
    difference_from_free_atom_d_e: float | None
    ligand_charge_capture: LigandChargeCaptureStatus
    u_ev: float | None
    chi0_diagonal_per_ev: float | None
    u_times_abs_chi0: float | None
    regime_indicator_status: ComparisonStatus

    def to_mapping(self) -> dict[str, object]:
        return {
            "site_id": self.site_id,
            "reference_occupation_e": self.reference_occupation_e,
            "formal_d_electrons": self.formal_d_electrons,
            "difference_from_formal_d_e": self.difference_from_formal_d_e,
            "formal_comparison": self.formal_comparison.value,
            "free_atom_d_electrons": self.free_atom_d_electrons,
            "difference_from_free_atom_d_e": self.difference_from_free_atom_d_e,
            "ligand_charge_capture": self.ligand_charge_capture.value,
            "u_ev": self.u_ev,
            "chi0_diagonal_per_ev": self.chi0_diagonal_per_ev,
            "u_times_abs_chi0": self.u_times_abs_chi0,
            "regime_indicator_status": self.regime_indicator_status.value,
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> ProjectorSiteDiagnostic:
        try:
            site_id = _validated_site_id(value.get("site_id"))
            return cls(
                site_id=site_id,
                reference_occupation_e=_optional_finite(
                    value.get("reference_occupation_e"), "reference_occupation_e"
                ),
                formal_d_electrons=_optional_nonnegative(
                    value.get("formal_d_electrons"), "formal_d_electrons"
                ),
                difference_from_formal_d_e=_optional_finite(
                    value.get("difference_from_formal_d_e"), "difference_from_formal_d_e"
                ),
                formal_comparison=ComparisonStatus(value["formal_comparison"]),
                free_atom_d_electrons=_optional_nonnegative(
                    value.get("free_atom_d_electrons"), "free_atom_d_electrons"
                ),
                difference_from_free_atom_d_e=_optional_finite(
                    value.get("difference_from_free_atom_d_e"), "difference_from_free_atom_d_e"
                ),
                ligand_charge_capture=LigandChargeCaptureStatus(value["ligand_charge_capture"]),
                u_ev=_optional_finite(value.get("u_ev"), "u_ev"),
                chi0_diagonal_per_ev=_optional_finite(
                    value.get("chi0_diagonal_per_ev"), "chi0_diagonal_per_ev"
                ),
                u_times_abs_chi0=_optional_finite(value.get("u_times_abs_chi0"), "u_times_abs_chi0"),
                regime_indicator_status=ComparisonStatus(value["regime_indicator_status"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ProjectorDiagnosticError("invalid projector site diagnostic mapping") from exc


@dataclass(frozen=True)
class Method2ProjectorWarning:
    """Machine-readable, permanent comparability warning for Method 2."""

    code: str = "SIESTA_METHOD_2_ATOMIC_NONORTHOGONALIZED_PROJECTOR"
    severity: DiagnosticSeverity = DiagnosticSeverity.WARNING
    decision_role: ProjectorDiagnosticStatus = ProjectorDiagnosticStatus.RECORD_ONLY
    projector_generation_method: int = 2
    atomic: bool = True
    orthogonalized: bool = False
    comparable_to_orthogonalized_projector_u: bool = False
    message: str = (
        "SIESTA Method 2 uses atomic, non-orthogonalized projectors; its U is not comparable "
        "to U values from orthogonalized projector schemes."
    )

    def to_mapping(self) -> dict[str, object]:
        return {
            "code": self.code,
            "severity": self.severity.value,
            "decision_role": self.decision_role.value,
            "projector_generation_method": self.projector_generation_method,
            "atomic": self.atomic,
            "orthogonalized": self.orthogonalized,
            "comparable_to_orthogonalized_projector_u": self.comparable_to_orthogonalized_projector_u,
            "message": self.message,
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> Method2ProjectorWarning:
        expected = cls().to_mapping()
        if dict(value) != expected:
            raise ProjectorDiagnosticError("unsupported Method 2 projector warning mapping")
        return cls()


@dataclass(frozen=True)
class ProjectorDiagnostics:
    """Campaign projector diagnostics, all explicitly record-only."""

    status: ProjectorDiagnosticStatus
    projector_generation_method: int
    decision_role: ProjectorDiagnosticStatus
    method2_warning: Method2ProjectorWarning
    sites: tuple[ProjectorSiteDiagnostic, ...]

    def to_mapping(self) -> dict[str, object]:
        return {
            "status": self.status.value,
            "projector_generation_method": self.projector_generation_method,
            "decision_role": self.decision_role.value,
            "method2_warning": self.method2_warning.to_mapping(),
            "sites": [site.to_mapping() for site in self.sites],
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> ProjectorDiagnostics:
        if (
            value.get("status") != ProjectorDiagnosticStatus.RECORD_ONLY.value
            or value.get("decision_role") != ProjectorDiagnosticStatus.RECORD_ONLY.value
        ):
            raise ProjectorDiagnosticError("projector diagnostics must remain RECORD_ONLY")
        try:
            method = value["projector_generation_method"]
            if isinstance(method, bool) or not isinstance(method, int) or method != 2:
                raise ValueError("method must be 2")
            warning = value["method2_warning"]
            rows = value["sites"]
            if (
                not isinstance(warning, Mapping)
                or not isinstance(rows, list)
                or any(not isinstance(item, Mapping) for item in rows)
            ):
                raise ValueError("invalid warning or site list")
            return cls(
                status=ProjectorDiagnosticStatus.RECORD_ONLY,
                projector_generation_method=2,
                decision_role=ProjectorDiagnosticStatus.RECORD_ONLY,
                method2_warning=Method2ProjectorWarning.from_mapping(warning),
                sites=tuple(ProjectorSiteDiagnostic.from_mapping(item) for item in rows),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ProjectorDiagnosticError("invalid projector diagnostics mapping") from exc


METHOD2_PROJECTOR_WARNING = Method2ProjectorWarning()


def build_projector_diagnostics(
    site_inputs: Sequence[ProjectorDiagnosticInput],
    *,
    projector_generation_method: int,
) -> ProjectorDiagnostics:
    """Calculate site diagnostics without changing any scientific decision.

    ``U * abs(chi0_II)`` is dimensionless and is reported as a regime
    indicator. It is approximately constant when screened and bare responses
    remain proportional. The method-2 warning records the projector scheme's
    scope and is independent of whether a numerical U is available.
    """
    if (
        isinstance(projector_generation_method, bool)
        or not isinstance(projector_generation_method, int)
        or projector_generation_method != 2
    ):
        raise ProjectorDiagnosticError("projector diagnostics require the validated SIESTA Method 2 scheme")
    site_ids: set[str] = set()
    rows: list[ProjectorSiteDiagnostic] = []
    ordered_site_inputs = sorted(site_inputs, key=lambda item: _validated_site_id(item.site_id))
    for item in ordered_site_inputs:
        site_id = _validated_site_id(item.site_id)
        if site_id in site_ids:
            raise ProjectorDiagnosticError(f"duplicate projector diagnostic site {site_id!r}")
        site_ids.add(site_id)
        occupation = _optional_nonnegative(item.reference_occupation_e, "reference_occupation_e")
        u_ev = _optional_finite(item.u_ev, "u_ev")
        chi0 = _optional_finite(item.chi0_diagonal_per_ev, "chi0_diagonal_per_ev")
        reference = item.electron_reference
        if reference is not None:
            reference.validate()
        formal = None if reference is None else reference.formal_d_electrons
        free_atom = None if reference is None else reference.free_atom_d_electrons
        formal_diff = None if occupation is None or formal is None else occupation - formal
        free_diff = None if occupation is None or free_atom is None else occupation - free_atom
        formal_status = (
            ComparisonStatus.RECORDED if formal_diff is not None else ComparisonStatus.NOT_ASSESSED
        )
        capture = (
            LigandChargeCaptureStatus.NOT_ASSESSED
            if free_diff is None
            else LigandChargeCaptureStatus.CAPTURE_INDICATED
            if free_diff > 0.0
            else LigandChargeCaptureStatus.NOT_INDICATED
        )
        regime_indicator = None if u_ev is None or chi0 is None else u_ev * abs(chi0)
        rows.append(
            ProjectorSiteDiagnostic(
                site_id=site_id,
                reference_occupation_e=occupation,
                formal_d_electrons=formal,
                difference_from_formal_d_e=formal_diff,
                formal_comparison=formal_status,
                free_atom_d_electrons=free_atom,
                difference_from_free_atom_d_e=free_diff,
                ligand_charge_capture=capture,
                u_ev=u_ev,
                chi0_diagonal_per_ev=chi0,
                u_times_abs_chi0=regime_indicator,
                regime_indicator_status=(
                    ComparisonStatus.RECORDED
                    if regime_indicator is not None
                    else ComparisonStatus.NOT_ASSESSED
                ),
            )
        )
    return ProjectorDiagnostics(
        status=ProjectorDiagnosticStatus.RECORD_ONLY,
        projector_generation_method=2,
        decision_role=ProjectorDiagnosticStatus.RECORD_ONLY,
        method2_warning=METHOD2_PROJECTOR_WARNING,
        sites=tuple(rows),
    )


def _validated_site_id(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ProjectorDiagnosticError("site_id must be a non-empty string")
    return value


def _validated_nonnegative(value: object, label: str) -> float:
    try:
        return require_nonnegative_finite(value, label)
    except ValidationError as exc:
        raise ProjectorDiagnosticError(str(exc)) from exc


def _optional_nonnegative(value: object, label: str) -> float | None:
    return None if value is None else _validated_nonnegative(value, label)


def _optional_finite(value: object, label: str) -> float | None:
    if value is None:
        return None
    try:
        return require_finite(value, label)
    except ValidationError as exc:
        raise ProjectorDiagnosticError(str(exc)) from exc
