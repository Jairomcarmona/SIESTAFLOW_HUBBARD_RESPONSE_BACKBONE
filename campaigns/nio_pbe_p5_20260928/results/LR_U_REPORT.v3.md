# Informe de respuesta lineal de Hubbard

- **Campaña:** 73a0a508-93df-41e2-b1bd-993c3dc7d94a
- **Material:** NiO-AFMII-PBE-adaptive-20260928
- **Funcional:** PBE
- **Versión SIESTA:** 5.4.2
- **Analizador:** siestaflow_hubbard 0.1.2 — siestaflow.lr_u_analysis.v3
- **Cantidad calculada:** `U_scalar_charge` (eV)
- **Estado numérico:** **NUMERICAL_CANDIDATE_UNASSESSED**
- **Aceptación física:** **NOT_ESTABLISHED**
- **Estimador principal:** polynomial, grado 3
- **Malla α (eV):** `-0.06, -0.04, -0.02, 0.02, 0.04, 0.06`
- **Acción DAG registrada:** `RECORDED_ONLY`

El resultado corresponde a `U_scalar_charge` de la respuesta de carga declarada. No se convierte automáticamente en `Ueff_Dudarev` ni implica aceptación física.

## 1. Resumen de U por sitio

| Cantidad | Sitio | Valor (eV) | Método | Sensibilidad al modelo (eV) | Sensibilidad a ventana (eV) | Estado numérico | Acción DAG |
|---|---|---:|---|---:|---:|---|---|
| U_scalar_charge | NiLR0 | 6.8642677 | polynomial | 0.00247086598 | 0.00137353857 | NUMERICAL_CANDIDATE_UNASSESSED | RECORDED_ONLY |
| U_scalar_charge | NiLR1 | 6.86438748 | polynomial | 0.00273761882 | 0.00152051625 | NUMERICAL_CANDIDATE_UNASSESSED | RECORDED_ONLY |

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
| NiLR0 | -0.06 | NiLR0 | 8.439208 | 8.451157 | 8.44409 | 5e-07 / 5e-07 / 5e-07 |
| NiLR0 | -0.06 | NiLR1 | 8.439208 | 8.435974 | 8.439153 | 5e-07 / 5e-07 / 5e-07 |
| NiLR0 | -0.04 | NiLR0 | 8.439208 | 8.447161 | 8.44246 | 5e-07 / 5e-07 / 5e-07 |
| NiLR0 | -0.04 | NiLR1 | 8.439208 | 8.437051 | 8.439172 | 5e-07 / 5e-07 / 5e-07 |
| NiLR0 | -0.02 | NiLR0 | 8.439208 | 8.443177 | 8.440834 | 5e-07 / 5e-07 / 5e-07 |
| NiLR0 | -0.02 | NiLR1 | 8.439208 | 8.438128 | 8.43919 | 5e-07 / 5e-07 / 5e-07 |
| NiLR0 | 0.02 | NiLR0 | 8.439208 | 8.435243 | 8.437583 | 5e-07 / 5e-07 / 5e-07 |
| NiLR0 | 0.02 | NiLR1 | 8.439208 | 8.440281 | 8.439226 | 5e-07 / 5e-07 / 5e-07 |
| NiLR0 | 0.04 | NiLR0 | 8.439208 | 8.431293 | 8.435958 | 5e-07 / 5e-07 / 5e-07 |
| NiLR0 | 0.04 | NiLR1 | 8.439208 | 8.441357 | 8.439245 | 5e-07 / 5e-07 / 5e-07 |
| NiLR0 | 0.06 | NiLR0 | 8.439208 | 8.427353 | 8.434335 | 5e-07 / 5e-07 / 5e-07 |
| NiLR0 | 0.06 | NiLR1 | 8.439208 | 8.442434 | 8.439263 | 5e-07 / 5e-07 / 5e-07 |
| NiLR1 | -0.06 | NiLR0 | 8.439208 | 8.435975 | 8.439153 | 5e-07 / 5e-07 / 5e-07 |
| NiLR1 | -0.06 | NiLR1 | 8.439208 | 8.451156 | 8.44409 | 5e-07 / 5e-07 / 5e-07 |
| NiLR1 | -0.04 | NiLR0 | 8.439208 | 8.437052 | 8.439172 | 5e-07 / 5e-07 / 5e-07 |
| NiLR1 | -0.04 | NiLR1 | 8.439208 | 8.447161 | 8.44246 | 5e-07 / 5e-07 / 5e-07 |
| NiLR1 | -0.02 | NiLR0 | 8.439208 | 8.438128 | 8.43919 | 5e-07 / 5e-07 / 5e-07 |
| NiLR1 | -0.02 | NiLR1 | 8.439208 | 8.443177 | 8.440834 | 5e-07 / 5e-07 / 5e-07 |
| NiLR1 | 0.02 | NiLR0 | 8.439208 | 8.440281 | 8.439226 | 5e-07 / 5e-07 / 5e-07 |
| NiLR1 | 0.02 | NiLR1 | 8.439208 | 8.435243 | 8.437583 | 5e-07 / 5e-07 / 5e-07 |
| NiLR1 | 0.04 | NiLR0 | 8.439208 | 8.441357 | 8.439245 | 5e-07 / 5e-07 / 5e-07 |
| NiLR1 | 0.04 | NiLR1 | 8.439208 | 8.431293 | 8.435958 | 5e-07 / 5e-07 / 5e-07 |
| NiLR1 | 0.06 | NiLR0 | 8.439208 | 8.442434 | 8.439263 | 5e-07 / 5e-07 / 5e-07 |
| NiLR1 | 0.06 | NiLR1 | 8.439208 | 8.427353 | 8.434335 | 5e-07 / 5e-07 / 5e-07 |

## 4. Ajustes elemento por elemento

Cada fila corresponde a (sitio observado `I`, sitio perturbado `J`, modo). La pendiente del ajuste principal forma el elemento χ⁰_IJ (BARE) o χ_IJ (SCREENED). Los residuos son `n calculada − n ajustada` en el orden de α indicado por el análisis.

| Sitio observado I | Sitio perturbado J | Modo | Ajuste | Grado | Puntos | gl residuales | Pendiente c₁ (e·eV⁻¹) | Coeficientes con unidades | R² | Condición diseño | RMS residuo (e) | Máx. abs. residuo (e) | Residuos (e) |
|---|---|---|---|---:|---:|---:|---:|---|---:|---:|---:|---:|---|
| NiLR0 | NiLR0 | BARE | principal | 3 | 6 | 2 | -0.19834127 | c0=8.43920443 e; c1=-0.19834127 e·eV⁻¹; c2=0.0140561225 e·eV⁻²; c3=-0.00694444446 e·eV⁻³ | 1 | 6.57466612 | 1.06479427e-07 | 1.76870746e-07 | [-6.80272727e-09, -1.36054457e-08, 6.80272105e-08, -1.70068027e-07, 1.76870746e-07, -5.4421772e-08] |
| NiLR0 | NiLR0 | BARE | lineal_misma_malla | 1 | 6 | 4 | -0.198360714 | c0=8.43923067 e; c1=-0.198360714 e·eV⁻¹ | 0.999995312 | — | 1.85564347e-05 | 2.46904762e-05 | [2.46904762e-05, -4.0952381e-06, -2.08809524e-05, -2.0452381e-05, -3.23809524e-06, 2.39761905e-05] |
| NiLR0 | NiLR0 | BARE | lineal_interior | 1 | 2 | 0 | -0.19835 | c0=8.43921 e; c1=-0.19835 e·eV⁻¹ | 1 | — | 2.80866677e-15 | 3.55271368e-15 | [1.77635684e-15, 3.55271368e-15] |
| NiLR0 | NiLR0 | SCREENED | principal | 3 | 6 | 2 | -0.0812662698 | c0=8.43920757 e; c1=-0.0812662698 e·eV⁻¹; c2=0.00130102041 e·eV⁻²; c3=-0.00694444444 e·eV⁻³ | 0.999999982 | 6.57466612 | 4.74998509e-07 | 7.48299325e-07 | [2.68707476e-07, -7.48299325e-07, 5.27210881e-07, 2.89115643e-07, -5.57823135e-07, 2.21088431e-07] |
| NiLR0 | NiLR0 | SCREENED | lineal_misma_malla | 1 | 6 | 4 | -0.0812857143 | c0=8.43921 e; c1=-0.0812857143 e·eV⁻¹ | 0.999999734 | — | 1.81265393e-06 | 2.85714285e-06 | [2.85714285e-06, -1.42857143e-06, -1.71428572e-06, -1.28571429e-06, -5.71428574e-07, 2.14285714e-06] |
| NiLR0 | NiLR0 | SCREENED | lineal_interior | 1 | 2 | 0 | -0.081275 | c0=8.4392085 e; c1=-0.081275 e·eV⁻¹ | 1 | — | 1.25607397e-15 | 1.77635684e-15 | [0, 1.77635684e-15] |
| NiLR1 | NiLR0 | BARE | principal | 3 | 6 | 2 | 0.0538206349 | c0=8.43920443 e; c1=0.0538206349 e·eV⁻¹; c2=-0.000140306122 e·eV⁻²; c3=0.00347222222 e·eV⁻³ | 0.999999996 | 6.57466612 | 1.52455339e-07 | 2.51700683e-07 | [6.46258442e-08, -1.56462589e-07, 6.80272088e-08, 1.87074829e-07, -2.51700683e-07, 8.8435371e-08] |
| NiLR1 | NiLR0 | BARE | lineal_misma_malla | 1 | 6 | 4 | 0.0538303571 | c0=8.43920417 e; c1=0.0538303571 e·eV⁻¹ | 0.999999984 | — | 2.92091528e-07 | 4.40476189e-07 | [-3.45238098e-07, 4.76190465e-08, 4.40476189e-07, 2.26190476e-07, -3.80952383e-07, 1.19047616e-08] |
| NiLR1 | NiLR0 | BARE | lineal_interior | 1 | 2 | 0 | 0.053825 | c0=8.4392045 e; c1=0.053825 e·eV⁻¹ | 1 | — | 3.97205465e-15 | 5.32907052e-15 | [5.32907052e-15, 1.77635684e-15] |
| NiLR1 | NiLR0 | SCREENED | principal | 3 | 6 | 2 | 0.000904563492 | c0=8.43920821 e; c1=0.000904563492 e·eV⁻¹; c2=-2.55102028e-05 e·eV⁻²; c3=0.00347222221 e·eV⁻³ | 0.999960039 | 6.57466612 | 2.49716393e-07 | 4.21768704e-07 | [-9.86394664e-08, 2.31292512e-07, -8.50340172e-08, -3.23129255e-07, 4.21768704e-07, -1.46258508e-07] |
| NiLR1 | NiLR0 | SCREENED | lineal_misma_malla | 1 | 6 | 4 | 0.000914285714 | c0=8.43920817 e; c1=0.000914285714 e·eV⁻¹ | 0.999941511 | — | 3.02108989e-07 | 4.52380956e-07 | [-3.09523815e-07, 4.04761899e-07, 1.19047614e-07, -4.52380956e-07, 2.61904759e-07, -2.38095268e-08] |
| NiLR1 | NiLR0 | SCREENED | lineal_interior | 1 | 2 | 0 | 0.0009 | c0=8.439208 e; c1=0.0009 e·eV⁻¹ | 1 | — | 2.80866677e-15 | 3.55271368e-15 | [1.77635684e-15, 3.55271368e-15] |
| NiLR0 | NiLR1 | BARE | principal | 3 | 6 | 2 | 0.0538117063 | c0=8.4392045 e; c1=0.0538117063 e·eV⁻¹; c2=1.17696169e-12 e·eV⁻²; c3=0.00347222221 e·eV⁻³ | 0.999999994 | 6.57466612 | 1.78174161e-07 | 2.3809524e-07 | [-4.76190571e-08, 1.90476186e-07, -2.3809524e-07, 2.38095236e-07, -1.90476195e-07, 4.76190447e-08] |
| NiLR0 | NiLR1 | BARE | lineal_misma_malla | 1 | 6 | 4 | 0.0538214286 | c0=8.4392045 e; c1=0.0538214286 e·eV⁻¹ | 0.999999989 | — | 2.43975019e-07 | 3.57142861e-07 | [-2.14285722e-07, 3.57142852e-07, -7.14285751e-08, 7.14285679e-08, -3.57142861e-07, 2.14285713e-07] |
| NiLR0 | NiLR1 | BARE | lineal_interior | 1 | 2 | 0 | 0.053825 | c0=8.4392045 e; c1=0.053825 e·eV⁻¹ | 1 | — | 3.97205465e-15 | 5.32907052e-15 | [5.32907052e-15, 1.77635684e-15] |
| NiLR0 | NiLR1 | SCREENED | principal | 3 | 6 | 2 | 0.000904563492 | c0=8.43920821 e; c1=0.000904563492 e·eV⁻¹; c2=-2.55102028e-05 e·eV⁻²; c3=0.00347222221 e·eV⁻³ | 0.999960039 | 6.57466612 | 2.49716393e-07 | 4.21768704e-07 | [-9.86394664e-08, 2.31292512e-07, -8.50340172e-08, -3.23129255e-07, 4.21768704e-07, -1.46258508e-07] |
| NiLR0 | NiLR1 | SCREENED | lineal_misma_malla | 1 | 6 | 4 | 0.000914285714 | c0=8.43920817 e; c1=0.000914285714 e·eV⁻¹ | 0.999941511 | — | 3.02108989e-07 | 4.52380956e-07 | [-3.09523815e-07, 4.04761899e-07, 1.19047614e-07, -4.52380956e-07, 2.61904759e-07, -2.38095268e-08] |
| NiLR0 | NiLR1 | SCREENED | lineal_interior | 1 | 2 | 0 | 0.0009 | c0=8.439208 e; c1=0.0009 e·eV⁻¹ | 1 | — | 2.80866677e-15 | 3.55271368e-15 | [1.77635684e-15, 3.55271368e-15] |
| NiLR1 | NiLR1 | BARE | principal | 3 | 6 | 2 | -0.198345635 | c0=8.43920457 e; c1=-0.198345635 e·eV⁻¹; c2=0.0138903061 e·eV⁻²; c3=-0.00347222224 e·eV⁻³ | 1 | 6.57466612 | 1.52455338e-07 | 2.51700676e-07 | [-6.46258584e-08, 1.56462582e-07, -6.80272105e-08, -1.87074832e-07, 2.51700676e-07, -8.84353764e-08] |
| NiLR1 | NiLR1 | BARE | lineal_misma_malla | 1 | 6 | 4 | -0.198355357 | c0=8.4392305 e; c1=-0.198355357 e·eV⁻¹ | 0.999995422 | — | 1.833566e-05 | 2.41785714e-05 | [2.41785714e-05, -3.71428572e-06, -2.06071429e-05, -2.03928571e-05, -3.28571429e-06, 2.38214286e-05] |
| NiLR1 | NiLR1 | BARE | lineal_interior | 1 | 2 | 0 | -0.19835 | c0=8.43921 e; c1=-0.19835 e·eV⁻¹ | 1 | — | 2.80866677e-15 | 3.55271368e-15 | [1.77635684e-15, 3.55271368e-15] |
| NiLR1 | NiLR1 | SCREENED | principal | 3 | 6 | 2 | -0.0812662698 | c0=8.43920757 e; c1=-0.0812662698 e·eV⁻¹; c2=0.00130102041 e·eV⁻²; c3=-0.00694444444 e·eV⁻³ | 0.999999982 | 6.57466612 | 4.74998509e-07 | 7.48299325e-07 | [2.68707476e-07, -7.48299325e-07, 5.27210881e-07, 2.89115643e-07, -5.57823135e-07, 2.21088431e-07] |
| NiLR1 | NiLR1 | SCREENED | lineal_misma_malla | 1 | 6 | 4 | -0.0812857143 | c0=8.43921 e; c1=-0.0812857143 e·eV⁻¹ | 0.999999734 | — | 1.81265393e-06 | 2.85714285e-06 | [2.85714285e-06, -1.42857143e-06, -1.71428572e-06, -1.28571429e-06, -5.71428574e-07, 2.14285714e-06] |
| NiLR1 | NiLR1 | SCREENED | lineal_interior | 1 | 2 | 0 | -0.081275 | c0=8.4392085 e; c1=-0.081275 e·eV⁻¹ | 1 | — | 1.25607397e-15 | 1.77635684e-15 | [0, 1.77635684e-15] |

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
| NiLR0 | -0.0812662698 | 0.000904563492 |
| NiLR1 | 0.000904563492 | -0.0812662698 |

### χ⁰ simetrizada (eV⁻¹)

| Sitio observado \ Sitio perturbado | NiLR0 | NiLR1 |
|---|---:|---:|
| NiLR0 | -0.19834127 | 0.0538161706 |
| NiLR1 | 0.0538161706 | -0.198345635 |

### χ simetrizada (eV⁻¹)

| Sitio observado \ Sitio perturbado | NiLR0 | NiLR1 |
|---|---:|---:|
| NiLR0 | -0.0812662698 | 0.000904563492 |
| NiLR1 | 0.000904563492 | -0.0812662698 |

### χ⁰ usada para inversión (eV⁻¹)

| Sitio observado \ Sitio perturbado | NiLR0 | NiLR1 |
|---|---:|---:|
| NiLR0 | -0.19834127 | 0.0538117063 |
| NiLR1 | 0.0538206349 | -0.198345635 |

### χ usada para inversión (eV⁻¹)

| Sitio observado \ Sitio perturbado | NiLR0 | NiLR1 |
|---|---:|---:|
| NiLR0 | -0.0812662698 | 0.000904563492 |
| NiLR1 | 0.000904563492 | -0.0812662698 |

### (χ⁰)⁻¹ (eV)

| Sitio observado \ Sitio perturbado | NiLR0 | NiLR1 |
|---|---:|---:|
| NiLR0 | -5.44248532 | -1.47656096 |
| NiLR1 | -1.47680596 | -5.44236554 |

### χ⁻¹ (eV)

| Sitio observado \ Sitio perturbado | NiLR0 | NiLR1 |
|---|---:|---:|
| NiLR0 | -12.306753 | -0.136984748 |
| NiLR1 | -0.136984748 | -12.306753 |

### U_matrix (eV)

| Sitio observado \ Sitio perturbado | NiLR0 | NiLR1 |
|---|---:|---:|
| NiLR0 | 6.8642677 | -1.33957621 |
| NiLR1 | -1.33982121 | 6.86438748 |

### Diagnóstico de inversión: ajuste principal

| Matriz | Método | Residuo izquierdo Frobenius | Residuo derecho Frobenius |
|---|---|---:|---:|
| χ⁰ | direct_inv | 1.16406438e-16 | 1.21047169e-16 |
| χ | direct_inv | 1.11060962e-16 | 1.11060962e-16 |

**Condición de χ⁰:** rango 2/2; determinante 0.0364439449; número de condición 1.74471989; estado `FULL_RANK`.

**Condición de χ:** rango 2/2; determinante 0.00660338838; número de condición 1.0225123; estado `FULL_RANK`.

## 6. Sensibilidad, diagnósticos y estado

| Análisis | Ventana máxima α (eV) | Método | Tipo de ventana | Estado de matriz | U por sitio (eV) | Cota de impresión (eV) |
|---|---:|---|---|---|---|---:|
| Principal | — | polynomial | — | FULL_RANK | NiLR0: 6.8642677; NiLR1: 6.86438748 | 0.0118330619 |
| Lineal misma malla | — | linear | — | FULL_RANK | NiLR0: 6.86179683; NiLR1: 6.86164986 | 0.0043441796 |
| Ventana | 0.02 | linear | resolution_limited_two_point_central_difference | FULL_RANK | NiLR0: 6.86305628; NiLR1: 6.86305628 | 0.0101391948 |
| Ventana | 0.04 | linear | eligible_linear_fit_window | FULL_RANK | NiLR0: 6.86317037; NiLR1: 6.86317037 | 0.00608321832 |
| Ventana | 0.06 | linear | eligible_linear_fit_window | FULL_RANK | NiLR0: 6.86179683; NiLR1: 6.86164986 | 0.0043441796 |

- Diferencia máxima de U entre modelos/ventanas informada: 0.00273761882 eV.
- Evaluación frente al umbral: `UNASSESSED_TOLERANCE_MISSING`; métricas requeridas completas: true.
- Umbral configurado para sensibilidad: — eV.
- Fuente de ocupación ajustada: `siesta_occupations_total`.
- Cota determinista de redondeo de la fuente de ocupación impresa: 0.0118330619 eV; causa: deterministic bound propagated from siesta_occupations_total print intervals. No es un intervalo estadístico ni incluye ruido SCF.
- Validación SCF: true.
- Continuidad de estado: true.

Causas y advertencias registradas:
- `sensitivity_tolerance_not_configured`

## 7. Procedencia y archivos fuente

| Tipo | SHA-256 registrados |
|---|---|
| bare_fdf_sha256 | 0cea98c3b2e7e428bef703931cb732e7aab11f39ce3fe8f7a83105565f8b00aa, 3ca1d004f9ff5369198ef5828a34ae12f076fc459a59f8c47e777cf223f45a6d, 6e377cd84f9a11691d5d86831e9cdafbbebcac317a913483adda307a218c31e9, 757f2b41a2e02b53281563358e15576caa263ce1eb783d2ceac008328f09c255, 7db558879c3ef94b284ccbf1282c3906b47e8b14fbe360b7dcecf20e33ee6c3b, 8c456bf2107afacd44d21ac6596c536312d3fb569320d07ef319ef291bee277b, b1181a92d720ca273dfbadb34164ad53844490b4a3613667dfb470515b2bea12, bfa49c6dfd9ea3bbbb3e9d176eef868b0fd3b854a014bea35ad162baff826a9b, c4a233cec7dced236bad89f8b5ddee1d61686ddac4619292e80dd32344064433, d6c1c06d42d96ea19ad17bffdd4468fe52bd657c8e436f53fb5738aea29cb4d7, e4c908b534a714bc1b1d3899a56456bdcb11f40088c01a4f8290272718df697c, e9e5d07fed4e2758265470a3507b1ee9e1cfc4bedfc431353b0cd94479755bb8 |
| bare_out_sha256 | 29f91fb8f91e0d6fadfaeacf3fcd16af7ff0f67f12f4b15e360abd76d6ec8286, 36bc36cfd01533600614790b2930123000710895801662f4d0c4bf4b2d4932a7, 42935f17fab475c1995510d7a549923968ac85bd4e520ab0b206fac9b2785cd7, 483dfa4d18b024b2c42f0cf03bfbc4749681b863a360300d4882839a3d75320c, 5abc8b36a007acfd635796bc42784cef8a44b40fbe2ba30744d22f9de47b3912, 97e4b6007dd3bb1489ea487db4169999346c8dc9ab4d98a2849d491a27cb990f, 98fdd62e66113840a21c5e25746ec717137d5d1f81285a0619a4d58a9addc089, 9c1429caabc9a9e43c1a67859597a2898976e8841229d5fd54689038f838f7f9, bf3c0f89bd1061e775be9d229057e8101053fec6077d18a3c7f65fe9335e3b1d, d55db9f07de42b66e2e42c1ca94f4ba3e8b96e003526097ffaa6de2ec1dd2fb4, f5011b95778cbd13616f79960db30af5879b118d075d704c356150a40ce59069, f9afc3aeb59a177f47fb56e3875aebf56f3e7cd67cc0d065805354364cceebce |
| parent_dm_sha256 | f7fca191f941bbda5ee38eb361096aa8a802dfd410e12aaa680f39f3cf2193ef |
| projector_fingerprints | 1f9b40877be7fc45f7da2f33a4787c500940121fe897a874a2b1df88f50d4d7a, 938e53c7ed28aeea35cbb9004c603260074d169c62024f987b11ed8f9f2c5cc4 |
| screened_fdf_sha256 | 0800a9ee7ba8adc3bae372457114abadccfd00322da32cf43dc344efd994f4fd, 21c2b330a501c742bb6abad377f8abea815a83a34e74fae7691fd008776a195e, 3d4645f1bc0f495240b6aeb8404cbfce4d792ea5fb86540cf204668de9828f70, 5b9ec5f64ea05290f35c411280a69a304a20362ff7ed0ec8b90ad0ac0bf22f98, 5d15274f023766b59bd54fcaee65a88e779fa3e44afc3cea5993222d4acc5940, 65c909c85914773b47ea3e2e770cc34ccd162633396ba200ed2e46cae672ed4e, 6b58dfc0a005de8af4c453b88f76bd2fc6a9cb77f04c34cadfd24ce523576c1f, b019668ecb18c45d0f0895c6fa0c40cb206c4c78dc5ee640d8283baf3c120dfb, ced272c74909782c8c6d3c04941568154b5f2e838a46826e622047272a267150, dd3b000669cf92ddec455d1aeee12ee160730515655a7079134ba22cc951b280, e747150758675410281a0539b0a1bdd0d37b86f8a4438769dbf06d23d8a266a9, eaa2e7c7ec6fc4aac964df2b2d6a88e71402f89551987891b1e3a7f1c512cb95 |
| screened_out_sha256 | 058efe74fcce9917c403332129cb51faa49fa4d42460f9c9a3b12ec57ed54950, 297cadfc23fa933afc7c76e9c7f3a2d8e8a099aaa79fb1474aea25704b22cf70, 3fa86adb093714c8fc4ed5c79db6e23db4ced13c6e7cec19ddf6542daa96d173, 5e2c795418f81e4457139bc30bcb30c73845b77801c04daf86641243c80cb644, 6750a80ee38782cf4f68d3591e25bfb89692c0569446b6965366a8b05c7cf15b, a42e93536abc9ad05bd4a67f4531c00b71e385f9bd99035c47759694c07caa90, a66db26ca23d4456b6bba4eec31397c5d068e46562e6e74d1920d9e1bb5e9537, b0c670bb3216ed9e52ff95256453b6039870c3293edd40615098e29df7cbb9ce, b57dfe5401b6b9ca660c6dc82b7319daa302d402e998a37d85ae49f740d9ad04, d42fb4b2aaae0d2709719fec616026c2c9aad1bd827988c758a6ccb438d9faf8, dc38cf75401b4d600669abce24559e82f2d21cea9276eb928febcb3fffdc49cc, e04271a04d1663fc01623ca86bcc6d1735839c9053d82be91aee95e549fc0dbf |

### Entradas declaradas de la campaña

| Archivo | Ruta | SHA-256 |
|---|---|---|
| campaign_contract | backend_contract.json | 030c00b7368e6238bb87ab46db0ee18510f1aec37190b56ce1f2c9e982d6cafe |
| execution_profile | execution_profile.json | fbc9ff5ae47a6791d0e1ff962b6070f8690f1ffef475bafd8784a7388d755ae1 |
| lr_config | lr_config.json | 619895c0908c5c557a476151a9e06a63483254b7e0b814af084784ac07fd7cd6 |
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
| — | Referencia | REFERENCE_SCREENED | reference | .siestaflow/attempts/52367a6622b19f08825e/attempt-1790646750401132562-a3054c02/reference_52367a6622b1/siesta.fdf | .siestaflow/attempts/52367a6622b19f08825e/attempt-1790646750401132562-a3054c02/reference_52367a6622b1/siesta.out | b4fb34e642d862be6949a5b2033a60c5b9fcae56119879583bb3eaf237620ee7 / b9c5066f28e241a565d8842213697b550a44ee15ff1636569f3aa402d47ac468 | 08076428b02c2bfe4ead3beb94fda377102a08ec0c8f02d6232da7f2ce38c10b |
| -0.06 | NiLR0 | BARE | response:lr_s000_m0p06_bare | .siestaflow/attempts/a9b894b5b55ba9409a6b/attempt-1790646794926391125-7f67d251/response_lr_s000_m0p06_bare_a9b894b5b55b/siesta.fdf | .siestaflow/attempts/a9b894b5b55ba9409a6b/attempt-1790646794926391125-7f67d251/response_lr_s000_m0p06_bare_a9b894b5b55b/siesta.out | 8c456bf2107afacd44d21ac6596c536312d3fb569320d07ef319ef291bee277b / d55db9f07de42b66e2e42c1ca94f4ba3e8b96e003526097ffaa6de2ec1dd2fb4 | 0b91baab8cfb2c1a3628b4dd528dbda2858a03a45f01bd780ada2ab9fba24924 |
| -0.06 | NiLR0 | SCREENED | response:lr_s000_m0p06_screened | .siestaflow/attempts/365d9074957c7d4a53a6/attempt-1790646800808360710-3c16445f/response_lr_s000_m0p06_screened_365d9074957c/siesta.fdf | .siestaflow/attempts/365d9074957c7d4a53a6/attempt-1790646800808360710-3c16445f/response_lr_s000_m0p06_screened_365d9074957c/siesta.out | 5b9ec5f64ea05290f35c411280a69a304a20362ff7ed0ec8b90ad0ac0bf22f98 / a42e93536abc9ad05bd4a67f4531c00b71e385f9bd99035c47759694c07caa90 | 264b506f7b4a9d28be66839e6e05d9110f193a8541e2b4584f0d94ad509607c1 |
| -0.04 | NiLR0 | BARE | response:lr_s000_m0p04_bare | .siestaflow/attempts/91a02247ffc2e934feaa/attempt-1790646829326164610-82b72952/response_lr_s000_m0p04_bare_91a02247ffc2/siesta.fdf | .siestaflow/attempts/91a02247ffc2e934feaa/attempt-1790646829326164610-82b72952/response_lr_s000_m0p04_bare_91a02247ffc2/siesta.out | e4c908b534a714bc1b1d3899a56456bdcb11f40088c01a4f8290272718df697c / 29f91fb8f91e0d6fadfaeacf3fcd16af7ff0f67f12f4b15e360abd76d6ec8286 | 80587f3ddb2f8df21eb3bd94ef9e8427ca07377d160afa9e5be0e3ab620c297e |
| -0.04 | NiLR0 | SCREENED | response:lr_s000_m0p04_screened | .siestaflow/attempts/9c0863b8a961ad7b6d5b/attempt-1790646835729482643-c0fad5b2/response_lr_s000_m0p04_screened_9c0863b8a961/siesta.fdf | .siestaflow/attempts/9c0863b8a961ad7b6d5b/attempt-1790646835729482643-c0fad5b2/response_lr_s000_m0p04_screened_9c0863b8a961/siesta.out | ced272c74909782c8c6d3c04941568154b5f2e838a46826e622047272a267150 / e04271a04d1663fc01623ca86bcc6d1735839c9053d82be91aee95e549fc0dbf | 9a9b6fed60ccaa56db4b5ebceae12c1e484ba66f9c4b722beec2abd2cd29a203 |
| -0.02 | NiLR0 | BARE | response:lr_s000_m0p02_bare | .siestaflow/attempts/8119c375c5841b7b956a/attempt-1790646861293922741-53313280/response_lr_s000_m0p02_bare_8119c375c584/siesta.fdf | .siestaflow/attempts/8119c375c5841b7b956a/attempt-1790646861293922741-53313280/response_lr_s000_m0p02_bare_8119c375c584/siesta.out | bfa49c6dfd9ea3bbbb3e9d176eef868b0fd3b854a014bea35ad162baff826a9b / f9afc3aeb59a177f47fb56e3875aebf56f3e7cd67cc0d065805354364cceebce | 350a6438cebc7c3caf638f7f45a0f9847eadd5a6f1833921c77087a35bbbc95d |
| -0.02 | NiLR0 | SCREENED | response:lr_s000_m0p02_screened | .siestaflow/attempts/4f60f687d724e53d32ff/attempt-1790646867385626852-c3803113/response_lr_s000_m0p02_screened_4f60f687d724/siesta.fdf | .siestaflow/attempts/4f60f687d724e53d32ff/attempt-1790646867385626852-c3803113/response_lr_s000_m0p02_screened_4f60f687d724/siesta.out | 6b58dfc0a005de8af4c453b88f76bd2fc6a9cb77f04c34cadfd24ce523576c1f / 058efe74fcce9917c403332129cb51faa49fa4d42460f9c9a3b12ec57ed54950 | 531be4333daa90744635350b48cd998cece829d360499628432380bd335e19ef |
| 0.02 | NiLR0 | BARE | response:lr_s000_p0p02_bare | .siestaflow/attempts/8e7e82caf7897a723870/attempt-1790646891895386236-3d9ebee7/response_lr_s000_p0p02_bare_8e7e82caf789/siesta.fdf | .siestaflow/attempts/8e7e82caf7897a723870/attempt-1790646891895386236-3d9ebee7/response_lr_s000_p0p02_bare_8e7e82caf789/siesta.out | 7db558879c3ef94b284ccbf1282c3906b47e8b14fbe360b7dcecf20e33ee6c3b / 36bc36cfd01533600614790b2930123000710895801662f4d0c4bf4b2d4932a7 | 64a4e40fe2e8260be59207ae13237912f9469cbcd7086171447f4eb54f6d8ea6 |
| 0.02 | NiLR0 | SCREENED | response:lr_s000_p0p02_screened | .siestaflow/attempts/bce88b1318147f2362e2/attempt-1790646898326949935-e9cdf277/response_lr_s000_p0p02_screened_bce88b131814/siesta.fdf | .siestaflow/attempts/bce88b1318147f2362e2/attempt-1790646898326949935-e9cdf277/response_lr_s000_p0p02_screened_bce88b131814/siesta.out | b019668ecb18c45d0f0895c6fa0c40cb206c4c78dc5ee640d8283baf3c120dfb / b57dfe5401b6b9ca660c6dc82b7319daa302d402e998a37d85ae49f740d9ad04 | b3153fbe4c8fd3034dc66749948eb802b9622da8d358b2675115594c81793cff |
| 0.04 | NiLR0 | BARE | response:lr_s000_p0p04_bare | .siestaflow/attempts/ba8edcc7ec7dc5665b5b/attempt-1790646919986518699-28407ba9/response_lr_s000_p0p04_bare_ba8edcc7ec7d/siesta.fdf | .siestaflow/attempts/ba8edcc7ec7dc5665b5b/attempt-1790646919986518699-28407ba9/response_lr_s000_p0p04_bare_ba8edcc7ec7d/siesta.out | c4a233cec7dced236bad89f8b5ddee1d61686ddac4619292e80dd32344064433 / f5011b95778cbd13616f79960db30af5879b118d075d704c356150a40ce59069 | 5f4ec55366120991258e5fde4986ebf2a5f3a97c042fdc3edb12a55441d364aa |
| 0.04 | NiLR0 | SCREENED | response:lr_s000_p0p04_screened | .siestaflow/attempts/ff40fe49cff9b19265a2/attempt-1790646925818815237-fbdb3285/response_lr_s000_p0p04_screened_ff40fe49cff9/siesta.fdf | .siestaflow/attempts/ff40fe49cff9b19265a2/attempt-1790646925818815237-fbdb3285/response_lr_s000_p0p04_screened_ff40fe49cff9/siesta.out | 0800a9ee7ba8adc3bae372457114abadccfd00322da32cf43dc344efd994f4fd / dc38cf75401b4d600669abce24559e82f2d21cea9276eb928febcb3fffdc49cc | 15b653fe1be96ffcd2d083ff54be3a576794c2dbb2af3277e1e4751fb20db8d8 |
| 0.06 | NiLR0 | BARE | response:lr_s000_p0p06_bare | .siestaflow/attempts/d839ffe229398f9de504/attempt-1790646951571157546-151ab95e/response_lr_s000_p0p06_bare_d839ffe22939/siesta.fdf | .siestaflow/attempts/d839ffe229398f9de504/attempt-1790646951571157546-151ab95e/response_lr_s000_p0p06_bare_d839ffe22939/siesta.out | b1181a92d720ca273dfbadb34164ad53844490b4a3613667dfb470515b2bea12 / 9c1429caabc9a9e43c1a67859597a2898976e8841229d5fd54689038f838f7f9 | 9980089eb9e7200654dac6c4dee0a827158cdb1a5a931819b02b95da3b644e42 |
| 0.06 | NiLR0 | SCREENED | response:lr_s000_p0p06_screened | .siestaflow/attempts/3fe519aeb5e10966f238/attempt-1790646958310970014-0aff1267/response_lr_s000_p0p06_screened_3fe519aeb5e1/siesta.fdf | .siestaflow/attempts/3fe519aeb5e10966f238/attempt-1790646958310970014-0aff1267/response_lr_s000_p0p06_screened_3fe519aeb5e1/siesta.out | 3d4645f1bc0f495240b6aeb8404cbfce4d792ea5fb86540cf204668de9828f70 / 3fa86adb093714c8fc4ed5c79db6e23db4ced13c6e7cec19ddf6542daa96d173 | dce2a6ff40477d5dde5723d6c44f70fd781b0d8d7f7d34a571e4eec984fd61dd |
| -0.06 | NiLR1 | BARE | response:lr_s001_m0p06_bare | .siestaflow/attempts/8a7d4f4a323274cedc2a/attempt-1790646981452321622-d5483bd0/response_lr_s001_m0p06_bare_8a7d4f4a3232/siesta.fdf | .siestaflow/attempts/8a7d4f4a323274cedc2a/attempt-1790646981452321622-d5483bd0/response_lr_s001_m0p06_bare_8a7d4f4a3232/siesta.out | 0cea98c3b2e7e428bef703931cb732e7aab11f39ce3fe8f7a83105565f8b00aa / 42935f17fab475c1995510d7a549923968ac85bd4e520ab0b206fac9b2785cd7 | 06c78233ee889add103c70f6e8271160ac564f4d0f5b8277a7515a8f599e8698 |
| -0.06 | NiLR1 | SCREENED | response:lr_s001_m0p06_screened | .siestaflow/attempts/cd98d0ad2b097309a007/attempt-1790646988173030696-10ba6dfa/response_lr_s001_m0p06_screened_cd98d0ad2b09/siesta.fdf | .siestaflow/attempts/cd98d0ad2b097309a007/attempt-1790646988173030696-10ba6dfa/response_lr_s001_m0p06_screened_cd98d0ad2b09/siesta.out | e747150758675410281a0539b0a1bdd0d37b86f8a4438769dbf06d23d8a266a9 / a66db26ca23d4456b6bba4eec31397c5d068e46562e6e74d1920d9e1bb5e9537 | 81c949638add75b84eb314c1991674b8db53aae884975d1a09a970f6aafe32cc |
| -0.04 | NiLR1 | BARE | response:lr_s001_m0p04_bare | .siestaflow/attempts/f920cfb21087d4d86fc4/attempt-1790647016726139652-03ee49b8/response_lr_s001_m0p04_bare_f920cfb21087/siesta.fdf | .siestaflow/attempts/f920cfb21087d4d86fc4/attempt-1790647016726139652-03ee49b8/response_lr_s001_m0p04_bare_f920cfb21087/siesta.out | d6c1c06d42d96ea19ad17bffdd4468fe52bd657c8e436f53fb5738aea29cb4d7 / 483dfa4d18b024b2c42f0cf03bfbc4749681b863a360300d4882839a3d75320c | 23d486cc6afa9d0568e81dd3c39dda6f3e004f3a7fccc7fbfae5f8535d8b6409 |
| -0.04 | NiLR1 | SCREENED | response:lr_s001_m0p04_screened | .siestaflow/attempts/d1b788ec0f0198f1157a/attempt-1790647023122513815-734199ce/response_lr_s001_m0p04_screened_d1b788ec0f01/siesta.fdf | .siestaflow/attempts/d1b788ec0f0198f1157a/attempt-1790647023122513815-734199ce/response_lr_s001_m0p04_screened_d1b788ec0f01/siesta.out | 21c2b330a501c742bb6abad377f8abea815a83a34e74fae7691fd008776a195e / 297cadfc23fa933afc7c76e9c7f3a2d8e8a099aaa79fb1474aea25704b22cf70 | 1a1384e35f1208d5700daebf335c08cd4b4e6eec942cf288624b9f9419a40c22 |
| -0.02 | NiLR1 | BARE | response:lr_s001_m0p02_bare | .siestaflow/attempts/d40fa0516e62855bdc5a/attempt-1790647052716799084-d98a8ded/response_lr_s001_m0p02_bare_d40fa0516e62/siesta.fdf | .siestaflow/attempts/d40fa0516e62855bdc5a/attempt-1790647052716799084-d98a8ded/response_lr_s001_m0p02_bare_d40fa0516e62/siesta.out | 3ca1d004f9ff5369198ef5828a34ae12f076fc459a59f8c47e777cf223f45a6d / 98fdd62e66113840a21c5e25746ec717137d5d1f81285a0619a4d58a9addc089 | b3404015217e676dfebe1cbc655441beb2bbf6e5720866d8e9eff13745b09e76 |
| -0.02 | NiLR1 | SCREENED | response:lr_s001_m0p02_screened | .siestaflow/attempts/8a60c8950b2acc786cdb/attempt-1790647058304226998-b9f728d9/response_lr_s001_m0p02_screened_8a60c8950b2a/siesta.fdf | .siestaflow/attempts/8a60c8950b2acc786cdb/attempt-1790647058304226998-b9f728d9/response_lr_s001_m0p02_screened_8a60c8950b2a/siesta.out | eaa2e7c7ec6fc4aac964df2b2d6a88e71402f89551987891b1e3a7f1c512cb95 / 6750a80ee38782cf4f68d3591e25bfb89692c0569446b6965366a8b05c7cf15b | 902475fab9b631f3d5a91564ed9ceb5456f590ec133a3bc7a892021ecd9491ae |
| 0.02 | NiLR1 | BARE | response:lr_s001_p0p02_bare | .siestaflow/attempts/dc07ce4a6f186716bf4f/attempt-1790647078177763974-b760eab5/response_lr_s001_p0p02_bare_dc07ce4a6f18/siesta.fdf | .siestaflow/attempts/dc07ce4a6f186716bf4f/attempt-1790647078177763974-b760eab5/response_lr_s001_p0p02_bare_dc07ce4a6f18/siesta.out | 757f2b41a2e02b53281563358e15576caa263ce1eb783d2ceac008328f09c255 / bf3c0f89bd1061e775be9d229057e8101053fec6077d18a3c7f65fe9335e3b1d | 77123be42779430725ca8ed6af982d4ae245dc1371bcfdab10d36baf5e32bf86 |
| 0.02 | NiLR1 | SCREENED | response:lr_s001_p0p02_screened | .siestaflow/attempts/5844c04f7ade2a15396c/attempt-1790647085576389308-95df9cc5/response_lr_s001_p0p02_screened_5844c04f7ade/siesta.fdf | .siestaflow/attempts/5844c04f7ade2a15396c/attempt-1790647085576389308-95df9cc5/response_lr_s001_p0p02_screened_5844c04f7ade/siesta.out | 65c909c85914773b47ea3e2e770cc34ccd162633396ba200ed2e46cae672ed4e / 5e2c795418f81e4457139bc30bcb30c73845b77801c04daf86641243c80cb644 | e867237475baad182d3d33ff0d7616e9e7e5a8e1e749c95291e2a702e18fcc03 |
| 0.04 | NiLR1 | BARE | response:lr_s001_p0p04_bare | .siestaflow/attempts/16b7f66f8f4a159ce519/attempt-1790647106641338750-baba7491/response_lr_s001_p0p04_bare_16b7f66f8f4a/siesta.fdf | .siestaflow/attempts/16b7f66f8f4a159ce519/attempt-1790647106641338750-baba7491/response_lr_s001_p0p04_bare_16b7f66f8f4a/siesta.out | e9e5d07fed4e2758265470a3507b1ee9e1cfc4bedfc431353b0cd94479755bb8 / 5abc8b36a007acfd635796bc42784cef8a44b40fbe2ba30744d22f9de47b3912 | 099bd5a9b93f55190115df690525588f18e156544a42bac4ed00db3561f13790 |
| 0.04 | NiLR1 | SCREENED | response:lr_s001_p0p04_screened | .siestaflow/attempts/4b49380df8041040dffa/attempt-1790647112601448425-14fc57cc/response_lr_s001_p0p04_screened_4b49380df804/siesta.fdf | .siestaflow/attempts/4b49380df8041040dffa/attempt-1790647112601448425-14fc57cc/response_lr_s001_p0p04_screened_4b49380df804/siesta.out | dd3b000669cf92ddec455d1aeee12ee160730515655a7079134ba22cc951b280 / b0c670bb3216ed9e52ff95256453b6039870c3293edd40615098e29df7cbb9ce | c55a43624c9776c7e03b50160da60ff7dd947422746cad294f7a21eb873f3f03 |
| 0.06 | NiLR1 | BARE | response:lr_s001_p0p06_bare | .siestaflow/attempts/db6326ee96bee0a6337f/attempt-1790647140950990323-f998f45d/response_lr_s001_p0p06_bare_db6326ee96be/siesta.fdf | .siestaflow/attempts/db6326ee96bee0a6337f/attempt-1790647140950990323-f998f45d/response_lr_s001_p0p06_bare_db6326ee96be/siesta.out | 6e377cd84f9a11691d5d86831e9cdafbbebcac317a913483adda307a218c31e9 / 97e4b6007dd3bb1489ea487db4169999346c8dc9ab4d98a2849d491a27cb990f | 42d22195700791d35b206cab728b6412f39852a17ef7be63515db8c8e919eba0 |
| 0.06 | NiLR1 | SCREENED | response:lr_s001_p0p06_screened | .siestaflow/attempts/0f345e8a7aa02280696e/attempt-1790647150059543036-c40d4901/response_lr_s001_p0p06_screened_0f345e8a7aa0/siesta.fdf | .siestaflow/attempts/0f345e8a7aa02280696e/attempt-1790647150059543036-c40d4901/response_lr_s001_p0p06_screened_0f345e8a7aa0/siesta.out | 5d15274f023766b59bd54fcaee65a88e779fa3e44afc3cea5993222d4acc5940 / d42fb4b2aaae0d2709719fec616026c2c9aad1bd827988c758a6ccb438d9faf8 | 07b1dd71b0205ffa3004d761045d9cf4ce03019ac0f0783f75c176c3142660bd |

La sensibilidad entre estimadores y ventanas es un diagnóstico y no un intervalo de confianza. La cota determinista de redondeo se calcula desde los tokens del total `Occupations:` impreso; si faltan esos tokens, queda como no disponible.
