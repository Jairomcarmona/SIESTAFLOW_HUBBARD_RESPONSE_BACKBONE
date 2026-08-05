# Plateau Detection Policy

A plateau is defined as a connected region in parameter space.

## Requirements for a Plateau
1. Result stability (variance within tolerance).
2. Linearity of response.
3. Electronic state continuity.
4. Magnetic stability.
5. Good matrix conditioning (passes condition gate).
6. Local sensitivity stability.
7. NO blocking gates failed.

## Action
Detection of a plateau leads to `CANDIDATE_LOCK` and triggers `FULL_RESPONSE`. It DOES NOT mean the $U$ is automatically accepted.
