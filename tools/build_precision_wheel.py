#!/usr/bin/env python3
"""Create the offline 0.1.2 patch wheel from the frozen 0.1.0 wheel.

The local Python installation has no setuptools build backend.  This builder
preserves every entry from the frozen base wheel and adds only the two new
pure-Python precision modules, then regenerates standard wheel metadata/RECORD.
"""
from __future__ import annotations

import base64
import csv
from hashlib import sha256
from io import StringIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "siestaflow_hubbard-0.1.0-py3-none-any.whl"
OUTPUT = ROOT / "dist/precision-correction-0.1.2/siestaflow_hubbard-0.1.2-py3-none-any.whl"
BASE_DIST_INFO = "siestaflow_hubbard-0.1.0.dist-info"
DIST_INFO = "siestaflow_hubbard-0.1.2.dist-info"
PATCH_FILES = {
    "src/siestaflow_hubbard/domain/quantized_response.py": "siestaflow_hubbard/domain/quantized_response.py",
    "src/siestaflow_hubbard/siesta_backend/occupation_precision.py": "siestaflow_hubbard/siesta_backend/occupation_precision.py",
    "src/siestaflow_hubbard/execution/slurm_foreground.py": "siestaflow_hubbard/execution/slurm_foreground.py",
}


def record_digest(data: bytes) -> str:
    value = base64.urlsafe_b64encode(sha256(data).digest()).rstrip(b"=").decode("ascii")
    return f"sha256={value}"


def main() -> None:
    if not BASE.is_file() or OUTPUT.exists():
        raise SystemExit("base wheel missing or output already exists; refusing to overwrite")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, bytes] = {}
    with ZipFile(BASE) as archive:
        for name in archive.namelist():
            if name.startswith(BASE_DIST_INFO + "/"):
                relative = name[len(BASE_DIST_INFO) + 1:]
                if relative == "RECORD":
                    continue
                content = archive.read(name)
                if relative == "METADATA":
                    content = content.replace(b"Version: 0.1.0\n", b"Version: 0.1.2\n")
                elif relative == "WHEEL":
                    content = content.replace(b"Generator: setuptools (84.0.0)",
                                              b"Generator: SIESTAFLOW precision patch builder")
                payload[f"{DIST_INFO}/{relative}"] = content
            else:
                payload[name] = archive.read(name)
    for source, member in PATCH_FILES.items():
        payload[member] = (ROOT / source).read_bytes()

    record_name = f"{DIST_INFO}/RECORD"
    record_buffer = StringIO(newline="")
    writer = csv.writer(record_buffer, lineterminator="\n")
    for name in sorted(payload):
        content = payload[name]
        writer.writerow((name, record_digest(content), len(content)))
    writer.writerow((record_name, "", ""))
    payload[record_name] = record_buffer.getvalue().encode("utf-8")

    with ZipFile(OUTPUT, "w") as archive:
        for name, content in sorted(payload.items()):
            info = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, content)
    print(f"wheel={OUTPUT.relative_to(ROOT)}")
    print(f"sha256={sha256(OUTPUT.read_bytes()).hexdigest()}")


if __name__ == "__main__":
    main()
