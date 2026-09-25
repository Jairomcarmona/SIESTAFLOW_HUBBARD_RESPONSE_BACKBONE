# Cu3N: auditoría de reducción por simetría

## Alcance y procedencia

Este registro analiza de forma *offline* la campaña
`CU3N_PBE_LRU_SC222_RC3p0_V1` contenida en el archivo de evidencia original
`cu3n_mathematical_evidence_20260812T210120Z.tar.gz`.

- SHA-256 del archivo: `76f5effd3d124d1723725a9f30d4ac17056b4d892f73b4c14c6028f96a87f11f`.
- El análisis usó `runs/00_REFERENCE/siesta.fdf`,
  `runs/00_REFERENCE/siesta.out`, `occupations.json`, `chi0.csv`, `chi.csv` y
  `U_by_site.csv` del mismo archivo.
- No se ejecutó SIESTA ni se modificó la campaña original.

## Puerta de estado magnético

La FDF declara `Spin non-polarized`. La salida de SIESTA 5.4.2 confirma
`Spin configuration = none`, un único componente de espín y simetría de
reversión temporal activa, además de cierre normal. Por ello se certificó el
campo de momentos nulo para los 32 átomos; no se usó `DM.InitSpin` como
evidencia.

## Resultado geométrico y de subespacio

El auditor conservador encontró 384 operaciones geométricas candidatas y ocho
operaciones que preservan simultáneamente geometría, estado no magnético y la
definición local del subespacio. Las rotaciones orbitales no se certifican: el
resultado sólo permite las traslaciones que preservan las definiciones
explícitas del proyector.

Los 24 Cu correlacionados se separan en tres órbitas de ocho sitios:

| órbita | índices de Cu correlacionados |
| --- | --- |
| X | 0, 3, 6, 9, 12, 15, 18, 21 |
| Y | 1, 4, 7, 10, 13, 16, 19, 22 |
| Z | 2, 5, 8, 11, 14, 17, 20, 23 |

## Consistencia de la reconstrucción archivada

Para cada una de las ocho operaciones certificadas se evaluó

\[
\max_{I,J}\left|\chi^{(0)}_{IJ}-\chi^{(0)}_{p(I)p(J)}\right|,
\qquad
\max_{I,J}\left|\chi_{IJ}-\chi_{p(I)p(J)}\right|.
\]

Los dos residuales máximos fueron exactamente `0.0` en los CSV archivados. Los
intervalos máximo-mínimo de \(U_I\) dentro de las órbitas X, Y y Z fueron,
respectivamente, \(8.88\times10^{-15}\), \(0.0\) y
\(1.95\times10^{-14}\) eV. Esto confirma que los índices, las permutaciones
y la reconstrucción almacenada son internamente consistentes.

## Límite científico: no es todavía una validación independiente

El archivo contiene doce perturbaciones explícitas: \(\pm\alpha\), BARE y
SCREENED para los representantes X, Y y Z. Las columnas de los otros 21 Cu
fueron generadas por reconstrucción de simetría. Por tanto, la igualdad exacta
de las matrices anteriores es esperable y **no** prueba por sí sola que una
segunda perturbación SIESTA de un sitio trasladado reproduzca su representante.

Antes de habilitar la reducción automática en campañas de producción debe
ejecutarse una prueba sombra por órbita: seleccionar un Cu trasladado que no
haya sido perturbado, correr BARE \(\pm\alpha\) y SCREENED \(\pm\alpha\), y
comparar su columna directamente calculada con la columna trasladada del
representante. Sólo si esas cuatro respuestas satisfacen tolerancias físicas y
numéricas predefinidas puede la campaña familiar autorizar la reducción.
