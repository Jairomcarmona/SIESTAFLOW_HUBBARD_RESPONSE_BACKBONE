"""The pure provenance and alpha gates compose before matrix assembly."""

import numpy as np

from siestaflow_hubbard.domain.alpha_selection import AlphaSelectionPolicy, select_common_alpha_window
from siestaflow_hubbard.domain.observation_provenance import Observation, RunIdentity, validate_response_lot


def _hash(character):
    return character * 64


def test_complete_provenance_lot_feeds_one_common_alpha_decision():
    alphas = (-0.2, -0.1, -0.05, 0.0, 0.05, 0.1, 0.2)
    expected, observations = {}, []
    for mode, slope in (("BARE", -0.20), ("SCREENED", -0.10)):
        for index, alpha in enumerate(alphas):
            step = f"{mode}_{index}"
            identity = RunIdentity(
                campaign="temporary-local-gate",
                step=step,
                mode=mode,
                alpha_ev=alpha,
                observed_channel="Mn:3d:0",
                perturbed_channel="Mn:3d:0",
                fdf_sha256=_hash("a"),
                pseudos=(("Mn", _hash("b")), ("O", _hash("c"))),
                parent_dm_sha256=_hash("d"),
                subspace_sha256=_hash("e"),
                projector_sha256=_hash("f"),
                physical_model_sha256=_hash("1"),
                runtime_sha256=_hash("2"),
                magnetic_reference_sha256=_hash("3"),
                selector_policy_sha256=_hash("4"),
            )
            expected[step] = identity
            observations.append(
                Observation(
                    identity=identity,
                    occupation=4.0 + slope * alpha,
                    output_sha256=_hash("5"),
                    scf_state="bare_selected_verified" if mode == "BARE" else "converged_verified",
                    scf_evidence_sha256=_hash("6"),
                    dm_read_verified=True,
                    complete=True,
                    return_code=0,
                )
            )

    lot = validate_response_lot(observations, expected, alphas)
    assert lot["status"] == "compatible_for_analysis"
    occupations = np.array([[4.0 - 0.20 * alpha, 4.0 - 0.10 * alpha] for alpha in alphas])
    moments = np.zeros((7, 1, 3))
    report = select_common_alpha_window(alphas, occupations, moments, 0.1, AlphaSelectionPolicy(1e-7))
    assert report["status"] == "proposed"
    assert report["recommended_alpha_ev"] == 0.2
