# Technical Debt

This document tracks engineering shortcuts, hardcodings, and placeholder implementations in the SIESTAFLOW Hubbard Response Backbone.

## Current Inventory (v0.1.0)
- **Placeholder Tests (P0-008)**: 79 passing tests exist, but many are `test_placeholder` and do not test actual adversarial mutations.
- **Hardcoded Production Examples (P0-009)**: The `run_yoltla_campaign.py` has hardcoded references to Cu3N, Yoltla Slurm partitions (`tt2d-64p`), and specific directory paths.
- **Simulated Diagnostics (P0-006)**: The regression engine currently simulates $R^2 = 1.0$ and fake residuals instead of calculating them from physical data.
- **Mandatory Booleans (P0-003)**: FDF builder handles booleans by presence, not by strict value overriding.
- **Last-Block Output Parsing (P0-004)**: The SIESTA output parser currently extracts the final block of text, rather than constructing a precise event stream of SCF and population iterations.
