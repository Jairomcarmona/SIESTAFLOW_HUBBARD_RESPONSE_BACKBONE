# Candidate Selection Policy

Defines how a specific configuration is chosen from a plateau.

## Rules
- **Priority**: Based on optimal physical metrics (e.g., maximum stability).
- **Desempate (Tiebreaker)**: A deterministic tiebreaker MUST be implemented.
- **Budget-Aware**: Selection MUST account for the available computational budget for the full response matrix.
