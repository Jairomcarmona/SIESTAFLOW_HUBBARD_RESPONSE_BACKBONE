# Archived one-off maintenance scripts

These scripts were root-level, unreferenced utilities from the repository's
initial RC cleanup work. They are preserved here as historical source, not as
supported maintenance commands. Several rewrite or append test files when run;
inspect them before any manual use.

The `First tracked commit` column records the origin of each archived path.
All nine paths were added by commit `49e915ac4e12b1d389bdd804ea0b6d1f649817f2`
(`Final RC fixes: Physical invariants, coverage restoration, and Subagent F
validation`); the later HubbardFlow rename commits only modified some of them.

| Script | Original purpose | First tracked commit |
| --- | --- | --- |
| `add_imports.py` | Walk test files and add `SemanticValidator` and `CampaignManifest` imports when needed. | `49e915ac4e12b1d389bdd804ea0b6d1f649817f2` |
| `append_tests.py` | Append legacy CLI failure-case tests to `tests/test_cli_and_manifest.py`. | `49e915ac4e12b1d389bdd804ea0b6d1f649817f2` |
| `fix_block.py` | Rewrite an expected DFTU projector block in a backend test. | `49e915ac4e12b1d389bdd804ea0b6d1f649817f2` |
| `fix_tests.py` | Replace broad placeholder-like test files with a generated semantic-validation test. | `49e915ac4e12b1d389bdd804ea0b6d1f649817f2` |
| `fix_tests_safe.py` | Earlier variant that replaces placeholder-like tests with generated assertions. | `49e915ac4e12b1d389bdd804ea0b6d1f649817f2` |
| `fix_tests_safest.py` | More selective variant that replaces test placeholders and adds imports. | `49e915ac4e12b1d389bdd804ea0b6d1f649817f2` |
| `patch_fdf.py` | Update expected FDF text in `tests/backend/test_fdf_builder.py`. | `49e915ac4e12b1d389bdd804ea0b6d1f649817f2` |
| `test_proj.py` | Print a sample DFTU projector block built by `FdfBuilder`. | `49e915ac4e12b1d389bdd804ea0b6d1f649817f2` |
| `update_cli_tests.py` | Append legacy campaign-state CLI tests to `tests/test_cli_and_manifest.py`. | `49e915ac4e12b1d389bdd804ea0b6d1f649817f2` |
