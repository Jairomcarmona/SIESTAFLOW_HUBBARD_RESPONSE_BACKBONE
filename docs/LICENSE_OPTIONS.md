# License decision for HubbardFlow

**Decision owner:** copyright holder(s), not the implementation team. No license has
been selected, and this repository intentionally has no `LICENSE` file yet. Do not
publish or describe the project as licensed until the rights holder makes and records
that decision.

The options below are a short orientation, not legal advice. Their official texts are
linked for review:

| Option | Practical effect to consider | Official text |
| --- | --- | --- |
| BSD 3-Clause (`BSD-3-Clause`) | Permissive redistribution and modification, including in proprietary products, subject to preserving notices and the disclaimer; it also restricts use of contributor names for endorsement. | [Open Source Initiative: BSD 3-Clause](https://opensource.org/license/BSD-3-clause) |
| Apache License 2.0 (`Apache-2.0`) | Permissive redistribution and modification with express patent-license terms and patent-litigation termination provisions; includes notice and attribution requirements. | [Apache Software Foundation: Apache License 2.0](https://www.apache.org/licenses/LICENSE-2.0.html) |
| GNU GPL v3.0 (`GPL-3.0-only` or `GPL-3.0-or-later`) | Copyleft: distribution of covered modified works carries source and license obligations; the holder must decide whether to permit later GPL versions. | [GNU Project: GPL v3.0](https://www.gnu.org/licenses/gpl-3.0.html) |

Before adding `LICENSE`, the rights holder should confirm who owns or may license every
contribution, choose an SPDX identifier and exact license text, and approve the
copyright notice. The repository is prepared for that decision through the metadata
placeholders in `CITATION.cff`, `codemeta.json`, and `.zenodo.json`; all must be completed
together with `LICENSE` before a public release.

## Release metadata status

- Project version is `0.1.2`, synchronized with `pyproject.toml` by
  `tests/unit/test_release_metadata.py`.
- Author identity, contributor roles, affiliations, ORCID identifiers, and license are
  intentionally marked `PENDIENTE_AUTOR` because no approved values were supplied.
- No DOI, publication date, or additional author details are asserted here.
