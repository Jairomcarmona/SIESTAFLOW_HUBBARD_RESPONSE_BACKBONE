"""Qualify an installed native API wheel outside the source checkout."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    uv = shutil.which("uv")
    if uv is None:
        raise SystemExit("uv 0.11.14 must be on PATH")
    wheels = list((root / "dist").glob("hubbardflow-0.1.3-*.whl"))
    if len(wheels) != 1:
        raise SystemExit("expected exactly one built hubbardflow 0.1.3 wheel")
    env = {key: value for key, value in os.environ.items() if key not in {"PYTHONPATH", "PYTHONHOME"}}
    with tempfile.TemporaryDirectory(prefix="hubbardflow-consumer-") as directory:
        target = Path(directory)
        requirements = target / "requirements.txt"
        subprocess.run(
            [uv, "export", "--locked", "--no-dev", "--no-emit-project", "--format", "requirements-txt", "--quiet", "-o", str(requirements)],
            cwd=root, env=env, check=True,
        )
        venv = target / "env"
        subprocess.run([uv, "venv", "--python", sys.executable, str(venv)], cwd=target, env=env, check=True)
        python = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        subprocess.run([uv, "pip", "install", "--python", str(python), "--require-hashes", "-r", str(requirements)], cwd=target, env=env, check=True)
        subprocess.run([uv, "pip", "install", "--python", str(python), "--no-deps", str(wheels[0])], cwd=target, env=env, check=True)
        script = target / "consumer.py"
        fixture = target / "native_consumer.json"
        shutil.copyfile(root / "tests/consumer/public_api_consumer.py", script)
        shutil.copyfile(root / "tests/fixtures/public_api_v1/native_consumer.json", fixture)
        subprocess.run([str(python), "-I", str(script), str(fixture), str(root)], cwd=target, env=env, check=True)


if __name__ == "__main__":
    main()
