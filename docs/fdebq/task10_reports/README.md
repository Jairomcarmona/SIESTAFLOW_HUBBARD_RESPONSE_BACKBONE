# TASK 10 diagnostic goldens

The JSON files here freeze the admission/coverage contract and source hashes,
without repeating every geometric operation. Tests compare these contracts and
also require byte-identical JSON and Markdown on repeated full diagnostics.

The source files are read only. The diagnostic schedules no runs. It requires
two distinct report destinations, which cannot overwrite either source.

Example, from an environment with HubbardFlow dependencies installed:

```powershell
$env:PYTHONPATH='src;.'
python tools/hubbardflow_plan_diagnose.py examples/tmo_campaigns/CoO_ref.fdf `
  --reference-output examples/tmo_campaigns/CoO_ref.out `
  --json coverage-diagnostic.json --markdown coverage-diagnostic.md
```

The named `coverage-policy-v1` profile supplies the versioned bands. Spin flip
and rotations remain off; explicit `--allow-spin-flip` / `--allow-rotations`
are recorded in the qualification digest. `--coverage DISABLED` records that
choice and keeps every column explicit. `--identity-dir` supplies explicit
directories for label-specific semantic identity evidence. Parent DM identity
is recorded as absent unless actual evidence is supplied by a later plan stage.

CoO/NiO/FeO have negative admission goldens. The named Cu3N output is also
negative: its echoed input declares a nonzero potential shift and differs from
the supplied FDF. MnO has positive D1 admission but negative semantic identity
qualification. See BLOCKERS.md for the precise source limitations. Synthetic
tests cover non-polarized translations and MnO 16->2 / 16->1 candidates.

Both are `conservative implementer decision` under AMENDMENTS_2.md:
neither source limitation is repaired by fabricating or joining evidence.
