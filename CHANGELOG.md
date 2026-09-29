# Changelog

## 0.1.2 — 2026-09-28

**Estado del cierre de producto:** `PRODUCT_BLOCKED`. Las puertas operativas
P0–P6 se completaron, pero la campaña NiO P5 quedó como
`NUMERICAL_CANDIDATE_UNASSESSED` / `NOT_ESTABLISHED`; la construcción del wheel
no establece aceptación científica del U. Véanse el
[registro final](docs/P0_EXECUTION_20260928.md) y el
[inventario de sincronización](docs/ESTADO_REPOSITORIO_Y_PUBLICACION_20260929.md).

- Added the v3 response-analysis/report contract with an explicit occupation source, token-resolution bounds, per-site `U_scalar_charge`, SCF and magnetic diagnostics, and a separate physical-acceptance state.
- Completed the public campaign lifecycle commands: `init`, `run`, `status`, `resume`, `report`, and `stop` for PowerShell → WSL; added direct-manifest CLI routing for Linux with a validated, already granted Slurm allocation.
- Campaign manifests record an automatic input hash inventory. The local WSL worker serializes SIESTA nodes, and `report` renders saved analysis without launching SIESTA.
- Added a fixed-grid route budget of `1 + 2 × S × A`; the frozen six-amplitude examples cost 13 SIESTA nodes for one correlated site and 25 for the two-site NiO alternative.
- Validated wheel `dist/siestaflow_hubbard-0.1.2-py3-none-any.whl` in clean Windows and WSL virtual environments. Public `audit-fdf`, `status`, `resume`, and `report` commands were exercised against the completed P5 campaign; the resume check reused the completed DAG and did not relaunch SIESTA.
- The release reports `NUMERICAL_CANDIDATE_UNASSESSED` when a scientific U tolerance is absent and does not claim physical acceptance. It does not map `U_scalar_charge` automatically to `Ueff_Dudarev`.

## Earlier releases

Earlier implementation history is retained in the repository's archived campaign records and integration plans. Those records are historical evidence and are not rewritten by this release.
