from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace

from siestaflow_hubbard.execution.campaign_runner import CampaignRunner
from siestaflow_hubbard.execution.dag_contract import NodeState
from siestaflow_hubbard.execution.generic_executor import NodeReceipt


class _Checkpoint:
    def __init__(self, receipts):
        self.receipts = receipts

    def load(self):
        return self.receipts


def _source(root: Path, node_id: str, mode: str, attempt_suffix: str, receipts, records):
    node_key = sha256(node_id.encode()).hexdigest()[:20]
    attempt = root / ".siestaflow" / "attempts" / node_key / f"attempt-123456-{attempt_suffix}"
    attempt.mkdir(parents=True)
    fdf = attempt / "run.fdf"
    output = attempt / "run.out"
    dm = attempt / "run.DM"
    fdf.write_bytes(b"same deterministic FDF")
    output.write_bytes(b"same deterministic output")
    dm.write_bytes(b"same deterministic DM")
    hashes = {
        "fdf": sha256(fdf.read_bytes()).hexdigest(),
        "output": sha256(output.read_bytes()).hexdigest(),
        "dm": sha256(dm.read_bytes()).hexdigest(),
    }
    evidence_digest = sha256(node_id.encode()).hexdigest()
    records[node_id] = {
        "state": NodeState.VALIDATED.value,
        "kind": "siesta",
        "scf_level_id": "strict",
        "evidence_digest": evidence_digest,
        "command": {
            "cwd": str(attempt), "stdin_path": str(fdf), "stdout_path": str(output),
        },
        "artifact_spec": {"dm": "run.DM"},
        "provenance": {"artifacts": hashes},
    }
    receipts[node_id] = NodeReceipt(node_id, NodeState.VALIDATED, evidence_digest)
    return {
        "node_id": node_id,
        "mode": mode,
        "state": NodeState.VALIDATED.value,
        "evidence_digest": evidence_digest,
        "fdf_path": fdf.relative_to(root).as_posix(),
        "fdf_sha256": hashes["fdf"],
        "out_path": output.relative_to(root).as_posix(),
        "out_sha256": hashes["output"],
        "dm_path": dm.relative_to(root).as_posix(),
        "dm_sha256": hashes["dm"],
    }


def test_runtime_identity_uses_only_receipted_active_grid_and_scf_level(tmp_path: Path) -> None:
    root = tmp_path.resolve()
    runner = CampaignRunner.__new__(CampaignRunner)
    runner.root = root
    runner.sites = [{"index": 0, "site_id": "NiLR0", "atom_index": 0}]
    runner.records = {}
    receipts = {}
    runner.executor = SimpleNamespace(checkpoint=_Checkpoint(receipts))

    reference = _source(root, "reference:strict", "REFERENCE_SCREENED", "aaaaaaaa", receipts, runner.records)
    bare = _source(root, "response:strict:bare", "BARE", "bbbbbbbb", receipts, runner.records)
    screened = _source(root, "response:strict:screened", "SCREENED", "cccccccc", receipts, runner.records)
    # An unrelated node from another active level/grid must not leak into this
    # analysis identity: only IDs in the verified observation dataset count.
    _source(root, "response:base:inactive", "SCREENED", "dddddddd", receipts, runner.records)
    runner.records["response:base:inactive"]["scf_level_id"] = "base"

    dataset = {
        "reference_source": reference,
        "rows": [{
            "perturbed_site_index": 0,
            "alpha_eV": 0.1,
            "sources": {"bare": bare, "screened": screened},
        }],
    }
    identity = runner._analysis_execution_identity(dataset, scf_level_id="strict", alpha_grid=[0.1])

    assert identity["source_root"] == str(root)
    assert set(identity["execution_attempt_ids"]) == {
        "attempt-123456-aaaaaaaa", "attempt-123456-bbbbbbbb", "attempt-123456-cccccccc",
    }
