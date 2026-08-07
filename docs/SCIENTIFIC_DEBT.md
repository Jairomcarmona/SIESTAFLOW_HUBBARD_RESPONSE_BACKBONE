# Scientific Debt

This document tracks scientific shortcuts, ambiguities, and unresolved physical assumptions in the SIESTAFLOW Hubbard Response Backbone.

## Current Inventory (v0.1.0)
- **DFTU.Proj Grammar Inconsistency (P0-001)**: Suspected mismatch between our FDF serializer and exact SIESTA 5.4.2 method-2 semantics for $U, J, r_c, \omega, \lambda$.
- **Alpha Modeling (P0-002)**: Uncertainty around how `DFTU.PotentialShift` handles $U$ and $\alpha$.
- **BARE Observation Protocol (P0-005)**: The procedure for identifying $n_0(\alpha)$ vs $n(\alpha)$ is not formally validated against the exact sequence of SIESTA 5.4.2 output events.
- **Multisite Reduction**: The repository currently reduces multisite response matrices to scalar $U$ values without explicit scientific justification or gauge policy.
