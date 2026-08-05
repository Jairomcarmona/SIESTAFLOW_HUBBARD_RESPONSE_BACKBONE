#!/usr/bin/env python3
from pathlib import Path
import json, hashlib, sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]

REQUIRED = [
    "README.md",
    "CHANGELOG.md",
    "STATUS.md",
    "AGENT_DIRECTIVE.md",
    "docs/01_science/SCIENTIFIC_CONTRACT.md",
    "docs/02_architecture/DAG_SPEC.md",
    "docs/02_architecture/STATE_MACHINE.md",
    "docs/04_validation/ADVERSARIAL_TEST_PLAN.md",
    "schemas/campaign.schema.json",
    "schemas/matrix_bundle.schema.json",
    "examples/minimal_synthetic_campaign/campaign.json",
    "examples/minimal_synthetic_campaign/response_dataset.json",
    "examples/minimal_synthetic_campaign/matrix_bundle.json",
    "package_manifest.json",
    "backbone_manifest.sha256",
]

def fail(msg):
    print(f"FAIL: {msg}")
    raise SystemExit(1)

for rel in REQUIRED:
    if not (ROOT / rel).is_file():
        fail(f"missing required file: {rel}")

for path in sorted(ROOT.rglob("*.json")):
    try:
        json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"invalid JSON {path.relative_to(ROOT)}: {exc}")

try:
    import jsonschema
    from referencing import Registry, Resource
except Exception as exc:
    fail(f"jsonschema and referencing are required: {exc}")

schemas = {}
registry = Registry()
for schema_path in sorted((ROOT / "schemas").glob("*.json")):
    data = json.loads(schema_path.read_text(encoding="utf-8"))
    sid = data.get("$id", schema_path.name)
    schemas[schema_path.name] = data
    registry = registry.with_resource(sid, Resource.from_contents(data))

pairs = {
    "examples/minimal_synthetic_campaign/methodology.lock.json": "methodology.schema.json",
    "examples/minimal_synthetic_campaign/geometry_identity.json": "geometry_identity.schema.json",
    "examples/minimal_synthetic_campaign/correlated_subspaces.json": "correlated_subspaces.schema.json",
    "examples/minimal_synthetic_campaign/projector_policy.json": "projector_policy.schema.json",
    "examples/minimal_synthetic_campaign/perturbation_policy.json": "perturbation_policy.schema.json",
    "examples/minimal_synthetic_campaign/numerical_settings.json": "numerical_settings.schema.json",
    "examples/minimal_synthetic_campaign/campaign.json": "campaign.schema.json",
    "examples/minimal_synthetic_campaign/runtime_identity.json": "runtime_identity.schema.json",
    "examples/minimal_synthetic_campaign/candidate.lock.json": "candidate_lock.schema.json",
    "examples/minimal_synthetic_campaign/response_dataset.json": "response_dataset.schema.json",
    "examples/minimal_synthetic_campaign/regression_results.json": "regression_results.schema.json",
    "examples/minimal_synthetic_campaign/matrix_bundle.json": "matrix_bundle.schema.json",
    "examples/minimal_synthetic_campaign/gate_results.json": "gate_results.schema.json",
    "examples/minimal_synthetic_campaign/sensitivity_report.json": "sensitivity_report.schema.json",
    "examples/minimal_synthetic_campaign/materialized_dag.json": "dag.schema.json",
    "package_manifest.json": "package_manifest.schema.json",
}

for data_rel, schema_name in pairs.items():
    data = json.loads((ROOT / data_rel).read_text(encoding="utf-8"))
    schema = schemas[schema_name]
    try:
        jsonschema.Draft202012Validator(schema, registry=registry).validate(data)
    except Exception as exc:
        fail(f"schema validation failed for {data_rel}: {exc}")

# Verify package_manifest.json: all files except both manifest files.
pkg = json.loads((ROOT / "package_manifest.json").read_text(encoding="utf-8"))
pkg_paths = {item["path"] for item in pkg["files"]}
expected_pkg_paths = {
    p.relative_to(ROOT).as_posix()
    for p in ROOT.rglob("*")
    if p.is_file() and p.name not in {"package_manifest.json", "backbone_manifest.sha256"}
}
if pkg_paths != expected_pkg_paths:
    fail(f"package_manifest file set mismatch: missing={sorted(expected_pkg_paths-pkg_paths)}, extra={sorted(pkg_paths-expected_pkg_paths)}")
for item in pkg["files"]:
    path = ROOT / item["path"]
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != item["sha256"] or path.stat().st_size != item["size_bytes"]:
        fail(f"package_manifest mismatch: {item['path']}")

# Verify SHA-256 manifest: all files except itself.
sha_entries = {}
for line in (ROOT / "backbone_manifest.sha256").read_text(encoding="utf-8").splitlines():
    if not line.strip():
        continue
    digest, rel = line.split("  ", 1)
    sha_entries[rel] = digest
expected_sha_paths = {
    p.relative_to(ROOT).as_posix()
    for p in ROOT.rglob("*")
    if p.is_file() and p.name != "backbone_manifest.sha256"
}
if set(sha_entries) != expected_sha_paths:
    fail(f"SHA manifest file set mismatch: missing={sorted(expected_sha_paths-set(sha_entries))}, extra={sorted(set(sha_entries)-expected_sha_paths)}")
for rel, digest in sha_entries.items():
    actual = hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()
    if actual != digest:
        fail(f"hash mismatch: {rel}")

# Recompute synthetic matrix algebra.
bundle = json.loads((ROOT / "examples/minimal_synthetic_campaign/matrix_bundle.json").read_text(encoding="utf-8"))
if bundle["formula"] != "inverse(chi0)-inverse(chi)":
    fail("wrong U formula")
if bundle["recommended_single_U_ev"] is not None:
    fail("automatic scalar U recommendation is forbidden")
for key in ("chi0", "chi"):
    fam = bundle[key]
    selected = np.array(fam["selected"]["values"], dtype=float)
    inverse = np.array(fam["inverse"]["values"], dtype=float)
    if selected.shape[0] != selected.shape[1]:
        fail(f"{key} selected matrix is not square")
    if not np.allclose(np.linalg.inv(selected), inverse, rtol=1e-12, atol=1e-12):
        fail(f"{key} stored inverse is incompatible")
    left = np.linalg.norm(inverse @ selected - np.eye(selected.shape[0]), ord="fro")
    right = np.linalg.norm(selected @ inverse - np.eye(selected.shape[0]), ord="fro")
    if abs(left - fam["left_residual_fro"]) > 1e-12 or abs(right - fam["right_residual_fro"]) > 1e-12:
        fail(f"{key} stored inversion residual is incompatible")
expected_u = np.array(bundle["chi0"]["inverse"]["values"]) - np.array(bundle["chi"]["inverse"]["values"])
stored_u = np.array(bundle["u_matrix"]["values"])
if not np.allclose(expected_u, stored_u, rtol=1e-12, atol=1e-12):
    fail("stored U matrix does not equal inverse(chi0)-inverse(chi)")

# Verify aggregation dimensions are general and consistent.
subspaces = json.loads((ROOT / "examples/minimal_synthetic_campaign/correlated_subspaces.json").read_text(encoding="utf-8"))
A = np.array(subspaces["aggregation_matrix"]["values"], dtype=float)
if A.shape != (len(subspaces["aggregation_matrix"]["row_ids"]), len(subspaces["aggregation_matrix"]["column_ids"])):
    fail("aggregation matrix dimensions are inconsistent")
if len(subspaces["perturbation_targets"]) != A.shape[0]:
    fail("synthetic example does not produce a square physical susceptibility")

# Scan normative core for known project-specific literals.
forbidden = ["Mn01", "birnessite", "Birnessite", "Yoltla", "range(6)", "12x6", "12×6"]
for base in [ROOT / "docs", ROOT / "schemas"]:
    for path in base.rglob("*"):
        if path.is_file() and path.suffix in {".md", ".json"}:
            text = path.read_text(encoding="utf-8", errors="ignore")
            for token in forbidden:
                if token in text:
                    fail(f"forbidden hardcoded token {token!r} in {path.relative_to(ROOT)}")

print("PASS: structure, JSON Schemas, full manifests, synthetic matrix algebra, non-hardcoding and human-decision constraints")
