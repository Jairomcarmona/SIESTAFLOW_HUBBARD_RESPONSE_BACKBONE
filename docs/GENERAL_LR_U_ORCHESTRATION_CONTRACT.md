# Contrato general de orquestación LR-U

## Propósito

Este proyecto implementa un flujo de respuesta lineal de diferencias finitas
para un backend SIESTA. No es una colección de campañas por material. El
núcleo científico recibe una estructura FDF, subespacios DFT+U, evidencia del
estado de referencia y una política declarada; el perfil de ejecución aporta
el planificador y el entorno de cómputo sin entrar en la matemática.

## Flujo y puertas científicas

```text
entrada FDF + PSML
  -> auditor de subespacio / procedencia
  -> referencia SIESTA convergida y estado magnético evidenciado
  -> plan de simetría provisional
  -> perturbaciones BARE y SCREENED con +/- alpha
  -> sombras directas de las clases reducibles
  -> autorización o expansión explícita
  -> chi0, chi, inversión directa, U y evidencia final
```

Ninguna puerta puede ser sustituida por un valor por defecto, por un promedio
ni por una pseudoinversa. Un fallo o evidencia incompleta produce una campaña
explícita, no una reducción silenciosa.

## Núcleo independiente del backend y del clúster

`domain.symmetry_reduction` define:

- `SymmetryReductionPolicy`: amplitud de perturbación y tolerancias fijadas
  **antes** de ejecutar;
- `SymmetryReductionPlan`: representantes, sombras y las cuatro respuestas
  BARE/SCREENED con signos opuestos para cada sitio requerido;
- `ShadowObservation`: comparación completa de ocupaciones, columnas
  `chi0` y `chi` frente a la transformación predicha;
- `ReductionAuthorization`: autorización de reducción o expansión de las
  órbitas rechazadas a perturbaciones explícitas.

No contiene símbolos químicos, nombres de materiales, rutas, comandos MPI,
particiones Slurm ni supuestos de supercelda. La misma lógica puede usarse
con cualquier adaptador que entregue una geometría canónica, ocupaciones y
una evidencia magnética verificable.

## Adaptador SIESTA

El adaptador FDF valida la geometría, los campos `DFTU.Proj` y los índices de
sitio. La evidencia magnética se extrae de la salida final de SIESTA, no de
`DM.InitSpin`. Si no existe evidencia de referencia unida al hash exacto de
la FDF, el adaptador genera un plan explícito.

Por defecto sólo se permiten operaciones con rotación identidad. Una
rotación orbital no se deduce de coordenadas: requiere que el backend
certifique que el subespacio y la ocupación escalar son invariantes.

## Reducción y prueba sombra

Una clase de equivalencia es provisional. Para cada clase reducible, el
planificador selecciona determinísticamente un representante y un miembro
distinto unido por una operación permitida. Ejecuta ambos con BARE/SCREENED y
`+/- alpha`.

La reducción se autoriza únicamente si las cuatro salidas son científicamente
válidas y si los residuales de ocupación, `chi0` y `chi` quedan bajo los
umbrales publicados. Una sombra fallida no se promedia: toda su órbita pasa a
expansión explícita.

## Ejecución y reanudación

El plan no presupone Slurm. Un adaptador de ejecución materializa FDFs,
ordena nodos del DAG y registra cada resultado validado. Un perfil privado de
clúster puede ejecutar las tareas secuencialmente dentro de una asignación
grande o con otro modelo de recursos. La reanudación debe reutilizar sólo
resultados cuya procedencia y validación sigan siendo válidas.

## Estado de implementación

El núcleo de planificación, autorización y expansión explícita está
implementado y probado localmente. El materializador SIESTA consume ahora un
`PerturbationSpec` y preserva la FDF auditada mientras cambia sólo el sitio
objetivo y los controles BARE/SCREENED. El DAG científico neutral representa
referencia, respuestas, compuerta de sombras y expansión posterior a un
rechazo.

## Candados de implementación y alcance

El núcleo incorpora ahora un ejecutor reanudable neutral al planificador. Un
adaptador privado de ejecución (`local` o `Slurm`) recibe un nodo listo y debe
devolver una evidencia validada; el núcleo conserva un *checkpoint* JSON
ligado al hash exacto del DAG. Un DAG distinto no puede reutilizarlo. Un nodo
hijo nunca inicia hasta que todos sus padres estén validados y la primera
salida terminal inválida detiene el avance. Esto permite reutilizar una
referencia o una perturbación certificada sin reutilizar resultados de otra
política científica.

El adaptador SIESTA dispone de un `SiestaCommandFactory` que materializa cada
referencia o perturbación en un directorio nuevo, copia exclusivamente los
artefactos estáticos declarados, preserva la FDF de referencia y construye un
comando Hydra desde un perfil ya validado. El comando usa entrada, salida y
error explícitos, sin *shell* ni un `sbatch` por nodo. El *wrapper* privado de
la asignación sigue siendo responsable de cargar módulos; el núcleo no ejecuta
comandos de módulo ni conoce el sitio.

El factory y el validador no autorizan todavía una campaña BARE de producción
por sí solos: un certificado BARE debe ligarse a la salida y traza nativa
producidas **después** de esa ejecución. Si no existe tal sidecar verificable,
el nodo BARE falla cerrado. La implementación pendiente es un proveedor de
evidencia BARE que reciba una traza nativa sancionada; no se debe reemplazar
por heurísticas sobre el número de iteraciones SCF.

La selección adaptativa de amplitud está representada por un DAG alternativo
explícito. Para una amplitud nominal \(h\), éste materializa
\(\{-2h,-h,-h/2,0,h/2,h,2h\}\): el punto cero es la referencia y cada punto
no nulo contiene sus ramas BARE y SCREENED. La compuerta de linealidad admite
únicamente una ventana común que conserve el estado magnético, tenga señal
resuelta y pase los criterios predeclarados de residuo y deriva de pendiente.
Un fin normal de SIESTA no autoriza por sí solo la inversión de matrices.

La capacidad certificada actual del adaptador es **DFT+U escalar, colineal y
un subespacio correlacionado por sitio**. Las solicitudes no colineales, con
SOC, varios subespacios por sitio, transformaciones orbitales covariantes o
DFT+U+V se rechazan antes de materializar una FDF. Esta limitación evita el
resultado aparentemente exitoso pero físicamente mal interpretado.

Para ampliar esas capacidades hacen falta adaptadores específicos y pruebas
con evidencia real:

1. simetría cristalográfica mediante una librería canónica y simetría
   magnética basada en la salida de referencia, incluyendo la representación
   del orbital bajo cada rotación;
2. extracción de matrices espinoriales complejas para no colinealidad/SOC y
   pruebas de covariancia;
3. definición, perturbación y ensamblaje de pares intersitio para \(U+V\);
4. un plugin de ejecución local y otro Slurm que materialicen FDF, lancen el
   backend y construyan `NodeReceipt` sólo después de validar outputs.

Los ZIP de campañas históricas permanecen como fixtures de integración y
evidencia, no como reglas del software ni como perfiles públicos de clúster.
