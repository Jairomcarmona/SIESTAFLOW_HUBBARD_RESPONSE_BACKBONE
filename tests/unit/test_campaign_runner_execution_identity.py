from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace

from hubbardflow.execution.campaign_runner import CampaignRunner
from hubbardflow.execution.dag_contract import NodeState
from hubbardflow.execution.generic_executor import NodeReceipt
from hubbardflow.execution.campaign_store import CampaignStore


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
    runner.store = CampaignStore(root / "node-evidence.json", lambda: runner.executor.checkpoint)

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


def test_revalidation_persists_hash_warnings_without_any_invalidation(tmp_path: Path) -> None:
    import json
    from hubbardflow.execution.lr_dag import LRDag, LRDagNode, LRNodeKind

    evidence_path = tmp_path / "analysis.json"
    evidence_path.write_text("{}", encoding="utf-8")
    runner = CampaignRunner.__new__(CampaignRunner)
    runner.control = tmp_path / ".siestaflow"
    runner.campaign = {"campaign_id": "synthetic", "input_identity": "a" * 64}
    runner.adaptive_policy_digest = None
    runner.adaptive_policy = None
    runner.shadow = None
    runner.dag = LRDag((LRDagNode("matrix-analysis", LRNodeKind.MATRIX_ANALYSIS, ()),), False)
    receipts = {"matrix-analysis": NodeReceipt("matrix-analysis", NodeState.VALIDATED, "a" * 64)}
    runner.executor = SimpleNamespace(checkpoint=_Checkpoint(receipts))
    runner.records = {
        "matrix-analysis": {
            "evidence_path": str(evidence_path),
            "evidence_digest": "b" * 64,
            "evidence_sha256": "c" * 64,
        }
    }
    runner.store = CampaignStore(tmp_path / "node-evidence.json", lambda: runner.executor.checkpoint)
    runner._revalidate_reuse()
    restored = json.loads(runner.store.records_path.read_text(encoding="utf-8"))
    assert restored["nodes"]["matrix-analysis"]["traceability_warnings"] == [
        "NODE_EVIDENCE_DIGEST_MISMATCH",
        "EVIDENCE_FILE_DIGEST_MISMATCH",
        "RECEIPT_EVIDENCE_DIGEST_MISMATCH",
    ]
    assert runner.checkpoint() == receipts
