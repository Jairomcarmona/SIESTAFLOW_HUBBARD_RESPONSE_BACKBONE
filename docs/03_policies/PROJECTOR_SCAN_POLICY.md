# Projector Scan Policy

The scan over projector parameters is treated abstractly.

## Parameters
- $r_c$: Cutoff radius.
- $\omega$: Energy shift/spread.
- `method`: Generation method.
- `manifold`: Target orbital manifold.

## Scan DAG
1. `COARSE_SCAN`
2. `REFINEMENT`
3. `EVALUATION`
4. `PLATEAU_DETECTION`
5. `LOCK`
6. `FULL_RESPONSE`

No hardcoded specific numeric values for parameters are permitted in the policy.
