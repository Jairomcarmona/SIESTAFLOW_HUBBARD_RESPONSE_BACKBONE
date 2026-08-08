from typing import List, Dict, Optional, Tuple
import numpy as np

from .fit_engine import RegressionRecord
from ..domain.cardinals import Cardinals
from ..domain.provenance import PerturbationIdentity, ObservableIdentity, ResponseMatrix
from ..domain.exceptions import RecordCompletenessError

from ..domain.matrix_pipeline import compute_antisymmetry, symmetrize

def assemble_provenance_matrix(
    regression_records: List[RegressionRecord],
    cardinals: Cardinals,
    perturbation_identities: List[PerturbationIdentity],
    observable_identities: List[ObservableIdentity],
    methodology_lock_hash: str = "UNKNOWN",
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
    regression_ids: Dict[Tuple[str, str], List[str]] = {}

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
        regression_ids[(row_ids[o], col_ids[p])] = [getattr(r, 'artifact_id', f"REG-O{o}-P{p}")]

    if len(seen_pairs) != expected_count:
        raise RecordCompletenessError("Not all (o, p) pairs covered.")

    sym_R = symmetrize(R_vals) if R_vals.shape[0] == R_vals.shape[1] else None

    return ResponseMatrix(
        matrix=R_vals,
        row_ids=row_ids,
        column_ids=col_ids,
        units=units,
        regression_ids=regression_ids,
        raw_matrix=R_vals,
        symmetrized_matrix=sym_R,
        methodology_lock_hash=methodology_lock_hash
    )

def transform_to_chi(
    R_matrix: ResponseMatrix,
    cardinals: Cardinals,
    subspace_identities: List[str]
) -> ResponseMatrix:
    """
    Applies the linear response transformation chi = A @ R.
    Returns a raw ResponseMatrix. Symmetrization is NOT applied unconditionally.
    """
    from ..domain.matrix_pipeline import compute_antisymmetry, symmetrize
    
    chi_vals = cardinals.chi(R_matrix.matrix)
    
    _, _, rel_frob = compute_antisymmetry(chi_vals)
    chi_sym = symmetrize(chi_vals)
    
    if len(subspace_identities) != cardinals.N:
        raise ValueError(f"Expected {cardinals.N} subspace identities, got {len(subspace_identities)}")
        
    col_ids = R_matrix.column_ids
    row_ids = subspace_identities

    chi_reg_ids = {}
    for i, r_id in enumerate(row_ids):
        for j, c_id in enumerate(col_ids):
            contributing = []
            for k, obs_id in enumerate(R_matrix.row_ids):
                if cardinals.A[i, k] != 0:
                    r_list = R_matrix.regression_ids.get((obs_id, c_id), [])
                    contributing.extend(r_list)
            chi_reg_ids[(r_id, c_id)] = list(set(contributing))

    source_ids = [R_matrix.artifact_id] if hasattr(R_matrix, 'artifact_id') and R_matrix.artifact_id else []

    return ResponseMatrix(
        matrix=chi_vals, # STRICT CANONICAL LR RAW DEFINITION
        row_ids=row_ids,
        column_ids=col_ids,
        units=R_matrix.units,
        regression_ids=chi_reg_ids,
        raw_matrix=chi_vals,
        symmetrized_matrix=chi_sym,
        antisymmetry_norm=rel_frob,
        methodology_lock_hash=R_matrix.methodology_lock_hash,
        source_artifact_ids=source_ids
    )

def select_response_matrix(response_matrix: ResponseMatrix, policy: str = "RAW") -> ResponseMatrix:
    """
    Selects between RAW and SYMMETRIZED matrix representations based on an explicit numerical policy.
    """
    if policy.upper() == "RAW":
        target = response_matrix.raw_matrix if response_matrix.raw_matrix is not None else response_matrix.matrix
    elif policy.upper() in ("SYMMETRIZED", "SYM"):
        target = response_matrix.symmetrized_matrix if response_matrix.symmetrized_matrix is not None else response_matrix.matrix
    else:
        raise ValueError(f"Unknown response matrix policy: {policy}")
        
    source_ids = [response_matrix.artifact_id] if hasattr(response_matrix, 'artifact_id') and response_matrix.artifact_id else []
    
    return ResponseMatrix(
        matrix=target,
        row_ids=response_matrix.row_ids,
        column_ids=response_matrix.column_ids,
        units=response_matrix.units,
        regression_ids=response_matrix.regression_ids,
        raw_matrix=response_matrix.raw_matrix,
        symmetrized_matrix=response_matrix.symmetrized_matrix,
        antisymmetry_norm=response_matrix.antisymmetry_norm,
        methodology_lock_hash=response_matrix.methodology_lock_hash,
        source_artifact_ids=source_ids
    )
