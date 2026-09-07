# Resumable single-allocation DAG execution playbook

This is the fixed operational pattern for an HPC campaign in which a validated
parent calculation supplies an artifact to multiple response calculations. It
is independent of material, scheduler partition, hostnames, account, paths,
and executable location. Those values belong to a private site execution
profile, not to this document.

The pattern has been exercised end to end for independent linear-response
campaigns: a parent artifact was reused, response calculations ran in a
deterministic order, semantic validation gated every edge, and analysis ran
only after the required response set was valid.

## Objective

Acquire one scheduler allocation and retain it while the controller traverses
the complete DAG. A single calculation consumes the entire declared MPI
allocation at a time. This is deliberately different from:

- a scheduler array, where each child obtains an independent allocation;
- launching several background MPI programs inside one allocation;
- requesting `N` scheduler tasks but launching each program with fewer than
  `N` MPI ranks.

The allocation is an execution resource; it does not change the scientific
DAG, inputs, or numerical acceptance rules.

## Fixed graph semantics

```text
REFERENCE --validated parent artifact--> RESPONSE[1] --> RESPONSE[2] --> ... --> RESPONSE[n] --> ANALYZE
```

The response nodes may be scientifically independent siblings, but are run
sequentially as a scheduling policy. Each child receives a fresh copy of the
same validated parent artifact. It must never inherit a sibling's work copy.

The ordered controller loop is:

1. validate an already existing parent or run it;
2. for each declared response node, skip it only when it is scientifically
   valid; otherwise stage a fresh parent copy, run it, then validate it;
3. run analysis exactly once after every required node is valid.

No descendant may start after a failed parent, failed output validation, or
failed scientific validation.

## Allocation and MPI placement contract

The private execution profile declares three consistent values:

```text
allocated nodes = H
processes per node = P
MPI ranks per calculation = H × P
```

At job start, before changing a scientific run directory, the controller must:

1. read the scheduler's granted node list, rather than infer hosts;
2. verify that exactly `H` unique hosts were granted;
3. verify that scheduler task count is exactly `H × P`;
4. launch a harmless MPI placement probe using the exact planned launcher,
   hosts, ranks and processes-per-node;
5. require exactly `P` probe records for every granted host.

Only a passing probe authorizes the first scientific executable. This catches
host-resolution, SSH/bootstrap, process-count and topology errors before they
can create or replace scientific output.

For a Hydra-based private plugin, the command shape is conceptually:

```text
mpiexec.hydra -bootstrap <declared> -hosts <granted-hosts> \
  -ppn P -n (H × P) <executable>
```

The controller itself is not an MPI process. It launches exactly one MPI
calculation, waits for its terminal validation, and only then launches the
next one.

## Resume and evidence preservation

Resume is a scientific state transition, not merely a scheduler retry.

| Prior node state | Resume action |
|---|---|
| Validated parent | preserve it and reuse its immutable artifact |
| Validated child | skip it |
| Missing or interrupted child | archive its attempt evidence, stage a fresh parent copy, rerun it |
| Failed validation | archive its evidence; stop or retry only under an explicit workflow policy |
| Analysis absent with all inputs valid | run analysis |

An interrupted attempt's stdout, stderr, termination marker and mutable work
artifact must be retained in an attempt archive before a retry. It is
diagnostic evidence only: it must not be accepted as a result or reused as a
parent artifact.

For every child attempt, overwrite the child's work-copy destination from the
validated canonical parent immediately before launch. This prevents accidental
use of a partial or stale child artifact.

## Scientific gates

A scheduler exit code alone is insufficient. Define the workflow's gate for
each response mode and apply it immediately after the executable returns.

For the linear-response SIESTA workflow, the required gates are:

| Node | Required acceptance |
|---|---|
| Reference | normal completion, converged SCF, semantic parent artifact present and non-empty |
| BARE response | normal completion and valid semantic BARE observation; convergence requirement is workflow-defined |
| SCREENED response | normal completion, converged SCF, valid semantic SCREENED observation |
| Analysis | every declared response observation valid; required matrices full rank; direct inversion succeeds |

Analysis must not silently use a pseudoinverse, partial response set, or
fallback numerical path unless the scientific workflow explicitly defines and
labels that alternative.

## Completion conditions

The controller reports completion only after all conditions hold:

```text
placement probe passed
AND parent is validated
AND every declared response is validated
AND final analysis is validated
AND final result artifact is present
```

The final record should expose logical DAG events, for example:

```text
PLACEMENT_OK
SKIP_VALID <node>
RUN <node>
DONE <node>
COMPLETE <result>
```

The event stream permits read-only monitoring of the current node and next
node without modifying calculations.

## Prohibited patterns

- Do not mix the single-allocation controller with job arrays or manual child
  submissions for the same campaign.
- Do not run sibling MPI calculations in the background unless the workflow
  explicitly groups them and provides isolated, validated placement for each.
- Do not submit a replacement parent while a valid parent artifact exists.
- Do not overwrite a valid output during resume.
- Do not retain an allocation after the controller has no runnable or pending
  node.
- Do not publish site profiles, scheduler logs, node names, paths, users,
  accounts, private artifacts, or production outputs in the public repository.

## Campaign author checklist

Before submission, the campaign author must confirm:

- [ ] The workflow lock declares all nodes, parent artifacts and analysis
      inputs.
- [ ] The private site profile supplies a validated allocation and launcher.
- [ ] The wrapper has Unix line endings and strict shell mode.
- [ ] The placement probe is executed before the first scientific run.
- [ ] Each child gets a fresh canonical parent work copy.
- [ ] Every node has an explicit normal-completion, convergence and semantic
      validation policy.
- [ ] Resume archives invalid attempts and skips only validated nodes.
- [ ] Analysis has no partial or implicit fallback path.
