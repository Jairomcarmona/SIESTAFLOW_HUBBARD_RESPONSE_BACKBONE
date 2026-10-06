from dataclasses import replace

import pytest

from hubbardflow.domain.observation_provenance import Observation, RunIdentity, validate_response_lot


H = "a" * 64


def _identity(step, mode, alpha):
    return RunIdentity(
        campaign="local-integration",
        step=step,
        mode=mode,
        alpha_ev=alpha,
        observed_channel="Mn:3d:0",
        perturbed_channel="Mn:3d:0",
        fdf_sha256=H,
        pseudos=(("Mn", "b" * 64), ("O", "c" * 64)),
        parent_dm_sha256="d" * 64,
        subspace_sha256="e" * 64,
        projector_sha256="f" * 64,
        physical_model_sha256="1" * 64,
        runtime_sha256="2" * 64,
        magnetic_reference_sha256="3" * 64,
        selector_policy_sha256="4" * 64,
    )


def _observation(identity):
    state = "bare_selected_verified" if identity.mode == "BARE" else "converged_verified"
    return Observation(identity, 4.2, "5" * 64, state, "6" * 64, True, True, 0)


def test_complete_lot_is_accepted_and_mixed_dm_or_missing_point_is_rejected():
    expected, observations = {}, []
    for mode in ("BARE", "SCREENED"):
        for alpha in (-0.1, 0.0, 0.1):
            step = f"{mode}_{alpha:+.2f}"
            identity = _identity(step, mode, alpha)
            expected[step] = identity
            observations.append(_observation(identity))
    accepted = validate_response_lot(observations, expected, (-0.1, 0.0, 0.1))
    assert accepted["status"] == "compatible_for_analysis"
    with pytest.raises(ValueError, match="incomplete"):
        validate_response_lot(observations[:-1], expected, (-0.1, 0.0, 0.1))
    altered = replace(observations[-1], identity=replace(observations[-1].identity, parent_dm_sha256="7" * 64))
    changed_plan = dict(expected)
    changed_plan[altered.identity.step] = altered.identity
    result = validate_response_lot(observations[:-1] + [altered], changed_plan, (-0.1, 0.0, 0.1))
    assert result["status"] == accepted["status"]
    assert any(w["reason"] == "ARTIFACT_DIGEST_MISMATCH" for w in result["traceability_warnings"])


def test_observation_requires_mode_specific_semantic_evidence():
    identity = _identity("SCREENED_+0.10", "SCREENED", 0.1)
    expected = {identity.step: identity}
    invalid = replace(_observation(identity), scf_state="bare_selected_verified")
    with pytest.raises(ValueError, match="semantic"):
        validate_response_lot([invalid], expected, (0.1,), ("SCREENED",))


@pytest.mark.parametrize("field", ["parent_dm_sha256", "fdf_sha256"])
@pytest.mark.parametrize("value", [None, "", "malformed"])
def test_file_hash_metadata_never_substitutes_for_semantic_checks(field, value):
    identity = _identity("SCREENED_+0.10", "SCREENED", 0.1)
    observation = _observation(replace(identity, **{field: value}))
    result = validate_response_lot([observation], {identity.step: identity}, (0.1,), ("SCREENED",))
    assert result["status"] == "compatible_for_analysis"
    assert result["traceability_warnings"]
    invalid = replace(observation, dm_read_verified=False)
    with pytest.raises(ValueError, match="semantic"):
        validate_response_lot([invalid], {identity.step: identity}, (0.1,), ("SCREENED",))
