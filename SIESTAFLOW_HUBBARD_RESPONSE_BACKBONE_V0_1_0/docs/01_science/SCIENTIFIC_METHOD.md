# Método científico

## Modelo de respuesta

Para cada perturbación independiente `j` y cada observable `i`, se obtienen poblaciones como
función de una perturbación simétrica `alpha`.

Las pendientes forman respuestas primarias:

\[
R^0_{ij} = \frac{\partial n_i^{BARE}}{\partial \alpha_j},
\qquad
R_{ij} = \frac{\partial n_i^{SCREENED}}{\partial \alpha_j}.
\]

Una transformación explícita de observables `A` produce susceptibilidades físicas:

\[
\chi_0 = A R^0, \qquad \chi = A R.
\]

Sólo matrices cuadradas físicamente definidas pueden invertirse. La matriz Hubbard es:

\[
U = \chi_0^{-1} - \chi^{-1}.
\]

## Requisitos

- Las respuestas DEBEN provenir de la misma geometría, subespacios, pseudopotenciales y estado base.
- La ventana de perturbación DEBE demostrar señal suficiente y linealidad.
- Las matrices DEBEN pasar completitud, antisimetría, rango, condición e inversión.
- La sensibilidad DEBE cuantificarse.
- El resultado DEBE conservar matrices y datos intermedios.


## Convenciones normativas

Las palabras **DEBE**, **NO DEBE**, **DEBERÍA**, **NO DEBERÍA** y **PUEDE** son normativas.  
Una regla marcada como DEBE es obligatoria para conformidad. Una regla marcada como DEBERÍA
puede omitirse sólo con una justificación registrada y auditable.
