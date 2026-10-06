# PowerShell → WSL campaign CLI

This route creates a fixed-grid or policy-driven adaptive-α campaign in the profile's WSL ext4 workspace. The profile sets the MPI rank count, and a detached WSL worker executes one SIESTA node at a time. Closing PowerShell does not stop the worker. `wsl --shutdown` or a Windows restart does; continue with `resume` afterward.

## Install the command

Install the package in the Windows Python environment used by PowerShell and in the selected WSL distribution. The Windows installation provides the PowerShell-facing command; the WSL installation runs the detached worker.

```powershell
py -m pip install -e .
```

```bash
python3 -m pip install -e .
```

Run these commands from the HubbardFlow checkout root. This package does not install SIESTA or MPI.

## Local WSL profile template

Save as `local-wsl-profile.json` and replace every `<...>` marker with the observed values for the target distribution. Keep `evidence` as `UNKNOWN` while assembling the profile: `init` intentionally refuses that value. Set it to `VALIDATED_RUNTIME` only after confirming the named distribution, Python interpreter, SIESTA binary, direct Open MPI launcher and resource limits are present and usable. No machine-specific path or validated runtime is assumed here.

```json
{
  "target": "local_wsl",
  "evidence": "UNKNOWN",
  "wsl": {
    "distribution": "<wsl-distribution-name>",
    "python_executable": "/usr/bin/python3",
    "workspace_root": "/home/<linux-user>/hubbardflow-campaigns"
  },
  "allocation": {
    "nodes": 1,
    "total_cpus": 4,
    "memory": "<available-memory, e.g. 8G>",
    "walltime": "<HH:MM:SS>",
    "max_parallel_steps": 1,
    "shutdown_margin_seconds": 60,
    "termination_grace_seconds": 30
  },
  "runtime": {
    "module_commands": [],
    "siesta_executable": "/<absolute-wsl-path>/siesta",
    "exclusive": true,
    "environment": {},
    "launcher": {
      "kind": "openmpi",
      "command": ["/<absolute-wsl-path>/mpiexec.openmpi"],
      "bootstrap": "local",
      "processes_per_node": 4
    }
  },
  "task_policy": {
    "max_attempts": 1,
    "require_scf_converged": true
  }
}
```

`total_cpus` and `processes_per_node` must match; set both to the rank count you intend to use. Campaign initialization and the worker reject a count above the CPU affinity visible inside WSL. For example, choosing ten ranks means setting both fields to `10`, after confirming `nproc` in that distribution. A shared file lock under `workspace_root` serializes SIESTA nodes across campaigns using that workspace, so only one local SIESTA process runs at a time. The launcher must be a direct executable path named `orterun`, `mpiexec.openmpi` or `mpirun.openmpi`; shell wrappers and Hydra/SSH are not accepted for `local_wsl`.

The profile's `VALIDATED_RUNTIME` declaration is a deployment assertion, not proof that a scientific backend is admitted. Before a worker starts, the existing admission gate still checks the exact SIESTA executable identity/version against the supplied compatibility registry and the source-audited SIESTA 5.4.2 BARE profile. A different SIESTA version requires a matching audited profile; it is not accepted by changing this JSON label.

## Linear-response config template

Save as `lr-config.json`; Windows paths below are placeholders. Correlated `site_id` values must match the FDF's `DFTU.Proj`/species labels, and `atom_index` is 1-based. Every declared site is perturbed at each symmetric α value, in both BARE and SCREENED modes.

```json
{
  "schema": "siestaflow.lr_config.v2",
  "material": "<material-label>",
  "functional": "PBE",
  "sites": [
    {"site_id": "M0", "atom_index": 1, "orbit_id": "M0"},
    {"site_id": "M1", "atom_index": 2, "orbit_id": "M1"}
  ],
  "alpha_grid_ev": [-0.15, -0.10, -0.05, 0.05, 0.10, 0.15],
  "pseudopotentials": {
    "M0": "C:\\path\\to\\M.psml",
    "M1": "C:\\path\\to\\M.psml",
    "O": "C:\\path\\to\\O.psml"
  },
  "static_artifacts": {},
  "compatibility_registry": "C:\\path\\to\\backend-compatibility.json",
  "version_text_source": "C:\\path\\to\\siesta-version.txt",
  "declared_executable": "siesta",
  "reference_dm_name": "reference.DM",
  "analysis_policy": {
    "estimator": "auto",
    "polynomial_degree": 3,
    "minimum_residual_dof": 1,
    "matrix_for_inversion": "raw"
  }
}
```

Use the actual complete species labels in `pseudopotentials`; this illustration uses two correlated sites plus oxygen and may need adjustment to the FDF. The PSML files must identify the same functional as the reference FDF. The supplied registry and version text must correspond to the exact WSL SIESTA executable. A `magnetic_moment_tolerance_muB` may be added only when it is declared for this campaign. If omitted, moment continuity is reported as unknown and a computable U remains a sensitive numerical candidate; a detected branch change suppresses a combined U.

The config above selects the compatible fixed-grid route. For an adaptive campaign, add a versioned `adaptive_alpha_policy` object and keep `alpha_grid_ev` equal to its six non-zero seed amplitudes; zero is the one shared reference calculation. `init` copies that policy into the campaign config and manifest, and the worker rejects a changed seed or a budget smaller than the seed run.

### Declaring sensitivity tolerance

Sensitivity tolerance has no inferred value and remains unset unless explicitly declared. Set the absolute tolerance in eV in the LR config:

```json
{
  "analysis_policy": {
    "sensitivity_tolerance_eV": 0.02
  }
}
```

The value must be finite and nonnegative; zero is a valid exact threshold. Product commands also accept `--sensitivity-tolerance-ev VALUE`, which freezes the supplied value into the effective LR config and records `provided_via=cli`. Reports record the effective declaration as `declared_by=config`, its source channel, and the resulting state: `UNASSESSED`, `SENSITIVE`, `WITHIN_TOLERANCE_EVIDENCE_INCOMPLETE`, or `NUMERICAL_CANDIDATE`. Without a declared tolerance the result remains `UNASSESSED`; HubbardFlow does not infer a threshold.

### Adaptive policy with no uncalibrated tolerances

The following illustrative policy deliberately omits stability, truncation, and noise thresholds. It can record a numerical candidate and stop as sensitive, but it cannot claim `STOP_STABLE`, probe SCF noise, shrink, or expand. The example values for `h_eV` and the seed span are inputs to this illustration, not validated SIESTA defaults.

```json
{
  "adaptive_alpha_policy": {
    "schema": "siestaflow.adaptive_alpha_policy.v1",
    "h_eV": 0.05,
    "alpha_seed_span_eV": 0.15,
    "alpha_ceiling_eV": null,
    "max_refinement_rounds": 2,
    "max_alpha_points": 11,
    "total_siesta_node_budget": 25,
    "round_analysis": {
      "initial": {"active_window_eV": 0.15, "estimator": "polynomial", "polynomial_degree": 3, "minimum_residual_dof": 1, "matrix_for_inversion": "raw"},
      "shrink": [
        {"active_window_eV": 0.10, "estimator": "polynomial", "polynomial_degree": 3, "minimum_residual_dof": 1, "matrix_for_inversion": "raw"},
        {"active_window_eV": 0.05, "estimator": "polynomial", "polynomial_degree": 3, "minimum_residual_dof": 1, "matrix_for_inversion": "raw"}
      ],
      "expand": [
        {"active_window_eV": 0.15, "estimator": "polynomial", "polynomial_degree": 3, "minimum_residual_dof": 1, "matrix_for_inversion": "raw"},
        {"active_window_eV": 0.15, "estimator": "polynomial", "polynomial_degree": 3, "minimum_residual_dof": 1, "matrix_for_inversion": "raw"}
      ]
    },
    "tol_abs_eV": null,
    "tol_rel": null,
    "truncation_threshold_eV": null,
    "sensitivity_delta_tolerance_eV": null,
    "probe_trigger_ratio": null,
    "scf_materiality_ratio": null,
    "rho_min": null,
    "scf_probe_level": null
  }
}
```

For the two-site example above, the seed budget is 25 SIESTA nodes: one reference shared across the campaign plus BARE and SCREENED at six non-zero α values for each site. Set `total_siesta_node_budget` to the actual total job allowance; it also counts each new reference, SCF probe, and missing response node. Every refinement branch declares its own fit window, method, degree, minimum residual DoF, and inversion matrix. Missing predicates produce a sensitive result with the reason and remaining budget; values are not inferred from other campaigns or literature.

With the illustrated `h_eV = 0.05`, each `shrink` round adds the next symmetric inner pair (first ±0.025 eV, then ±0.0125 eV). The fit window narrows from ±0.10 eV to ±0.05 eV, so adding points also changes which observations enter the fit. A cubic fit with one residual degree of freedom needs at least five usable α points in each declared window; `init` rejects a policy that cannot supply them. The seed run alone costs 25 nodes for the two-site example; each shrink round adds eight response nodes, before any SCF probe or strict-level rerun. The example budget of 25 intentionally cannot fund refinement, which is consistent with its omitted thresholds and sensitive stop.

## Commands

From PowerShell, with the profile and input files on Windows:

```powershell
hubbardflow init .\reference.fdf --lr-config .\lr-config.json --profile .\local-wsl-profile.json --name material-lr
hubbardflow run .\material-lr.siestaflow.json
hubbardflow status .\material-lr.siestaflow.json
hubbardflow resume .\material-lr.siestaflow.json
hubbardflow report .\material-lr.siestaflow.json
hubbardflow stop .\material-lr.siestaflow.json
```

`init` creates the campaign directory and immutable input inventory under the WSL profile's `workspace_root`. It writes a small Windows pointer JSON beside the current PowerShell directory unless `--pointer` supplies another location. `run` returns after registering the detached worker. `report` shows the canonical Markdown report once matrix analysis completes; before that it shows campaign status. Resume revalidates completed node evidence and reruns only invalid/incomplete nodes and their descendants.

## Linux CLI with an existing Slurm allocation

The Linux public CLI can create and control a direct `campaign.v2.json` manifest for a profile with `target="slurm"`. Run it inside the already granted allocation with the site-validated profile. This interface uses the allocation's hosts; it does not submit `sbatch`.

```bash
hubbardflow audit-fdf ./reference.fdf
hubbardflow init ./reference.fdf --lr-config ./lr-config.json --profile ./slurm-profile.json --name material-lr --campaign-root /scratch/hubbardflow-campaigns
hubbardflow run /scratch/hubbardflow-campaigns/material-lr/campaign.v2.json
hubbardflow status /scratch/hubbardflow-campaigns/material-lr/campaign.v2.json
hubbardflow resume /scratch/hubbardflow-campaigns/material-lr/campaign.v2.json
hubbardflow report /scratch/hubbardflow-campaigns/material-lr/campaign.v2.json
hubbardflow stop /scratch/hubbardflow-campaigns/material-lr/campaign.v2.json
```

The Slurm launcher, profile, and allocation must pass the existing runtime checks. This is not a generic SSH or queue-submission route. See [HPC_SLURM_EXECUTION_CONTRACT.md](HPC_SLURM_EXECUTION_CONTRACT.md).

## Fixed-grid node cost and result states

For `S` correlated sites and `A` nonzero α amplitudes, a fixed-grid campaign uses `1 + 2 × S × A` SIESTA nodes: one shared reference and BARE plus SCREENED for every site/amplitude pair. The six-amplitude routes frozen for this release use 13 nodes for one site and 25 for the two-site NiO alternative. Adaptive campaigns require their own declared total node budget and policy; this example does not set adaptive defaults.

The report may terminate with `NUMERICAL_CANDIDATE_UNASSESSED` when no scientific U tolerance is configured, and it keeps physical acceptance separate. HubbardFlow does not convert `U_scalar_charge` automatically to `Ueff_Dudarev`. Freeze α, tolerances, projectors, windows, and criteria before a campaign; do not tune them to obtain a preferred result.
