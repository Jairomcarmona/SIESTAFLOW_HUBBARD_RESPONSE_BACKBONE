# Matriz de compatibilidad de backend

Una campaña no autoriza una semántica BARE por el nombre de un módulo, una
ruta institucional o un código de salida. La admisión es una función pura de:

\[
(\mathrm{backend\_id},\ \mathrm{version},\ \mathrm{SHA256(executable)},\
 \mathrm{scientific\ profile}) .
\]

`BackendCompatibilityRegistry` almacena esa matriz en JSON canónico con
esquema `backend_compatibility_v1`. Una entrada debe ser creada mediante una
revisión científica/documental del backend identificado; no se crean entradas
al observar una corrida ordinaria.

El flujo portátil es:

1. El plugin privado selecciona explícitamente el ejecutable y obtiene texto
   de versión por su mecanismo local.
2. `identify_backend` calcula el SHA-256 sin buscar `PATH`, cargar módulos ni
   lanzar SIESTA.
3. `admit_siesta542_potential_shift_hamiltonian` exige una coincidencia exacta
   con la matriz.
4. Sólo una admisión válida permite usar el perfil
   `siesta-5.4.2-potential-shift-hamiltonian-v1` en el materializador y el
   validador BARE.

La ausencia de coincidencia, una versión distinta, un hash distinto o una
entrada bloqueada detienen la campaña antes de que se acepte evidencia BARE.
Esto no exige repetir una validación física por clúster: el mismo backend
identificado reutiliza la misma entrada explícita. Un binario distinto es una
combinación nueva y permanece bloqueado hasta recibir una decisión trazable.

## Registro de una combinación revisada

El plugin privado captura su banner de versión en un archivo de texto y pasa
el ejecutable que realmente declarará al lanzador. Desde la raíz del proyecto:

```bash
PYTHONPATH=src python tools/register_siesta542_backend.py \
  --registry private/backend_compatibility.json \
  --executable /ruta/explicita/a/siesta \
  --version-text private/siesta-version.txt \
  --reason 'revisión documentada del backend y perfil científico' \
  --write
```

La herramienta sólo lee el ejecutable para calcular su SHA-256 y el texto ya
capturado; no ejecuta SIESTA ni carga módulos. Sin `--write` imprime el JSON
canónico como vista previa y no modifica nada.
