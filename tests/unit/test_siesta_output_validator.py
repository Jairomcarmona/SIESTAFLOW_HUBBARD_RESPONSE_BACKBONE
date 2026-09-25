import json
from hashlib import sha256
from pathlib import Path
from subprocess import CompletedProcess

import pytest

from siestaflow_hubbard.execution.lr_dag import LRDagNode, LRNodeKind
from siestaflow_hubbard.execution.runtime_adapters import NodeCommand
from siestaflow_hubbard.domain.symmetry_reduction import PerturbationSpec, ResponseMode
from siestaflow_hubbard.siesta_backend.output_validator import (
    SiestaArtifactSpec,
    SiestaOutputValidationError,
    SiestaOutputValidator,
    SiestaValidationPolicy,
)
from siestaflow_hubbard.domain.backend_compatibility import (
    BackendCompatibilityRegistry, BackendIdentity, CompatibilityRecord,
    CompatibilityState, ScientificProfile,
)
from siestaflow_hubbard.siesta_backend.backend_admission import admit_siesta542_potential_shift_hamiltonian
from siestaflow_hubbard.siesta_backend.backend_admission_plugin import admit_siesta542_from_campaign_contract
from siestaflow_hubbard.siesta_backend.backend_identity import sha256_file
from siestaflow_hubbard.domain.lr_campaign_contract import LinearResponseBareCampaignContract
from siestaflow_hubbard.siesta_backend.siesta542_bare_profile import Siesta542PotentialShiftHamiltonianProfile


def _digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _completed() -> CompletedProcess[str]:
    return CompletedProcess(("siesta",), 0, "", "")


def _screened_node(node_id: str = "response:screened") -> LRDagNode:
    spec = PerturbationSpec("screened", "orbit", 0, "M0", ResponseMode.SCREENED, 0.05, "representative")
    return LRDagNode(node_id, LRNodeKind.PERTURBATION, ("reference",), spec)


def _production_validator(tmp_path: Path, artifacts: dict[str, SiestaArtifactSpec]) -> tuple[SiestaOutputValidator, Path]:
    """Build an actual campaign-contract admission for validator tests."""
    executable = tmp_path / "siesta"; executable.write_bytes(b"fixture executable")
    profile = Siesta542PotentialShiftHamiltonianProfile()
    private = tmp_path / "private"; private.mkdir()
    (private / "backend.json").write_text(json.dumps({
        "schema": "backend_compatibility_v1", "records": [{
            "backend": {"backend_id": "siesta", "version": "5.4.2", "executable_sha256": sha256_file(executable)},
            "profile": {"profile_id": profile.profile_id, "version": profile.profile_version,
                        "metadata": {"source_revision": profile.source_revision}},
            "state": "compatible", "reason": "fixture",
        }],
    }), encoding="utf-8")
    (private / "version.txt").write_text("SIESTA Version : 5.4.2\n", encoding="utf-8")
    contract = LinearResponseBareCampaignContract(
        campaign_id="fixture", scientific_profile=ScientificProfile(profile.profile_id, profile.profile_version),
        compatibility_registry="private/backend.json", declared_executable=executable.name,
        version_text_source="private/version.txt",
    )
    admission = admit_siesta542_from_campaign_contract(
        campaign_root=tmp_path, contract=contract, executable_path=executable, profile=profile,
    )
    return SiestaOutputValidator(artifacts, policy=SiestaValidationPolicy(
        siesta_version=admission.observed.version, bare_profile=profile, bare_backend_admission=admission,
    )), executable


def _command(tmp_path: Path, executable: Path, fdf: str, output: str) -> NodeCommand:
    return NodeCommand(
        (str(executable),), tmp_path,
        stdin_path=tmp_path / fdf, stdout_path=tmp_path / output,
    )


def test_screened_requires_fdf_output_dm_and_normal_scf(tmp_path: Path):
    (tmp_path / "run.fdf").write_text("NumberOfAtoms 1\n")
    (tmp_path / "run.out").write_text("SCF: converged\nsiesta: normal completion\n")
    (tmp_path / "run.DM").write_bytes(b"dm")
    (tmp_path / "reference.DM").write_bytes(b"parent dm")
    node = _screened_node()
    validator, executable = _production_validator(tmp_path, {node.node_id: SiestaArtifactSpec("run.fdf", "run.out", "run.DM", str(tmp_path / "siesta"), "reference.DM")})
    receipt = validator.validate(node, _command(tmp_path, executable, "run.fdf", "run.out"), _completed())
    assert receipt.state.value == "VALIDATED"
    assert len(receipt.evidence_digest) == 64
    assert validator.last_provenance["semantic"]["response_mode"] == "SCREENED"
    assert validator.last_provenance["semantic"]["reference_dm_sha256"] == sha256_file(tmp_path / "reference.DM")


def test_screened_rejects_normal_exit_without_dm(tmp_path: Path):
    (tmp_path / "run.fdf").write_text("NumberOfAtoms 1\n")
    (tmp_path / "run.out").write_text("siesta: normal completion\n")
    (tmp_path / "reference.DM").write_bytes(b"parent dm")
    node = _screened_node()
    validator, executable = _production_validator(tmp_path, {node.node_id: SiestaArtifactSpec("run.fdf", "run.out", "run.DM", str(tmp_path / "siesta"), "reference.DM")})
    with pytest.raises(SiestaOutputValidationError, match="DM"):
        validator.validate(node, _command(tmp_path, executable, "run.fdf", "run.out"), _completed())


def test_reference_requires_magnetic_or_explicit_nonpolarized_evidence(tmp_path: Path):
    (tmp_path / "reference.fdf").write_text("NumberOfAtoms 1\nSpin non-polarized\n")
    (tmp_path / "reference.out").write_text(
        "redata: Spin configuration = none\n"
        "redata: Number of spin components = 1\n"
        "redata: Time-Reversal Symmetry = T\n"
        "siesta: normal completion\n"
    )
    (tmp_path / "reference.DM").write_bytes(b"dm")
    node = LRDagNode("reference", LRNodeKind.REFERENCE, ())
    validator, executable = _production_validator(tmp_path, {"reference": SiestaArtifactSpec("reference.fdf", "reference.out", "reference.DM", str(tmp_path / "siesta"))})
    receipt = validator.validate(node, _command(tmp_path, executable, "reference.fdf", "reference.out"), _completed())
    assert receipt.state.value == "VALIDATED"
    assert validator.last_provenance["semantic"]["magnetic_parser"] == "siesta_5_4_explicit_nonpolarized_v1"


def test_unknown_mode_is_rejected_even_with_normal_exit(tmp_path: Path):
    (tmp_path / "run.fdf").write_text("NumberOfAtoms 1\n")
    (tmp_path / "run.out").write_text("siesta: normal completion\n")
    (tmp_path / "run.DM").write_bytes(b"dm")
    bad = PerturbationSpec("bad", "orbit", 0, "M0", "SOC", 0.05, "representative")
    node = LRDagNode("response:bad", LRNodeKind.PERTURBATION, ("reference",), bad)
    validator, executable = _production_validator(tmp_path, {node.node_id: SiestaArtifactSpec("run.fdf", "run.out", "run.DM", str(tmp_path / "siesta"))})
    with pytest.raises(SiestaOutputValidationError, match="only BARE and SCREENED"):
        validator.validate(node, _command(tmp_path, executable, "run.fdf", "run.out"), _completed())


def test_malformed_perturbation_node_fails_closed_with_contract_error(tmp_path: Path):
    (tmp_path / "run.fdf").write_text("NumberOfAtoms 1\n")
    (tmp_path / "run.out").write_text("siesta: normal completion\n")
    (tmp_path / "run.DM").write_bytes(b"dm")
    node = LRDagNode("response:malformed", LRNodeKind.PERTURBATION, ("reference",), None)
    validator, executable = _production_validator(tmp_path, {node.node_id: SiestaArtifactSpec("run.fdf", "run.out", "run.DM", str(tmp_path / "siesta"))})
    with pytest.raises(SiestaOutputValidationError, match="no perturbation specification"):
        validator.validate(node, _command(tmp_path, executable, "run.fdf", "run.out"), _completed())


def test_bare_rejects_a_legacy_validator_without_profile_and_admission(tmp_path: Path):
    executable = tmp_path / "siesta"; executable.write_bytes(b"fixture executable")
    reference_dm = tmp_path / "reference.DM"; reference_dm.write_bytes(b"parent dm")
    fdf = tmp_path / "bare.fdf"; fdf.write_text("SCF.MustConverge F\n")
    output = tmp_path / "bare.out"; output.write_text("hubbard_term: recalculating local occupations\n>> End of run\n")
    (tmp_path / "bare.DM").write_bytes(b"child dm")
    node = LRDagNode(
        "response:bare", LRNodeKind.PERTURBATION, ("reference",),
        PerturbationSpec("bare", "orbit", 0, "M0", ResponseMode.BARE, 0.05, "representative"),
    )
    validator = SiestaOutputValidator({node.node_id: SiestaArtifactSpec(
        "bare.fdf", "bare.out", "bare.DM", str(executable), "reference.DM"
    )})
    with pytest.raises(SiestaOutputValidationError, match="campaign contract"):
        validator.validate(node, NodeCommand(("fixture", str(executable)), tmp_path), _completed())


def test_bare_rejects_permissive_policy_without_profile_and_admission(tmp_path: Path):
    (tmp_path / "bare.fdf").write_text("SCF.MustConverge F\n")
    (tmp_path / "bare.out").write_text("hubbard_term: recalculating local occupations\n>> End of run\n")
    (tmp_path / "bare.DM").write_bytes(b"child dm")
    node = LRDagNode(
        "response:bare-permissive", LRNodeKind.PERTURBATION, ("reference",),
        PerturbationSpec("bare", "orbit", 0, "M0", ResponseMode.BARE, 0.05, "representative"),
    )
    with pytest.raises(TypeError):
        SiestaValidationPolicy(require_bare_semantic_trace=False)
    validator = SiestaOutputValidator({node.node_id: SiestaArtifactSpec("bare.fdf", "bare.out", "bare.DM")})
    with pytest.raises(SiestaOutputValidationError, match="campaign contract"):
        validator.validate(node, NodeCommand(("fixture",), tmp_path), _completed())


@pytest.mark.parametrize("node", [
    LRDagNode("reference-no-admission", LRNodeKind.REFERENCE, ()),
    _screened_node("screened-no-admission"),
])
def test_public_validator_rejects_reference_and_screened_without_campaign_admission(
    tmp_path: Path, node: LRDagNode,
):
    prefix = "reference" if node.kind is LRNodeKind.REFERENCE else "screened"
    (tmp_path / f"{prefix}.fdf").write_text("Spin non-polarized\n", encoding="utf-8")
    (tmp_path / f"{prefix}.out").write_text("siesta: normal completion\n", encoding="utf-8")
    (tmp_path / f"{prefix}.DM").write_bytes(b"dm")
    validator = SiestaOutputValidator({node.node_id: SiestaArtifactSpec(
        f"{prefix}.fdf", f"{prefix}.out", f"{prefix}.DM"
    )})
    with pytest.raises(SiestaOutputValidationError, match="campaign contract"):
        validator.validate(node, NodeCommand(("fixture",), tmp_path), _completed())


def test_low_level_registry_admission_cannot_authorize_public_bare_validation(tmp_path: Path):
    executable = tmp_path / "siesta"; executable.write_bytes(b"fixture executable")
    profile = Siesta542PotentialShiftHamiltonianProfile()
    scientific = ScientificProfile(profile.profile_id, profile.profile_version, {"source_revision": profile.source_revision})
    registry = BackendCompatibilityRegistry((CompatibilityRecord(
        BackendIdentity("siesta", "5.4.2", sha256_file(executable)), scientific,
        CompatibilityState.COMPATIBLE, "fixture",
    ),))
    admission = admit_siesta542_potential_shift_hamiltonian(
        executable, "Version : 5.4.2", registry, profile,
    )
    fdf = tmp_path / "bare.fdf"; fdf.write_text(profile.materialize("SystemLabel fixture\n"))
    example = (Path(__file__).resolve().parents[2] / "examples" / "MnO_BARE_+0.05.out").read_text(encoding="utf-8")
    cleaned = example.replace("SCF_NOT_CONV", "SCF_STATUS").replace("ABNORMAL_TERMINATION", "TERMINATION")
    (tmp_path / "bare.out").write_text(cleaned + "\nsiesta: normal completion\n")
    (tmp_path / "bare.DM").write_bytes(b"child dm")
    (tmp_path / "reference.DM").write_bytes(b"parent dm")
    node = LRDagNode(
        "response:bare-profile", LRNodeKind.PERTURBATION, ("reference",),
        PerturbationSpec("bare", "orbit", 0, "M0", ResponseMode.BARE, 0.05, "representative"),
    )
    validator = SiestaOutputValidator({node.node_id: SiestaArtifactSpec(
        "bare.fdf", "bare.out", "bare.DM", str(executable), "reference.DM"
    )}, policy=SiestaValidationPolicy(
        bare_profile=profile, bare_backend_admission=admission,
    ))
    with pytest.raises(SiestaOutputValidationError, match="campaign contract"):
        validator.validate(node, NodeCommand(("fixture", str(executable)), tmp_path), _completed())
