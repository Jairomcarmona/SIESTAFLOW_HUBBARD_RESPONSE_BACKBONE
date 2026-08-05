# Alpha Selection Policy

The alpha grid undergoes a specific lifecycle.

## Lifecycle Phases

1. `PROPOSED`: Initial grid definition (e.g., symmetric pairs, zero, $K_p \ge 5$).
2. `PILOTED`: Minimal execution to verify basic stability.
3. `REFINED`: Adaptive addition of points if slope error requires it.
4. `LOCKED`: Fixed for final matrix evaluation.

## Constraints
Adding points to one channel $p$ DOES NOT invalidate the existing points on other channels or the same channel. Ragged grids are permitted.
