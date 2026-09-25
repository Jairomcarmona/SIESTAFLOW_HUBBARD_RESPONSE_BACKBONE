# Auditoría fuente de la rama BARE: SIESTA 5.4.2

## Alcance y trazabilidad

Se inspeccionó de forma estática la etiqueta oficial `5.4.2` del repositorio
SIESTA, clonada en `third_party/siesta-5.4.2-source-audit`, con `HEAD`
`e486d12067b96ff688179f0496d0ec21b6fae0ab`. No se compiló ni ejecutó
SIESTA, MPI, Hydra o Slurm durante esta auditoría.

Este documento describe la semántica de la fuente publicada. Aún debe
compararse el binario institucional con esa versión mediante su versión,
hash/receta de build y un control pequeño; no se presupone identidad perfecta
de un binario modificado por un administrador.

## Hechos verificables en la fuente

1. `SCF.MustConverge` se lee en `Src/read_options.F90` y sólo decide si una
   falta de convergencia al final del bucle provoca `ABNORMAL_TERMINATION`.
   No congela Hartree--XC ni transforma por sí misma un cálculo en BARE.
2. `DFTU.PotentialShift=true` fuerza `DFTU.FirstIteration=true` en
   `Src/dftu_specs.f`. El manual de 5.4.2 declara que el desplazamiento local
   permite registrar el cambio de poblaciones y obtener `U` siguiendo
   Cococcioni--de Gironcoli.
3. La mezcla Hamiltoniana es el valor predeterminado (`Src/read_options.F90`).
   Con ella `Src/siesta_forces.F90` realiza una preparación
   `setup_hamiltonian(0)` antes del bucle SCF. En el primer paso real ejecuta
   `compute_DM(1)` y después `setup_hamiltonian(1)`.
4. `setup_hamiltonian` llama `hubbard_term` con `Dscf`. En la ruta de
   `PotentialShift`, esa rutina construye el desplazamiento local y emite las
   poblaciones proyectadas (`Src/dftu.F`). Por tanto, con mezcla Hamiltoniana,
   la población emitida durante `setup_hamiltonian(1)` se calcula desde la DM
   producida por la diagonalización del Hamiltoniano preparado con la DM padre
   y el desplazamiento. La reconstrucción del Hamiltoniano ocurre después de
   esa diagonalización.

## Consecuencia para la selección BARE

La ocupación candidata a \(n^{(0)}\) en esta ruta es la **segunda** impresión
inicial de `hubbard_term` con contador `1`: la que aparece después de
`stepf: Fermi-Dirac step function` y antes de la primera línea `scf: 1`.
La primera impresión con contador `1` pertenece al prepaso `iscf=0` y refleja
la DM padre. El contador DFT+U no identifica por sí solo el paso SCF porque se
reinicia para `iscf <= 1`.

En contraste, bajo `SCF.Mix density`, la fuente ejecuta
`setup_hamiltonian(iscf)` antes de `compute_DM(iscf)`. La primera población
perturbada imprimible aparece en el siguiente armado de Hamiltoniano, cuando
la ruta ya ha incorporado la DM de respuesta. Esa configuración no debe
promoverse automáticamente como \(\chi^0\) mediante la regla anterior.

## Hallazgo sobre el código actual

El constructor histórico materializa BARE con `SCF.Mix density`, dos pasos y
el selector histórico busca una pseudo-`scf_iteration == 2`. Esa regla no se
deduce de la fuente 5.4.2 y no puede certificarse como BARE Cococcioni bajo el
perfil de mezcla Hamiltoniana descrito aquí.

Esto no demuestra que los números previos sean físicamente inútiles; sí
significa que deben clasificarse como resultados de la **semántica histórica**
hasta que se haga la comparación controlada. No se debe reutilizar la etiqueta
`VERIFIED_BARE` para ellos.

## Perfil correctivo integrado de forma aislada

Se incorporó el perfil
`siesta-5.4.2-potential-shift-hamiltonian-v1` en
`src/siestaflow_hubbard/siesta_backend/siesta542_bare_profile.py`. Exige:

- `DFTU.PotentialShift true`, `DFTU.FirstIteration true`;
- `DM.UseSaveDM true` y DM padre con hash coincidente;
- `SCF.Mix Hamiltonian` explícito (sin depender del valor predeterminado);
- un único paso SCF útil para el BARE; `SCF.MustConverge false` sólo permite
  terminar el control no autoconsistente, no es evidencia de congelamiento;
- un parser de contexto que seleccione el bloque posterior a `stepf` y previo
  a `scf: 1`, no un contador genérico de DFT+U;
- una prueba de regresión sobre salida real conservada y un control local/HPC
  mínimo con el módulo institucional.

El perfil selecciona únicamente el bloque de población situado estrictamente
entre esos dos marcadores, y rechaza los resultados sin la firma de mezcla
Hamiltoniana. Sus pruebas focalizadas cubren la salida real conservada de MnO,
la materialización explícita de FDF, mezcla de densidad y marcadores ausentes.

La integración al ejecutor de producción permanece intencionalmente separada:
el validador BARE histórico sigue fallando cerrado. Antes de autorizar una
campaña nueva, debe enlazarse este perfil a una receta/versión verificable del
binario institucional y hacer un control pequeño que demuestre esa firma.
Eso evita tanto alterar SCREENED como reinterpretar campañas archivadas.
