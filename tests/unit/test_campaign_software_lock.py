from pathlib import Path

from hubbardflow.execution.campaign_software_lock import _locked_file_path


class FakeDistribution:
    def __init__(self, root: Path):
        self.root = root

    def locate_file(self, path):
        return self.root / path


def test_current_lock_path_resolves_inside_hubbardflow_distribution(tmp_path):
    dist = FakeDistribution(tmp_path / "site-packages")

    result = _locked_file_path(
        tmp_path,
        "src/hubbardflow/execution/slurm_foreground.py",
        dist,
        require_installed_wheel=True,
    )

    assert result == tmp_path / "site-packages/hubbardflow/execution/slurm_foreground.py"


def test_legacy_campaign_lock_path_resolves_inside_its_locked_distribution(tmp_path):
    dist = FakeDistribution(tmp_path / "site-packages")

    result = _locked_file_path(
        tmp_path,
        "src/siestaflow_hubbard/execution/slurm_foreground.py",
        dist,
        require_installed_wheel=True,
    )

    assert result == tmp_path / "site-packages/siestaflow_hubbard/execution/slurm_foreground.py"


def test_legacy_source_path_maps_to_renamed_tree_without_rewriting_lock_record(tmp_path):
    result = _locked_file_path(
        tmp_path,
        "src/siestaflow_hubbard/execution/slurm_foreground.py",
        None,
        require_installed_wheel=False,
    )

    assert result == tmp_path / "src/hubbardflow/execution/slurm_foreground.py"
