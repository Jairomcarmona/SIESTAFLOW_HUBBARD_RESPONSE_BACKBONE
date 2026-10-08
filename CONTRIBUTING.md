# Contributing to HubbardFlow

Contributions must preserve the scientific and architectural requirements in
[`AGENTS.md`](AGENTS.md). In particular, changes to the scientific definitions or
acceptance rules require an explicit task and cited policy; do not infer a threshold
or weaken a failing scientific test.

## Before opening a pull request

1. Work on a focused branch and keep one task per pull request.
2. Read `AGENTS.md` and the policy documents relevant to the change.
3. Add or update tests with the implementation. Do not edit the frozen V6 baseline.
4. Run the repository checks required by `AGENTS.md` and include the commands and
   concise results in the pull request description.
5. Describe the change, what was verified, what remains outside scope, and any
   unresolved question. Do not claim SIESTA or cluster validation unless it ran and
   its evidence is cited.

## Release process

1. The copyright holder completes author identity, contributor roles, affiliations,
   ORCID identifiers, and the license placeholders in `CITATION.cff`, `codemeta.json`,
   and `.zenodo.json`, then approves and adds the corresponding `LICENSE` text.
2. Select the next semantic version (`MAJOR.MINOR.PATCH`) according to the public API
   and compatibility impact. Update `[project].version` in `pyproject.toml`, the three
   metadata files, and `CHANGELOG.md` in the same change. The metadata synchronization
   test must pass.
3. Review the changelog entry and verify the full CI suite on the release commit.
4. Create an annotated, version-matching Git tag (for example, `vX.Y.Z`) only after
   approval, and publish the source distribution/wheel from that tagged commit.
5. Archive that same source revision with the approved metadata in the selected
   archival service. Record the resulting DOI only after the archive assigns it; do
   not prefill or invent a DOI.

No release should be cut while `PENDIENTE_AUTOR` remains in the citation or archive
metadata, or while the license decision and `LICENSE` file are absent.
