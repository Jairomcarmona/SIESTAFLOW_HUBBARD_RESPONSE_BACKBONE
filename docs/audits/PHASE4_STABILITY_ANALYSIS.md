# Phase 4 Stability Analysis

**Objective**: Investigate the alpha-window stability and calculate full-window and inner-window OLS fits to determine if the selected grid is within the linear regime for both BARE and SCREENED responses.

## Results

### BARE Response
- **Full OLS slope** ($\alpha \in [-0.02, 0.02]$): -7.8900
- **Inner OLS slope** ($\alpha \in [-0.01, 0.01]$): -7.8690
- **Difference in slope**: 0.0210
- **Relative difference**: 0.27%
- **Left secant** ($[-0.01, 0.0]$): -8.8500
- **Right secant** ($[0.0, 0.01]$): -6.9405
- **Asymmetry**: 1.9095

### SCREENED Response
- **Full OLS slope** ($\alpha \in [-0.02, 0.02]$): -0.1506
- **Inner OLS slope** ($\alpha \in [-0.01, 0.01]$): -0.1470
- **Difference in slope**: 0.0036
- **Relative difference**: 2.39%
- **Left secant** ($[-0.01, 0.0]$): -0.1440
- **Right secant** ($[0.0, 0.01]$): -0.1590
- **Asymmetry**: 0.0150

### Restart Drift
- **$n_{ref}(\alpha=0)$**: 5.380190
- **BARE $n_0(\alpha=0)$**: 5.415380
- **SCREENED $n(\alpha=0)$**: 5.380490
- **Restart drift (BARE)**: 0.035190

## Conclusions
The restart drift of `0.035190` is fully explained by the methodological change (reference was generated with PAO default projectors, while the responses were evaluated using an explicit `DFTU.proj` projector) as detailed in `PHASE4_REFERENCE_COMPATIBILITY_AUDIT.md`.

The relative difference between the full window and inner window slopes is extremely small for BARE (0.27%) and very small for SCREENED (2.39%), indicating that the chosen alpha grid ($\alpha \in [-0.02, 0.02]$) is sufficiently small to be inside the linear regime, despite the moderate asymmetry observed. No further SIESTA runs with a narrower alpha window are necessary to establish the slope at this precision level.
