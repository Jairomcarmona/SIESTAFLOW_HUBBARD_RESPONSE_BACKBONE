# Contrato científico

## Entradas científicas obligatorias

- geometría y celda;
- especies y pseudopotenciales;
- base y parámetros numéricos;
- estado magnético de referencia;
- subespacios correlacionados;
- targets perturbables;
- observables de población;
- transformación de observables;
- definición del proyector;
- política de perturbación;
- definición backend de BARE/SCREENED.

## Invariantes

1. La geometría permanece fija en toda matriz.
2. La identidad de cada átomo y especie permanece fija.
3. El subespacio usado para calcular `U` es el mismo que se pretende usar posteriormente.
4. Las respuestas BARE y SCREENED comparten la misma perturbación y referencia.
5. No se mezclan resultados de candidatos, binarios o pseudopotenciales distintos.
6. La matriz invertida coincide byte a byte o numéricamente con la archivada como seleccionada.
7. La fórmula de `U` usa resta, no suma.
8. La aprobación científica no se deriva automáticamente del estado de ejecución.

## Resultado automático máximo

```json
{
  "scientific_status": "CANDIDATE_READY_FOR_REVIEW",
  "recommended_single_U_ev": null
}
```


## Convenciones normativas

Las palabras **DEBE**, **NO DEBE**, **DEBERÍA**, **NO DEBERÍA** y **PUEDE** son normativas.  
Una regla marcada como DEBE es obligatoria para conformidad. Una regla marcada como DEBERÍA
puede omitirse sólo con una justificación registrada y auditable.
