# Contrato de plugins y backends

Un backend DEBE implementar:

- `probe_runtime()`;
- `materialize_reference_input()`;
- `materialize_response_input()`;
- `run_contract()`;
- `parse_runtime_identity()`;
- `parse_reference_state()`;
- `extract_bare_observations()`;
- `extract_screened_observations()`;
- `validate_termination()`;
- `collect_artifacts()`.

## Condiciones

- Parsing sin heurísticas silenciosas.
- Cada valor extraído conserva localización y evidencia.
- Las diferencias de versión se aíslan en adaptadores.
- Un backend no puede aprobar científicamente un resultado.


## Convenciones normativas

Las palabras **DEBE**, **NO DEBE**, **DEBERÍA**, **NO DEBERÍA** y **PUEDE** son normativas.  
Una regla marcada como DEBE es obligatoria para conformidad. Una regla marcada como DEBERÍA
puede omitirse sólo con una justificación registrada y auditable.
