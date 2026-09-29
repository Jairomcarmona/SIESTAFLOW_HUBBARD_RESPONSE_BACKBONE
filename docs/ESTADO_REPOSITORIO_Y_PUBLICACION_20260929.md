# Estado del repositorio y distancia respecto a GitHub

**Fecha de inspección y publicación:** 2026-09-29. **Alcance:** lectura del
checkout, verificación de la rama remota, selección de archivos, commit local
y publicación en una rama de GitHub con PR borrador.

## Conclusión inmediata

El trabajo de cierre de SIESTAFLOW se consolidó en la rama
`codex/sync-product-20260929`, que reúne la implementación 0.1.2, pruebas,
documentación y resultados NiO seleccionados. La rama está publicada en
GitHub mediante el [PR borrador #4](https://github.com/Jairomcarmona/SIESTAFLOW_HUBBARD_RESPONSE_BACKBONE/pull/4),
con base `fix/mno-audit-20260925`. **`main` aún no contiene estos cambios**;
quien analice el código debe abrir la rama o el diff de ese PR.

La rama local de partida fue `fix/mno-audit-20260925` en
`e53a6b0266bd83e8e41589973c59eb251ce034a7`. Una consulta de lectura
`git ls-remote` desde el entorno autorizado confirmó ese mismo SHA para la
rama remota y `bc2d1d0fccb4670476bac22c852476315a660e58` para `main`.
Se preparó una rama nueva basada en `fix/mno-audit-20260925`, de modo que su
diff de producto se pueda revisar por separado de los PR anteriores.

## Inventario previo a seleccionar los archivos

| Categoría | Estado observado | Relevancia |
|---|---|---|
| Archivos ya seguidos por Git con modificaciones locales | 28 en el checkout completo, incluidos `README.md`, `docs/USER_MANUAL.md`, `pyproject.toml`, CLI, ejecutores, análisis y pruebas | Contienen parte del comportamiento de la entrega 0.1.2; no están en `HEAD`. |
| Módulos de producto aún sin seguimiento | 8 bajo `src/siestaflow_hubbard/`: control adaptativo, análisis LR, reproducibilidad de malla, runner, campaña v2, inicialización y supervisor WSL, informe U | Son código esencial para lo descrito en la documentación nueva. Un commit sólo de documentos no publicaría esa implementación. |
| Pruebas aún sin seguimiento | 15 bajo `tests/` en la inspección dirigida | Incluyen análisis v3, runner, adaptación y reproducibilidad; requieren selección y revisión antes de publicar. |
| Documentos Markdown aún sin seguimiento | Al menos 16 bajo `docs/` antes de este inventario, incluidos el eje rector, registro P0–P6, contrato de precisión, quickstart e informe de contexto | El expediente que se quiere entregar a ChatGPT no se obtiene leyendo sólo la rama remota. |
| Entradas y resultados NiO locales sin seguimiento | 18 archivos visibles en las carpetas dirigidas `campaigns/nio_pbe_adaptive_20260928` y `campaigns/nio_pbe_p5_20260928` | Distinguir entradas/configuración de resultados versionados; los OUT/DM reales de P5 están en WSL y no se deben reemplazar por una copia incompleta. |
| Wheel local | `dist/siestaflow_hubbard-0.1.2-py3-none-any.whl` existe | La existencia del wheel no prueba que el código fuente correspondiente esté publicado en GitHub. |

El commit local seleccionó 73 archivos. Quedaron fuera el ZIP modificado,
temporales, campañas ajenas al cierre NiO y otros archivos sin seguimiento.
Los resultados NiO incluidos son archivos locales versionados; los OUT/DM
reales de P5 continúan en la ruta WSL documentada y no se sustituyeron por
una copia incompleta.

### Verificación de la selección

- Primera selección focalizada de análisis v3, reproducibilidad, runner y CLI:
  **35 passed**.
- Segunda selección de adaptación, ocupación, Cu1, benchmarks y NiO:
  **40 passed, 2 failed** por llamadas de tests que trataban métodos de
  instancia como métodos de clase. `implementador_luna` corrigió sólo las
  llamadas en los dos archivos afectados; esas **8 pruebas pasaron** después.
- Los primeros intentos de pytest dentro del sandbox no pudieron crear su
  directorio temporal; se ejecutaron las mismas selecciones con un basetemp
  nuevo en el workspace mediante el entorno autorizado. Ninguna prueba
  ejecutó SIESTA.
- El hash SHA-256 del parche experimental `f20.12` coincide con la constante
  registrada en el runner. Ese chequeo sólo valida identidad del archivo;
  no lo convierte en ruta de producto portable.

La reconstrucción del wheel a partir del commit preparado y una revisión
exhaustiva de CI remota siguen pendientes. El registro P6 conserva la
validación del wheel construido durante el cierre del 28 de septiembre.

## Estado científico y operativo que debe acompañar la publicación

El [registro final P0–P6](P0_EXECUTION_20260928.md) documenta `PASS` operativo
en P0–P6, una auditoría científica Sol `APTO` antes de P5, una única campaña
NiO P5 de 25 nodos y un wheel 0.1.2 instalado en Windows y WSL. Su estado
terminal es **`PRODUCT_BLOCKED`**, porque el valor P5 sigue siendo
`NUMERICAL_CANDIDATE_UNASSESSED` / `NOT_ESTABLISHED` frente al objetivo
científico exigido por el usuario. El [informe del cuello de botella](INFORME_CONTEXTO_CUELLO_BOTELLA_U_20260929.md)
explica las magnitudes y rutas de investigación; no reabre ni aprueba una
campaña.

Publicar sólo `README.md` o sólo los documentos nuevos induciría a pensar que
GitHub contiene el CLI/análisis v3 al que se refieren. Publicar sin el estado
terminal sugeriría que el wheel 0.1.2 implica `PRODUCT_READY`. Ambas lecturas
serían inexactas.

## Unidad mínima coherente para una actualización de GitHub

1. **Código fuente y empaquetado:** seleccionar las modificaciones de
   `src/siestaflow_hubbard/`, `pyproject.toml` y los módulos nuevos realmente
   importados por la ruta pública 0.1.2; comprobar sus relaciones de importación
   y dependencia. Registrar cualquier componente experimental fuera de alcance.
2. **Pruebas y evidencia:** incluir las pruebas pertinentes para esos módulos
   y el registro P0–P6 con los hashes de artefactos ya documentados. Usar
   referencias a los datos grandes/inmutables y su ubicación, sin fabricar un
   archivo de campaña incompleto ni reescribir reportes históricos.
3. **Documentación de usuario:** incluir `README.md`, manual, quickstart,
   changelog, eje rector, contrato de precisión e informe de contexto con el
   estado `PRODUCT_BLOCKED` visible y el alcance portable de SIESTA estándar.
4. **Revisión del conjunto seleccionado:** inspeccionar el diff final y su
   tamaño, excluir staging de compilación y temporales, y verificar que la
   versión 0.1.2 descrita puede construirse desde las fuentes publicadas.
5. **Publicación:** el primer `git push` fue rechazado por la revisión
   automática porque el repositorio es público y aún faltaba autorización
   explícita para exportar este conjunto exacto. El usuario autorizó después
   el commit, se envió la rama y se abrió el
   [PR borrador #4](https://github.com/Jairomcarmona/SIESTAFLOW_HUBBARD_RESPONSE_BACKBONE/pull/4).
   El PR está disponible para revisión; no está fusionado en `main`.

## Límite científico para esa actualización

La publicación del repositorio no cambia el resultado científico. La ruta
experimental de impresión `f20.12` requiere una SIESTA recompilada y queda
fuera del producto portable. No se altera α, SCF, ventana, proyector, estimador
ni criterio para conseguir un U deseado. El objetivo ±0.02 eV es operativo y
posterior; la cota conservadora que supera ese valor impide certificarlo bajo
el contrato actual, pero no demuestra que el error real de U lo supere.
