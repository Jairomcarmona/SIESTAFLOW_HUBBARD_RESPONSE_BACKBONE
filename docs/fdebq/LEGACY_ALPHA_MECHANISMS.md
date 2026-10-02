# Legacy alpha mechanisms

FD-EBQ review §M.1 marks the older alpha-selection mechanisms for deprecation.
They remain available for compatibility in this change; their calculations,
decisions, and callers are unchanged.

## The two `AdaptiveAlphaPolicy` classes

| Class | Module | Role and usage |
|---|---|---|
| `AdaptiveAlphaPolicy` | `hubbardflow.domain.adaptive_alpha_control` | Versioned round-control policy. `execution/campaign_runner.py::_execute_adaptive_gate` passes its round evidence to `decide_round`. |
| `AdaptiveAlphaPolicy` | `hubbardflow.domain.adaptive_alpha` | Seven-point legacy wrapper around `AlphaSelectionPolicy`. Historical `tools/*` callers use `authorize_alpha_window`; `execution/lr_dag.py` also accepts this policy for its legacy adaptive-alpha DAG. |

The class names are identical, but the policies are different types with
different fields and purposes. The names are not changed in this task.

## Older selector and decision behavior

`hubbardflow.domain.alpha_selection.AlphaSelectionPolicy` and
`select_common_alpha_window` implement the threshold-based seven-point,
three-window selector used by `adaptive_alpha.authorize_alpha_window` and
historical tools. Review §M.1 identifies its thresholds and diagnostics as
legacy.

The round controller's `decide_round` can emit `STOP_STABLE` after comparisons
based on the stability of U between rounds (review finding 9 and §M.1). That
decision logic is intentionally unchanged here. Replacing it belongs to phase
2 and requires its own scientific validation and authorization.
