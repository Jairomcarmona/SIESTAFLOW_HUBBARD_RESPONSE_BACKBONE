import os
import hashlib
import json
from typing import List, Dict, Any, Optional


class CheckpointScientificAcceptanceDisabledError(RuntimeError):
    """Integrity sidecars cannot certify a scientific execution step."""

class CheckpointManager:
    def __init__(self, work_dir: str):
        self.work_dir = work_dir
        os.makedirs(self.work_dir, exist_ok=True)

    def _compute_sha256(self, filepath: str) -> str:
        sha256_hash = hashlib.sha256()
        with open(filepath, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def _sidecar_path(self, filepath: str) -> str:
        return f"{filepath}.sha256"

    def record_checkpoint(self, filepaths: List[str]):
        """Records the SHA256 of the given files into their respective sidecars."""
        for filepath in filepaths:
            full_path = os.path.join(self.work_dir, filepath)
            if os.path.exists(full_path):
                file_hash = self._compute_sha256(full_path)
                with open(self._sidecar_path(full_path), "w") as f:
                    f.write(file_hash)

    def verify_checkpoint(self, filepaths: List[str]) -> bool:
        """Verifies if the given files exist and match their recorded SHA256 sidecars."""
        if not filepaths:
            return False
        for filepath in filepaths:
            full_path = os.path.join(self.work_dir, filepath)
            sidecar = self._sidecar_path(full_path)
            
            if not os.path.exists(full_path) or not os.path.exists(sidecar):
                return False
                
            with open(sidecar, "r") as f:
                expected_hash = f.read().strip()
                
            actual_hash = self._compute_sha256(full_path)
            if expected_hash != actual_hash:
                return False
                
        return True

    def is_step_completed(self, step_name: str, expected_outputs: List[str]) -> bool:
        """Removed: use a validated node receipt, not integrity sidecars."""
        del step_name, expected_outputs
        raise CheckpointScientificAcceptanceDisabledError(
            "checkpoint hashes are integrity evidence, not scientific completion"
        )

    def mark_step_completed(self, step_name: str, outputs: List[str]):
        """Removed: recording hashes cannot mark a scientific step complete."""
        del step_name, outputs
        raise CheckpointScientificAcceptanceDisabledError(
            "checkpoint hashes cannot mark a scientific step complete"
        )
