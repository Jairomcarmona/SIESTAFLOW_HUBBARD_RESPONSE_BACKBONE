# Versionado y control de cambios

## Versiones independientes

- `software_version`: versión de implementación.
- `methodology_version`: definición científica y matemática.
- `schema_version`: contratos serializados.
- `backend_version`: implementación SIESTA concreta.
- `campaign_version`: revisión de una campaña.
- `evidence_package_version`: formato del paquete final.

## Reglas

Un cambio de software sin cambio metodológico PUEDE reutilizar evidencia sólo si no altera
resultados ni parsing. Un cambio metodológico NO DEBE reutilizar caché previa sin una migración
explícita.

Cada lock DEBE declarar todas las versiones y hashes relevantes.


## Convenciones normativas

Las palabras **DEBE**, **NO DEBE**, **DEBERÍA**, **NO DEBERÍA** y **PUEDE** son normativas.  
Una regla marcada como DEBE es obligatoria para conformidad. Una regla marcada como DEBERÍA
puede omitirse sólo con una justificación registrada y auditable.
