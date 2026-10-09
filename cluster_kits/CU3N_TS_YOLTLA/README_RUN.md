# CU3N_TS_YOLTLA

This kit prepares a Cu3N translation-shadow (TS) campaign on Yoltla. Any
SIESTA job requires an explicit launch variable. Codex did not access Yoltla
or run SIESTA while preparing this kit.

The vendored HubbardFlow source is pinned to commit
`d7d2d824ed7e6cd87a1dfafe0866b4ecd9e06650`. This includes the non-polarized
BARE output parser required for Cu3N. Setup verifies the commit and the
Yoltla SIESTA executable hash before allowing campaign commands.

## Frozen calculation inputs

- FDF: PBE, SC222, 32 atoms, 24 Cu projector labels, 2x2x2 k-grid.
- Spin: `Spin non-polarized`.
- Projector: method 2, `DFTU.PotentialShift true`, MeshCutoff 200 Ry.
- Geometry: `MD.NumCGsteps 0`; HubbardFlow does not relax coordinates.
- Response alpha grid: -0.1, -0.05, -0.025, 0.025, 0.05, 0.1 eV.
- Scheduler: `q4d-40p`, 2 nodes, 16 ranks per node, one SIESTA at a time.

Input hashes are in `inputs/INPUTS.sha256`. The exact full-site FDF and
pseudopotentials are supplied. `CHECKSUMS.sha256` covers the kit files.

## Workflow

1. On the login node, run setup. It verifies checksums, pins the code,
   verifies the binary identity, and writes local absolute-path configs.

   ```bash
   bash bin/setup_login.sh
   ```

2. Run a fresh reference. This is one SIESTA reference calculation and
   archives its output and DM for planning. It requires an explicit flag.

   ```bash
   sbatch --export=ALL,HF_START_REFERENCE=YES submit_reference.slurm
   ```

   Wait for `REFERENCE_READY` in the job log. The step fails closed unless
   both the FDF and output prove non-polarized mode:
   `Spin non-polarized`, `Spin configuration = none`,
   `Number of spin components = 1`, and
   `Time-Reversal Symmetry = T`.

3. Run the TS planner dry-run. This allocates Yoltla resources but does not
   execute SIESTA. Without `HF_START_TS=YES`, the script exits after the
   plan checks.

   ```bash
   sbatch submit_ts.slurm
   ```

   The expected plan is three translation classes of eight Cu sites, six
   calculated columns, and 72 BARE/SCREENED response run specs. The campaign
   also has its own reference node when execution is explicitly enabled.
   The plan must report `ADMISSIBLE_TRANSLATION_SHADOWED`; shadow results are
   still pending at dry-run time.

4. Optional: run the one-column probe after its generated FDF diff is
   reviewed. It is one reference plus 12 response runs. It does not launch
   TS.

   ```bash
   sbatch --export=ALL,HF_START_PROBE=YES submit_probe.slurm
   ```

5. Run the full TS campaign only after reviewing the reference, dry-run,
   and probe evidence. This explicit variable is required on every launch
   and resume submission.

   ```bash
   sbatch --export=ALL,HF_START_TS=YES submit_ts.slurm
   ```

   On `USR1`, the script requests `hubbardflow stop` with a 60-second
   timeout, waits for the worker to drain, and leaves the manifest for
   resume. Resubmit with the same explicit variable to resume.

## Walltime and interpretation

The archived reference was reported at about 77 seconds. That is a past
measurement, not a runtime guarantee. Measure this fresh reference and the
one-column probe before estimating the full campaign. The full plan has six
times as many response runs as the probe. Compare the estimate with the
allocated walltime after reserving the 15-minute USR1 shutdown margin.
The Slurm limit is 96 hours; split work only by stopping and resuming the
same campaign manifest.

The probe reports one site's diagnostic U. It is not a supercell U.
Previously reported values are context only: 12.716122 eV from the
one-column probe and 12.673925610317943 eV from an archived test using a
different grid/run. The LR-16 target 12.6751 eV has unknown provenance and
is marked `PENDIENTE_LR16_CU3N_TARGET_PROVENANCE`; it is never an acceptance
criterion.

LR-16 acceptance compares TS and direct U per site on the same geometry,
using a tolerance declared by the user. This kit declares no acceptance
tolerance and cannot certify LR-16 by itself.

## Evidence and safeguards

After the jobs finish, make a light evidence pack:

```bash
bash bin/pack_evidence.sh
```

The pack includes the FDF, SIESTA outputs, non-matrix JSON evidence, logs,
receipts, and hashes. It excludes pseudopotentials, DMs, matrix exports, and
the matrix-bearing report source in `results/data/` and rendered report in
`results/`.

The kit has not been tested on Yoltla. The local dry-run used the supplied
full-site FDF and matching archived reference output; scheduler placement,
the fresh reference, the one-column probe, and campaign execution remain
for the operator to verify. Never interpret a hash difference as a
physical acceptance result.
