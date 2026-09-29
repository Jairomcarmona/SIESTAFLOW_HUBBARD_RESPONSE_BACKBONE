# Polynomial response fitting

## Mathematical operation

For each perturbed site (J), observed site (I), and response channel
(BARE or SCREENED), the engine can fit

\[
n_I(\alpha_J) = c_0 + c_1\alpha_J + c_2\alpha_J^2 + c_3\alpha_J^3.
\]

The response matrix element is the analytic derivative at the origin,
\(\chi_{IJ}=c_1\), rather than a finite-amplitude slope or an average of
several (U) values. The BARE and SCREENED matrices are then inverted using
the existing direct-inversion policy to form
\(U=\chi_0^{-1}-\chi^{-1}\).

Alpha is scaled before the least-squares fit to condition the polynomial
design. The implementation rejects duplicate alpha observations, a rank-
deficient design, alpha values that do not bracket zero, and a fit with fewer
residual degrees of freedom than the declared minimum. It does not silently
lower the polynomial degree.

## Configuration and audit trail

The reusable implementation is in
`src/siestaflow_hubbard/domain/matrix_lr.py`:

- `fit_polynomial_response` fits one response curve and reports the derivative,
  coefficients, (R^2), residuals, residual RMS, residual degrees of freedom,
  and design condition number.
- `ResponseFitPolicy` fixes the method, polynomial degree, minimum residual
  degrees of freedom, and optional symmetric alpha window.
- `fit_response_matrix` applies the policy consistently to every matrix
  element in both response channels.
- `analyze_matrix_response_campaign` carries the declared fit method, degree,
  and window into its result.

`LRScientificConfiguration` in
`src/siestaflow_hubbard/domain/convergence_engine.py` stores the same choices
and includes them in the analysis configuration identity. Example:

```python
from dataclasses import replace

fit_config = replace(
    material_configuration,
    response_fit_method="polynomial",
    response_polynomial_degree=3,
    response_minimum_residual_dof=1,
    response_alpha_window_ev=0.02,
)
```

The linear method remains the default. A five-point cubic fit has one residual
degree of freedom; the seven-point grid has three. Both values are recorded so
the fit diagnostics show how much evidence constrains the chosen model. A
window should come from the separate alpha-linearity gate, not be picked by
looking for a preferred (U).

The sequential production analysis path uses the same function through
`production_benchmarks/lr_arithmetic.py`; select it through
`production_benchmarks/campaign_controller.py::matrix_analysis` with
`mode_5point=True` and `response_fit_method="polynomial"`. The resulting
analysis JSON records fit method, degree, alpha values, and per-element
coefficients and residual diagnostics. No SIESTA calculation is launched by
this option; it changes postprocessing of observations already present.

## Interpretation

Polynomial regression has a published precedent for extracting the response
derivative from multiple finite perturbations; ABINIT's `lrUJ` tutorial uses
polynomial fitting with degree capped at three by default. The general matrix
algebra follows the LR construction, while element-by-element polynomial
selection is an explicit software extension: the cited 2024 review describes
matrix polynomial fitting as a more complex avenue that was not yet explored
there ([ABINIT LRUJ tutorial](https://docs.abinit.org/tutorial/lruj/),
[MacEnulty et al. (2024)](https://doi.org/10.1088/2516-1075/ad610f)).

Polynomial regression is an estimator, not proof that all sampled points
share one electronic state or lie in one physical response regime. The
independent alpha gate and state/magnetic checks remain responsible for
admitting the interval. The polynomial degree is declared in the campaign
configuration; the software does not select the degree by agreement with a
reference value. The same-point linear fit is retained in each element's
diagnostics for model-sensitivity reporting.
