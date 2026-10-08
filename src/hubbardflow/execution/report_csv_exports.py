"""CSV exports for persisted HubbardFlow analysis evidence."""

from __future__ import annotations

import csv
from collections.abc import Mapping
from pathlib import Path
from typing import Any


def _write_csv(path: Path, rows: list[list[Any]]) -> None:
    with path.open("w", encoding="ascii", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerows(rows)


def export_report_csv(source: Mapping[str, Any], data_dir: Path) -> None:
    """Export the saved U vector and complete raw chi0/chi matrices."""
    analysis = source.get("analysis")
    analysis = analysis if isinstance(analysis, Mapping) else {}
    primary = analysis.get("primary")
    primary = primary if isinstance(primary, Mapping) else {}
    dataset = analysis.get("response_observation_dataset")
    dataset = dataset if isinstance(dataset, Mapping) else {}
    site_map = dataset.get("site_index_map")
    names: dict[int, str] = {}
    if isinstance(site_map, list):
        names = {
            int(item["index"]): str(item["site_id"])
            for item in site_map
            if isinstance(item, Mapping)
            and isinstance(item.get("index"), int)
            and item.get("site_id") is not None
        }
    u_by_site = primary.get("U_by_site_eV")
    rows: list[list[Any]] = [["site_index", "site_id", "U_eV"]]
    if isinstance(u_by_site, Mapping) and u_by_site:
        for key, value in sorted(u_by_site.items(), key=lambda item: str(item[0])):
            index = int(key) if str(key).isdigit() else None
            rows.append(
                [key, names.get(index, "NOT_ASSESSED") if index is not None else "NOT_ASSESSED", value]
            )
    else:
        rows.append(["NOT_ASSESSED", "NOT_ASSESSED", "NOT_ASSESSED"])
    _write_csv(data_dir / "u_by_site.csv", rows)
    for raw_key, filename in (("chi0_raw", "chi0_matrix.csv"), ("chi_raw", "chi_matrix.csv")):
        matrix = primary.get(raw_key)
        if isinstance(matrix, list) and matrix:
            labels = [names.get(index, str(index)) for index in range(len(matrix))]
            csv_rows: list[list[Any]] = [["site_id", *labels]]
            for index, row in enumerate(matrix):
                values = row if isinstance(row, list) else []
                csv_rows.append(
                    [
                        labels[index],
                        *[
                            values[column]
                            if column < len(values) and values[column] is not None
                            else "NOT_ASSESSED"
                            for column in range(len(labels))
                        ],
                    ]
                )
        else:
            csv_rows = [["site_id", "NOT_ASSESSED"], ["NOT_ASSESSED", "NOT_ASSESSED"]]
        _write_csv(data_dir / filename, csv_rows)
