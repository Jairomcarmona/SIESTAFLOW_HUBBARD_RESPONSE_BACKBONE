from typing import List, Dict, Optional, Tuple
import numpy as np

from .fit_engine import RegressionRecord
from ..domain.cardinals import Cardinals
from ..domain.provenance import PerturbationIdentity, ObservableIdentity, ResponseMatrix
from ..domain.exceptions import RecordCompletenessError

def assemble_provenance_matrix(
    regression_records: List[RegressionRecord],
    cardinals: Cardinals,
    perturbation_identities: List[PerturbationIdentity],
    observable_identities: List[ObservableIdentity],
    methodology_lock_hash: str = "TBD",
    units: str = "1/eV"
) -> ResponseMatrix:
    """
    Takes regression records and assembles the O x P slope matrix R, wrapped in a ResponseMatrix.
    """
    if len(perturbation_identities) != cardinals.P:
        raise ValueError(f"Expected {cardinals.P} perturbation identities, got {len(perturbation_identities)}.")
        
    if len(observable_identities) != cardinals.O:
        raise ValueError(f"Expected {cardinals.O} observable identities, got {len(observable_identities)}.")

    expected_count = cardinals.O * cardinals.P
    if len(regression_records) != expected_count:
        raise RecordCompletenessError(
            f"Expected {expected_count} regression records (O={cardinals.O}, P={cardinals.P}), "
            f"got {len(regression_records)}."
        )

    R_vals = np.zeros((cardinals.O, cardinals.P), dtype=float)
    seen_pairs = set()
    regression_ids: Dict[Tuple[str, str], str] = {}

    row_ids = [obs.channel_id for obs in observable_identities]
    col_ids = [pert.channel_id for pert in perturbation_identities]

    for r in regression_records:
        o = r.observable_index
        p = r.channel_index
        if o < 0 or o >= cardinals.O or p < 0 or p >= cardinals.P:
            raise RecordCompletenessError(
                f"Record observable_index={o}, channel_index={p} out of bounds."
            )
        pair = (o, p)
        if pair in seen_pairs:
            raise RecordCompletenessError(f"Duplicate observable_index={o}, channel_index={p}")
        seen_pairs.add(pair)
        
        R_vals[o, p] = r.slope
        
        # We store the regression diagnostic status as a pseudo regression_id for provenance,
        # or we could store a hash of the regression record.
        # Here we just store a string representation.
        reg_id = f"REG-O{o}-P{p}-{r.diagnostic_status}"
        regression_ids[(row_ids[o], col_ids[p])] = reg_id

    if len(seen_pairs) != expected_count:
        raise RecordCompletenessError("Not all (o, p) pairs covered.")

    return ResponseMatrix(
        matrix=R_vals,
        row_ids=row_ids,
        column_ids=col_ids,
        units=units,
        regression_ids=regression_ids,
        methodology_lock_hash=methodology_lock_hash
    )

def transform_to_chi(
    R_matrix: ResponseMatrix,
    cardinals: Cardinals,
    subspace_identities: List[str]
) -> ResponseMatrix:
    """
    Applies the transformation chi = A @ R.
    Returns a new ResponseMatrix representing chi or chi0.
    """
    chi_vals = cardinals.chi(R_matrix.matrix)
    
    if len(subspace_identities) != cardinals.N:
        raise ValueError(f"Expected {cardinals.N} subspace identities, got {len(subspace_identities)}")
        
    # The columns of chi remain the perturbation channels
    col_ids = R_matrix.column_ids
    # The rows of chi become the subspace identities
    row_ids = subspace_identities

    # We map the regression IDs by taking the union of dependencies,
    # but for now we just pass a simple dict to indicate transformation.
    chi_reg_ids = {}
    for i, r_id in enumerate(row_ids):
        for j, c_id in enumerate(col_ids):
            chi_reg_ids[(r_id, c_id)] = "TRANSFORMED"

    return ResponseMatrix(
        matrix=chi_vals,
        row_ids=row_ids,
        column_ids=col_ids,
        units=R_matrix.units,
        regression_ids=chi_reg_ids,
        methodology_lock_hash=R_matrix.methodology_lock_hash
    )
