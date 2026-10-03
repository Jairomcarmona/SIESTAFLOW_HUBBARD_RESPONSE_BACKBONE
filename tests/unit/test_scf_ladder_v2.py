"""Representable levels, user-run references and immutable parent-DM identities."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from hubbardflow.domain.scf_ladder import estimate_ladder
from hubbardflow.domain.scf_ladder_models import (
    ScfLadderError,
    ScfLadderProtocol,
    ScfLevel,
    ScfReason,
    ScfStatus,
)
from hubbardflow.domain.symmetry_reduction import ResponseMode
from hubbardflow.siesta_backend.fdf_model import FdfErrorCode, FdfModelError, _one
from hubbardflow.siesta_backend.scf_ladder_inputs import (
    materialize_ladder_input,
    materialize_ladder_reference,
    validate_ladder_output,
)
from hubbardflow.siesta_backend.siesta542_bare_profile import Siesta542PotentialShiftHamiltonianProfile
from tests.unit.test_scf_ladder import ladder
from tests.unit.test_scf_ladder import policy as historical_policy
from tests.unit.test_scf_ladder_inputs import source_text
from tools.fdebq_scf_ladder_campaign import (
    LadderReferenceInput,
    LadderReferenceReceipt,
    LadderRunInput,
    LadderRunReceipt,
    build_ladder_references,
    build_ladder_runs,
)
from tools.fdebq_validate_t0_t4 import validate_ladder_receipts


def protocol() -> ScfLadderProtocol:
    return ScfLadderProtocol(
        "scf-ladder-v2",
        True,
        (ScfLevel("L0", 1e-3, 1e-3), ScfLevel("L1", 1e-4, 1e-4), ScfLevel("L2", 1e-5, 1e-5)),
        2.0,
        0.8,
    )


def criteria_source(alpha_ev: float) -> str:
    return source_text(alpha_ev) + (
        "SCF.DM.Tolerance 1.0e-5\nSCF.H.Tolerance 0.0001 eV\n"
        "SCF.DM.Converge T\nSCF.H.Converge T\nSCF.EDM.Converge F\n"
        "SCF.FreeE.Converge F\nSCF.Harris.Converge F\n"
    )


def echo(level: ScfLevel, *, converged: bool = True) -> str:
    assert level.h_tolerance_ev is not None
    return (
        f"redata: DM tolerance for SCF = {level.dm_tolerance:.6f}\n"
        f"redata: Hamiltonian tolerance for SCF = {level.h_tolerance_ev:.6f} eV\n"
        "redata: Require DM convergence for SCF = T\n"
        "redata: Require H convergence for SCF = T\n"
        + ("SCF Convergence by DM criterion\n" if converged else "")
        + "siesta: normal completion\n"
    )


@pytest.mark.parametrize("field", ("dm_tolerance", "h_tolerance_ev"))
@pytest.mark.parametrize("value", (5e-7, 1.5e-6, float("nan"), float("inf")))
def test_v2_rejects_unprovable_tolerances(field: str, value: float) -> None:
    p = protocol()
    with pytest.raises(ScfLadderError):
        changed = (
            replace(p.levels[0], dm_tolerance=value)
            if field == "dm_tolerance"
            else replace(p.levels[0], h_tolerance_ev=value)
        )
        replace(p, levels=(changed, *p.levels[1:]))


def test_v2_requires_explicit_h_and_v1_is_not_production_evidence(tmp_path: Path) -> None:
    p = protocol()
    with pytest.raises(ScfLadderError, match="explicit h_tolerance_ev"):
        replace(p, levels=(ScfLevel("L0", 1e-3), *p.levels[1:]))
    mapping = historical_policy().to_mapping()
    rows = mapping["levels"]
    assert isinstance(rows, list)
    for row in rows:
        assert isinstance(row, dict)
        row.pop("h_tolerance_ev")
    old = ScfLadderProtocol.from_mapping(mapping)
    assert old.status is ScfStatus.NOT_ESTABLISHED
    assert old.reason_codes == (ScfReason.SCF_LADDER_PROTOCOL_V1,)
    parent = tmp_path / "toy.DM"
    parent.write_bytes(b"parent")
    asset = tmp_path / "toy.psml"
    asset.write_bytes(b"pseudopotential")
    inputs = []
    for index, alpha in enumerate((-0.08, -0.01, 0.01, 0.08)):
        source = tmp_path / f"source{index}.fdf"
        source.write_text(source_text(alpha), encoding="utf-8")
        inputs.append(
            LadderRunInput("toy", ResponseMode.SCREENED, alpha, str(source), str(parent), (str(asset),))
        )
    with pytest.raises(ScfLadderError, match="SCF_LADDER_PROTOCOL_V1"):
        build_ladder_runs(tuple(inputs), old, tmp_path / "rejected")
    assert validate_ladder_receipts(old, (), ()).reason_codes == old.reason_codes
    with pytest.raises(ScfLadderError, match="SCF_LADDER_PROTOCOL_V1"):
        estimate_ladder(ladder(), replace(old, version="scf-ladder-v1"))


def test_reference_materializer_rejects_unsafe_restart_before_parsing(tmp_path: Path) -> None:
    source = tmp_path / "unsafe-reference.fdf"
    source.write_text("file_dm_init parent.DM\n", encoding="utf-8")
    with pytest.raises(ScfLadderError, match="File.DM.Init"):
        materialize_ladder_reference(source, protocol().levels[0])


@pytest.mark.parametrize("h_tolerances", ((1e-4, 1e-4, 1e-6), (1e-4, 2e-4, 3e-4)))
def test_v2_requires_h_tolerances_to_tighten_with_dm(h_tolerances: tuple[float, float, float]) -> None:
    with pytest.raises(ScfLadderError, match="SCF H tolerances must strictly decrease"):
        ScfLadderProtocol(
            "scf-ladder-v2",
            True,
            tuple(
                ScfLevel(level_id, dm_tolerance, h_tolerance)
                for level_id, dm_tolerance, h_tolerance in zip(
                    ("L0", "L1", "L2"), (1e-3, 1e-4, 1e-5), h_tolerances
                )
            ),
            2.0,
            0.8,
        )


@given(st.integers(min_value=1, max_value=100_000))
def test_exact_six_decimal_level_roundtrip(units: int) -> None:
    level = ScfLevel("explicit", units / 1_000_000, units / 1_000_000)
    level.require_echo_representable()
    assert ScfLevel.from_mapping(json.loads(json.dumps(level.to_mapping()))) == level


def test_tolerances_replace_both_dm_spellings_and_record_criteria(tmp_path: Path) -> None:
    source = tmp_path / "source.fdf"
    source.write_text(criteria_source(0.01), encoding="utf-8")
    result = materialize_ladder_input(source, "toy", ResponseMode.SCREENED, 0.01, protocol().levels[1])
    assert _one(result.effective_text, "DM.Tolerance") is None
    assert _one(result.effective_text, "SCF.DM.Tolerance") == "0.000100"
    assert _one(result.effective_text, "SCF.H.Tolerance") == "0.000100 eV"
    assert dict(result.effective_criteria)["SCF.EDM.Converge"] == "F"
    assert dict(result.effective_criteria)["SCF.FreeE.Converge"] == "F"
    assert dict(result.effective_criteria)["SCF.Harris.Converge"] == "F"
    assert dict(result.effective_criteria)["MaxSCFIterations"] == "300"
    source.write_text(criteria_source(0.01).replace("SCF.DM.Tolerance", "scf_dm_tolerance"), encoding="utf-8")
    with pytest.raises(ScfLadderError, match="SCF.DM.Tolerance"):
        materialize_ladder_input(source, "toy", ResponseMode.SCREENED, 0.01, protocol().levels[1])


def test_reference_has_no_shift_and_preserves_block_payload(tmp_path: Path) -> None:
    source = tmp_path / "reference.fdf"
    source.write_text(
        criteria_source(0) + "%block LongOutput\nDFTU.PotentialShift true\nDM.Tolerance 42\n%endblock\n",
        encoding="utf-8",
    )
    materialized = materialize_ladder_reference(source, protocol().levels[1])
    assert _one(materialized.effective_text, "DFTU.PotentialShift") == "false"
    assert "DFTU.PotentialShift true\nDM.Tolerance 42" in materialized.effective_text
    source.write_text(criteria_source(0).replace("SCF.DM.Tolerance", "scf_dm_tolerance"), encoding="utf-8")
    with pytest.raises(FdfModelError) as error:
        materialize_ladder_reference(source, protocol().levels[1])
    assert error.value.code is FdfErrorCode.NONCANONICAL_MANAGED_LABEL


@pytest.mark.parametrize(
    ("old", "new", "reason"),
    (
        ("0.001000", "0.000999", ScfReason.SCF_LEVEL_NOT_APPLIED),
        ("0.001000", "0.0010001", ScfReason.SCF_LEVEL_NOT_APPLIED),
        (
            "Require H convergence for SCF = T",
            "Require H convergence for SCF = F",
            ScfReason.SCF_CRITERIA_NOT_ACTIVE,
        ),
    ),
)
def test_echo_mismatch_is_not_established(tmp_path: Path, old: str, new: str, reason: ScfReason) -> None:
    output = tmp_path / "siesta.out"
    output.write_text(echo(protocol().levels[0]).replace(old, new), encoding="utf-8")
    checked = validate_ladder_output(output, protocol().levels[0])
    assert checked.status is ScfStatus.NOT_ESTABLISHED
    assert reason in checked.reason_codes


def prepared_references(tmp_path: Path) -> tuple[LadderReferenceReceipt, ...]:
    source = tmp_path / "reference.fdf"
    source.write_text(criteria_source(0), encoding="utf-8")
    p = protocol()
    refs = build_ladder_references(
        tuple(LadderReferenceInput(level.level_id, str(source), ()) for level in p.levels),
        p,
        tmp_path / "references",
    )
    for reference in refs:
        level = next(level for level in p.levels if level.level_id == reference.level_id)
        directory = Path(reference.directory)
        (directory / "siesta.out").write_text(echo(level), encoding="utf-8")
        (directory / "toy.DM").write_bytes(reference.level_id.encode())
        assert (
            hashlib.sha256((directory / "input.fdf").read_bytes()).hexdigest()
            == reference.materialization.materialized_fdf_sha256
        )
        assert LadderReferenceReceipt.from_mapping(reference.to_mapping()) == reference
    return refs


def requests(
    tmp_path: Path, refs: tuple[LadderReferenceReceipt, ...], mode: ResponseMode
) -> tuple[LadderRunInput, ...]:
    inputs = []
    for reference in refs:
        for alpha in (-0.08, -0.01, 0.01, 0.08):
            source = tmp_path / f"{reference.level_id}-{alpha}.fdf"
            text = criteria_source(alpha)
            if mode is ResponseMode.BARE:
                text = Siesta542PotentialShiftHamiltonianProfile().materialize(text)
            source.write_text(text, encoding="utf-8")
            inputs.append(
                LadderRunInput(
                    "toy",
                    mode,
                    alpha,
                    str(source),
                    str(Path(reference.directory) / "toy.DM"),
                    (),
                    reference.level_id,
                )
            )
    return tuple(inputs)


@pytest.mark.parametrize("mode", (ResponseMode.BARE, ResponseMode.SCREENED))
def test_each_level_has_its_own_parent_and_validator_never_rehashes_run_dm(
    tmp_path: Path, mode: ResponseMode
) -> None:
    refs = prepared_references(tmp_path)
    p = protocol()
    runs = build_ladder_runs(requests(tmp_path, refs, mode), p, tmp_path / "runs", refs)
    assert len(runs) == 12
    assert len({r.parent_dm_sha256 for r in runs}) == 3
    for run in runs:
        directory = Path(run.directory)
        level = next(level for level in p.levels if level.level_id == run.level_id)
        if mode is ResponseMode.BARE:
            assert _one((directory / "input.fdf").read_text(encoding="utf-8"), "MaxSCFIterations") == "1"
        text = echo(level, converged=mode is ResponseMode.SCREENED)
        if mode is ResponseMode.BARE:
            text += "SCF_NOT_CONV\n"
        (directory / "siesta.out").write_text(text, encoding="utf-8")
        # Deliberately model SIESTA's overwrite. The frozen parent remains the reference bytes.
        (directory / "toy.DM").write_bytes(b"overwritten by the perturbed run")
        assert LadderRunReceipt.from_mapping(run.to_mapping()) == run
    assert validate_ladder_receipts(p, runs, refs).status is ScfStatus.ESTABLISHED


def test_screened_failure_marker_still_rejects_output(tmp_path: Path) -> None:
    refs = prepared_references(tmp_path)
    p = protocol()
    runs = build_ladder_runs(requests(tmp_path, refs, ResponseMode.SCREENED), p, tmp_path / "runs", refs)
    for run in runs:
        level = next(level for level in p.levels if level.level_id == run.level_id)
        (Path(run.directory) / "siesta.out").write_text(echo(level) + "SCF_NOT_CONV\n", encoding="utf-8")
    assert validate_ladder_receipts(p, runs, refs).reason_codes == (ScfReason.SCF_UNDER_RESOLVED,)


def test_bare_shared_parent_is_rejected_before_materialization(tmp_path: Path) -> None:
    refs = prepared_references(tmp_path)
    inputs = requests(tmp_path, refs, ResponseMode.BARE)
    for reference in refs:
        (Path(reference.directory) / "toy.DM").write_bytes(b"shared")
    output = tmp_path / "must-not-exist"
    with pytest.raises(ScfLadderError, match="PARENT_LEVEL_NOT_DISTINCT"):
        build_ladder_runs(inputs, protocol(), output, refs)
    assert not output.exists()


@pytest.mark.parametrize("failure", ("missing", "explicit"))
def test_reference_needs_positive_convergence_evidence(tmp_path: Path, failure: str) -> None:
    refs = prepared_references(tmp_path)
    reference = refs[0]
    level = next(level for level in protocol().levels if level.level_id == reference.level_id)
    text = echo(level, converged=failure == "explicit")
    if failure == "explicit":
        text += "SCF_NOT_CONV\n"
    output = Path(reference.directory) / "siesta.out"
    output.write_text(text, encoding="utf-8")
    result = validate_ladder_output(output, level, reference_fdf=Path(reference.directory) / "input.fdf")
    assert result.reason_codes == (ScfReason.LEVEL_REFERENCE_NOT_CONVERGED,)
    with pytest.raises(ScfLadderError, match="LEVEL_REFERENCE_NOT_CONVERGED"):
        build_ladder_runs(
            requests(tmp_path, refs, ResponseMode.BARE), protocol(), tmp_path / "rejected", refs
        )
