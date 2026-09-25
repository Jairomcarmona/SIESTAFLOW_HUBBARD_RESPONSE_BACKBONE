from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import shutil

import pytest


ROOT = Path(__file__).resolve().parents[2]
CAMPAIGN = ROOT / "campaigns" / "cu_one_atom_noise_calibrated_lr_v1"
RUNNER_PATH = ROOT / "tools" / "run_preregistered_cu_one_atom_campaign.py"
SPEC = importlib.util.spec_from_file_location("predeclared_cu_campaign", RUNNER_PATH)
RUNNER = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(RUNNER)


def _json(relative):
    return json.loads((CAMPAIGN / relative).read_text(encoding="utf-8"))


def test_static_campaign_is_admitted_without_a_calibration_result():
    admitted = RUNNER.verify_package(require_result=False)
    assert admitted["status"] == "ADMITTED"
    assert admitted["calibration_result"] == "absent"


def test_lock_and_plan_strictly_separate_calibration_from_response_mesh():
    calibration = _json("locks/calibration-methodology-lock.json")
    response = _json("locks/response-methodology-lock.json")
    response_plan = _json("plans/response-plan.json")
    assert calibration["calibration"]["replica_count"] == 5
    assert calibration["calibration"]["control_alpha_ev"] == 0.0
    assert calibration["calibration"]["deterministic_floor_e"] >= calibration["calibration"]["output_quantum_e"]
    assert response["occupation_noise_source"]["forbid_numeric_literal_here"] is True
    assert len(response_plan["responses"]) == 12
    assert all(item["alpha_ev"] != 0.0 for item in response_plan["responses"])


def test_fdf_hash_and_recorded_native_six_decimal_format_evidence_are_locked():
    fdf = CAMPAIGN / "inputs/reference.fdf"
    expected = _json("locks/response-methodology-lock.json")["input_provenance"]["reference_fdf_sha256"]
    assert sha256(fdf.read_bytes()).hexdigest() == expected
    evidence = _json("locks/calibration-methodology-lock.json")["calibration"]["output_quantum_evidence"]
    assert "5 decimal places" in evidence
    assert "5e-5 e" in evidence


def test_response_admission_fails_closed_without_external_result():
    with pytest.raises(ValueError, match="calibration result is required"):
        RUNNER.verify_package(require_result=True)


def test_calibration_submit_dry_run_has_five_separate_four_rank_slurm_jobs():
    plan = RUNNER.submit_calibration(dry_run=True)
    assert plan["status"] == "DRY_RUN"
    assert len(plan["commands"]) == 5
    assert all(command[:8] == ["sbatch", "--wait", "--parsable", "-p", "local", "-N", "1", "-n"]
               for command in plan["commands"])
    assert all("-n" in command and command[command.index("-n") + 1] == "4" for command in plan["commands"])


def _archived_output_templates():
    runs = ROOT / "docs/evidence/siesta542_openmpi_slurm_full_campaign_20260920_run2_wheel/runs"
    reference = next((runs / "reference").rglob("siesta.out")).parent
    bare = next((runs / "responses").glob("*BARE_p0p025*"))
    screened = next((runs / "responses").glob("*SCREENED_p0p025*"))
    return {"reference": reference, "response:BARE_zero": bare, "response:SCREENED_zero": screened}


def _write_structural_replica_fixture(campaign, index, *, restart=None, duplicate_job=False, tamper_output=False,
                                      nonconverged_screened=False, mutate_child_fdf=False):
    """Construct nonphysical binder fixtures from archived output syntax.

    These edited files test fail-closed structure and parser behavior only;
    they are never physical calibration evidence or a claimed SIESTA run.
    """
    lock = json.loads((campaign / "locks/calibration-methodology-lock.json").read_text())
    root = campaign / "results/calibration-replicas" / f"replica-{index:02d}"
    sources = _archived_output_templates()
    output_paths, fdf_paths = {}, {}
    for node, source in sources.items():
        target = root / "runs" / node.replace(":", "_") / "siesta.out"
        target.parent.mkdir(parents=True, exist_ok=True)
        output_text = (source / "siesta.out").read_text(encoding="utf-8", errors="replace")
        reference_text = (campaign / "inputs/reference.fdf").read_text(encoding="utf-8", errors="replace")
        if node == "reference":
            fdf_text = reference_text
        else:
            fdf_text = RUNNER._expected_zero_control_fdf(node, reference_text)
            if mutate_child_fdf and node == "response:SCREENED_zero":
                fdf_text = fdf_text.replace("MeshCutoff          100.0 Ry", "MeshCutoff          90.0 Ry")
        dump_start = "************************** Dump of input data file ****************************"
        dump_end = "************************** End of input data file *****************************"
        assert output_text.count(dump_start) == output_text.count(dump_end) == 1
        output_text = output_text.split(dump_start, 1)[0] + dump_start + "\n" + fdf_text.rstrip() + "\n" + dump_end + output_text.split(dump_end, 1)[1]
        if nonconverged_screened and node == "response:SCREENED_zero":
            output_text = output_text.replace("Job completed", "SCF_NOT_CONV\nJob completed")
        target.write_text(output_text, encoding="utf-8")
        fdf_target = target.with_name("siesta.fdf"); fdf_target.write_text(fdf_text, encoding="utf-8")
        output_paths[node] = target
        fdf_paths[node] = fdf_target
    if tamper_output:
        output_paths["reference"].write_text("forged output", encoding="utf-8")
    dm = root / "reference.DM"; dm.write_bytes(f"real-replica-parent-{index}".encode())
    dm_sha = sha256(dm.read_bytes()).hexdigest()
    pseudo = root / "inputs/Cu1.psml"; pseudo.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "examples/tmo_campaigns/Cu1.psml", pseudo)
    nodes = ("reference", "response:BARE_zero", "response:SCREENED_zero")
    argv = [lock["runtime"]["mpi_launcher"], "--host", "test-host:4", "--map-by", "ppr:4:node",
            "-np", "4", lock["runtime"]["siesta_executable"]]
    digests = {}
    for node in nodes:
        is_reference = node == "reference"
        mode = None if is_reference else ("BARE" if "BARE" in node else "SCREENED")
        semantic = {"node_kind": "REFERENCE" if is_reference else "PERTURBATION"}
        if mode is not None:
            semantic["response_mode"] = mode
            semantic["reference_dm_sha256"] = dm_sha
        if node == "response:BARE_zero":
            semantic["reference_dm_sha256"] = dm_sha
            semantic["bare_profile"] = "siesta-5.4.2-potential-shift-hamiltonian-v1"
        perturbation = None if is_reference else {"run_id": f"{mode}_zero", "orbit_id": "orbit_001",
            "site_index": 0, "site_id": "Cu1", "mode": mode, "alpha_ev": 0.0,
            "purpose": "independent_zero_shift_control"}
        provenance_payload = {"schema": "siestaflow-siesta-node-evidence-v1", "node_id": node,
                      "node": {"node_id": node, "kind": "REFERENCE" if is_reference else "PERTURBATION",
                               "dependencies": [] if is_reference else ["reference"], "perturbation": perturbation},
                      "artifacts": {"fdf": sha256(fdf_paths[node].read_bytes()).hexdigest(),
                      "output": sha256(output_paths[node].read_bytes()).hexdigest(), "dm": dm_sha},
                      "semantic": semantic}
        digest = sha256(json.dumps({"node_id": node, "argv": argv, "payload": provenance_payload},
                                   sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()
        digests[node] = digest
        provenance = {**provenance_payload, "evidence_digest": digest}
        path = root / "provenance" / (node.replace(":", "_") + ".json")
        path.parent.mkdir(parents=True, exist_ok=True); path.write_text(json.dumps(provenance), encoding="utf-8")
    receipts = [{"node_id": node, "state": "VALIDATED", "evidence_digest": digests[node]} for node in nodes]
    receipts_path = root / "receipts.json"; receipts_path.write_text(json.dumps(receipts), encoding="utf-8")
    profile = {"runtime": {"launcher": {"processes_per_node": 4}}, "allocation": {"total_cpus": 4}}
    commands = [{"node_id": node, "argv": argv, "stdin_path": str(fdf_paths[node]), "stdout_path": str(output_paths[node]),
                 "dm_path": str(dm),
                 "stdin_sha256_before_execution": sha256(fdf_paths[node].read_bytes()).hexdigest(),
                 "parent_reference_dm_sha256_before_execution": None if node == "reference" else dm_sha} for node in nodes]
    result = {"schema": "siestaflow-calibration-replica-v2", "replica_id": f"replica-{index:02d}",
              "slurm_job_id": "700" if duplicate_job else str(700 + index), "slurm_restart_count": restart,
              "alpha_ev": 0.0, "validated": True, "occupations": {"forged": 0.0}, "receipts_path": "receipts.json",
              "receipts_sha256": sha256(receipts_path.read_bytes()).hexdigest(), "reference_dm_path": str(dm),
              "reference_dm_sha256": dm_sha, "pseudo_path": str(pseudo),
              "parent_dm_sha256": {"BARE": dm_sha, "SCREENED": dm_sha}, "commands": commands,
              "execution_profile": profile, "reference_fdf_sha256": lock["input_provenance"]["reference_fdf_sha256"],
              "pseudo_sha256": lock["input_provenance"]["pseudo_sha256"], "siesta_sha256": lock["runtime"]["siesta_sha256"],
              "mpi_launcher": lock["runtime"]["mpi_launcher"], "mpi_launcher_sha256": lock["runtime"]["mpi_launcher_sha256"]}
    path = root / "replica-result.json"; path.write_text(json.dumps(result), encoding="utf-8")
    return path


def _real_receipt_input(tmp_path, monkeypatch, **kwargs):
    isolated = tmp_path / "campaign"; shutil.copytree(CAMPAIGN, isolated)
    monkeypatch.setattr(RUNNER, "CAMPAIGN", isolated)
    paths = [_write_structural_replica_fixture(isolated, index, **kwargs) for index in range(1, 6)]
    raw = tmp_path / "real-receipts.json"; raw.write_text(json.dumps({"replica_result_paths": [str(path) for path in paths]}), encoding="utf-8")
    return isolated, raw, paths


def test_bind_reparses_structural_output_fixtures_and_never_uses_declared_scalars(tmp_path, monkeypatch):
    _, raw, _ = _real_receipt_input(tmp_path, monkeypatch)
    bound = RUNNER.bind_calibration(raw)
    assert bound["occupation_noise_e"] >= 5e-5
    assert bound["occupation_noise_e"] != 1e-99
    assert RUNNER.verify_package(require_result=True)["calibration_result"] == "bound"


@pytest.mark.parametrize("kwargs", [
    {"duplicate_job": True}, {"restart": "1"}, {"tamper_output": True},
    {"nonconverged_screened": True}, {"mutate_child_fdf": True},
])
def test_bind_rejects_duplicate_job_retry_or_forged_output(tmp_path, monkeypatch, kwargs):
    _, raw, _ = _real_receipt_input(tmp_path, monkeypatch, **kwargs)
    with pytest.raises(ValueError):
        RUNNER.bind_calibration(raw)


def test_response_admission_reopens_and_rehashes_bound_replica_evidence(tmp_path, monkeypatch):
    isolated, raw, paths = _real_receipt_input(tmp_path, monkeypatch)
    RUNNER.bind_calibration(raw)
    replica = json.loads(paths[0].read_text(encoding="utf-8"))
    output = Path(replica["commands"][0]["stdout_path"])
    output.write_text(output.read_text(encoding="utf-8") + "\npost-bind tamper\n", encoding="utf-8")
    with pytest.raises(ValueError):
        RUNNER.verify_package(require_result=True)


def test_bound_result_cannot_be_overwritten_and_response_freezes_hashes(tmp_path, monkeypatch):
    _, raw, _ = _real_receipt_input(tmp_path, monkeypatch)
    RUNNER.bind_calibration(raw)
    with pytest.raises(ValueError, match="refusing to overwrite"):
        RUNNER.bind_calibration(raw)
    response = RUNNER.submit_response(dry_run=True)
    assert response["status"] == "DRY_RUN"
    assert "--export=NONE,OMP_NUM_THREADS=1" in response["command"]
    wrap = response["command"][-1]
    assert "--expected-calibration-result-sha256" in wrap
    assert "--expected-calibration-lock-sha256" in wrap
    assert "env -u PYTHONPATH" in wrap


@pytest.mark.parametrize("mutation", [
    lambda payload: payload.update({"occupation_noise_e": 1e-99}),
    lambda payload: payload.update({"unexpected": "forged"}),
    lambda payload: payload["replica_receipts"][0].update({"receipts_sha256": "not-a-hash"}),
])
def test_central_result_validator_rejects_floor_json_and_hash_forgery(tmp_path, monkeypatch, mutation):
    isolated, raw, _ = _real_receipt_input(tmp_path, monkeypatch)
    RUNNER.bind_calibration(raw)
    result_path = isolated / "results/calibration-result.json"
    payload = json.loads(result_path.read_text()); mutation(payload)
    result_path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError):
        RUNNER.verify_package(require_result=True)


def test_strict_json_rejects_nonfinite_constants(tmp_path):
    from siestaflow_hubbard.domain.occupation_noise_calibration import load_strict_json
    bad = tmp_path / "bad.json"; bad.write_text('{"value": NaN}', encoding="utf-8")
    with pytest.raises(ValueError, match="non-finite JSON"):
        load_strict_json(bad)
