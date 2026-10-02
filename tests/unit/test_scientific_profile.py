import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from hubbardflow.domain.scientific_profile import (
    ScientificProfileError,
    V6_PBE_REFERENCE_PROFILE,
    profile_from_explicit_functional,
    require_lr_qualified,
    resolve_scientific_profile,
)
from hubbardflow.execution.campaign_v2 import CampaignV2Error, validate_reference_fdf
from hubbardflow.siesta_backend.fdf_builder import FdfBuilder


def test_v6_pbe_profile_is_typed_versioned_and_qualified():
    profile = profile_from_explicit_functional("PBE")
    assert profile == V6_PBE_REFERENCE_PROFILE
    assert profile.profile_id == "hubbardflow.v6.pbe-reference"
    assert profile.version == 1
    assert profile.xc_functional == "PBE"
    assert profile.qualification_status == "V6_VALIDATED"
    schema = json.loads((Path(__file__).resolve().parents[2] / "schemas/xc_profile.v1.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(profile.to_mapping())


def test_missing_functional_never_migrates_to_pbe():
    with pytest.raises(ScientificProfileError, match="declared explicitly"):
        profile_from_explicit_functional(None)
    with pytest.raises(CampaignV2Error, match="declared explicitly"):
        validate_reference_fdf("", None)


def test_legacy_v2_explicit_functional_migrates_and_profile_must_match():
    migrated = resolve_scientific_profile("PBE")
    assert migrated == V6_PBE_REFERENCE_PROFILE
    assert resolve_scientific_profile("PBE", migrated.to_mapping()) == migrated
    inconsistent = profile_from_explicit_functional("SCAN").to_mapping()
    with pytest.raises(ScientificProfileError, match="differs"):
        resolve_scientific_profile("PBE", inconsistent)


def test_recognized_xc_is_not_mistaken_for_a_validated_lr_profile():
    declared_only = profile_from_explicit_functional("SCAN")
    assert declared_only.qualification_status == "DECLARED_UNVALIDATED"
    schema = json.loads((Path(__file__).resolve().parents[2] / "schemas/xc_profile.v1.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(declared_only.to_mapping())
    with pytest.raises(ScientificProfileError, match="not validated"):
        require_lr_qualified(declared_only)


def test_fdf_materializer_requires_species_and_projector_values_explicitly():
    with pytest.raises(ValueError, match="requires species, n, l, rc and omega"):
        FdfBuilder().modify_fdf_content("SystemLabel fixture\n", alpha=0.01, execution_mode="DEVELOPMENT")
    with pytest.raises(ValueError, match="explicitly declare"):
        FdfBuilder().construct_dftu_proj_block(
            [{"species": "site0", "n": 3, "l": 2, "rc": 3.0}],
            alpha=0.01, target_species="site0", execution_mode="DEVELOPMENT",
        )
