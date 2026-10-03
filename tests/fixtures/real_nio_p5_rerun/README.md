# Real NiO P5 rerun fixture

This fixture records the completed Part A product campaign `nio_p5_product_2`
from `/home/jmc/.local/state/siestaflow/campaigns/nio_p5_product_2`. The
campaign used the eight byte-verified inputs listed in
`docs/fdebq/REAL_VALIDATION_NIO_P5.md`, the route-only rewritten `lr_config`,
SIESTA 5.4.2, and Open MPI with four ranks per SIESTA invocation. The frozen
source tree was commit `5a3fe5b3d51da0a229a2d2d8e93e839089edd9cb` (the requested
`5a3fe5b` prefix).

`lr_u_analysis.v3.json` is the campaign analysis. `response_observation_dataset.json`
is its embedded verified occupation dataset extracted as a separate artifact.
The analysis and dataset are byte-bound to the same campaign result; the
dataset SHA256 is recorded below.

Recomputing the complete analysis JSON from the dataset alone is not supported
by the runner's current analysis boundary. `analyze_verified_lr` accepts
`ResponseObservation` objects, while the runner also supplies magnetic branch
evidence, validated occupation half-widths, campaign metadata and input
provenance, then appends the receipt-bound dataset. The dataset does not carry
all of those runner inputs. We therefore did not claim a dataset-only replay;
the Part B POSIX campaign replay is the end-to-end golden.
