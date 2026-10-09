# Kit validation record

## Fixed identities

- HubbardFlow source commit:
  `d7d2d824ed7e6cd87a1dfafe0866b4ecd9e06650`.
- Full-site FDF SHA-256:
  `cb83162115cd2e8b414c1ebd05acc276b7b9a5d75535e18196f91e5a33641eaa`.
- Cu pseudopotential SHA-256, for CuLR00 through CuLR23:
  `7bfaec0d9a98a9ca167a7f486ba99a3dacd557317dede740478780a80f21f738`.
- N pseudopotential SHA-256:
  `f2ed77995cd0bedd479ce33a47dbde5c6ba0802913535ae5c1b337cd909d3028`.
- Yoltla SIESTA 5.4.2 SHA-256:
  `c69519dc7296ca8f9e454303947084ee246efd609be4bc05244a31a91b82e37e`.
- Yoltla Hydra adapter SHA-256:
  `6fc5282b2440f319640960a7c6cd2a6a774163d926d3ae469e81ae8c2374872b`.

## Local checks

The full-site planner dry-run used the matching archived reference output
with SHA-256
`d37fd112b86d53def7798d8c9c38e850d2d40c79a15cd4f3a33b2565814322fd`.
It reported three translation classes of eight Cu sites, six calculated
columns, and 72 response run specs. Execution admission was
`ADMISSIBLE_TRANSLATION_SHADOWED`; shadows remain pending until executed.

The reference checker requires `Spin non-polarized` in the input and all
three one-spin markers in the SIESTA output. The one-column probe generator
removes only the 23 non-representative four-line projector records and
writes a unified diff for review.

The local direct plan had 24 columns and 288 response run specs. The
generated one-column probe plan had one column and 12 response run specs.
These plan checks validate dimensions only; they do not replace a fresh
reference, probe execution, or TS shadow evidence.

On the archived full-site output, the checker found the required markers
at lines 6911, 6912, and 6913. The FDF directive is at line 77.

No SIESTA process or Yoltla job was launched for this validation. Scheduler
placement, a fresh Yoltla reference, the probe, and TS remain unverified.
