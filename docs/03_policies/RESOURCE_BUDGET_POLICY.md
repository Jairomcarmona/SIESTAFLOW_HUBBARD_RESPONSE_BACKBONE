# Resource Budget Policy

Limits the operational footprint of the agent.

## Constraints
- **Max Tasks**: Upper limit on queued/running tasks.
- **CPU/Memory/Walltime**: Tracked against the HPC profile.
- **Priority**: Queue prioritization.
- **Pruning**: Unpromising branches of a projector scan MUST be pruned to save budget.
- **Reserve**: A budget reserve MUST be held back to ensure the `FULL_RESPONSE` matrix can be computed.
