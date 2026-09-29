# Informe de respuesta lineal de Hubbard

- **Campaña:** 99d5ee67-d9cf-41f1-9f8f-39315c6e81fd
- **Material:** NiO-AFMII-PBE-adaptive-20260928
- **Funcional:** PBE
- **Versión SIESTA:** 5.4.2
- **Analizador:** siestaflow_hubbard 0.1.2 — siestaflow.lr_u_analysis.v3
- **Cantidad calculada:** `U_scalar_charge` (eV)
- **Estado numérico:** **NUMERICAL_CANDIDATE_UNASSESSED**
- **Aceptación física:** **NOT_ESTABLISHED**
- **Estimador principal:** polynomial, grado 3
- **Malla α (eV):** `-0.06, -0.04, -0.02, 0.02, 0.04, 0.06`
- **Acción DAG registrada:** `ADAPTIVE_ROUND_ANALYSIS`

El resultado corresponde a `U_scalar_charge` de la respuesta de carga declarada. No se convierte automáticamente en `Ueff_Dudarev` ni implica aceptación física.

## 1. Resumen de U por sitio

| Cantidad | Sitio | Valor (eV) | Método | Sensibilidad al modelo (eV) | Sensibilidad a ventana (eV) | Estado numérico | Acción DAG |
|---|---|---:|---|---:|---:|---|---|
| U_scalar_charge | NiLR0 | 6.85404812 | polynomial | 0.00320939808 | 0.00225483303 | NUMERICAL_CANDIDATE_UNASSESSED | ADAPTIVE_ROUND_ANALYSIS |
| U_scalar_charge | NiLR1 | 6.8541679 | polynomial | 0.00294264524 | 0.00210785535 | NUMERICAL_CANDIDATE_UNASSESSED | ADAPTIVE_ROUND_ANALYSIS |

## 2. Convención y cálculo matemático

El índice de fila `I` identifica el sitio cuya ocupación se observa; el índice de columna `J` identifica el sitio al que se aplica la perturbación α. Las ocupaciones se expresan en electrones y α en eV.

Para cada sitio perturbado `J`, se ajusta la respuesta de cada sitio observado `I` alrededor de α = 0:

```text
n_I(α_J) = c_0 + c_1 α_J + c_2 α_J² + …
χ⁰_IJ = (∂n⁰_I / ∂α_J)|₀   [BARE, eV⁻¹]
χ_IJ  = (∂n_I  / ∂α_J)|₀   [SCREENED, eV⁻¹]
U_matrix = (χ⁰)⁻¹ − χ⁻¹   [eV]
U_scalar_charge(I) = U_matrix[I,I]
```

El análisis usó ajuste `polynomial` de grado 3; para el cúbico, la derivada en cero es el coeficiente lineal `c₁`. La inversión se hizo con las matrices `raw`. No se aplica pseudoinversa ni regularización silenciosa.

## 3. Ocupaciones verificadas usadas por el análisis

Dataset `siestaflow.lr_u_verified_dataset.v2`; α en eV, ocupación en electron.

| Sitio perturbado | α (eV) | Sitio observado | n referencia (e) | n BARE (e) | n SCREENED (e) | ½ ancho del observable impreso (ref/BARE/SCREENED, e) |
|---|---:|---|---:|---:|---:|---|
| NiLR0 | -0.06 | NiLR0 | 8.439208 | 8.451157 | 8.444088 | 5e-07 / 5e-07 / 5e-07 |
| NiLR0 | -0.06 | NiLR1 | 8.439208 | 8.435974 | 8.439153 | 5e-07 / 5e-07 / 5e-07 |
| NiLR0 | -0.04 | NiLR0 | 8.439208 | 8.447161 | 8.442461 | 5e-07 / 5e-07 / 5e-07 |
| NiLR0 | -0.04 | NiLR1 | 8.439208 | 8.437051 | 8.439171 | 5e-07 / 5e-07 / 5e-07 |
| NiLR0 | -0.02 | NiLR0 | 8.439208 | 8.443177 | 8.440832 | 5e-07 / 5e-07 / 5e-07 |
| NiLR0 | -0.02 | NiLR1 | 8.439208 | 8.438128 | 8.439188 | 5e-07 / 5e-07 / 5e-07 |
| NiLR0 | 0.02 | NiLR0 | 8.439208 | 8.435243 | 8.43758 | 5e-07 / 5e-07 / 5e-07 |
| NiLR0 | 0.02 | NiLR1 | 8.439208 | 8.440281 | 8.439227 | 5e-07 / 5e-07 / 5e-07 |
| NiLR0 | 0.04 | NiLR0 | 8.439208 | 8.431293 | 8.435954 | 5e-07 / 5e-07 / 5e-07 |
| NiLR0 | 0.04 | NiLR1 | 8.439208 | 8.441357 | 8.439247 | 5e-07 / 5e-07 / 5e-07 |
| NiLR0 | 0.06 | NiLR0 | 8.439208 | 8.427353 | 8.434331 | 5e-07 / 5e-07 / 5e-07 |
| NiLR0 | 0.06 | NiLR1 | 8.439208 | 8.442434 | 8.439263 | 5e-07 / 5e-07 / 5e-07 |
| NiLR1 | -0.06 | NiLR0 | 8.439208 | 8.435975 | 8.439153 | 5e-07 / 5e-07 / 5e-07 |
| NiLR1 | -0.06 | NiLR1 | 8.439208 | 8.451156 | 8.444088 | 5e-07 / 5e-07 / 5e-07 |
| NiLR1 | -0.04 | NiLR0 | 8.439208 | 8.437052 | 8.439171 | 5e-07 / 5e-07 / 5e-07 |
| NiLR1 | -0.04 | NiLR1 | 8.439208 | 8.447161 | 8.442461 | 5e-07 / 5e-07 / 5e-07 |
| NiLR1 | -0.02 | NiLR0 | 8.439208 | 8.438128 | 8.439188 | 5e-07 / 5e-07 / 5e-07 |
| NiLR1 | -0.02 | NiLR1 | 8.439208 | 8.443177 | 8.440832 | 5e-07 / 5e-07 / 5e-07 |
| NiLR1 | 0.02 | NiLR0 | 8.439208 | 8.440281 | 8.439227 | 5e-07 / 5e-07 / 5e-07 |
| NiLR1 | 0.02 | NiLR1 | 8.439208 | 8.435243 | 8.43758 | 5e-07 / 5e-07 / 5e-07 |
| NiLR1 | 0.04 | NiLR0 | 8.439208 | 8.441357 | 8.439247 | 5e-07 / 5e-07 / 5e-07 |
| NiLR1 | 0.04 | NiLR1 | 8.439208 | 8.431293 | 8.435954 | 5e-07 / 5e-07 / 5e-07 |
| NiLR1 | 0.06 | NiLR0 | 8.439208 | 8.442434 | 8.439263 | 5e-07 / 5e-07 / 5e-07 |
| NiLR1 | 0.06 | NiLR1 | 8.439208 | 8.427353 | 8.434331 | 5e-07 / 5e-07 / 5e-07 |

## 4. Ajustes elemento por elemento

Cada fila corresponde a (sitio observado `I`, sitio perturbado `J`, modo). La pendiente del ajuste principal forma el elemento χ⁰_IJ (BARE) o χ_IJ (SCREENED). Los residuos son `n calculada − n ajustada` en el orden de α indicado por el análisis.

| Sitio observado I | Sitio perturbado J | Modo | Ajuste | Grado | Puntos | gl residuales | Pendiente c₁ (e·eV⁻¹) | Coeficientes con unidades | R² | Condición diseño | RMS residuo (e) | Máx. abs. residuo (e) | Residuos (e) |
|---|---|---|---|---:|---:|---:|---:|---|---:|---:|---:|---:|---|
| NiLR0 | NiLR0 | BARE | principal | 3 | 6 | 2 | -0.19834127 | c0=8.43920443 e; c1=-0.19834127 e·eV⁻¹; c2=0.0140561225 e·eV⁻²; c3=-0.00694444446 e·eV⁻³ | 1 | 6.57466612 | 1.06479427e-07 | 1.76870746e-07 | [-6.80272727e-09, -1.36054457e-08, 6.80272105e-08, -1.70068027e-07, 1.76870746e-07, -5.4421772e-08] |
| NiLR0 | NiLR0 | BARE | lineal_misma_malla | 1 | 6 | 4 | -0.198360714 | c0=8.43923067 e; c1=-0.198360714 e·eV⁻¹ | 0.999995312 | — | 1.85564347e-05 | 2.46904762e-05 | [2.46904762e-05, -4.0952381e-06, -2.08809524e-05, -2.0452381e-05, -3.23809524e-06, 2.39761905e-05] |
| NiLR0 | NiLR0 | BARE | lineal_interior | 1 | 2 | 0 | -0.19835 | c0=8.43921 e; c1=-0.19835 e·eV⁻¹ | 1 | — | 2.80866677e-15 | 3.55271368e-15 | [1.77635684e-15, 3.55271368e-15] |
| NiLR0 | NiLR0 | SCREENED | principal | 3 | 6 | 2 | -0.0813355159 | c0=8.43920564 e; c1=-0.0813355159 e·eV⁻¹; c2=0.00108418367 e·eV⁻²; c3=0.00694444442 e·eV⁻³ | 0.99999998 | 6.57466612 | 4.97727261e-07 | 7.3129252e-07 | [-1.76870756e-07, 6.46258499e-07, -7.3129252e-07, 5.7823129e-07, -4.01360548e-07, 8.50340101e-08] |
| NiLR0 | NiLR0 | SCREENED | lineal_misma_malla | 1 | 6 | 4 | -0.0813160714 | c0=8.43920767 e; c1=-0.0813160714 e·eV⁻¹ | 0.999999805 | — | 1.55136908e-06 | 2.29761905e-06 | [1.36904762e-06, 6.90476188e-07, -1.98809524e-06, -1.3452381e-06, -1.02380952e-06, 2.29761905e-06] |
| NiLR0 | NiLR0 | SCREENED | lineal_interior | 1 | 2 | 0 | -0.0813 | c0=8.439206 e; c1=-0.0813 e·eV⁻¹ | 1 | — | 1.77635684e-15 | 1.77635684e-15 | [1.77635684e-15, 1.77635684e-15] |
| NiLR1 | NiLR0 | BARE | principal | 3 | 6 | 2 | 0.0538206349 | c0=8.43920443 e; c1=0.0538206349 e·eV⁻¹; c2=-0.000140306122 e·eV⁻²; c3=0.00347222222 e·eV⁻³ | 0.999999996 | 6.57466612 | 1.52455339e-07 | 2.51700683e-07 | [6.46258442e-08, -1.56462589e-07, 6.80272088e-08, 1.87074829e-07, -2.51700683e-07, 8.8435371e-08] |
| NiLR1 | NiLR0 | BARE | lineal_misma_malla | 1 | 6 | 4 | 0.0538303571 | c0=8.43920417 e; c1=0.0538303571 e·eV⁻¹ | 0.999999984 | — | 2.92091528e-07 | 4.40476189e-07 | [-3.45238098e-07, 4.76190465e-08, 4.40476189e-07, 2.26190476e-07, -3.80952383e-07, 1.19047616e-08] |
| NiLR1 | NiLR0 | BARE | lineal_interior | 1 | 2 | 0 | 0.053825 | c0=8.4392045 e; c1=0.053825 e·eV⁻¹ | 1 | — | 3.97205465e-15 | 5.32907052e-15 | [5.32907052e-15, 1.77635684e-15] |
| NiLR1 | NiLR0 | SCREENED | principal | 3 | 6 | 2 | 0.000978968254 | c0=8.439208 e; c1=0.000978968254 e·eV⁻¹; c2=8.92857162e-05 e·eV⁻²; c3=-0.0173611111 e·eV⁻³ | 0.999766834 | 6.57466612 | 6.13990331e-07 | 9.04761899e-07 | [-3.33333347e-07, 9.04761899e-07, -5.95238099e-07, -4.76190479e-07, 8.09523803e-07, -3.09523815e-07] |
| NiLR1 | NiLR0 | SCREENED | lineal_misma_malla | 1 | 6 | 4 | 0.000930357143 | c0=8.43920817 e; c1=0.000930357143 e·eV⁻¹ | 0.999328727 | — | 1.04178571e-06 | 1.61904762e-06 | [6.54761898e-07, 4.76190429e-08, -1.55952381e-06, 2.26190474e-07, 1.61904762e-06, -9.88095239e-07] |
| NiLR1 | NiLR0 | SCREENED | lineal_interior | 1 | 2 | 0 | 0.000975 | c0=8.4392075 e; c1=0.000975 e·eV⁻¹ | 1 | — | 3.55271368e-15 | 3.55271368e-15 | [3.55271368e-15, 3.55271368e-15] |
| NiLR0 | NiLR1 | BARE | principal | 3 | 6 | 2 | 0.0538117063 | c0=8.4392045 e; c1=0.0538117063 e·eV⁻¹; c2=1.17696169e-12 e·eV⁻²; c3=0.00347222221 e·eV⁻³ | 0.999999994 | 6.57466612 | 1.78174161e-07 | 2.3809524e-07 | [-4.76190571e-08, 1.90476186e-07, -2.3809524e-07, 2.38095236e-07, -1.90476195e-07, 4.76190447e-08] |
| NiLR0 | NiLR1 | BARE | lineal_misma_malla | 1 | 6 | 4 | 0.0538214286 | c0=8.4392045 e; c1=0.0538214286 e·eV⁻¹ | 0.999999989 | — | 2.43975019e-07 | 3.57142861e-07 | [-2.14285722e-07, 3.57142852e-07, -7.14285751e-08, 7.14285679e-08, -3.57142861e-07, 2.14285713e-07] |
| NiLR0 | NiLR1 | BARE | lineal_interior | 1 | 2 | 0 | 0.053825 | c0=8.4392045 e; c1=0.053825 e·eV⁻¹ | 1 | — | 3.97205465e-15 | 5.32907052e-15 | [5.32907052e-15, 1.77635684e-15] |
| NiLR0 | NiLR1 | SCREENED | principal | 3 | 6 | 2 | 0.000978968254 | c0=8.439208 e; c1=0.000978968254 e·eV⁻¹; c2=8.92857162e-05 e·eV⁻²; c3=-0.0173611111 e·eV⁻³ | 0.999766834 | 6.57466612 | 6.13990331e-07 | 9.04761899e-07 | [-3.33333347e-07, 9.04761899e-07, -5.95238099e-07, -4.76190479e-07, 8.09523803e-07, -3.09523815e-07] |
| NiLR0 | NiLR1 | SCREENED | lineal_misma_malla | 1 | 6 | 4 | 0.000930357143 | c0=8.43920817 e; c1=0.000930357143 e·eV⁻¹ | 0.999328727 | — | 1.04178571e-06 | 1.61904762e-06 | [6.54761898e-07, 4.76190429e-08, -1.55952381e-06, 2.26190474e-07, 1.61904762e-06, -9.88095239e-07] |
| NiLR0 | NiLR1 | SCREENED | lineal_interior | 1 | 2 | 0 | 0.000975 | c0=8.4392075 e; c1=0.000975 e·eV⁻¹ | 1 | — | 3.55271368e-15 | 3.55271368e-15 | [3.55271368e-15, 3.55271368e-15] |
| NiLR1 | NiLR1 | BARE | principal | 3 | 6 | 2 | -0.198345635 | c0=8.43920457 e; c1=-0.198345635 e·eV⁻¹; c2=0.0138903061 e·eV⁻²; c3=-0.00347222224 e·eV⁻³ | 1 | 6.57466612 | 1.52455338e-07 | 2.51700676e-07 | [-6.46258584e-08, 1.56462582e-07, -6.80272105e-08, -1.87074832e-07, 2.51700676e-07, -8.84353764e-08] |
| NiLR1 | NiLR1 | BARE | lineal_misma_malla | 1 | 6 | 4 | -0.198355357 | c0=8.4392305 e; c1=-0.198355357 e·eV⁻¹ | 0.999995422 | — | 1.833566e-05 | 2.41785714e-05 | [2.41785714e-05, -3.71428572e-06, -2.06071429e-05, -2.03928571e-05, -3.28571429e-06, 2.38214286e-05] |
| NiLR1 | NiLR1 | BARE | lineal_interior | 1 | 2 | 0 | -0.19835 | c0=8.43921 e; c1=-0.19835 e·eV⁻¹ | 1 | — | 2.80866677e-15 | 3.55271368e-15 | [1.77635684e-15, 3.55271368e-15] |
| NiLR1 | NiLR1 | SCREENED | principal | 3 | 6 | 2 | -0.0813355159 | c0=8.43920564 e; c1=-0.0813355159 e·eV⁻¹; c2=0.00108418367 e·eV⁻²; c3=0.00694444442 e·eV⁻³ | 0.99999998 | 6.57466612 | 4.97727261e-07 | 7.3129252e-07 | [-1.76870756e-07, 6.46258499e-07, -7.3129252e-07, 5.7823129e-07, -4.01360548e-07, 8.50340101e-08] |
| NiLR1 | NiLR1 | SCREENED | lineal_misma_malla | 1 | 6 | 4 | -0.0813160714 | c0=8.43920767 e; c1=-0.0813160714 e·eV⁻¹ | 0.999999805 | — | 1.55136908e-06 | 2.29761905e-06 | [1.36904762e-06, 6.90476188e-07, -1.98809524e-06, -1.3452381e-06, -1.02380952e-06, 2.29761905e-06] |
| NiLR1 | NiLR1 | SCREENED | lineal_interior | 1 | 2 | 0 | -0.0813 | c0=8.439206 e; c1=-0.0813 e·eV⁻¹ | 1 | — | 1.77635684e-15 | 1.77635684e-15 | [1.77635684e-15, 1.77635684e-15] |

## 5. Matrices de respuesta, inversas y U

Representación seleccionada para inversión: `raw`. Las matrices raw y simetrizadas se conservan como evidencia.

### χ⁰ raw (BARE) (eV⁻¹)

| Sitio observado \ Sitio perturbado | NiLR0 | NiLR1 |
|---|---:|---:|
| NiLR0 | -0.19834127 | 0.0538117063 |
| NiLR1 | 0.0538206349 | -0.198345635 |

### χ raw (SCREENED) (eV⁻¹)

| Sitio observado \ Sitio perturbado | NiLR0 | NiLR1 |
|---|---:|---:|
| NiLR0 | -0.0813355159 | 0.000978968254 |
| NiLR1 | 0.000978968254 | -0.0813355159 |

### χ⁰ simetrizada (eV⁻¹)

| Sitio observado \ Sitio perturbado | NiLR0 | NiLR1 |
|---|---:|---:|
| NiLR0 | -0.19834127 | 0.0538161706 |
| NiLR1 | 0.0538161706 | -0.198345635 |

### χ simetrizada (eV⁻¹)

| Sitio observado \ Sitio perturbado | NiLR0 | NiLR1 |
|---|---:|---:|
| NiLR0 | -0.0813355159 | 0.000978968254 |
| NiLR1 | 0.000978968254 | -0.0813355159 |

### χ⁰ usada para inversión (eV⁻¹)

| Sitio observado \ Sitio perturbado | NiLR0 | NiLR1 |
|---|---:|---:|
| NiLR0 | -0.19834127 | 0.0538117063 |
| NiLR1 | 0.0538206349 | -0.198345635 |

### χ usada para inversión (eV⁻¹)

| Sitio observado \ Sitio perturbado | NiLR0 | NiLR1 |
|---|---:|---:|
| NiLR0 | -0.0813355159 | 0.000978968254 |
| NiLR1 | 0.000978968254 | -0.0813355159 |

### (χ⁰)⁻¹ (eV)

| Sitio observado \ Sitio perturbado | NiLR0 | NiLR1 |
|---|---:|---:|
| NiLR0 | -5.44248532 | -1.47656096 |
| NiLR1 | -1.47680596 | -5.44236554 |

### χ⁻¹ (eV)

| Sitio observado \ Sitio perturbado | NiLR0 | NiLR1 |
|---|---:|---:|
| NiLR0 | -12.2965334 | -0.148003191 |
| NiLR1 | -0.148003191 | -12.2965334 |

### U_matrix (eV)

| Sitio observado \ Sitio perturbado | NiLR0 | NiLR1 |
|---|---:|---:|
| NiLR0 | 6.85404812 | -1.32855777 |
| NiLR1 | -1.32880277 | 6.8541679 |

### Diagnóstico de inversión: ajuste principal

| Matriz | Método | Residuo izquierdo Frobenius | Residuo derecho Frobenius |
|---|---|---:|---:|
| χ⁰ | direct_inv | 1.16406438e-16 | 1.21047169e-16 |
| χ | direct_inv | 1.47365454e-18 | 2.20032009e-18 |

**Condición de χ⁰:** rango 2/2; determinante 0.0364439449; número de condición 1.74471989; estado `FULL_RANK`.

**Condición de χ:** rango 2/2; determinante 0.00661450776; número de condición 1.02436561; estado `FULL_RANK`.

## 6. Sensibilidad, diagnósticos y estado

| Análisis | Ventana máxima α (eV) | Método | Tipo de ventana | Estado de matriz | U por sitio (eV) | Cota de impresión (eV) |
|---|---:|---|---|---|---|---:|
| Principal | — | polynomial | — | FULL_RANK | NiLR0: 6.85404812; NiLR1: 6.8541679 | 0.011834223 |
| Lineal misma malla | — | linear | — | FULL_RANK | NiLR0: 6.85725752; NiLR1: 6.85711054 | 0.00434300016 |
| Ventana | 0.02 | linear | resolution_limited_two_point_central_difference | FULL_RANK | NiLR0: 6.85953316; NiLR1: 6.85953316 | 0.0101488424 |
| Ventana | 0.04 | linear | eligible_linear_fit_window | FULL_RANK | NiLR0: 6.85500269; NiLR1: 6.85500269 | 0.00608206191 |
| Ventana | 0.06 | linear | eligible_linear_fit_window | FULL_RANK | NiLR0: 6.85725752; NiLR1: 6.85711054 | 0.00434300016 |

- Diferencia máxima de U entre modelos/ventanas informada: 0.00320939808 eV.
- Evaluación frente al umbral: `UNASSESSED_TOLERANCE_MISSING`; métricas requeridas completas: true.
- Umbral configurado para sensibilidad: — eV.
- Fuente de ocupación ajustada: `siesta_occupations_total`.
- Cota determinista de redondeo de la fuente de ocupación impresa: 0.011834223 eV; causa: deterministic bound propagated from siesta_occupations_total print intervals. No es un intervalo estadístico ni incluye ruido SCF.
- Validación SCF: true.
- Continuidad de estado: true.

Causas y advertencias registradas:
- `sensitivity_tolerance_not_configured`

## 7. Procedencia y archivos fuente

| Tipo | SHA-256 registrados |
|---|---|
| bare_fdf_sha256 | 01a35bd5e69df0795430c40b0875154cda4f050f9c53ecf30adcfcc4645e64bc, 1a04dddad1b330e1619ac4c09e2a0cadd35ec5c04366ce4c64d96a538aace910, 1ed4ff658c1d84315b8f5c5eea1101823426227265ee464c881ae8988df85d3d, 3714e11768e88dece9005bf21beaacceaa3ce402dbf7d18f9cdca457171407e8, 3a6fd9b8fb5b6409a9ef7f39da0b50f7fecbbef4dda4762700d5f06deb8f9213, 493d5704b52e04a874ff14cb98f86d83d9080e051dacc33d9b1ded505bc8fd11, 4bf296342392903701862cfc4bca42bda523e96f4b114fa6961f0e627d3bd89c, 662d676c2da5b348ec1175450b475e9e61ac92f6a45812baa56775710ca0b602, 9069fe1cd11b4bdd0f97c4fd5fb1c528d7314ef4d498f58f3925bc665e0b450d, 907e0cd7426e68bdf9951d0cca15e9927a0b7c069cbae2cdc4f11122423a1b05, d811c503dd5760a05bac72b8384c469833bdfbf9e5058bd076257960f93a934e, ed046b452227a2591af3918b303455f9d8c576f23968be40ff0d01f368514140 |
| bare_out_sha256 | 02cd3189dc8ec916bd5722fd82ff1b5905632bad106a38f69ed9beafc6dffc73, 059cdb7825ec59285aa29a15a942c757bd358ad54a0aac3df932e0537992299c, 3b010902c6bc490e0ed31a117123b70812cac7e170185b8c24b14d9510373cba, 40da44264230409e6bb2a292e8d9a98bcfb9280832e99164e0a4c3e2f0ed49c5, 631f6837d205fdba380e7730af348b19c3284bbfd7e0bb6678ffb78cce66a946, b18f071a3625c9ee43dd4867469fa596620a7112e66f7476491e30fdba7b87f1, b1f58f8728490a301e63be23cc911098c0e63f0b591da87ed8f235ba80dc2d4b, b2fe574d0cae8242eb9c6fff45949ab9caf4240714afff041322a492cdc56167, cedfe42dda8640460a1148606993c6c7b0a99136c315770990913f7da9684f33, d55714e6be836e192f0caccd189f55ebc70bfcba60b5b6e88e9e773aa1485082, e34e53e5a585bfa3d0fc5c8cf69a0ec93bb9053d580c2ec4bebcd3029473b0fb, ec223f58a2ab8eead806b1f8d0daa3cd7b5a1a33b9951bc02308feb708ad0278 |
| parent_dm_sha256 | f7fca191f941bbda5ee38eb361096aa8a802dfd410e12aaa680f39f3cf2193ef |
| projector_fingerprints | 1f9b40877be7fc45f7da2f33a4787c500940121fe897a874a2b1df88f50d4d7a, 938e53c7ed28aeea35cbb9004c603260074d169c62024f987b11ed8f9f2c5cc4 |
| screened_fdf_sha256 | 0cab454848840e2e38adcfb24ca1ffb0ac6e4d8b2840f8d8694dca29b3fba366, 1417887f3602c69fadfb677543b14427170720e481db907975dcf3d44bbb19a0, 14e47fde128fe27351d1d231ef8b1c70a2486dd46b1426d21ebc2aa7a8f7f194, 69cdd970b741dfea4fe9488365adc71d7fe74b75651218e022f7e47f4d1cc2dc, 757c10af42ac3065038570ad037de1644f6c613215c024371784316e9b9b0e33, 7bd4eb266ded35eeaf20689cd1298f91808e72e898334c2cc3599a60d0ac6345, 9b0f027be3c4d22a59e882a3670aaa08af400e6dd7112366665fc2f43f9fb68a, a465103589c5a9709a6570d64f37160fd2f8717f9aaccc2002fe2277dc7caa21, b9f0ccbf1fcb8de5e365cb48a3d449dde2546f98204ad2ded72c3332ca7f9c59, ccdc4b96512b54a5e5649a8bb0f659e542bf142e983b0ef1d43ef88f4dbf4f0a, d3c32e27d4ecb3a5b1000a682f88c21c68bc39f56de5cbb67c36a3429f7d4468, e163edfd426c213b37feefbb997c3f476a447ebc2c60bf4e309daf61873035cb |
| screened_out_sha256 | 29c14506e0e87522417ec4cb34db2d26a30a5737807c9ecc2addd411ad68d9ef, 2bb7c55d9a800c3cc3b36634077de01c12a934ed5a5f9dabce549acea693f1b5, 31722cc6d35d3bddfcc01a1d67868dba2ce91930d32115f355b2c3f4dd71d09c, 5c91cef5d8665295e275d523ae9729595a3b75f0a2b065c4e85fbcb02a09a423, 612ca280acb16e7451a80ef3ae2c4e5736a3049b4d12bc4776ba7d0d1cf59fa1, 6ce3428d1a608179e77eea8849e4d9ef19fca4deaf4b3d2857a21de97ed97184, 747b81cba0a5c4ac5a46730d51c841854b6398391ed50e95b70be72147ddca97, 896964697447b302fb44b7475a1110e4d3fe143108c6a5b481bd9fbc7e6a092e, b00da6d81ac26e823ea68202d506b5ae471e102fc05d4b907c5957b747811917, b82fc2d20c5ba8e8085556198521da8c0f1164e743cb0e6da6f956427512bf33, d721c9a29adc216cefffb6950387badd22202ee9392507b62f93d2ff83f656d6, e6b8feb18398c43676a53268321920e150f34aa708ef1cd230132aed6bd5f778 |

### Entradas declaradas de la campaña

| Archivo | Ruta | SHA-256 |
|---|---|---|
| campaign_contract | backend_contract.json | 65bf304fcb211194816011644096904fcd5126dbc83a4a33cb3a3127960cd74d |
| execution_profile | execution_profile.json | fbc9ff5ae47a6791d0e1ff962b6070f8690f1ffef475bafd8784a7388d755ae1 |
| lr_config | lr_config.json | a80ae70321b53dbe197a4d0b2d8946933747ad81e57c6fa62d79b5dc6a812831 |
| reference_fdf | reference.fdf | b4fb34e642d862be6949a5b2033a60c5b9fcae56119879583bb3eaf237620ee7 |

### Pseudopotenciales declarados

| Especie | Archivo | SHA-256 |
|---|---|---|
| NiLR0 | pseudopotentials/NiLR0.psml | 192eb05ffb64671715e570e2ca9a99a551cf15544984592082d43004f8554e06 |
| NiLR1 | pseudopotentials/NiLR1.psml | 192eb05ffb64671715e570e2ca9a99a551cf15544984592082d43004f8554e06 |
| O | pseudopotentials/O.psml | 224ded5c59176d9bcb76d19b7a4a68a48d5dffabf8b262f64d5760250e87c35e |

### Ejecutable y versión de SIESTA

| Ejecutable declarado | Ruta ejecutable | Versión admitida | Archivo de versión | SHA-256 del archivo de versión |
|---|---|---|---|---|
| siesta | /home/jmc/.local/siesta-5.4.2-openmpi/bin/siesta | 5.4.2 | software/siesta_version.txt | bb5a9b03dfaec9953401a7ef8db045149461047c44f15f9c5bf7758900b5f3ee |

### Archivos de cada respuesta validada

| α perturbado | Sitio perturbado | Modo | Nodo | FDF | .out | SHA-256 FDF / .out | Digest de evidencia del recibo |
|---:|---|---|---|---|---|---|---|
| — | Referencia | REFERENCE_SCREENED | reference:adaptive:c64f889134214da9:base | .siestaflow/attempts/95787691423a4b0e3eac/attempt-1790609522103140072-d9ba696d/reference_adaptive_c64f889134214da9_base_95787691423a/siesta.fdf | .siestaflow/attempts/95787691423a4b0e3eac/attempt-1790609522103140072-d9ba696d/reference_adaptive_c64f889134214da9_base_95787691423a/siesta.out | b4fb34e642d862be6949a5b2033a60c5b9fcae56119879583bb3eaf237620ee7 / 13a6a00b0bbc7a023fa23d60f908c0ace8ef537af7b70d744677aaf0d9e435c8 | d4ed762e6f23a87de4aa3fb02efff01abfec4d5087065107b73313125769cbbe |
| -0.06 | NiLR0 | BARE | response:c64f889134214da9:r0:lr_s000_m0p06_bare_scf_base_parent_reference_adaptive_c64f889134214da9_base | .siestaflow/attempts/ff6236e3ca42c31208da/attempt-1790609549101356221-81894067/response_c64f889134214da9_r0_lr_s000_m0p06_bare_scf_base_parent_referenc_ff6236e3ca42/siesta.fdf | .siestaflow/attempts/ff6236e3ca42c31208da/attempt-1790609549101356221-81894067/response_c64f889134214da9_r0_lr_s000_m0p06_bare_scf_base_parent_referenc_ff6236e3ca42/siesta.out | 493d5704b52e04a874ff14cb98f86d83d9080e051dacc33d9b1ded505bc8fd11 / b18f071a3625c9ee43dd4867469fa596620a7112e66f7476491e30fdba7b87f1 | 865ba216f6b25314b7e36588fa1bb7de76b33c4cf717d0612fe025f555e633c7 |
| -0.06 | NiLR0 | SCREENED | response:c64f889134214da9:r0:lr_s000_m0p06_screened_scf_base_parent_reference_adaptive_c64f889134214da9_base | .siestaflow/attempts/01fd5e241044ec8d402d/attempt-1790609553906882897-1639a1b1/response_c64f889134214da9_r0_lr_s000_m0p06_screened_scf_base_parent_refe_01fd5e241044/siesta.fdf | .siestaflow/attempts/01fd5e241044ec8d402d/attempt-1790609553906882897-1639a1b1/response_c64f889134214da9_r0_lr_s000_m0p06_screened_scf_base_parent_refe_01fd5e241044/siesta.out | 7bd4eb266ded35eeaf20689cd1298f91808e72e898334c2cc3599a60d0ac6345 / e6b8feb18398c43676a53268321920e150f34aa708ef1cd230132aed6bd5f778 | 35dd7bbc6490b45b8abe482e677d0bfc27d5ec176e704572fb814f492b8dfd2c |
| -0.04 | NiLR0 | BARE | response:c64f889134214da9:r0:lr_s000_m0p04_bare_scf_base_parent_reference_adaptive_c64f889134214da9_base | .siestaflow/attempts/c827e02689b3fba45442/attempt-1790609581236017913-37ae69fc/response_c64f889134214da9_r0_lr_s000_m0p04_bare_scf_base_parent_referenc_c827e02689b3/siesta.fdf | .siestaflow/attempts/c827e02689b3fba45442/attempt-1790609581236017913-37ae69fc/response_c64f889134214da9_r0_lr_s000_m0p04_bare_scf_base_parent_referenc_c827e02689b3/siesta.out | ed046b452227a2591af3918b303455f9d8c576f23968be40ff0d01f368514140 / d55714e6be836e192f0caccd189f55ebc70bfcba60b5b6e88e9e773aa1485082 | 92b9ecae8f7648c32879feebec890b1f4d90ed610eb89da96e844874265d355f |
| -0.04 | NiLR0 | SCREENED | response:c64f889134214da9:r0:lr_s000_m0p04_screened_scf_base_parent_reference_adaptive_c64f889134214da9_base | .siestaflow/attempts/3f17a8d609369d1c9edf/attempt-1790609586238563738-3d35b0f8/response_c64f889134214da9_r0_lr_s000_m0p04_screened_scf_base_parent_refe_3f17a8d60936/siesta.fdf | .siestaflow/attempts/3f17a8d609369d1c9edf/attempt-1790609586238563738-3d35b0f8/response_c64f889134214da9_r0_lr_s000_m0p04_screened_scf_base_parent_refe_3f17a8d60936/siesta.out | 69cdd970b741dfea4fe9488365adc71d7fe74b75651218e022f7e47f4d1cc2dc / 2bb7c55d9a800c3cc3b36634077de01c12a934ed5a5f9dabce549acea693f1b5 | 4da289cbe292a5d1cb75487a6b71605f617df8fb0af5bfa32252321ad7a3bf52 |
| -0.02 | NiLR0 | BARE | response:c64f889134214da9:r0:lr_s000_m0p02_bare_scf_base_parent_reference_adaptive_c64f889134214da9_base | .siestaflow/attempts/2533545ff11332262cb7/attempt-1790609617666579246-c1f913b7/response_c64f889134214da9_r0_lr_s000_m0p02_bare_scf_base_parent_referenc_2533545ff113/siesta.fdf | .siestaflow/attempts/2533545ff11332262cb7/attempt-1790609617666579246-c1f913b7/response_c64f889134214da9_r0_lr_s000_m0p02_bare_scf_base_parent_referenc_2533545ff113/siesta.out | 907e0cd7426e68bdf9951d0cca15e9927a0b7c069cbae2cdc4f11122423a1b05 / b1f58f8728490a301e63be23cc911098c0e63f0b591da87ed8f235ba80dc2d4b | bee090f0e27d47629d4a93d89a39454cf402e3c980bf26633b08c507db80279e |
| -0.02 | NiLR0 | SCREENED | response:c64f889134214da9:r0:lr_s000_m0p02_screened_scf_base_parent_reference_adaptive_c64f889134214da9_base | .siestaflow/attempts/d7a40c8aa6e97632b6b4/attempt-1790609622834863687-d0cac548/response_c64f889134214da9_r0_lr_s000_m0p02_screened_scf_base_parent_refe_d7a40c8aa6e9/siesta.fdf | .siestaflow/attempts/d7a40c8aa6e97632b6b4/attempt-1790609622834863687-d0cac548/response_c64f889134214da9_r0_lr_s000_m0p02_screened_scf_base_parent_refe_d7a40c8aa6e9/siesta.out | 14e47fde128fe27351d1d231ef8b1c70a2486dd46b1426d21ebc2aa7a8f7f194 / b82fc2d20c5ba8e8085556198521da8c0f1164e743cb0e6da6f956427512bf33 | a5b31be12bdf1ae75017d95898c3c45c745b978e8b5cc04e130645681c14d808 |
| 0.02 | NiLR0 | BARE | response:c64f889134214da9:r0:lr_s000_p0p02_bare_scf_base_parent_reference_adaptive_c64f889134214da9_base | .siestaflow/attempts/b5178e5e6d57036e65b0/attempt-1790609652403195484-a19fb3ab/response_c64f889134214da9_r0_lr_s000_p0p02_bare_scf_base_parent_referenc_b5178e5e6d57/siesta.fdf | .siestaflow/attempts/b5178e5e6d57036e65b0/attempt-1790609652403195484-a19fb3ab/response_c64f889134214da9_r0_lr_s000_p0p02_bare_scf_base_parent_referenc_b5178e5e6d57/siesta.out | 01a35bd5e69df0795430c40b0875154cda4f050f9c53ecf30adcfcc4645e64bc / 02cd3189dc8ec916bd5722fd82ff1b5905632bad106a38f69ed9beafc6dffc73 | d011de4d89bbb229fa8795c042cbbaa66fcad20ede3323f3b07151f017c23763 |
| 0.02 | NiLR0 | SCREENED | response:c64f889134214da9:r0:lr_s000_p0p02_screened_scf_base_parent_reference_adaptive_c64f889134214da9_base | .siestaflow/attempts/990f2d24558d6eb806cf/attempt-1790609657724503674-07d8199e/response_c64f889134214da9_r0_lr_s000_p0p02_screened_scf_base_parent_refe_990f2d24558d/siesta.fdf | .siestaflow/attempts/990f2d24558d6eb806cf/attempt-1790609657724503674-07d8199e/response_c64f889134214da9_r0_lr_s000_p0p02_screened_scf_base_parent_refe_990f2d24558d/siesta.out | 9b0f027be3c4d22a59e882a3670aaa08af400e6dd7112366665fc2f43f9fb68a / 747b81cba0a5c4ac5a46730d51c841854b6398391ed50e95b70be72147ddca97 | bad4799a5fd87d532001715b113e1434674e7af48a7864662404066ee0700088 |
| 0.04 | NiLR0 | BARE | response:c64f889134214da9:r0:lr_s000_p0p04_bare_scf_base_parent_reference_adaptive_c64f889134214da9_base | .siestaflow/attempts/3b4e95bb1c098bb3a662/attempt-1790609688031822431-5d607b73/response_c64f889134214da9_r0_lr_s000_p0p04_bare_scf_base_parent_referenc_3b4e95bb1c09/siesta.fdf | .siestaflow/attempts/3b4e95bb1c098bb3a662/attempt-1790609688031822431-5d607b73/response_c64f889134214da9_r0_lr_s000_p0p04_bare_scf_base_parent_referenc_3b4e95bb1c09/siesta.out | 1ed4ff658c1d84315b8f5c5eea1101823426227265ee464c881ae8988df85d3d / 059cdb7825ec59285aa29a15a942c757bd358ad54a0aac3df932e0537992299c | 5e15fb084b6f1b1ba91a6a760c5776e8d83aa0e58f9858e2cd0cfd1ccdf836ea |
| 0.04 | NiLR0 | SCREENED | response:c64f889134214da9:r0:lr_s000_p0p04_screened_scf_base_parent_reference_adaptive_c64f889134214da9_base | .siestaflow/attempts/5e29d95670d33a18fd35/attempt-1790609693011908698-2d4f77bf/response_c64f889134214da9_r0_lr_s000_p0p04_screened_scf_base_parent_refe_5e29d95670d3/siesta.fdf | .siestaflow/attempts/5e29d95670d33a18fd35/attempt-1790609693011908698-2d4f77bf/response_c64f889134214da9_r0_lr_s000_p0p04_screened_scf_base_parent_refe_5e29d95670d3/siesta.out | ccdc4b96512b54a5e5649a8bb0f659e542bf142e983b0ef1d43ef88f4dbf4f0a / 6ce3428d1a608179e77eea8849e4d9ef19fca4deaf4b3d2857a21de97ed97184 | f67d8443c8840b42fdbb819847e8c7262ec46edf3a519c5a88d49c993a2b1f42 |
| 0.06 | NiLR0 | BARE | response:c64f889134214da9:r0:lr_s000_p0p06_bare_scf_base_parent_reference_adaptive_c64f889134214da9_base | .siestaflow/attempts/24484c88941694b45f86/attempt-1790609723404226395-9c9874bd/response_c64f889134214da9_r0_lr_s000_p0p06_bare_scf_base_parent_referenc_24484c889416/siesta.fdf | .siestaflow/attempts/24484c88941694b45f86/attempt-1790609723404226395-9c9874bd/response_c64f889134214da9_r0_lr_s000_p0p06_bare_scf_base_parent_referenc_24484c889416/siesta.out | 1a04dddad1b330e1619ac4c09e2a0cadd35ec5c04366ce4c64d96a538aace910 / 40da44264230409e6bb2a292e8d9a98bcfb9280832e99164e0a4c3e2f0ed49c5 | 9e22b440d86adcc1d0e5d1dae57779a1a37d2e23040cb5c40b2541e640dba15b |
| 0.06 | NiLR0 | SCREENED | response:c64f889134214da9:r0:lr_s000_p0p06_screened_scf_base_parent_reference_adaptive_c64f889134214da9_base | .siestaflow/attempts/ed0814b865398399bf81/attempt-1790609728788152120-78b6fd29/response_c64f889134214da9_r0_lr_s000_p0p06_screened_scf_base_parent_refe_ed0814b86539/siesta.fdf | .siestaflow/attempts/ed0814b865398399bf81/attempt-1790609728788152120-78b6fd29/response_c64f889134214da9_r0_lr_s000_p0p06_screened_scf_base_parent_refe_ed0814b86539/siesta.out | b9f0ccbf1fcb8de5e365cb48a3d449dde2546f98204ad2ded72c3332ca7f9c59 / 29c14506e0e87522417ec4cb34db2d26a30a5737807c9ecc2addd411ad68d9ef | 96e7c4dfff0a4c2a9bc5a41a412dc2a548fd2aa043015dbc55335a32f08fcc05 |
| -0.06 | NiLR1 | BARE | response:c64f889134214da9:r0:lr_s001_m0p06_bare_scf_base_parent_reference_adaptive_c64f889134214da9_base | .siestaflow/attempts/503652abfaf0ee280397/attempt-1790609755797855121-81a1bc6e/response_c64f889134214da9_r0_lr_s001_m0p06_bare_scf_base_parent_referenc_503652abfaf0/siesta.fdf | .siestaflow/attempts/503652abfaf0ee280397/attempt-1790609755797855121-81a1bc6e/response_c64f889134214da9_r0_lr_s001_m0p06_bare_scf_base_parent_referenc_503652abfaf0/siesta.out | 3a6fd9b8fb5b6409a9ef7f39da0b50f7fecbbef4dda4762700d5f06deb8f9213 / ec223f58a2ab8eead806b1f8d0daa3cd7b5a1a33b9951bc02308feb708ad0278 | 9a030fe2383867b61ec7af38d3f9e3a1148bb4c3eb0f9e781e91cd26c6346274 |
| -0.06 | NiLR1 | SCREENED | response:c64f889134214da9:r0:lr_s001_m0p06_screened_scf_base_parent_reference_adaptive_c64f889134214da9_base | .siestaflow/attempts/c9696e86ce994994262d/attempt-1790609761537911551-d2325e64/response_c64f889134214da9_r0_lr_s001_m0p06_screened_scf_base_parent_refe_c9696e86ce99/siesta.fdf | .siestaflow/attempts/c9696e86ce994994262d/attempt-1790609761537911551-d2325e64/response_c64f889134214da9_r0_lr_s001_m0p06_screened_scf_base_parent_refe_c9696e86ce99/siesta.out | 757c10af42ac3065038570ad037de1644f6c613215c024371784316e9b9b0e33 / b00da6d81ac26e823ea68202d506b5ae471e102fc05d4b907c5957b747811917 | a2655e59b9be7f2fbc1e294b8affc51c2ac4f2bdad09bb3f69ba4044b6715298 |
| -0.04 | NiLR1 | BARE | response:c64f889134214da9:r0:lr_s001_m0p04_bare_scf_base_parent_reference_adaptive_c64f889134214da9_base | .siestaflow/attempts/56da72dec634261e3d89/attempt-1790609791370635697-1ed0edb2/response_c64f889134214da9_r0_lr_s001_m0p04_bare_scf_base_parent_referenc_56da72dec634/siesta.fdf | .siestaflow/attempts/56da72dec634261e3d89/attempt-1790609791370635697-1ed0edb2/response_c64f889134214da9_r0_lr_s001_m0p04_bare_scf_base_parent_referenc_56da72dec634/siesta.out | 3714e11768e88dece9005bf21beaacceaa3ce402dbf7d18f9cdca457171407e8 / 631f6837d205fdba380e7730af348b19c3284bbfd7e0bb6678ffb78cce66a946 | 199aa127b693e8d9f94cc10eb7ba6b09115f3526b942c969898cb83bc6c7a3d6 |
| -0.04 | NiLR1 | SCREENED | response:c64f889134214da9:r0:lr_s001_m0p04_screened_scf_base_parent_reference_adaptive_c64f889134214da9_base | .siestaflow/attempts/bbc77185b6046a9ca639/attempt-1790609796960032929-ed504dc2/response_c64f889134214da9_r0_lr_s001_m0p04_screened_scf_base_parent_refe_bbc77185b604/siesta.fdf | .siestaflow/attempts/bbc77185b6046a9ca639/attempt-1790609796960032929-ed504dc2/response_c64f889134214da9_r0_lr_s001_m0p04_screened_scf_base_parent_refe_bbc77185b604/siesta.out | 1417887f3602c69fadfb677543b14427170720e481db907975dcf3d44bbb19a0 / 5c91cef5d8665295e275d523ae9729595a3b75f0a2b065c4e85fbcb02a09a423 | 4c735c40027b7aac2f06986d72c885760c06d1c7b63331018fedc8a66def1cdc |
| -0.02 | NiLR1 | BARE | response:c64f889134214da9:r0:lr_s001_m0p02_bare_scf_base_parent_reference_adaptive_c64f889134214da9_base | .siestaflow/attempts/245a97e94ad192b25402/attempt-1790609830466938894-bde78806/response_c64f889134214da9_r0_lr_s001_m0p02_bare_scf_base_parent_referenc_245a97e94ad1/siesta.fdf | .siestaflow/attempts/245a97e94ad192b25402/attempt-1790609830466938894-bde78806/response_c64f889134214da9_r0_lr_s001_m0p02_bare_scf_base_parent_referenc_245a97e94ad1/siesta.out | 9069fe1cd11b4bdd0f97c4fd5fb1c528d7314ef4d498f58f3925bc665e0b450d / b2fe574d0cae8242eb9c6fff45949ab9caf4240714afff041322a492cdc56167 | 3b8cb6a8c1bfed2a49000870505f43b7abeed1ea8e4b4c5500f393150e7d6dcc |
| -0.02 | NiLR1 | SCREENED | response:c64f889134214da9:r0:lr_s001_m0p02_screened_scf_base_parent_reference_adaptive_c64f889134214da9_base | .siestaflow/attempts/42a7f20d3856f2d2f640/attempt-1790609835739113532-f293130e/response_c64f889134214da9_r0_lr_s001_m0p02_screened_scf_base_parent_refe_42a7f20d3856/siesta.fdf | .siestaflow/attempts/42a7f20d3856f2d2f640/attempt-1790609835739113532-f293130e/response_c64f889134214da9_r0_lr_s001_m0p02_screened_scf_base_parent_refe_42a7f20d3856/siesta.out | e163edfd426c213b37feefbb997c3f476a447ebc2c60bf4e309daf61873035cb / d721c9a29adc216cefffb6950387badd22202ee9392507b62f93d2ff83f656d6 | 2a0ea5d0df57d7d26f92279e23b0038a4748d6725dcd68ee2a1d3f5ab49b14dd |
| 0.02 | NiLR1 | BARE | response:c64f889134214da9:r0:lr_s001_p0p02_bare_scf_base_parent_reference_adaptive_c64f889134214da9_base | .siestaflow/attempts/49a4da4d1a174503ec58/attempt-1790609863618350468-0e7e797e/response_c64f889134214da9_r0_lr_s001_p0p02_bare_scf_base_parent_referenc_49a4da4d1a17/siesta.fdf | .siestaflow/attempts/49a4da4d1a174503ec58/attempt-1790609863618350468-0e7e797e/response_c64f889134214da9_r0_lr_s001_p0p02_bare_scf_base_parent_referenc_49a4da4d1a17/siesta.out | 4bf296342392903701862cfc4bca42bda523e96f4b114fa6961f0e627d3bd89c / 3b010902c6bc490e0ed31a117123b70812cac7e170185b8c24b14d9510373cba | c12e033feb06d0fc6f3cecb104902282fe21f2806dc30c48bb7e5491239caa59 |
| 0.02 | NiLR1 | SCREENED | response:c64f889134214da9:r0:lr_s001_p0p02_screened_scf_base_parent_reference_adaptive_c64f889134214da9_base | .siestaflow/attempts/e80aeae5950b3a4dfd1e/attempt-1790609869105804184-40223d65/response_c64f889134214da9_r0_lr_s001_p0p02_screened_scf_base_parent_refe_e80aeae5950b/siesta.fdf | .siestaflow/attempts/e80aeae5950b3a4dfd1e/attempt-1790609869105804184-40223d65/response_c64f889134214da9_r0_lr_s001_p0p02_screened_scf_base_parent_refe_e80aeae5950b/siesta.out | d3c32e27d4ecb3a5b1000a682f88c21c68bc39f56de5cbb67c36a3429f7d4468 / 612ca280acb16e7451a80ef3ae2c4e5736a3049b4d12bc4776ba7d0d1cf59fa1 | 074a48a5e7334ea03365ec745221b22628346dfeea9766ec5502df2c63c5c647 |
| 0.04 | NiLR1 | BARE | response:c64f889134214da9:r0:lr_s001_p0p04_bare_scf_base_parent_reference_adaptive_c64f889134214da9_base | .siestaflow/attempts/8a5372c06924bd4535cd/attempt-1790609896601725542-d2bd4035/response_c64f889134214da9_r0_lr_s001_p0p04_bare_scf_base_parent_referenc_8a5372c06924/siesta.fdf | .siestaflow/attempts/8a5372c06924bd4535cd/attempt-1790609896601725542-d2bd4035/response_c64f889134214da9_r0_lr_s001_p0p04_bare_scf_base_parent_referenc_8a5372c06924/siesta.out | 662d676c2da5b348ec1175450b475e9e61ac92f6a45812baa56775710ca0b602 / e34e53e5a585bfa3d0fc5c8cf69a0ec93bb9053d580c2ec4bebcd3029473b0fb | 0b1871f8ecf3dea22c309665e473f44f23d7c5f704e16f16020a20f9115de073 |
| 0.04 | NiLR1 | SCREENED | response:c64f889134214da9:r0:lr_s001_p0p04_screened_scf_base_parent_reference_adaptive_c64f889134214da9_base | .siestaflow/attempts/5a780d3af5f805a4e966/attempt-1790609901850259596-59861bba/response_c64f889134214da9_r0_lr_s001_p0p04_screened_scf_base_parent_refe_5a780d3af5f8/siesta.fdf | .siestaflow/attempts/5a780d3af5f805a4e966/attempt-1790609901850259596-59861bba/response_c64f889134214da9_r0_lr_s001_p0p04_screened_scf_base_parent_refe_5a780d3af5f8/siesta.out | 0cab454848840e2e38adcfb24ca1ffb0ac6e4d8b2840f8d8694dca29b3fba366 / 896964697447b302fb44b7475a1110e4d3fe143108c6a5b481bd9fbc7e6a092e | 284479206c33e1f2fc98cdb9efe38f90889bde4ef736b01a424fad1e0c2e555a |
| 0.06 | NiLR1 | BARE | response:c64f889134214da9:r0:lr_s001_p0p06_bare_scf_base_parent_reference_adaptive_c64f889134214da9_base | .siestaflow/attempts/1a22aa5274a1a2380da6/attempt-1790609931066536165-72eb73c6/response_c64f889134214da9_r0_lr_s001_p0p06_bare_scf_base_parent_referenc_1a22aa5274a1/siesta.fdf | .siestaflow/attempts/1a22aa5274a1a2380da6/attempt-1790609931066536165-72eb73c6/response_c64f889134214da9_r0_lr_s001_p0p06_bare_scf_base_parent_referenc_1a22aa5274a1/siesta.out | d811c503dd5760a05bac72b8384c469833bdfbf9e5058bd076257960f93a934e / cedfe42dda8640460a1148606993c6c7b0a99136c315770990913f7da9684f33 | 1cb90d54b78728dace214244c7a5c45e77ba7f923f0f728268ee04bc8d5ce14d |
| 0.06 | NiLR1 | SCREENED | response:c64f889134214da9:r0:lr_s001_p0p06_screened_scf_base_parent_reference_adaptive_c64f889134214da9_base | .siestaflow/attempts/f22ce02a6851faa21c93/attempt-1790609936724902451-eb0e75d8/response_c64f889134214da9_r0_lr_s001_p0p06_screened_scf_base_parent_refe_f22ce02a6851/siesta.fdf | .siestaflow/attempts/f22ce02a6851faa21c93/attempt-1790609936724902451-eb0e75d8/response_c64f889134214da9_r0_lr_s001_p0p06_screened_scf_base_parent_refe_f22ce02a6851/siesta.out | a465103589c5a9709a6570d64f37160fd2f8717f9aaccc2002fe2277dc7caa21 / 31722cc6d35d3bddfcc01a1d67868dba2ce91930d32115f355b2c3f4dd71d09c | e5100dbc1e215d89149f55d112ccdde6d6db08528aacee5cf7cfd9cbc3d07ee8 |

La sensibilidad entre estimadores y ventanas es un diagnóstico y no un intervalo de confianza. La cota determinista de redondeo se calcula desde los tokens del total `Occupations:` impreso; si faltan esos tokens, queda como no disponible.
