# EVENT PARSER VALIDATION REPORT (PHASE 3)

## 1. Parser Architecture
The new Event Parser (`src/siestaflow_hubbard/siesta_backend/event_parser.py`) implements a sequential, line-by-line streaming architecture that extracts raw Hubbard population events (`HubbardPopulationEvent`) from SIESTA 5.4.2 output files. It completely replaces the defective `last-block` heuristic.

**Key principles:**
- **Strict Separation of Concerns**: The parser extracts RAW observations and tags them as `UNCLASSIFIED`. It does NOT attempt to assign BARE or SCREENED physical roles based on hardcoded iteration logic.
- **Full Traceability**: Events retain their `scf_iteration` (if present in context), `occurrence_index`, and `dftu_population_iteration`.
- **Dynamic Dimension Inference**: Instead of hardcoding 5x5 matrices, the matrix dimension is derived strictly from `max(projector_index)` encountered in the raw text, allowing it to correctly map arbitrary subshells without hallucinating $l$ numbers.

## 2. Event Grammar & Extraction
The primary unit of extraction is the block encapsulated between:
`hubbard_term: recalculating local occupations N`
and the next occurrence of a section break (e.g., `recalculating Hamiltonian`, `siesta: iscf`).
Within this block, the parser dynamically collects multiple `hubbard_term: atom, species:` records.

## 3. Fixtures & Verification
A rigorous test suite (`tests/test_hubbard_event_parser.py`) provides coverage for the parser's logic.

- **Multi-atom & Multi-event**: Validated via `test_multiple_atoms_multiple_events`. The parser correctly processes overlapping contexts.
- **Spin Coverage**: Validated via `test_spin_polarized_collinear`. The parser automatically adapts its trace checksum to non-polarized (single column output mapped to UP with identical DOWN summary) and spin-polarized collinear (UP and DOWN distinct values).
- **Failure Modes & Corruption Rejection**:
  - `test_corruption_missing_element`: Fails precisely if `len(elements) != max_m^2`.
  - `test_corruption_duplicate_element`: Fails if `(m1, m2)` appears twice.
  - `test_corruption_trace_mismatch`: Fails via `ParseSemanticMismatch` if the computed matrix trace diverges from the `Occupations:` summary beyond `1e-4`.

## 4. Old-Parser Adversarial Reproduction
In `test_adversarial_old_parser_reproduction`, the old algorithm (`blocks[-1]`) was simulated on an output file with two events. The test empirically demonstrates that the old algorithm SILENTLY DROPS the first event (which contains the BARE observation), whereas the new parser captures both events flawlessly.

## 5. Limitations & Unsupported Formats
- Non-collinear spin and Spin-Orbit Coupling (SOC) are strictly disallowed for now. If encountered, the parser throws `UnsupportedSpinFormat` rather than misinterpreting complex/spinor terms.
- The `UNCLASSIFIED` events must be passed to a Semantic Mapper (Observation Selector) in Phase 4 to resolve P0-005.

## Conclusion
**P0-004 is officially VALIDATED.** The parser is scientifically robust and physically safe.
