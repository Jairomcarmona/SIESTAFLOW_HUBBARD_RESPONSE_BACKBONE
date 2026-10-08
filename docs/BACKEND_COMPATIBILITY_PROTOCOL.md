# Backend compatibility matrix

A campaign does not authorize BARE semantics based on a module name, an
institutional path, or an exit code. Admission is a pure function of:

\[
(\mathrm{backend\_id},\ \mathrm{version},\ \mathrm{SHA256(executable)},\
 \mathrm{scientific\ profile}) .
\]

`BackendCompatibilityRegistry` stores this matrix as canonical JSON using the
`backend_compatibility_v1` schema. An entry must be created through a
scientific/documentary review of the identified backend; entries are not
created by observing an ordinary run.

The portable workflow is:

1. The private plugin explicitly selects the executable and obtains version
   text through its local mechanism.
2. `identify_backend` computes the SHA-256 without searching `PATH`, loading
   modules, or launching SIESTA.
3. `admit_siesta542_potential_shift_hamiltonian` requires an exact match with
   the matrix.
4. Only a valid admission allows the
   `siesta-5.4.2-potential-shift-hamiltonian-v1` profile to be used by the
   materializer and BARE validator.

No match, a different version, a different hash, or a blocked entry stops the
campaign before BARE evidence is accepted. This does not require repeating a
physical validation for each cluster: the same identified backend reuses the
same explicit entry. A different binary is a new combination and remains
blocked until it receives a traceable decision.

## Registering a reviewed combination

The private plugin captures its version banner in a text file and passes the
executable it will actually declare to the launcher. From the project root:

```bash
PYTHONPATH=src python tools/register_siesta542_backend.py \
  --registry private/backend_compatibility.json \
  --executable /path/to/siesta \
  --version-text private/siesta-version.txt \
  --reason 'documented review of the backend and scientific profile' \
  --write
```

The tool only reads the executable to calculate its SHA-256 and reads the
already captured text; it does not execute SIESTA or load modules. Without
`--write`, it prints canonical JSON as a preview and changes nothing.
