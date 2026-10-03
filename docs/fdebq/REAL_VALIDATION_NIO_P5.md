# Real NiO P5 validation (Parte A)

## Execution identity and inputs

The SIESTA campaign ran from the frozen WSL/ext4 source tree
`/home/jmc/hubbardflow_validation/code_5a3fe5b3d51da0a229a2d2d8e93e839089edd9cb`,
whose `git rev-parse HEAD` was
`5a3fe5b3d51da0a229a2d2d8e93e839089edd9cb`. Python was
`/home/jmc/.local/state/siestaflow/hubbard-response-env/bin/python`; SIESTA was
`/home/jmc/.local/siesta-5.4.2-openmpi/bin/siesta`, version 5.4.2. The WSL
workspace was `/home/jmc/hubbardflow_validation/nio_p5_20261003`. All eight
required input contents were verified before copying. Their verified copies
remain under that workspace's `inputs/` directory.

| Input | SHA256 | Verified copy |
|---|---|---|
| `reference.fdf` | `b4fb34e642d862be6949a5b2033a60c5b9fcae56119879583bb3eaf237620ee7` | `inputs/reference.fdf` |
| original `provenance/source_lr_config.json` | `34357c804b55ba1b64528e7032d4fe94c20779e2ebedcb77e4c8d872a94cd14a` | `inputs/source_lr_config.json` |
| `execution_profile.json` | `fbc9ff5ae47a6791d0e1ff962b6070f8690f1ffef475bafd8784a7388d755ae1` | `inputs/execution_profile.json` |
| `pseudopotentials/NiLR0.psml` | `192eb05ffb64671715e570e2ca9a99a551cf15544984592082d43004f8554e06` | `inputs/pseudopotentials/NiLR0.psml` |
| `pseudopotentials/NiLR1.psml` | `192eb05ffb64671715e570e2ca9a99a551cf15544984592082d43004f8554e06` | `inputs/pseudopotentials/NiLR1.psml` |
| `pseudopotentials/O.psml` | `224ded5c59176d9bcb76d19b7a4a68a48d5dffabf8b262f64d5760250e87c35e` | `inputs/pseudopotentials/O.psml` |
| `software/backend_compatibility.json` | `5189620dfa1e8b6090cbdbb9c36c412835d16feb5c50bbc82b16c139d3bcff2e` | `inputs/software/backend_compatibility.json` |
| `software/siesta_version.txt` | `bb5a9b03dfaec9953401a7ef8db045149461047c44f15f9c5bf7758900b5f3ee` | `inputs/software/siesta_version.txt` |

The source configuration's hash was checked before rewriting. Only its four
absolute routes changed: the three pseudopotential paths now point to the
verified files below `inputs/pseudopotentials/`; `compatibility_registry` and
`version_text_source` now point below `inputs/software/`. No scientific or
policy field changed. The exact line diff is preserved at
`/home/jmc/hubbardflow_validation/nio_p5_20261003/lr_config_routes.diff`.
The rewritten `inputs/lr_config.json` was the one used by both `plan` and
`run`.

## Initial failure and diagnosis

The first product attempt used product folder `product` and campaign
`nio_p5_product`; that failed campaign and its files remain intact. Its
reference output was
`/home/jmc/.local/state/siestaflow/campaigns/nio_p5_product/.siestaflow/attempts/52367a6622b19f08825e/attempt-1791023189115487657-20e16006/reference_52367a6622b1/siesta.out`.
The output stopped at `stepf: Fermi-Dirac step function` (1071 lines),
`siesta.err` was empty, and the worker recorded `FAILED_EXECUTION` at
04:26:33.189 local time. The output's mtime was 04:26:33.183620; the nohup
`run.log` was last written at 04:26:33.189. The `run.pid` record was written at
04:26:28.140. The launch shell used `nohup ... &` followed by `sleep 4`; the
`wsl.exe` invocation duration was recorded as about 7.9 seconds, implying a
rough return time near 04:26:36 if measured from the `run.pid` timestamp. No
exact terminal-return timestamp or outer `wsl.exe` command transcript was
saved. On that approximate timeline `siesta.out` stopped about three seconds
before `wsl.exe` returned, so the recorded times **contradict** the specific
claim that it stopped writing seconds after the launch command finished. They
do not establish what stopped SIESTA, and no signal trace was recorded.

The exact `run` command passed to the launch shell was:

```sh
nohup env PYTHONPATH="$code/src" "$py" -m hubbardflow.cli run inputs/reference.fdf --lr-config inputs/lr_config.json --profile inputs/execution_profile.json --name nio_p5_product --output-dir product > run.log 2>&1 < /dev/null &
```

System evidence did not show OOM: `dmesg | tail -50` and `journalctl -k`
contained only WSL boot records, and searches for `Killed process`, `Out of
memory`, and OOM kill/reaper messages returned no hits. At the check, `free -h`
reported 7.4 GiB total, about 733 MiB used and 6.7 GiB available; swap was
0/2 GiB. `nproc` was 12. `MemTotal` was 7,778,964 kB and
`MemAvailable` about 7,040,000 kB.

The archived successful reference run and failed reference run had identical
materialized `siesta.fdf` SHA256
`b4fb34e642d862be6949a5b2033a60c5b9fcae56119879583bb3eaf237620ee7`.
Both used a 48 × 24 × 24 mesh (27,648 points), 200 Ry requested / 274.646 Ry
used cutoff, and MPI orbital distribution 17,17,17,13. The archived output
continued through `Job completed`; the failed output stopped immediately
after `stepf`.

A manual reproduction was performed under
`/home/jmc/hubbardflow_validation/nio_p5_20261003/diag_reference/`. The first
manual invocation accidentally ran from the repository root instead of the
copied node directory and failed with `Pseudopotential file not found:
NiLR0.{vps,psf,psml}`; that invalid-CWD result is retained in the diagnostic
record. The controlled invocation then ran in `diag_reference` with the
original argv:

```text
/usr/bin/orterun --host localhost:4 --map-by ppr:4:node -np 4 /home/jmc/.local/siesta-5.4.2-openmpi/bin/siesta
```

It exited 0 after 23.97 seconds, produced 2,425 output lines ending in `Job
completed`, and `/usr/bin/time -v` measured 190,888 KiB maximum RSS. Since the
same four-rank command succeeded with the same input and binary, the requested
one-rank reproduction was not run.

## Detached relaunch

The failed campaign and its `product` directory were not modified. Before the
new run, `nio_p5_product_2` did not exist; the existing
`nio_p5_product` campaign was left in place. `plan` and `run` used the same
`product_2` output directory and the frozen code above. The exact detached
launch command was:

```sh
setsid nohup env PYTHONPATH=/home/jmc/hubbardflow_validation/code_5a3fe5b3d51da0a229a2d2d8e93e839089edd9cb/src /home/jmc/.local/state/siestaflow/hubbard-response-env/bin/python -m hubbardflow.cli run inputs/reference.fdf --lr-config inputs/lr_config.json --profile inputs/execution_profile.json --name nio_p5_product_2 --output-dir product_2 < /dev/null > /home/jmc/hubbardflow_validation/nio_p5_20261003/product_2/run.log 2>&1
```

The launch shell returned at 04:48:02.696. A separate WSL invocation about
127 seconds later found worker PID 645 alive, plus `orterun` and four SIESTA
processes. The active response output grew from 36,328 to 44,205 bytes in four
seconds. `reference` had completed normally. The campaign completed at
04:52:55.384 local time, 292 seconds after its recorded worker start at
04:48:03.650. The worker state lists all 24 response nodes, `reference`,
`alpha-diagnostic-gate`, and `matrix-analysis` as validated.

The product `run` admission was `ADMISSIBLE_LEGACY_EQUIVALENT` with no admission
reasons. The product plan report still records coverage diagnostics
`REFERENCE_NOT_ADMISSIBLE` and `PARENT_DM_NOT_ESTABLISHED`; as instructed,
these did not block this direct-grid run. The plan itself does not calculate
run admission.

## Comparison against archived 20.9 result

The reference result was
`/home/jmc/.local/state/siestaflow/campaigns/nio-pbe-p5-20260928/results/lr_u_analysis.v3.json`.
The new result is
`/home/jmc/.local/state/siestaflow/campaigns/nio_p5_product_2/results/lr_u_analysis.v3.json`.

- **Exact grid and FDFs:** 24 coordinates across two sites, two modes and six
  alpha values. The `(site, atom_index, mode, alpha)` sets match exactly; all
  24 materialized FDF SHA256 values match exactly.
- **Occupations:** all 12 site/alpha observation rows match exactly for both
  BARE and SCREENED occupations at both observed sites. Maximum absolute
  difference is 0 electron, or 0 units of the 1e-6 electron print quantum.
- **U comparison:**

| Site | U new (eV) | U 20.9 (eV) | Absolute delta (eV) | New `U_scalar_half_width_by_site_eV` (eV) | Archived same field (eV) | New `U_scalar_interval_by_site_eV` (eV) | Archived same field (eV) |
|---|---:|---:|---:|---:|---:|---|---|
| NiLR0 (matrix index 0, atom index 0) | 6.864267700049239 | 6.864267700049239 | 0 | 0.0118330619317529 | 0.0118330619317529 | [6.852434638117486, 6.876100761980992] | [6.852434638117486, 6.876100761980992] |
| NiLR1 (matrix index 1, atom index 1) | 6.864387475210124 | 6.864387475210124 | 0 | 0.0118330619317529 | 0.0118330619317529 | [6.852554413278371, 6.876220537141878] | [6.852554413278371, 6.876220537141878] |

Both `primary` objects and `printing_rounding_bounds` objects compare equal.
Each U delta is also within the self-reported bound in each analysis. Verdict:
**IDENTICAL**.

The archived and rerun analysis JSON files are preserved under their campaign
result paths. The fixture copy of the new analysis and its separately extracted
observation dataset is in `tests/fixtures/real_nio_p5_rerun/`.

The analysis-only replay requested for this fixture is not implementable from
the dataset alone with the current interface: `analyze_verified_lr` accepts
`ResponseObservation` objects, and the runner also provides magnetic branch
evidence, validated occupation half-widths and campaign metadata, then adds
input provenance and the receipt-bound dataset. Those runner inputs are not
all represented in the dataset. No approximate or partial reconstruction is
claimed. The Part B POSIX replay is the end-to-end golden.

## Output inventory

The selected BARE and SCREENED output files, `siesta.out` block inventory,
example line numbers, and the note that eigenvalues are in `.EIG` rather than
printed as a list in stdout are recorded in
[`I5_OUTPUT_INVENTORY.md`](I5_OUTPUT_INVENTORY.md).
