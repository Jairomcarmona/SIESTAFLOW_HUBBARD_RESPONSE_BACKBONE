"""Keep public release metadata aligned with the package version."""

import json
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_citation_and_archival_metadata_versions_match_pyproject() -> None:
    with (ROOT / "pyproject.toml").open("rb") as source:
        project = tomllib.load(source)["project"]
    version = project["version"]

    citation = (ROOT / "CITATION.cff").read_text(encoding="utf-8")
    assert f"version: {version}" in citation.splitlines()

    codemeta = json.loads((ROOT / "codemeta.json").read_text(encoding="utf-8"))
    zenodo = json.loads((ROOT / ".zenodo.json").read_text(encoding="utf-8"))
    assert codemeta["version"] == version
    assert zenodo["version"] == version
