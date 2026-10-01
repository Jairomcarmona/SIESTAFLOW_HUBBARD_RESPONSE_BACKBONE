# Informe de respuesta lineal de Hubbard

- **Campaña:** 3c23a23d-36df-4dfb-81b1-72de11abfb3f
- **Material:** CoO-AFMII-PBE-Stage-U-B-V6
- **Funcional:** PBE
- **Versión SIESTA:** 5.4.2
- **Analizador:** siestaflow_hubbard 0.1.2 — siestaflow.lr_u_analysis.v3
- **Cantidad calculada:** `U_scalar_charge` (eV)
- **Estado numérico:** **NUMERICAL_CANDIDATE_SENSITIVE**
- **Aceptación física:** **NOT_ESTABLISHED**
- **Precisión numérica total:** `NOT_ASSESSED_TOTAL_PRECISION_COMPONENT_UNAVAILABLE`; tolerancia predeclarada: 0.02 eV.
- **Estimador principal:** polynomial, grado 3
- **Malla α (eV):** `-0.06, -0.04, -0.02, 0.02, 0.04, 0.06`
- **Acción DAG registrada:** `RECORDED_ONLY`

El resultado corresponde a `U_scalar_charge` de la respuesta de carga declarada. No se convierte automáticamente en `Ueff_Dudarev` ni implica aceptación física.

## 1. Resumen de U por sitio

| Cantidad | Sitio | Valor (eV) | Método | Sensibilidad al modelo (eV) | Sensibilidad a ventana (eV) | Estado numérico | Acción DAG |
|---|---|---:|---|---:|---:|---|---|
| U_scalar_charge | CoLR0 | 5.8171485 | polynomial | 0.0171576822 | 0.00863410563 | NUMERICAL_CANDIDATE_SENSITIVE | RECORDED_ONLY |
| U_scalar_charge | CoLR1 | 5.81501986 | polynomial | 0.0202611543 | 0.0104334771 | NUMERICAL_CANDIDATE_SENSITIVE | RECORDED_ONLY |

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
| CoLR0 | -0.06 | CoLR0 | 7.386585 | 7.467046 | 7.39361 | 5e-07 / 5e-07 / 5e-07 |
| CoLR0 | -0.06 | CoLR1 | 7.386586 | 7.315995 | 7.384515 | 5e-07 / 5e-07 / 5e-07 |
| CoLR0 | -0.04 | CoLR0 | 7.386585 | 7.440748 | 7.391272 | 5e-07 / 5e-07 / 5e-07 |
| CoLR0 | -0.04 | CoLR1 | 7.386586 | 7.338808 | 7.3852 | 5e-07 / 5e-07 / 5e-07 |
| CoLR0 | -0.02 | CoLR0 | 7.386585 | 7.413773 | 7.388929 | 5e-07 / 5e-07 / 5e-07 |
| CoLR0 | -0.02 | CoLR1 | 7.386586 | 7.362489 | 7.385894 | 5e-07 / 5e-07 / 5e-07 |
| CoLR0 | 0.02 | CoLR0 | 7.386585 | 7.35971 | 7.384242 | 5e-07 / 5e-07 / 5e-07 |
| CoLR0 | 0.02 | CoLR1 | 7.386586 | 7.41056 | 7.38728 | 5e-07 / 5e-07 / 5e-07 |
| CoLR0 | 0.04 | CoLR0 | 7.386585 | 7.333529 | 7.381899 | 5e-07 / 5e-07 / 5e-07 |
| CoLR0 | 0.04 | CoLR1 | 7.386586 | 7.434011 | 7.387973 | 5e-07 / 5e-07 / 5e-07 |
| CoLR0 | 0.06 | CoLR0 | 7.386585 | 7.308455 | 7.379557 | 5e-07 / 5e-07 / 5e-07 |
| CoLR0 | 0.06 | CoLR1 | 7.386586 | 7.456492 | 7.388669 | 5e-07 / 5e-07 / 5e-07 |
| CoLR1 | -0.06 | CoLR0 | 7.386585 | 7.316028 | 7.384515 | 5e-07 / 5e-07 / 5e-07 |
| CoLR1 | -0.06 | CoLR1 | 7.386586 | 7.467013 | 7.39361 | 5e-07 / 5e-07 / 5e-07 |
| CoLR1 | -0.04 | CoLR0 | 7.386585 | 7.338842 | 7.3852 | 5e-07 / 5e-07 / 5e-07 |
| CoLR1 | -0.04 | CoLR1 | 7.386586 | 7.440713 | 7.391272 | 5e-07 / 5e-07 / 5e-07 |
| CoLR1 | -0.02 | CoLR0 | 7.386585 | 7.362525 | 7.385894 | 5e-07 / 5e-07 / 5e-07 |
| CoLR1 | -0.02 | CoLR1 | 7.386586 | 7.413738 | 7.388929 | 5e-07 / 5e-07 / 5e-07 |
| CoLR1 | 0.02 | CoLR0 | 7.386585 | 7.410596 | 7.38728 | 5e-07 / 5e-07 / 5e-07 |
| CoLR1 | 0.02 | CoLR1 | 7.386586 | 7.359675 | 7.384242 | 5e-07 / 5e-07 / 5e-07 |
| CoLR1 | 0.04 | CoLR0 | 7.386585 | 7.434045 | 7.387974 | 5e-07 / 5e-07 / 5e-07 |
| CoLR1 | 0.04 | CoLR1 | 7.386586 | 7.333495 | 7.381898 | 5e-07 / 5e-07 / 5e-07 |
| CoLR1 | 0.06 | CoLR0 | 7.386585 | 7.456525 | 7.388664 | 5e-07 / 5e-07 / 5e-07 |
| CoLR1 | 0.06 | CoLR1 | 7.386586 | 7.308423 | 7.37956 | 5e-07 / 5e-07 / 5e-07 |

## 4. Ajustes elemento por elemento

Cada fila corresponde a (sitio observado `I`, sitio perturbado `J`, modo). La pendiente del ajuste principal forma el elemento χ⁰_IJ (BARE) o χ_IJ (SCREENED). Los residuos son `n calculada − n ajustada` en el orden de α indicado por el análisis.

| Sitio observado I | Sitio perturbado J | Modo | Ajuste | Grado | Puntos | gl residuales | Pendiente c₁ (e·eV⁻¹) | Coeficientes con unidades | R² | Condición diseño | RMS residuo (e) | Máx. abs. residuo (e) | Residuos (e) |
|---|---|---|---|---:|---:|---:|---:|---|---:|---:|---:|---:|---|
| CoLR0 | CoLR0 | BARE | principal | 3 | 6 | 2 | -1.35522321 | c0=7.38662336 e; c1=-1.35522321 e·eV⁻¹; c2=0.314362245 e·eV⁻²; c3=9.34375 e·eV⁻³ | 0.999999977 | 6.57466612 | 8.79200317e-06 | 1.35918367e-05 | [-4.20408164e-06, 1.07346939e-05, -5.81632653e-06, -9.38775511e-06, 1.35918367e-05, -4.91836735e-06] |
| CoLR0 | CoLR0 | BARE | lineal_misma_malla | 1 | 6 | 4 | -1.32906071 | c0=7.38721017 e; c1=-1.32906071 e·eV⁻¹ | 0.999886767 | — | 0.000611066492 | 0.00098847619 | [9.21904762e-05, 0.000375404762, -1.83809524e-05, -0.000918952381, -0.000518738095, 0.00098847619] |
| CoLR0 | CoLR0 | BARE | lineal_interior | 1 | 2 | 0 | -1.351575 | c0=7.3867415 e; c1=-1.351575 e·eV⁻¹ | 1 | — | 1.40433339e-15 | 1.77635684e-15 | [1.77635684e-15, 8.8817842e-16] |
| CoLR0 | CoLR0 | SCREENED | principal | 3 | 6 | 2 | -0.117196627 | c0=7.38658607 e; c1=-0.117196627 e·eV⁻¹; c2=-0.000663265305 e·eV⁻²; c3=0.0243055555 e·eV⁻³ | 0.999999994 | 6.57466612 | 3.92676726e-07 | 6.80272104e-07 | [-2.31292525e-07, 6.80272104e-07, -5.4421769e-07, -6.80272132e-08, 2.99319724e-07, -1.36054426e-07] |
| CoLR0 | CoLR0 | SCREENED | lineal_misma_malla | 1 | 6 | 4 | -0.117128571 | c0=7.38658483 e; c1=-0.117128571 e·eV⁻¹ | 0.999999911 | — | 1.51054495e-06 | 2.54761905e-06 | [-2.54761905e-06, 2.02380952e-06, 1.59523809e-06, -2.61904765e-07, -6.90476194e-07, -1.19047621e-07] |
| CoLR0 | CoLR0 | SCREENED | lineal_interior | 1 | 2 | 0 | -0.117175 | c0=7.3865855 e; c1=-0.117175 e·eV⁻¹ | 1 | — | 4.02139883e-15 | 4.4408921e-15 | [4.4408921e-15, 3.55271368e-15] |
| CoLR1 | CoLR0 | BARE | principal | 3 | 6 | 2 | 1.2055129 | c0=7.3865555 e; c1=1.2055129 e·eV⁻¹; c2=-0.0873214286 e·eV⁻²; c3=-9.64236111 e·eV⁻³ | 0.999999991 | 6.57466612 | 4.83128035e-06 | 8.19047619e-06 | [1.88095238e-06, -4.38095238e-06, 1.54761905e-06, 6.30952381e-06, -8.19047619e-06, 2.83333333e-06] |
| CoLR1 | CoLR0 | BARE | lineal_misma_malla | 1 | 6 | 4 | 1.17851429 | c0=7.3863925 e; c1=1.17851429 e·eV⁻¹ | 0.999912249 | — | 0.000476993224 | 0.000611357143 | [0.000313357143, -0.000443928571, -0.000333214286, 0.000597214286, 0.000477928571, -0.000611357143] |
| CoLR1 | CoLR0 | BARE | lineal_interior | 1 | 2 | 0 | 1.201775 | c0=7.3865245 e; c1=1.201775 e·eV⁻¹ | 1 | — | 2.66453526e-15 | 2.66453526e-15 | [2.66453526e-15, 2.66453526e-15] |
| CoLR1 | CoLR0 | SCREENED | principal | 3 | 6 | 2 | 0.034680754 | c0=7.38658536 e; c1=0.034680754 e·eV⁻¹; c2=0.00168367347 e·eV⁻²; c3=-0.0173611111 e·eV⁻³ | 0.999999395 | 6.57466612 | 1.1639911e-06 | 1.93197279e-06 | [6.76870749e-07, -1.93197279e-06, 1.44557823e-06, 4.93197279e-07, -1.17006803e-06, 4.86394557e-07] |
| CoLR1 | CoLR0 | SCREENED | lineal_misma_malla | 1 | 6 | 4 | 0.0346321429 | c0=7.3865885 e; c1=0.0346321429 e·eV⁻¹ | 0.999996879 | — | 2.64350057e-06 | 4.42857143e-06 | [4.42857143e-06, -3.21428571e-06, -1.85714286e-06, -1.14285714e-06, -7.85714287e-07, 2.57142857e-06] |
| CoLR1 | CoLR0 | SCREENED | lineal_interior | 1 | 2 | 0 | 0.03465 | c0=7.386587 e; c1=0.03465 e·eV⁻¹ | 1 | — | 2.26441955e-15 | 2.66453526e-15 | [2.66453526e-15, 1.77635684e-15] |
| CoLR0 | CoLR1 | BARE | principal | 3 | 6 | 2 | 1.2055129 | c0=7.3865915 e; c1=1.2055129 e·eV⁻¹; c2=-0.0882142857 e·eV⁻²; c3=-9.64236111 e·eV⁻³ | 0.99999999 | 6.57466612 | 5.21292655e-06 | 8.76190476e-06 | [2.09523809e-06, -4.95238095e-06, 1.9047619e-06, 6.66666666e-06, -8.76190476e-06, 3.04761904e-06] |
| CoLR0 | CoLR1 | BARE | lineal_misma_malla | 1 | 6 | 4 | 1.17851429 | c0=7.38642683 e; c1=1.17851429 e·eV⁻¹ | 0.999912143 | — | 0.00047728338 | 0.000612690476 | [0.00031202381, -0.000444261905, -0.000331547619, 0.000598880952, 0.000477595238, -0.000612690476] |
| CoLR0 | CoLR1 | BARE | lineal_interior | 1 | 2 | 0 | 1.201775 | c0=7.3865605 e; c1=1.201775 e·eV⁻¹ | 1 | — | 1.77635684e-15 | 1.77635684e-15 | [1.77635684e-15, 1.77635684e-15] |
| CoLR0 | CoLR1 | SCREENED | principal | 3 | 6 | 2 | 0.034715873 | c0=7.38658629 e; c1=0.034715873 e·eV⁻¹; c2=0.000829081633 e·eV⁻²; c3=-0.0381944444 e·eV⁻³ | 0.999999658 | 6.57466612 | 8.74493699e-07 | 1.42176871e-06 | [4.31972785e-07, -1.42176871e-06, 1.39455782e-06, -6.29251702e-07, 1.97278911e-07, 2.72108815e-08] |
| CoLR0 | CoLR1 | SCREENED | lineal_misma_malla | 1 | 6 | 4 | 0.0346089286 | c0=7.38658783 e; c1=0.0346089286 e·eV⁻¹ | 0.999997619 | — | 2.3072522e-06 | 3.70238095e-06 | [3.70238095e-06, -3.47619048e-06, -1.65476191e-06, -1.19047643e-08, 1.80952381e-06, -3.6904762e-07] |
| CoLR0 | CoLR1 | SCREENED | lineal_interior | 1 | 2 | 0 | 0.03465 | c0=7.386587 e; c1=0.03465 e·eV⁻¹ | 1 | — | 2.26441955e-15 | 2.66453526e-15 | [2.66453526e-15, 1.77635684e-15] |
| CoLR1 | CoLR1 | BARE | principal | 3 | 6 | 2 | -1.35521429 | c0=7.38658786 e; c1=-1.35521429 e·eV⁻¹; c2=0.315165816 e·eV⁻²; c3=9.34375 e·eV⁻³ | 0.999999978 | 6.57466612 | 8.61210586e-06 | 1.34489796e-05 | [-4.0612245e-06, 1.03061224e-05, -5.45918368e-06, -9.38775511e-06, 1.34489796e-05, -4.84693878e-06] |
| CoLR1 | CoLR1 | BARE | lineal_misma_malla | 1 | 6 | 4 | -1.32905179 | c0=7.38717617 e; c1=-1.32905179 e·eV⁻¹ | 0.9998865 | — | 0.000611784657 | 0.000989940476 | [9.37261905e-05, 0.000374761905, -1.9202381e-05, -0.000920130952, -0.000519095238, 0.000989940476] |
| CoLR1 | CoLR1 | BARE | lineal_interior | 1 | 2 | 0 | -1.351575 | c0=7.3867065 e; c1=-1.351575 e·eV⁻¹ | 1 | — | 4.02139883e-15 | 4.4408921e-15 | [4.4408921e-15, 3.55271368e-15] |
| CoLR1 | CoLR1 | SCREENED | principal | 3 | 6 | 2 | -0.117223016 | c0=7.38658543 e; c1=-0.117223016 e·eV⁻¹; c2=-0.000140306121 e·eV⁻²; c3=0.0381944444 e·eV⁻³ | 0.99999999 | 6.57466612 | 5.11212156e-07 | 7.82312922e-07 | [-5.442178e-08, 3.19727886e-07, -5.27210887e-07, 7.82312922e-07, -7.27891162e-07, 2.07482988e-07] |
| CoLR1 | CoLR1 | SCREENED | lineal_misma_malla | 1 | 6 | 4 | -0.117116071 | c0=7.38658517 e; c1=-0.117116071 e·eV⁻¹ | 0.999999857 | — | 1.91226202e-06 | 2.52380953e-06 | [-2.13095239e-06, 2.19047618e-06, 1.51190476e-06, -8.45238098e-07, -2.52380953e-06, 1.79761905e-06] |
| CoLR1 | CoLR1 | SCREENED | lineal_interior | 1 | 2 | 0 | -0.117175 | c0=7.3865855 e; c1=-0.117175 e·eV⁻¹ | 1 | — | 4.02139883e-15 | 4.4408921e-15 | [4.4408921e-15, 3.55271368e-15] |

## 5. Matrices de respuesta, inversas y U

Representación seleccionada para inversión: `raw`. Las matrices raw y simetrizadas se conservan como evidencia.

### χ⁰ raw (BARE) (eV⁻¹)

| Sitio observado \ Sitio perturbado | CoLR0 | CoLR1 |
|---|---:|---:|
| CoLR0 | -1.35522321 | 1.2055129 |
| CoLR1 | 1.2055129 | -1.35521429 |

### χ raw (SCREENED) (eV⁻¹)

| Sitio observado \ Sitio perturbado | CoLR0 | CoLR1 |
|---|---:|---:|
| CoLR0 | -0.117196627 | 0.034715873 |
| CoLR1 | 0.034680754 | -0.117223016 |

### χ⁰ simetrizada (eV⁻¹)

| Sitio observado \ Sitio perturbado | CoLR0 | CoLR1 |
|---|---:|---:|
| CoLR0 | -1.35522321 | 1.2055129 |
| CoLR1 | 1.2055129 | -1.35521429 |

### χ simetrizada (eV⁻¹)

| Sitio observado \ Sitio perturbado | CoLR0 | CoLR1 |
|---|---:|---:|
| CoLR0 | -0.117196627 | 0.0346983135 |
| CoLR1 | 0.0346983135 | -0.117223016 |

### χ⁰ usada para inversión (eV⁻¹)

| Sitio observado \ Sitio perturbado | CoLR0 | CoLR1 |
|---|---:|---:|
| CoLR0 | -1.35522321 | 1.2055129 |
| CoLR1 | 1.2055129 | -1.35521429 |

### χ usada para inversión (eV⁻¹)

| Sitio observado \ Sitio perturbado | CoLR0 | CoLR1 |
|---|---:|---:|
| CoLR0 | -0.117196627 | 0.034715873 |
| CoLR1 | 0.034680754 | -0.117223016 |

### (χ⁰)⁻¹ (eV)

| Sitio observado \ Sitio perturbado | CoLR0 | CoLR1 |
|---|---:|---:|
| CoLR0 | -3.53512782 | -3.14462608 |
| CoLR1 | -3.14462608 | -3.53515111 |

### χ⁻¹ (eV)

| Sitio observado \ Sitio perturbado | CoLR0 | CoLR1 |
|---|---:|---:|
| CoLR0 | -9.35227633 | -2.76969872 |
| CoLR1 | -2.76689686 | -9.35017097 |

### U_matrix (eV)

| Sitio observado \ Sitio perturbado | CoLR0 | CoLR1 |
|---|---:|---:|
| CoLR0 | 5.8171485 | -0.374927355 |
| CoLR1 | -0.377729219 | 5.81501986 |

### Diagnóstico de inversión: ajuste principal

| Matriz | Método | Residuo izquierdo Frobenius | Residuo derecho Frobenius |
|---|---|---:|---:|
| χ⁰ | direct_inv | 5.57980222e-16 | 4.80333478e-16 |
| χ | direct_inv | 2.69166322e-16 | 2.5382528e-16 |

**Condición de χ⁰:** rango 2/2; determinante 0.383356516; número de condición 17.105087; estado `FULL_RANK`.

**Condición de χ:** rango 2/2; determinante 0.0125341694; número de condición 1.84105399; estado `FULL_RANK`.

## 6. Sensibilidad, diagnósticos y estado

| Análisis | Ventana máxima α (eV) | Método | Tipo de ventana | Estado de matriz | U por sitio (eV) | Cota de impresión (eV) |
|---|---:|---|---|---|---|---:|
| Principal | — | polynomial | — | FULL_RANK | CoLR0: 5.8171485; CoLR1: 5.81501986 | 0.0111780307 |
| Lineal misma malla | — | linear | — | FULL_RANK | CoLR0: 5.83430618; CoLR1: 5.83528101 | 0.00409471901 |
| Ventana | 0.02 | linear | resolution_limited_two_point_central_difference | FULL_RANK | CoLR0: 5.81843045; CoLR1: 5.81843045 | 0.00957509382 |
| Ventana | 0.04 | linear | eligible_linear_fit_window | FULL_RANK | CoLR0: 5.82567208; CoLR1: 5.82484753 | 0.00574033975 |
| Ventana | 0.06 | linear | eligible_linear_fit_window | FULL_RANK | CoLR0: 5.83430618; CoLR1: 5.83528101 | 0.00409471901 |

- Diferencia máxima de U entre modelos/ventanas informada: 0.0202611543 eV.
- Evaluación frente al umbral: `MEASURED_EXCEEDS_TOLERANCE`; métricas requeridas completas: true.
- Umbral configurado para sensibilidad: 0.02 eV.
- Precisión numérica total: `NOT_ASSESSED_TOTAL_PRECISION_COMPONENT_UNAVAILABLE`; tolerancia predeclarada de U: 0.02 eV.
- Intervalo total de U por sitio: `NOT_ESTABLISHED_EMPIRICAL_REPLICAS_ARE_NOT_A_TOTAL_ERROR_BOUND`; causa: `observed response-grid repeatability is conditional and does not bound mathematical or physical error`.
- Redondeo determinista solamente: 0.0111780307 eV; comparación aislada con la tolerancia: `WITHIN_TOLERANCE_ALONE`. Este resultado de redondeo por sí solo no acepta precisión total ni física.
- Calibración de repetibilidad de malla: `NOT_PROVIDED`; motivo: `response_grid_calibration_not_configured`.
- Envolvente condicional por coordenada: `NOT_AVAILABLE`; alcance: `sin calibración completa de la malla`.
- Intervalo condicional por sitio (no total ni garantía): `—`.
- Comparación de reproducibilidad numérica con tolerancia predeclarada: `NOT_ASSESSED_TOTAL_PRECISION_COMPONENT_UNAVAILABLE`. Sólo se interpreta bajo el protocolo de réplicas declarado; no es aceptación física.
- Sensibilidad de estimador/ventana, redondeo determinista y variación observada entre réplicas son evidencias distintas; se informan por separado y no se presentan como cota matemática total.
- La falta de una envolvente completa significa que la reproducibilidad condicionada no está demostrada; no invalida el valor U calculado ni elimina los diagnósticos de estabilidad que se muestran arriba.
- Fuente de ocupación ajustada: `siesta_occupations_total`.
- Cota determinista de redondeo de la fuente de ocupación impresa: 0.0111780307 eV; causa: deterministic bound propagated from siesta_occupations_total print intervals. No es un intervalo estadístico ni incluye ruido SCF.
- Validación SCF: true.
- Continuidad de estado: true.

Causas y advertencias registradas:
- `estimator_or_window_sensitivity_exceeds_policy`

## 7. Procedencia y archivos fuente

| Tipo | SHA-256 registrados |
|---|---|
| bare_fdf_sha256 | 090e004b4cff7bba142aa2c432b3989a43405a7dc10d4b0158d84846f9d4d136, 1b0fa5f982c2b45188bd7f83c1f2c6ecdbf1fbfc9cf0248d993dfe2d7046ddfb, 45c3b97ccd2c714850afa7f1f769b854a04e281817bfb9e74c00cd9e209f6452, 47f7246252d57b43a4c5d57271f06ae4ee3f9c967b7dc86364eecc26d95b75a5, 4f4d098c31038601265386e0edc22d998a20500e28eb027b33efed31df9f5900, 6b2897f148ceaaafce5c08c5c0142c831062f458c86bdb56be6112ab153edb84, 78dd274cee87a4b55eaf631bae59ecf39020073424924499d9e352b2b1cc506e, 8c5abd9a705d865651d5c807b95ee9fc5e597b8f3df13dc5c06b9ab3ce57d0c7, 96c17e2d17b158797d45f1a6d1fa0c5d59785a3e76637425b9b4f5832996a60b, a64464b51c34292e67791a9e9ef77aa0b5ce12ca9dcc7d0046d6db60bd68d4ca, c4f25f68bd7ea6eb7a51666fbcbb8d02dbc408a5103724ed73504fe15361bf60, d2a5412ce7e13d1f206197440093b547e2069d5dac4a70aa0ec842777b882078 |
| bare_out_sha256 | 00cfb8ce0d219c4c9eafeaf61cad5fc9bf6bb903b16670203a31fe75c3edeec7, 0f39ec681db8988ad1b5ff396ae2fd6de71888f674dd7a1ae8a62bfc5f7ffe80, 1694d1ce9c22640535b8f1ac4e94750bc77aa528e92a972dcdf14c1ce88a6abe, 62c4a19a77e0497143871b8885d96d139cd2d9975272651082ef8c4de4685852, 64422037b24cd90168483112ef9bec77490eda85317e97d543285931fa8eed38, af69155b4d327a2c1d3e37bfe3042ed1f5bc41868337853ffc1ae9d2e1823fb9, c0688606c66297eba026cc1ebb87ddbaea2b9fed47d7ffc5594a21b4fd530481, c231def557bfaa7051f84e845d000bcd073ce247519f407fbecb0e426c4b7c43, c2f2ea9115e5646a789f649d8d86c3b75139c917f0c0948be186c3ed70fd0fbf, d2309c75ced0e18b0bac739c4eca3f5c3ed767941be27b8ff7ff6cfc586c5845, dc54a502fbdfe7e8d1f252eecf27e8843b90d9d59df8012b7d57ca39ffb6170c, f8655b4f1a9289a19e7b9b30af8d9bdfe869f253129dae1f28f694706c644314 |
| parent_dm_sha256 | b2ef2259125759f04e1fc77abce2440acdf46bea34a09a9481e4fe383b8a19a2 |
| projector_fingerprints | 5d27ed796b49025332f4f3c0f77fbff0f5b3e2841b4659df40106ad567390b34, 8e15e6c87adf7f76291516e77877b2e1bbd72da106c8e1ed1a1476783faf0fba |
| screened_fdf_sha256 | 1baa8b088409695f89e9a443805b603d2147b1b25fbd00a81ad7ffff9df4007a, 1e783b843ffe05c5786f1abd174a9d730e1db5b111c08301ee227a74009d25c7, 20ec259959907027327b38b39accab2ed66fdc874d8cb604641b5497da88cbcf, 49c1a14efe67204850f9cf150f3f559e6bc6aec32a8c445e6644623460dd2e22, 4c2a8caba70bc4b66412f856c037b431b6f237c695151e4dda4bf55b8a82fd5f, 5065142a4e65746d9c8017e0da5784d9206fbbb28daedb6b26f4cf90942de47c, 73f3d001cc06ef770b3da21af58bfde3fc2b76f7e361ad35434b70bf07e9363b, 91e98ad29d00110ad3deb51f160d980cec7764400f1c1d663ceb0cfeabeee895, a09ba7ba5ca8a5c4817c645e66f186d1cdcd6cfe0480950e76f349e0ad7cdd64, bf0c6a92ed3d7fad0f6e23d1185e3dd90c1756ae6069a7d5359d0265dccc1f49, cdd0ca93798db797380645bcd7d1ec90325ba2a400726068649eb179a03c63f7, f3218e7f1ae5383f1845ba11381f6c1d06403717e84446bc27583d5f1652598c |
| screened_out_sha256 | 04204b8d1c3990da0f488652eb781a4314a7975bcee6d2379fdd927d1b6ef1ff, 358bd49d0ac5583d704126bbac25ebe774284e0af6f25b6472e6ef2e1cb39171, 366c6e70580b88ba49522bbe7db084cb5df2727f7f3d22c9728ca386c6bb50bb, 4406c0933d36ed5eaccf94dda99c9687787bceb56f7acc222a2b85de07360bb4, 5195fd31d33b8d608bbec8ef42137e5c212a051629ad8c33d8d3bd8d8240c330, 63bc1efa24abe7c5a1819351bda012d47d1c10a20ae012cc38648fd8d953c206, 6dc83abf5475c57d6a58f84df45af7af61f627b6b2b60e1e818ffed4afcf4888, 8b045bc21bc6276616ecd499fe9dcb9314787838673a3a5b12cded567fdc9f5b, c2ac1a4e883c8aac0fdeacee63cab8a8a2bfb88f2a61afb20f9e1ba59d80e6a7, c512a4380a3d37f4b1e8a783dc4a23d77ce0abe1d786aedb1a35721fcbc4b1ee, db677c3a7b276d2cea45c9a3f902063c1b244b851872bb90d733bc976aa8cb14, eb55a51610efb63a92b36be3bb0ad92ef12553b8f02a53444fddfd9151094c2c |

### Entradas declaradas de la campaña

| Archivo | Ruta | SHA-256 |
|---|---|---|
| campaign_contract | backend_contract.json | c1ba3e7b62b292ef4485567fafae15ab19e3a6f2538bd65c4241cce1cf4f390e |
| execution_profile | execution_profile.json | 04ce20cc11656f378df2e090ee4d4ad2a45b553bc1681d6b1c79267a4b94f5dc |
| lr_config | lr_config.json | cd87813965940042544339f8a8909a95da26c46992c37f5dfe99ff043bdf6e1e |
| reference_fdf | reference.fdf | 591ca6e794bffb2427a4dc99c058217dc31d7c76f45018f434dec5541fbad66f |

### Pseudopotenciales declarados

| Especie | Archivo | SHA-256 |
|---|---|---|
| CoLR0 | pseudopotentials/CoLR0.psml | 72c9cf0cea3652fe1f5da5bf59fbe321253c540d09548937468acd72d899f44f |
| CoLR1 | pseudopotentials/CoLR1.psml | 72c9cf0cea3652fe1f5da5bf59fbe321253c540d09548937468acd72d899f44f |
| O | pseudopotentials/O.psml | 5ca5d753a995bd054279007ba76be71d622b60460c6f9a0d9bb37d81bdf185fe |

### Ejecutable y versión de SIESTA

| Ejecutable declarado | Ruta ejecutable | Versión admitida | Archivo de versión | SHA-256 del archivo de versión |
|---|---|---|---|---|
| siesta | /home/jmc/.local/siesta-5.4.2-openmpi/bin/siesta | 5.4.2 | software/siesta_version.txt | bb5a9b03dfaec9953401a7ef8db045149461047c44f15f9c5bf7758900b5f3ee |

### Archivos de cada respuesta validada

| α perturbado | Sitio perturbado | Modo | Nodo | FDF | .out | SHA-256 FDF / .out | Digest de evidencia del recibo |
|---:|---|---|---|---|---|---|---|
| — | Referencia | REFERENCE_SCREENED | reference | .siestaflow/attempts/52367a6622b19f08825e/attempt-1790837629460540661-fee5f431/reference_52367a6622b1/siesta.fdf | .siestaflow/attempts/52367a6622b19f08825e/attempt-1790837629460540661-fee5f431/reference_52367a6622b1/siesta.out | 591ca6e794bffb2427a4dc99c058217dc31d7c76f45018f434dec5541fbad66f / 7dc1873818b7a41a1a722bfdf648f81e1b758dbfd6b1d8bf66ee87540fd34848 | 20ed17b73f98e007bcd3cd15808673f2f5b36fde7754ec28b70dbbd9287cb9c9 |
| -0.06 | CoLR0 | BARE | response:lr_s000_m0p06_bare | .siestaflow/attempts/a9b894b5b55ba9409a6b/attempt-1790837683194378931-50688dff/response_lr_s000_m0p06_bare_a9b894b5b55b/siesta.fdf | .siestaflow/attempts/a9b894b5b55ba9409a6b/attempt-1790837683194378931-50688dff/response_lr_s000_m0p06_bare_a9b894b5b55b/siesta.out | 45c3b97ccd2c714850afa7f1f769b854a04e281817bfb9e74c00cd9e209f6452 / d2309c75ced0e18b0bac739c4eca3f5c3ed767941be27b8ff7ff6cfc586c5845 | 473f86825f37e7fc22caab3be6a69708571d5e5916fe71ad17ff005c2352878d |
| -0.06 | CoLR0 | SCREENED | response:lr_s000_m0p06_screened | .siestaflow/attempts/365d9074957c7d4a53a6/attempt-1790837688565097833-9dd3ca2e/response_lr_s000_m0p06_screened_365d9074957c/siesta.fdf | .siestaflow/attempts/365d9074957c7d4a53a6/attempt-1790837688565097833-9dd3ca2e/response_lr_s000_m0p06_screened_365d9074957c/siesta.out | a09ba7ba5ca8a5c4817c645e66f186d1cdcd6cfe0480950e76f349e0ad7cdd64 / c2ac1a4e883c8aac0fdeacee63cab8a8a2bfb88f2a61afb20f9e1ba59d80e6a7 | a41c75289cb79b32dac6cc38dcbd245f80fd6f63ceea48d38df4de03aae404aa |
| -0.04 | CoLR0 | BARE | response:lr_s000_m0p04_bare | .siestaflow/attempts/91a02247ffc2e934feaa/attempt-1790837721133463503-d4a6ba78/response_lr_s000_m0p04_bare_91a02247ffc2/siesta.fdf | .siestaflow/attempts/91a02247ffc2e934feaa/attempt-1790837721133463503-d4a6ba78/response_lr_s000_m0p04_bare_91a02247ffc2/siesta.out | a64464b51c34292e67791a9e9ef77aa0b5ce12ca9dcc7d0046d6db60bd68d4ca / 1694d1ce9c22640535b8f1ac4e94750bc77aa528e92a972dcdf14c1ce88a6abe | e40e1674ccfe15fd9a067ac844247b14023568be6728e198ab343599f77316b5 |
| -0.04 | CoLR0 | SCREENED | response:lr_s000_m0p04_screened | .siestaflow/attempts/9c0863b8a961ad7b6d5b/attempt-1790837728797369324-519f4582/response_lr_s000_m0p04_screened_9c0863b8a961/siesta.fdf | .siestaflow/attempts/9c0863b8a961ad7b6d5b/attempt-1790837728797369324-519f4582/response_lr_s000_m0p04_screened_9c0863b8a961/siesta.out | 91e98ad29d00110ad3deb51f160d980cec7764400f1c1d663ceb0cfeabeee895 / 6dc83abf5475c57d6a58f84df45af7af61f627b6b2b60e1e818ffed4afcf4888 | d0d37f899ab36c6a864e6d584ac56ed7e9ec3b4f048cd2ebd3666a67d7f5dd6b |
| -0.02 | CoLR0 | BARE | response:lr_s000_m0p02_bare | .siestaflow/attempts/8119c375c5841b7b956a/attempt-1790837768605013427-92a8253b/response_lr_s000_m0p02_bare_8119c375c584/siesta.fdf | .siestaflow/attempts/8119c375c5841b7b956a/attempt-1790837768605013427-92a8253b/response_lr_s000_m0p02_bare_8119c375c584/siesta.out | d2a5412ce7e13d1f206197440093b547e2069d5dac4a70aa0ec842777b882078 / 00cfb8ce0d219c4c9eafeaf61cad5fc9bf6bb903b16670203a31fe75c3edeec7 | efa03061c2f70c5f27bc5733aa1ff47e8553f4619e23ded5a85ddebf81d15e7f |
| -0.02 | CoLR0 | SCREENED | response:lr_s000_m0p02_screened | .siestaflow/attempts/4f60f687d724e53d32ff/attempt-1790837774491588097-53d96dc7/response_lr_s000_m0p02_screened_4f60f687d724/siesta.fdf | .siestaflow/attempts/4f60f687d724e53d32ff/attempt-1790837774491588097-53d96dc7/response_lr_s000_m0p02_screened_4f60f687d724/siesta.out | 5065142a4e65746d9c8017e0da5784d9206fbbb28daedb6b26f4cf90942de47c / 8b045bc21bc6276616ecd499fe9dcb9314787838673a3a5b12cded567fdc9f5b | 1418f5c67887f70c31ded26b6a500907670eeb37cb8374551d3921f447628b7f |
| 0.02 | CoLR0 | BARE | response:lr_s000_p0p02_bare | .siestaflow/attempts/8e7e82caf7897a723870/attempt-1790837801302545858-20bb48d3/response_lr_s000_p0p02_bare_8e7e82caf789/siesta.fdf | .siestaflow/attempts/8e7e82caf7897a723870/attempt-1790837801302545858-20bb48d3/response_lr_s000_p0p02_bare_8e7e82caf789/siesta.out | 1b0fa5f982c2b45188bd7f83c1f2c6ecdbf1fbfc9cf0248d993dfe2d7046ddfb / 0f39ec681db8988ad1b5ff396ae2fd6de71888f674dd7a1ae8a62bfc5f7ffe80 | 6b0faba85c602e02cf2832e678bd87bd3110046c98c12fff9ba6f4e3aa8b9e2e |
| 0.02 | CoLR0 | SCREENED | response:lr_s000_p0p02_screened | .siestaflow/attempts/bce88b1318147f2362e2/attempt-1790837806780016958-00f59b8b/response_lr_s000_p0p02_screened_bce88b131814/siesta.fdf | .siestaflow/attempts/bce88b1318147f2362e2/attempt-1790837806780016958-00f59b8b/response_lr_s000_p0p02_screened_bce88b131814/siesta.out | bf0c6a92ed3d7fad0f6e23d1185e3dd90c1756ae6069a7d5359d0265dccc1f49 / 4406c0933d36ed5eaccf94dda99c9687787bceb56f7acc222a2b85de07360bb4 | ae9abf496dd6b60ae01a3d2161ae7bf6f27844954a5b3ef2d390774820db15e4 |
| 0.04 | CoLR0 | BARE | response:lr_s000_p0p04_bare | .siestaflow/attempts/ba8edcc7ec7dc5665b5b/attempt-1790837837272739336-f2793a2b/response_lr_s000_p0p04_bare_ba8edcc7ec7d/siesta.fdf | .siestaflow/attempts/ba8edcc7ec7dc5665b5b/attempt-1790837837272739336-f2793a2b/response_lr_s000_p0p04_bare_ba8edcc7ec7d/siesta.out | 090e004b4cff7bba142aa2c432b3989a43405a7dc10d4b0158d84846f9d4d136 / c231def557bfaa7051f84e845d000bcd073ce247519f407fbecb0e426c4b7c43 | 4064f04076bc6b10eca514e4eda14258e7f2193fc2fa1cfa111a71f4d1bab5cc |
| 0.04 | CoLR0 | SCREENED | response:lr_s000_p0p04_screened | .siestaflow/attempts/ff40fe49cff9b19265a2/attempt-1790837842900245636-c579c549/response_lr_s000_p0p04_screened_ff40fe49cff9/siesta.fdf | .siestaflow/attempts/ff40fe49cff9b19265a2/attempt-1790837842900245636-c579c549/response_lr_s000_p0p04_screened_ff40fe49cff9/siesta.out | 1e783b843ffe05c5786f1abd174a9d730e1db5b111c08301ee227a74009d25c7 / 63bc1efa24abe7c5a1819351bda012d47d1c10a20ae012cc38648fd8d953c206 | 756ba7ded4a25318c36bc93a511379a534a6cfbf5d7017ddfa3b51dc3735a62d |
| 0.06 | CoLR0 | BARE | response:lr_s000_p0p06_bare | .siestaflow/attempts/d839ffe229398f9de504/attempt-1790837878253142122-8ece4140/response_lr_s000_p0p06_bare_d839ffe22939/siesta.fdf | .siestaflow/attempts/d839ffe229398f9de504/attempt-1790837878253142122-8ece4140/response_lr_s000_p0p06_bare_d839ffe22939/siesta.out | 8c5abd9a705d865651d5c807b95ee9fc5e597b8f3df13dc5c06b9ab3ce57d0c7 / c0688606c66297eba026cc1ebb87ddbaea2b9fed47d7ffc5594a21b4fd530481 | 40e277cbcc432f15ef098600f0f5c9a3e32a398937dc16269a5da06b1308c95e |
| 0.06 | CoLR0 | SCREENED | response:lr_s000_p0p06_screened | .siestaflow/attempts/3fe519aeb5e10966f238/attempt-1790837885091738506-17a00d95/response_lr_s000_p0p06_screened_3fe519aeb5e1/siesta.fdf | .siestaflow/attempts/3fe519aeb5e10966f238/attempt-1790837885091738506-17a00d95/response_lr_s000_p0p06_screened_3fe519aeb5e1/siesta.out | f3218e7f1ae5383f1845ba11381f6c1d06403717e84446bc27583d5f1652598c / eb55a51610efb63a92b36be3bb0ad92ef12553b8f02a53444fddfd9151094c2c | 9a635943872f8ea6692e76c3df837a4a2734dc8848830ddb0d63f07df61cac27 |
| -0.06 | CoLR1 | BARE | response:lr_s001_m0p06_bare | .siestaflow/attempts/8a7d4f4a323274cedc2a/attempt-1790837929701286802-10a4e248/response_lr_s001_m0p06_bare_8a7d4f4a3232/siesta.fdf | .siestaflow/attempts/8a7d4f4a323274cedc2a/attempt-1790837929701286802-10a4e248/response_lr_s001_m0p06_bare_8a7d4f4a3232/siesta.out | 6b2897f148ceaaafce5c08c5c0142c831062f458c86bdb56be6112ab153edb84 / f8655b4f1a9289a19e7b9b30af8d9bdfe869f253129dae1f28f694706c644314 | b867ed3be36c037a94e03147a44f5aa7c8d7f2291db834bf934d1d47bea1c485 |
| -0.06 | CoLR1 | SCREENED | response:lr_s001_m0p06_screened | .siestaflow/attempts/cd98d0ad2b097309a007/attempt-1790837937983585769-d8fa7cc9/response_lr_s001_m0p06_screened_cd98d0ad2b09/siesta.fdf | .siestaflow/attempts/cd98d0ad2b097309a007/attempt-1790837937983585769-d8fa7cc9/response_lr_s001_m0p06_screened_cd98d0ad2b09/siesta.out | 1baa8b088409695f89e9a443805b603d2147b1b25fbd00a81ad7ffff9df4007a / 5195fd31d33b8d608bbec8ef42137e5c212a051629ad8c33d8d3bd8d8240c330 | c5db043edf2f1ab33b467235c7f82d02739986981f829f275e0e6cfbccb83086 |
| -0.04 | CoLR1 | BARE | response:lr_s001_m0p04_bare | .siestaflow/attempts/f920cfb21087d4d86fc4/attempt-1790837974673524665-c361e2d1/response_lr_s001_m0p04_bare_f920cfb21087/siesta.fdf | .siestaflow/attempts/f920cfb21087d4d86fc4/attempt-1790837974673524665-c361e2d1/response_lr_s001_m0p04_bare_f920cfb21087/siesta.out | c4f25f68bd7ea6eb7a51666fbcbb8d02dbc408a5103724ed73504fe15361bf60 / af69155b4d327a2c1d3e37bfe3042ed1f5bc41868337853ffc1ae9d2e1823fb9 | 84d6eb8dc54a393ddda8bae7c99d3c65c8d5d590c1bab78140d002d2c898aa16 |
| -0.04 | CoLR1 | SCREENED | response:lr_s001_m0p04_screened | .siestaflow/attempts/d1b788ec0f0198f1157a/attempt-1790837980693398296-9712cdc4/response_lr_s001_m0p04_screened_d1b788ec0f01/siesta.fdf | .siestaflow/attempts/d1b788ec0f0198f1157a/attempt-1790837980693398296-9712cdc4/response_lr_s001_m0p04_screened_d1b788ec0f01/siesta.out | 20ec259959907027327b38b39accab2ed66fdc874d8cb604641b5497da88cbcf / 366c6e70580b88ba49522bbe7db084cb5df2727f7f3d22c9728ca386c6bb50bb | 19401d498b23223d48d5cfa9ecbc2d33870295dc9c74dbb29663779b04a06669 |
| -0.02 | CoLR1 | BARE | response:lr_s001_m0p02_bare | .siestaflow/attempts/d40fa0516e62855bdc5a/attempt-1790838022844725824-5799fc43/response_lr_s001_m0p02_bare_d40fa0516e62/siesta.fdf | .siestaflow/attempts/d40fa0516e62855bdc5a/attempt-1790838022844725824-5799fc43/response_lr_s001_m0p02_bare_d40fa0516e62/siesta.out | 78dd274cee87a4b55eaf631bae59ecf39020073424924499d9e352b2b1cc506e / dc54a502fbdfe7e8d1f252eecf27e8843b90d9d59df8012b7d57ca39ffb6170c | 5e3b450569631120ef93ca64d240076b1406cab14e6249a6fdfe69ca2e924477 |
| -0.02 | CoLR1 | SCREENED | response:lr_s001_m0p02_screened | .siestaflow/attempts/8a60c8950b2acc786cdb/attempt-1790838028924764341-04fa270a/response_lr_s001_m0p02_screened_8a60c8950b2a/siesta.fdf | .siestaflow/attempts/8a60c8950b2acc786cdb/attempt-1790838028924764341-04fa270a/response_lr_s001_m0p02_screened_8a60c8950b2a/siesta.out | cdd0ca93798db797380645bcd7d1ec90325ba2a400726068649eb179a03c63f7 / 358bd49d0ac5583d704126bbac25ebe774284e0af6f25b6472e6ef2e1cb39171 | a46e9facd0f657d2682912b4bb61323b820d9a100484c434a0c8ff2b37774c3f |
| 0.02 | CoLR1 | BARE | response:lr_s001_p0p02_bare | .siestaflow/attempts/dc07ce4a6f186716bf4f/attempt-1790838061153958723-0174ae13/response_lr_s001_p0p02_bare_dc07ce4a6f18/siesta.fdf | .siestaflow/attempts/dc07ce4a6f186716bf4f/attempt-1790838061153958723-0174ae13/response_lr_s001_p0p02_bare_dc07ce4a6f18/siesta.out | 96c17e2d17b158797d45f1a6d1fa0c5d59785a3e76637425b9b4f5832996a60b / 62c4a19a77e0497143871b8885d96d139cd2d9975272651082ef8c4de4685852 | 93797633a5177a57a022d54613904e35c1a05d91e93b2f46e94b68149c244c0a |
| 0.02 | CoLR1 | SCREENED | response:lr_s001_p0p02_screened | .siestaflow/attempts/5844c04f7ade2a15396c/attempt-1790838069411648657-6287aadd/response_lr_s001_p0p02_screened_5844c04f7ade/siesta.fdf | .siestaflow/attempts/5844c04f7ade2a15396c/attempt-1790838069411648657-6287aadd/response_lr_s001_p0p02_screened_5844c04f7ade/siesta.out | 49c1a14efe67204850f9cf150f3f559e6bc6aec32a8c445e6644623460dd2e22 / 04204b8d1c3990da0f488652eb781a4314a7975bcee6d2379fdd927d1b6ef1ff | 43cb2d3a3f0f062caaffe91611555988c1aa8299124f1cb4d8c5ec27c792e075 |
| 0.04 | CoLR1 | BARE | response:lr_s001_p0p04_bare | .siestaflow/attempts/16b7f66f8f4a159ce519/attempt-1790838107023755169-9288de3a/response_lr_s001_p0p04_bare_16b7f66f8f4a/siesta.fdf | .siestaflow/attempts/16b7f66f8f4a159ce519/attempt-1790838107023755169-9288de3a/response_lr_s001_p0p04_bare_16b7f66f8f4a/siesta.out | 4f4d098c31038601265386e0edc22d998a20500e28eb027b33efed31df9f5900 / 64422037b24cd90168483112ef9bec77490eda85317e97d543285931fa8eed38 | ae4cbb5283c3568b8deebdf3baccf52e05b23e0c6c344ece6c9486f1ac3bc689 |
| 0.04 | CoLR1 | SCREENED | response:lr_s001_p0p04_screened | .siestaflow/attempts/4b49380df8041040dffa/attempt-1790838113590437053-d43b27ff/response_lr_s001_p0p04_screened_4b49380df804/siesta.fdf | .siestaflow/attempts/4b49380df8041040dffa/attempt-1790838113590437053-d43b27ff/response_lr_s001_p0p04_screened_4b49380df804/siesta.out | 73f3d001cc06ef770b3da21af58bfde3fc2b76f7e361ad35434b70bf07e9363b / db677c3a7b276d2cea45c9a3f902063c1b244b851872bb90d733bc976aa8cb14 | 4a6fd6d29cff65a9b2e5a439c5aeeb24fe01ea841371b2374aa2a4fdf3e03140 |
| 0.06 | CoLR1 | BARE | response:lr_s001_p0p06_bare | .siestaflow/attempts/db6326ee96bee0a6337f/attempt-1790838148516245712-f9cc66b5/response_lr_s001_p0p06_bare_db6326ee96be/siesta.fdf | .siestaflow/attempts/db6326ee96bee0a6337f/attempt-1790838148516245712-f9cc66b5/response_lr_s001_p0p06_bare_db6326ee96be/siesta.out | 47f7246252d57b43a4c5d57271f06ae4ee3f9c967b7dc86364eecc26d95b75a5 / c2f2ea9115e5646a789f649d8d86c3b75139c917f0c0948be186c3ed70fd0fbf | ea33cb99add6fb8c090236917d3760b716523ec637fa4d4799df1bd1bdf8bdbb |
| 0.06 | CoLR1 | SCREENED | response:lr_s001_p0p06_screened | .siestaflow/attempts/0f345e8a7aa02280696e/attempt-1790838154138666874-b962ad07/response_lr_s001_p0p06_screened_0f345e8a7aa0/siesta.fdf | .siestaflow/attempts/0f345e8a7aa02280696e/attempt-1790838154138666874-b962ad07/response_lr_s001_p0p06_screened_0f345e8a7aa0/siesta.out | 4c2a8caba70bc4b66412f856c037b431b6f237c695151e4dda4bf55b8a82fd5f / c512a4380a3d37f4b1e8a783dc4a23d77ce0abe1d786aedb1a35721fcbc4b1ee | 9f10a6a7123a84b26a95d10b622eb9dc87461838d7d91dee59e4029666e6663b |

La sensibilidad entre estimadores y ventanas es un diagnóstico y no un intervalo de confianza. La cota determinista de redondeo se calcula desde los tokens del total `Occupations:` impreso; si faltan esos tokens, queda como no disponible.
