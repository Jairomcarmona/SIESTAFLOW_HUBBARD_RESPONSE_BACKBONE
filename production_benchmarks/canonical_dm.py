from siestaflow_hubbard.siesta_backend.adapter import prepare_canonical_dm
def assert_campaign_dm_invariant(reference_dm_path, child_dm_path, reference_sha256) -> str:
    prepare_canonical_dm(reference_dm_path, child_dm_path, reference_sha256)
    return "ok"
