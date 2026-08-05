import os
import hashlib
import json
from pathlib import Path
import zipfile

def sha256_file(filepath: Path) -> str:
    hasher = hashlib.sha256()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hasher.update(chunk)
    return hasher.hexdigest()

def package_release(project_dir: Path, output_zip: Path):
    # Create sidecars for all JSON files in examples
    examples_dir = project_dir / "examples"
    for json_file in examples_dir.rglob("*.json"):
        if json_file.is_file():
            sidecar = json_file.with_name(json_file.name + ".sha256")
            hash_val = sha256_file(json_file)
            with open(sidecar, "w", encoding="utf-8") as f:
                f.write(f"{hash_val}  {json_file.name}\n")
    
    # Generate MANIFEST.sha256
    manifest_entries = []
    for root, _, files in os.walk(project_dir):
        for file in files:
            if file == "MANIFEST.sha256" or file.endswith(".pyc") or ".git" in root or "__pycache__" in root:
                continue
            filepath = Path(root) / file
            rel_path = filepath.relative_to(project_dir).as_posix()
            manifest_entries.append((rel_path, sha256_file(filepath)))
            
    manifest_entries.sort(key=lambda x: x[0])
    
    manifest_path = project_dir / "MANIFEST.sha256"
    with open(manifest_path, "w", encoding="utf-8") as f:
        for rel_path, hash_val in manifest_entries:
            f.write(f"{hash_val}  {rel_path}\n")
            
    # Create ZIP
    with zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
        for rel_path, _ in manifest_entries:
            zf.write(project_dir / rel_path, rel_path)
        zf.write(manifest_path, "MANIFEST.sha256")
        
    # Create external SHA256 for ZIP
    zip_hash = sha256_file(output_zip)
    with open(output_zip.with_name(output_zip.name + ".sha256"), "w", encoding="utf-8") as f:
        f.write(f"{zip_hash}  {output_zip.name}\n")

if __name__ == "__main__":
    project_dir = Path(r"c:\Users\Jairo\Downloads\SIESTAFLOW_HUBBARD_RESPONSE_BACKBONE_V0_1_0")
    output_zip = project_dir.parent / "SIESTAFLOW_HUBBARD_RESPONSE_BACKBONE_V0_1_0.zip"
    package_release(project_dir, output_zip)
    print("Release packaged successfully.")
