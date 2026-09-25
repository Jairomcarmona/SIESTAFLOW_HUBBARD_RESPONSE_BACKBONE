# Method-2 P0 validation — 2026-09-24

## Scope

This record covers the root project tree `SIESTAFLOW_HUBBARD_RESPONSE_BACKBONE_V0_1_0`. It documents the local Method-2 preflight and restart-safety work from this iteration. No files under `proyectohubbard/` or any ZIP package were edited. The real SIESTA preflight used temporary copies under WSL `/tmp`; archived campaign inputs remained unchanged.

## Changes validated

- The effective FDF parser follows SIESTA 5.4.2 precedence for `LDAU.*` and `DFTU.*`, selects the effective projector block, and parses optional `E vcte rinn` shell-row fields and following lambda values.
- PSML selection resolves labels against FDF species and checks atomic number. Preflight manifests bind the complete FDF/configuration, source PSML identities, projected labels, and every generated projector profile; the verifier recalculates those identities when validating a cached preflight.
- The Slurm template revalidates Gate 0 before skipping it. Each run's marker binds the FDF, effective projector configuration, current selected source PSMLs and staged PSMLs, manifest record, and parent DM. The marker is written only after output validation and is archived with interrupted outputs.
- The DAG installer includes `siesta_dftu_fdf.py` and `psml_selection.py`. Adversarial coverage is in `tests/adversarial/test_method2_preflight_cache_identity.py`.

## WSL test and shell validation

The following command completed with **29 passed in 3.02 s**; the `bash -n` check returned exit code 0:

```bash
cd /mnt/c/Users/Jairo/Downloads/SIESTAFLOW_HUBBARD_RESPONSE_BACKBONE_V0_1_0
bash -n templates/slurm/submit_scientific_lru_dag.slurm
PYTHONPATH=src python3 -m pytest -p no:cacheprovider \
  --basetemp=/tmp/pytest-method2-audit-20260924b \
  tests/unit/test_method2*.py tests/adversarial/test_method2*.py
```

The passing set was `test_method2_effective_fdf.py`, `test_method2_projector_audit.py`, `test_method2_preflight_cache_identity.py`, and `test_method2_reference.py`. A first pytest collection without `PYTHONPATH=src` failed to import `siestaflow_hubbard`; the command above corrected the import path.

## Windows-focused test limits

On Windows, one focused pytest selection passed **8 tests** with the temporary-directory plugin disabled. A separate run using local workspace fixtures passed **16 tests** across the three Method-2 test files. Standard pytest fixture creation was constrained by ACL failures (`WinError 5`) under `%LOCALAPPDATA%\Temp\pytest-of-Jairo`; an adversarial run reported 2 passed and 4 setup errors while creating `tmp_path`. The six adversarial functions also passed when invoked directly with workspace fixtures. The Windows fixture errors do not affect the successful WSL run above.

## Real SIESTA 5.4.2 Method-2 preflight

The executable was `/home/jmc/.local/siesta-5.4.2-openmpi/bin/siesta`; its materializer log identified **Version 5.4.2**. The archived reference input was:

```text
campaigns/mno_afmii_strict_lr_v3r2/results/response-matrix-foreground-recovery-v4/00_REFERENCE/siesta.fdf
```

The FDF SHA-256 was `3c86abab6daf4c0c00a10da6a7e060470e54bcc5364f70a0e2932285c24941e6`. The 17 PSML inputs came from the same archived reference directory: labels `MnLR00`–`MnLR15` plus `O`. All Mn aliases had SHA-256 `0b97ccd71456e4a7b28316f78ddb30bb1f6a82d9aba386c7fde78090d31c0dc6`; `O.psml` had SHA-256 `5ca5d753a995bd054279007ba76be71d622b60460c6f9a0d9bb37d81bdf185fe`.

The materializer ran with one MPI rank and `--timeout-seconds 30`, using copied inputs and output under `/tmp/siestaflow-method2-recovery-v4-audit.oLiIvZ`. It returned exit code 0 with `PROJECTOR_MATERIALIZED_ONLY` and produced **16/16** expected `MnLR*.dftu_proj` profiles. The verifier printed `PROJECTOR_IDENTITY_OK`. The helper stopped SIESTA after the projector files stabilized; the captured output ended during initialization, without SCF completion. `pgrep -x siesta` and `pgrep -x mpiexec` were empty before and after the preflight. The archived FDF and selected PSML hashes were unchanged afterward.

The generated `MnLR00` profile passed `audit_method2_projector.py` with `PASS_PRELIGHT_REVIEW_REQUIRED` and recommendation `LOCALITY_WINDOW_AVAILABLE`. The FDF's `CutoffNorm` was `0.90`; the generated soft cutoff was `2.43936746583243 Bohr` (`1.2908576719367242 Å`), versus a nearest-neighbour distance of `4.185743366046081 Bohr` (`2.215 Å`). The reported cutoff-to-neighbour ratio was `0.5827799873303495`. These are locality-screen values, not a U selection or convergence result.

The WSL invocation copied the archived inputs into `/tmp`, passed one `--pseudo-source` option for each source PSML, and ran:

```bash
ROOT=/mnt/c/Users/Jairo/Downloads/SIESTAFLOW_HUBBARD_RESPONSE_BACKBONE_V0_1_0
REF="$ROOT/campaigns/mno_afmii_strict_lr_v3r2/results/response-matrix-foreground-recovery-v4/00_REFERENCE"
TOOLS="$ROOT/tools"
WORK=/tmp/siestaflow-method2-recovery-v4-audit.oLiIvZ
mkdir -p "$WORK/input" "$WORK/pseudopotentials" "$WORK/materialized"
cp "$REF/siesta.fdf" "$WORK/input/siesta.fdf"
cp "$REF"/*.psml "$WORK/pseudopotentials/"
mapfile -t PSEUDOS < <(find "$WORK/pseudopotentials" -maxdepth 1 -type f -name '*.psml' -print | sort)
PSEUDO_ARGS=()
for file in "${PSEUDOS[@]}"; do PSEUDO_ARGS+=(--pseudo-source "$file"); done
PYTHONPATH="$TOOLS" python3 "$TOOLS/materialize_method2_projector.py" \
  --fdf "$WORK/input/siesta.fdf" --central-label MnLR00 "${PSEUDO_ARGS[@]}" \
  --siesta /home/jmc/.local/siesta-5.4.2-openmpi/bin/siesta \
  --mpi-launcher mpiexec --ranks 1 --timeout-seconds 30 \
  --output-dir "$WORK/materialized"
PYTHONPATH="$ROOT/tools" python3 "$ROOT/tools/verify_method2_projector_identity.py" \
  --reference-fdf "$WORK/input/siesta.fdf" \
  --preflight-dir "$WORK/materialized" --label MnLR00 \
  --pseudo-directory "$WORK/pseudopotentials"

PYTHONPATH="$ROOT/tools" python3 "$ROOT/tools/audit_method2_projector.py" \
  --fdf "$WORK/input/siesta.fdf" --central-label MnLR00 \
  --psml "$WORK/pseudopotentials/MnLR00.psml" \
  --projector "$WORK/materialized/MnLR00.dftu_proj" \
  --json-out "$WORK/audit.json" --markdown-out "$WORK/audit.md"
```

## Limits of this evidence

- No complete DAG was run. The Slurm template was syntax-checked and its gate/marker behavior was inspected through focused tests, but no scheduler submission or cluster placement was exercised.
- No full SCF, response campaign, or LR-U extraction was run. This validation does not establish SCF convergence, LR linearity, response-matrix rank, a physical U value, or transferability.
- The locality audit explicitly requires human review. It does not automatically choose a cutoff or a Hubbard parameter.
