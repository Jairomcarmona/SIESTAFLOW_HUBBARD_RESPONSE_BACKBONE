"""Exercise the installed controller wheel without checkout imports or real jobs."""

from __future__ import annotations

import json
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
    environment = {key: value for key, value in os.environ.items() if key not in {"PYTHONPATH", "PYTHONHOME"}}
    with tempfile.TemporaryDirectory(prefix="hubbardflow-controller-consumer-") as directory:
        target = Path(directory)
        requirements = target / "requirements.txt"
        subprocess.run(
            [
                uv,
                "export",
                "--locked",
                "--no-dev",
                "--extra",
                "test",
                "--no-emit-project",
                "--format",
                "requirements-txt",
                "--quiet",
                "-o",
                str(requirements),
            ],
            cwd=root,
            env=environment,
            check=True,
        )
        venv = target / "env"
        subprocess.run(
            [uv, "venv", "--python", sys.executable, str(venv)], cwd=target, env=environment, check=True
        )
        python = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        for arguments in (
            ["install", "--require-hashes", "-r", str(requirements)],
            ["install", "--no-deps", str(wheels[0])],
            ["check"],
        ):
            subprocess.run(
                [uv, "pip", *arguments, "--python", str(python)], cwd=target, env=environment, check=True
            )
        for relative in (
            "tests/unit/test_controller_contracts.py",
            "tests/unit/test_controller_resume.py",
            "tests/unit/test_controller_resume_preflight.py",
            "tests/unit/test_perturbation_plan.py",
            "tests/unit/test_coverage.py",
            "tests/__init__.py",
            "tests/unit/__init__.py",
            "tools/__init__.py",
            "tools/hubbardflow_plan_diagnose.py",
            "tests/fixtures/controller-resume-rules/cases.json",
        ):
            destination = target / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(root / relative, destination)
        probe = target / "installed_probe.py"
        probe.write_text(
            "import importlib.metadata,json,os,pathlib,subprocess,sys,sysconfig\n"
            "from hashlib import sha256\n"
            "from hubbardflow.api import controller,controller_contracts,controller_ledger,controller_resume,controller_resume_preflight\n"
            "from hubbardflow import api\n"
            "assert sys.flags.isolated\n"
            "checkout=pathlib.Path(sys.argv[1]).resolve()\n"
            "for module in (controller,controller_contracts,controller_ledger,controller_resume,controller_resume_preflight):\n"
            "    path=pathlib.Path(module.__file__).resolve()\n"
            "    assert path.is_relative_to(pathlib.Path(sys.prefix).resolve()),path\n"
            "    assert not path.is_relative_to(checkout),path\n"
            "for schema_id in ('hubbardflow.api_result.v1','hubbardflow.analysis_result.v1',"
            "'hubbardflow.worker_status.v1'):\n"
            "    assert api.get_schema(schema_id).to_mapping()\n"
            "expected_schemas={"
            "'defs.schema':'2c4245ded2988c8ffeb5f9bed55fcac0d0aa57cf2805277a67b0408edebfb5f4',"
            "'qraft-controller-reservation.schema':'0c1694dd725d1d0eb8ce7e8a23bd537547629ab3dc463e158567c9cb50c3df56',"
            "'qraft-controller-ledger-entry.schema':'e93daa8ca193153563eec4c563da3360e2870d1228c8ceb8a62b6efb90dad2b3',"
            "'qraft-controller-resume-verdict.schema':'054993007e3bb579007a91262d9ea30a577b68b5273d9e2f675cc5c2fd8a1b54'}\n"
            "schema_dir=pathlib.Path(controller_contracts.__file__).with_name('schemas')\n"
            "for name,digest in expected_schemas.items():\n"
            "    assert sha256((schema_dir/name).read_bytes()).hexdigest()==digest,name\n"
            "entries=[e for e in importlib.metadata.distribution('hubbardflow').entry_points "
            "if e.group=='console_scripts' and e.name=='hubbardflow-controller']\n"
            "assert len(entries)==1 and entries[0].value=='hubbardflow.api.controller:main'\n"
            "exe=pathlib.Path(sysconfig.get_path('scripts'))/('hubbardflow-controller.exe' "
            "if os.name=='nt' else 'hubbardflow-controller')\n"
            "assert exe.is_file(),exe\n"
            "help_result=subprocess.run([str(exe),'--help'],capture_output=True,text=True,timeout=20)\n"
            "assert help_result.returncode==0,help_result.stderr\n"
            "if os.name=='nt':\n"
            "    result=subprocess.run([str(exe),'--qraft-reservation','absent.json','--campaign','absent.json'],"
            "capture_output=True,text=True,timeout=20)\n"
            "    assert result.returncode==2 and 'CONTROLLER_REQUIRES_POSIX' in result.stderr,result.stderr\n"
            "print(json.dumps({'installed':True,'isolated':True,'scientific_job':False}))\n",
            encoding="utf-8",
        )
        subprocess.run([str(python), "-I", str(probe), str(root)], cwd=target, env=environment, check=True)
        subprocess.run(
            [
                str(python),
                "-I",
                "-m",
                "pytest",
                "-q",
                "tests/unit/test_controller_contracts.py",
                "tests/unit/test_controller_resume.py",
                "tests/unit/test_controller_resume_preflight.py",
            ],
            cwd=target,
            env=environment,
            check=True,
        )
        vectors = json.loads((target / "tests/fixtures/controller-resume-rules/cases.json").read_bytes())
        print(
            json.dumps(
                {
                    "installed_controller": True,
                    "resume_vectors": len(vectors["cases"]),
                    "scientific_job": False,
                    "scope": "contracts and synthetic process lifecycle; not HF-1 qualification",
                }
            )
        )


if __name__ == "__main__":
    main()
