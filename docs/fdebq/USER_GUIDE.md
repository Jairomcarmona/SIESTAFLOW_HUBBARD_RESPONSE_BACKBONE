# HubbardFlow product commands

The FDF product interface freezes TASK 7–12 planning evidence and consumes its
immutable identity at the execution admission boundary. Production from this
interface currently returns `NOT_ESTABLISHED`: the complete FDRC I.5 runtime
state producer remains unavailable. No product command launches SIESTA in this
state. Existing `init`, `run campaign.v2.json`, `resume`, `status`, `report`,
`stop` and WSL pointer commands retain their existing interface.

```bash
hubbardflow plan system.fdf --lr-config lr.json \
  --reference-output reference.out --reference-dm reference.DM \
  --coverage DIAGNOSTIC --alpha-strategy FIXED_PROTOCOL_GRID \
  --output-dir product-plan
hubbardflow run system.fdf --output-dir product-plan
hubbardflow submit system.fdf --output-dir product-plan \
  --partition YOUR_PARTITION --account YOUR_ACCOUNT
```

The partition is required and chosen by the user. Account is optional and has
no default. Their values are recorded in the submission boundary receipt.
Machine profiles and local/MPI/SLURM dispatch remain upstream prerequisites
for production admission; this boundary does not infer a machine.

`plan system.fdf` without `--lr-config` creates an inventory diagnostic with
`NOT_ESTABLISHED / LR_CONFIG_REQUIRED`. It never invents an alpha grid,
estimator, tolerance or backend identity. With `--reference-output`, it also
records the single-output coverage diagnostic. Species identity directories
can be supplied with repeated `--identity-dir`; otherwise the FDF directory
is searched. Config pseudopotential directories are also searched.

The LR config uses the existing `siestaflow.lr_config.v2` schema. Its file
paths are relative to that config. The CLI accepts reference paths relative
to the current directory. Provide an explicit `alpha_grid_ev`, declared
analysis policy, functional, pseudopotentials, compatibility registry,
version text and executable identity, as for the existing `init` interface.
The planner calls the existing versioned estimator policy and retains the
fixed-grid behavior. CLI coverage/strategy/reference options override the
corresponding config fields and enter the frozen provenance.

## States and artifacts

| State | Meaning and next action |
|---|---|
| READY | Static plan qualified under its domain contract. Product execution still checks runtime dependencies. |
| REVIEW | Resolve shadows or required validation/evidence before qualified production. |
| NOT_ESTABLISHED | Supply missing protocol, reference, parent-DM, semantic species or validation evidence. |
| FAIL | Unsupported inventory or invalid input cannot be executed; correct the source. |
| AMBIGUOUS | An F1–F8 condition inside a declared band is inconclusive. It excludes reduction and retains explicit perturbations. |

The `run system.fdf` product route can execute a plan through the legacy campaign
runner only when it has an explicit fixed grid, a valid inventory, direct runs
for every site and mode, no adaptive policy, no reductions, no optional spin
flip/rotation/species split, and coverage set to `DISABLED` or `DIAGNOSTIC`.
For this route, missing reference and parent-DM evidence remain coverage
diagnostics; the plan still records them. Reduced or calibrated plans retain
the I.5 and pilot-reuse execution requirements, and `--override-plan-state`
cannot bypass those requirements.

| Plan shape | Product execution | State handling |
|---|---|---|
| Explicit fixed grid; every site/mode direct; no adaptive policy or optional symmetry | Admissible through `run system.fdf --profile P --name N` in a Linux shell | I.5 and pilot reuse are `NOT_REQUIRED`; reference/parent-DM findings remain coverage diagnostics |
| Reduced, calibrated, staged split, incomplete inventory, or unsupported coverage | Blocked with a receipt | Existing I.5, pilot reuse and plan-state requirements remain in force; an override does not admit execution |

The executable route freezes the merged path-resolved lr-config and hashes its
source inputs before initialization. It verifies the byte-preserving source
FDF/config copies, includes and declared dependency copies before starting the
legacy worker. An existing `execution_link.json` means the campaign already
has a linked run; continue it with `hubbardflow resume <campaign.v2.json>`.
On Windows, run the command from a Linux shell such as WSL. `submit` remains a
receipt-only request.

Default sidecar location is `.hubbardflow/<FDF stem>` in the current directory;
use `--output-dir` to choose a distinct location outside frozen V6 directories.
Destination protection reads every path in `SCIENTIFIC_BASELINE_V6.sha256`,
rejects all named AGENTS.md directories, frozen report/archive names and their
descendants, and prevents canonical sidecars from colliding with manifest
files. A missing or malformed manifest fails closed. Ordinary workspace and
external output directories remain available.
The artifacts are:

- `product_plan.json`: `hubbardflow.product_plan.v1`, exact plan state,
  immutable request, inventory, diagnostic coverage and all reason codes.
- `resolved_perturbation_plan.json`: the actual TASK 12
  `hubbardflow.resolved_perturbation_plan.v1`, when declared inputs support it.
  A protocol-free diagnostic does not fabricate this artifact.
- `product_campaign.lock`: `hubbardflow.product_campaign_lock.v1`, binding
  campaign identity and resolved plan digest.
- `plan_report.md`: inventory, every decision and evidence, F1–F8 values,
  mandatory shadows, coverage candidates versus computed columns, per-column
  alpha/estimator/SCF protocol, all provenance digests and required actions.
- `run.<digest>.receipt.json` or `submit.<digest>.receipt.json`:
  `hubbardflow.product_execution_boundary.v1`, requested execution, plan
  state, campaign/plan identities, override and scheduler choices.
  `run_report.md` / `submit_report.md` render the latest admission result.

`run` and `submit` load and validate the frozen resolved plan and campaign
identity. If no product artifact exists, they plan first. Repeating the same
request reuses its artifacts. Changed FDF/includes, reference output, DM,
species/static bytes, protocol, bands, flags or backend identity invalidate
the frozen artifact. Use a fresh output directory for a changed campaign.
A non-READY plan adds `PLAN_NOT_READY` and exits 3. A malformed input or
invalidated identity exits 2. `plan` exits 0 when it successfully writes a
diagnostic or plan, including a lower qualification state.

An explicit request can be recorded with:

```bash
hubbardflow run system.fdf --output-dir product-plan \
  --override-plan-state "user-declared exploratory request"
```

The reason enters an immutable receipt tied to the campaign identity. It
removes the user-state barrier, but unavailable production dependencies still
return `NOT_ESTABLISHED` and exit 3. `SCIENTIFIC_STATE_NOT_ESTABLISHED` records
the absent I.5 gate; `PILOT_REUSE_NOT_ESTABLISHED` records that no operational
pilot-source/complete receipt connection exists. No pilot is reused by name.

## Features and qualification limits

Coverage defaults to `DIAGNOSTIC` and computes all columns. `DISABLED` retains
the fixed explicit path. `TRANSLATION_SHADOWED` records representatives,
mandatory shadows and reconstruction maps; the runtime I.5 gate still limits
production admission. Diagnostic candidates never grant `PROVEN` by themselves.

### Translation-shadowed runs

Create a validated reference state first. The command runs only the unperturbed
reference node and saves its output and DM under `planning_reference/`:

```bash
hubbardflow reference system.fdf --lr-config lr_config.json \
  --profile execution_profile.json --name system-reference
```

Use the printed follow-up command to start the response campaign. It supplies
the archived reference files and opts into the qualified reduction:

```bash
hubbardflow run system.fdf --lr-config lr_config.json \
  --profile execution_profile.json --name system-ts \
  --reference-output .hubbardflow/system-reference/planning_reference/reference.out \
  --reference-dm .hubbardflow/system-reference/planning_reference/system.DM \
  --coverage TRANSLATION_SHADOWED
```

The DM filename must match the FDF `SystemLabel` output name. A
`PARENT_DM_NOT_REPRODUCED` result means the representative did not reproduce
the archived reference DM within the recorded evidence; the reduction cannot
continue from that parent and the affected class falls back to explicit
perturbations. Choose `DISABLED` when you want every site column explicitly
perturbed or when translation-based reduction is not qualified for the input.
Replace `system.DM` in the example with the exact `<SystemLabel>.DM` filename
written by the reference command.

Spin flip and rotations default to false. Opt-ins `--allow-spin-flip` and
`--allow-rotations` are recorded in the coverage policy and plan digest.
They retain the qualification limits in [VALIDATION_GATES.md](VALIDATION_GATES.md).
Rotations record `egg_box_quantification = NOT_QUANTIFIED`. The fixed/user
alpha strategies remain available; `CALIBRATED_GRID` reports
`CALIBRATION_PROTOCOL_REQUIRED` when no explicit protocol exists, or
`CALIBRATED_VALIDATION_NOT_ESTABLISHED` while I.5, SCF ESTIMATE and recorded
T0–T4 validation are unavailable. `auto_split_species` defaults to false;
opt-in stages shared labels with `STAGED_PENDING_GENERATED_IDENTITY` and binds
the staging manifest to the frozen product identity. Generated `.ion` verification
uses exact raw SHA256 equality; its receipt cannot unlock production on its own.
See [SPECIES_SPLIT_RUNBOOK.md](SPECIES_SPLIT_RUNBOOK.md) for the user-run procedure.
An unadmitted shared DFTU label reports `SHARED_LABEL_NEEDS_SPLIT`.

This report is planning/admission evidence. With execution blocked, χ0/χ,
matrix gates, U, budgets, qualification and the existing downstream
certification remain `NOT_ASSESSED`. Conditional error-model qualification
does not confer a certificate. Real runtime validation is performed by the
user using [T0_T4_RUNBOOK.md](T0_T4_RUNBOOK.md) and the validation gates.

## Long campaigns from WSL

Run long campaigns from WSL with a new product directory and a unique campaign name. Keep the product artifacts and launch log in `product_dir`. For a `local_wsl` execution profile, set `wsl.workspace_root` to a new campaign workspace in the same run directory; the campaign manifest and its results are created there. Set these variables in the launch shell, replacing the example paths with paths valid in that WSL distribution:

```bash
code=/path/to/frozen/hubbardflow
py=/path/to/python
fdf=/path/to/inputs/reference.fdf
lr_config=/path/to/inputs/lr_config.json
profile=/path/to/inputs/execution_profile.json
campaign_name=unique_campaign_name
product_dir=/path/to/new/product
campaign_workspace=/path/to/new/campaigns
campaign_manifest="$campaign_workspace/$campaign_name/campaign.v2.json"
```

Before launch, confirm that `$profile` has `wsl.workspace_root` set to `$campaign_workspace`. Launch from the Linux shell with `setsid` and `nohup` so the worker is detached from the terminal:

```bash
setsid nohup env PYTHONPATH="$code/src" "$py" -m hubbardflow.cli run \
  "$fdf" --lr-config "$lr_config" --profile "$profile" \
  --name "$campaign_name" --output-dir "$product_dir" \
  < /dev/null > "$product_dir/run.log" 2>&1 &
worker_pid=$!
printf 'worker PID: %s\n' "$worker_pid"
```

Open a separate WSL shell. Define `campaign_name`, `campaign_workspace`, `code` and `py` there too; shell variables from the launch terminal are not shared. Find the worker by its unique campaign name, then check its durable status:

```bash
campaign_name=unique_campaign_name
campaign_workspace=/path/to/new/campaigns
code=/path/to/frozen/hubbardflow
py=/path/to/python
campaign_manifest="$campaign_workspace/$campaign_name/campaign.v2.json"
pgrep -af "hubbardflow.cli run .*--name $campaign_name"
PYTHONPATH="$code/src" "$py" -m hubbardflow.cli status "$campaign_manifest"
```

A completed campaign should have a terminal completed status and its expected result artifacts. A failed node records `failure.json` in that node attempt's working directory (`command.cwd`); inspect it together with `run.log` and the worker state before deciding whether to resume. Do not infer success from the launch shell returning or from a log file existing. Keep one local SIESTA campaign active when the execution profile requires an exclusive local slot.

The product execution boundary may record `ADMISSIBLE_LEGACY_EQUIVALENT` for a fixed-grid run even when broader planning qualification remains `NOT_ESTABLISHED`; the run receipt and report state which admission was used. This is distinct from claiming the broader production qualification is established.
