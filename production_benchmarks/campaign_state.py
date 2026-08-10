"""
production_benchmarks/campaign_state.py

Real persistent, resumable campaign state.
Atomic state writes via write-temp/rename pattern.
All methods fully implemented.
"""
from __future__ import annotations
import hashlib
import json
import os
import tempfile
from typing import Any, Dict, List, Optional, Set


# ─────────────────────────────────────────────────────────────────────────────
# State file path
# ─────────────────────────────────────────────────────────────────────────────

STATE_FILENAME = "campaign_state.json"


class CampaignState:
    """
    Persistent campaign state keyed by calculation identity fingerprints.

    Atomic writes:
      1. Serialize to a temp file in the same directory
      2. Flush + sync
      3. Rename (atomic on POSIX; best-effort on Windows)
    """

    def __init__(self, campaign_dir: str):
        self.campaign_dir = os.path.abspath(campaign_dir)
        self._state_path = os.path.join(self.campaign_dir, STATE_FILENAME)

        self.completed:          Dict[str, Dict[str, Any]] = {}
        self.failed:             Dict[str, str] = {}
        self.reference_dm_sha256: Optional[str] = None
        self.current_dag_node:   str = ""
        self.material_statuses:  Dict[str, str] = {}
        self.current_accepted_configuration: Dict[str, Dict[str, Any]] = {}

        # Load existing state if present
        if os.path.exists(self._state_path):
            self.load()

    # ─── Public API ───────────────────────────────────────────────────────

    def mark_complete(self, key: str, result_dict: Dict[str, Any]) -> None:
        """Record a successful calculation."""
        self.completed[key] = result_dict
        # Remove from failed if it was previously failed and retried
        self.failed.pop(key, None)
        self.save()

    def mark_failed(self, key: str, err: str) -> None:
        """Record a failed calculation."""
        self.failed[key] = err
        self.save()

    def is_complete(self, key: str) -> bool:
        """Return True if key has a successful completion record."""
        return key in self.completed

    def save(self) -> None:
        """Write state atomically to disk."""
        os.makedirs(self.campaign_dir, exist_ok=True)

        payload = {
            "completed":           self.completed,
            "failed":              self.failed,
            "reference_dm_sha256": self.reference_dm_sha256,
            "current_dag_node":    self.current_dag_node,
            "material_statuses":   self.material_statuses,
            "current_accepted_configuration": self.current_accepted_configuration,
        }
        data = json.dumps(payload, indent=2, sort_keys=True)

        # Atomic write: temp -> rename
        fd, tmp_path = tempfile.mkstemp(
            dir=self.campaign_dir, suffix=".tmp", prefix=".campaign_state_"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(data)
                fh.flush()
                os.fsync(fh.fileno())
            # Rename into final position (atomic on POSIX, best-effort on Windows)
            os.replace(tmp_path, self._state_path)
        except Exception:
            # Clean up temp file on failure
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    def load(self) -> None:
        """Load state from disk."""
        with open(self._state_path, "r", encoding="utf-8") as fh:
            payload = json.load(fh)

        self.completed            = payload.get("completed", {})
        self.failed               = payload.get("failed", {})
        self.reference_dm_sha256  = payload.get("reference_dm_sha256", None)
        self.current_dag_node     = payload.get("current_dag_node", "")
        self.material_statuses    = payload.get("material_statuses", {})
        self.current_accepted_configuration = payload.get("current_accepted_configuration", {})

    def set_reference_dm(self, sha256: str) -> None:
        """Record the canonical reference DM hash after the reference run."""
        self.reference_dm_sha256 = sha256
        self.save()

    def set_dag_node(self, node: str) -> None:
        """Update the current DAG node."""
        self.current_dag_node = node
        self.save()

    def set_material_status(self, material: str, status: str) -> None:
        self.material_statuses[material] = status
        self.save()

    def pending_keys(self) -> List[str]:
        """Return calculation keys that have been seen as failed but not completed."""
        return [k for k in self.failed if k not in self.completed]

    def summary(self) -> Dict[str, Any]:
        return {
            "n_completed": len(self.completed),
            "n_failed":    len(self.failed),
            "n_pending":   len(self.pending_keys()),
            "reference_dm_sha256": self.reference_dm_sha256,
            "current_dag_node":    self.current_dag_node,
            "material_statuses":   self.material_statuses,
            "current_accepted_configuration": self.current_accepted_configuration,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Resume helper
# ─────────────────────────────────────────────────────────────────────────────

def resume_incomplete(campaign_dir: str) -> List[str]:
    """
    Return a list of calculation identity keys that need to be (re)run.

    A key is incomplete if:
    - it is recorded as failed and NOT in completed, OR
    - it is not in completed at all (i.e., never attempted)

    The second category requires a separate mechanism (campaign_plan) to
    enumerate all intended keys; this function only returns the failed subset.

    For full resume capability, callers should union this list with any
    keys in the campaign plan that are absent from completed.
    """
    state_path = os.path.join(campaign_dir, STATE_FILENAME)
    if not os.path.exists(state_path):
        return []

    state = CampaignState(campaign_dir)
    return state.pending_keys()
