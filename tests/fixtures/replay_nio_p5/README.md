# NiO P5 runner replay inputs

The fixture has one run record for each of the 24 materialized response FDFs
and one for the reference FDF. `manifest.json` binds each input FDF SHA256 to
the recorded `siesta.out` SHA256, the recorded DM SHA256 and their compressed
fixture paths. The two run artifacts are xz-compressed; the Python replay
executable verifies their hashes before returning them to the production
runner. The compressed SIESTA output and DM payloads total about 30.3 MB,
below the 50 MB cap. The test initializes from the byte-verified inputs in
`tests/fixtures/real_nio_p5_rerun/inputs/`.

`siesta` is the test executable registered by SHA256 in a test-written backend
compatibility registry. `mpirun.openmpi` executes its supplied executable
argument. Neither invokes a real SIESTA binary. The test's local WSL profile
uses one MPI rank and an empty environment.

`campaign_manifest.sha256.json` is the frozen manifest of every persisted
campaign file after deterministic campaign identity/timestamps and temporary
workspace/attempt path normalization. The test requests a safe stop on the
13th invocation, resumes from the real worker, and compares the final files to
this manifest.
