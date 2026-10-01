# Comparación literal de parámetros FDF y evidencia de restart

Baseline solicitado: commit `03ccd5913abdc6dd0e9e2cb59c0bc7637562c267`; tag `stage-ub-v6-20260930`; SIESTA `5.4.2`. Los valores se transcriben del `input.fdf` incluido en cada carpeta. La etiqueta `NOT_EXPLICIT_IN_FDF` significa que la palabra clave exacta no está escrita en ese archivo; no se sustituyeron defaults.

## Palabras clave y bloques solicitados

| Parámetro | FeO PBE converged (seedDM) | FeO PBE mix001_both DM producer | FeO LR-U original (100%) | FeO LR-U mix001_both (100%) | FeO LR-U seedDM (100%) | FeO LR-U continuation (25%) | NiO LR-U control |
|---|---|---|---|---|---|---|---|
| SystemName | FeO ideal AFM-II PBE Stage U-A | FeO ideal AFM-II PBE Stage U-A | FeO ideal AFM-II PBE Stage U-A | FeO ideal AFM-II PBE Stage U-A | FeO ideal AFM-II PBE Stage U-A | FeO ideal AFM-II PBE U continuation 25 percent | NiO AFM-II PBE seven-point reference |
| SystemLabel | FEO_PBE_REFERENCE | FEO_PBE_REFERENCE | FEO_PBE_REFERENCE | FEO_PBE_REFERENCE | FEO_PBE_REFERENCE | FEO_PBE_REFERENCE | NIO_PBE_REFERENCE |
| XC.Functional | GGA | GGA | GGA | GGA | GGA | GGA | GGA |
| XC.Authors | PBE | PBE | PBE | PBE | PBE | PBE | PBE |
| Spin | Spin polarized | Spin polarized | Spin polarized | Spin polarized | Spin polarized | Spin polarized | Spin polarized |
| NetCharge | NOT_EXPLICIT_IN_FDF | NOT_EXPLICIT_IN_FDF | NOT_EXPLICIT_IN_FDF | NOT_EXPLICIT_IN_FDF | NOT_EXPLICIT_IN_FDF | NOT_EXPLICIT_IN_FDF | NOT_EXPLICIT_IN_FDF |
| NumberOfAtoms | 4 | 4 | 4 | 4 | 4 | 4 | 4 |
| NumberOfSpecies | 3 | 3 | 3 | 3 | 3 | 3 | 3 |
| LatticeConstant | 4.334 Ang | 4.334 Ang | 4.334 Ang | 4.334 Ang | 4.334 Ang | 4.334 Ang | 4.17 Ang |
| LatticeVectors | %block LatticeVectors<br>  0.0 1.0 1.0<br>  0.5 0.0 0.5<br>  0.5 0.5 0.0<br>%endblock LatticeVectors | %block LatticeVectors<br>  0.0 1.0 1.0<br>  0.5 0.0 0.5<br>  0.5 0.5 0.0<br>%endblock LatticeVectors | %block LatticeVectors<br>  0.0 1.0 1.0<br>  0.5 0.0 0.5<br>  0.5 0.5 0.0<br>%endblock LatticeVectors | %block LatticeVectors<br>  0.0 1.0 1.0<br>  0.5 0.0 0.5<br>  0.5 0.5 0.0<br>%endblock LatticeVectors | %block LatticeVectors<br>  0.0 1.0 1.0<br>  0.5 0.0 0.5<br>  0.5 0.5 0.0<br>%endblock LatticeVectors | %block LatticeVectors<br>  0.0 1.0 1.0<br>  0.5 0.0 0.5<br>  0.5 0.5 0.0<br>%endblock LatticeVectors | %block LatticeVectors<br>  0.0  1.0  1.0<br>  0.5  0.0  0.5<br>  0.5  0.5  0.0<br>%endblock LatticeVectors |
| AtomicCoordinatesAndAtomicSpecies | %block AtomicCoordinatesAndAtomicSpecies<br>  0.00 0.00 0.00 1 # FeLR0 / AFM-II A<br>  0.50 0.00 0.00 2 # FeLR1 / AFM-II B<br>  0.25 0.50 0.50 3 # O<br>  0.75 0.50 0.50 3 # O<br>%endblock AtomicCoordinatesAndAtomicSpecies | %block AtomicCoordinatesAndAtomicSpecies<br>  0.00 0.00 0.00 1 # FeLR0 / AFM-II A<br>  0.50 0.00 0.00 2 # FeLR1 / AFM-II B<br>  0.25 0.50 0.50 3 # O<br>  0.75 0.50 0.50 3 # O<br>%endblock AtomicCoordinatesAndAtomicSpecies | %block AtomicCoordinatesAndAtomicSpecies<br>  0.00 0.00 0.00 1 # FeLR0 / AFM-II A<br>  0.50 0.00 0.00 2 # FeLR1 / AFM-II B<br>  0.25 0.50 0.50 3 # O<br>  0.75 0.50 0.50 3 # O<br>%endblock AtomicCoordinatesAndAtomicSpecies | %block AtomicCoordinatesAndAtomicSpecies<br>  0.00 0.00 0.00 1 # FeLR0 / AFM-II A<br>  0.50 0.00 0.00 2 # FeLR1 / AFM-II B<br>  0.25 0.50 0.50 3 # O<br>  0.75 0.50 0.50 3 # O<br>%endblock AtomicCoordinatesAndAtomicSpecies | %block AtomicCoordinatesAndAtomicSpecies<br>  0.00 0.00 0.00 1 # FeLR0 / AFM-II A<br>  0.50 0.00 0.00 2 # FeLR1 / AFM-II B<br>  0.25 0.50 0.50 3 # O<br>  0.75 0.50 0.50 3 # O<br>%endblock AtomicCoordinatesAndAtomicSpecies | %block AtomicCoordinatesAndAtomicSpecies<br>  0.00 0.00 0.00 1 # FeLR0 / AFM-II A<br>  0.50 0.00 0.00 2 # FeLR1 / AFM-II B<br>  0.25 0.50 0.50 3 # O<br>  0.75 0.50 0.50 3 # O<br>%endblock AtomicCoordinatesAndAtomicSpecies | %block AtomicCoordinatesAndAtomicSpecies<br>  0.00  0.00  0.00  1  # NiLR0<br>  0.50  0.00  0.00  2  # NiLR1<br>  0.25  0.50  0.50  3  # O<br>  0.75  0.50  0.50  3  # O<br>%endblock AtomicCoordinatesAndAtomicSpecies |
| PAO.BasisSize | DZP | DZP | DZP | DZP | DZP | DZP | DZP |
| PAO.EnergyShift | 0.005 Ry | 0.005 Ry | 0.005 Ry | 0.005 Ry | 0.005 Ry | 0.005 Ry | 0.005 Ry |
| PAO.SplitNorm | 0.15 | 0.15 | 0.15 | 0.15 | 0.15 | 0.15 | 0.15 |
| PAO.BasisType | split | split | split | split | split | split | split |
| MeshCutoff | 200 Ry | 200 Ry | 200 Ry | 200 Ry | 200 Ry | 200 Ry | 200 Ry |
| kgrid_Monkhorst_Pack | %block kgrid_Monkhorst_Pack<br>  2 0 0 0.0<br>  0 4 0 0.0<br>  0 0 4 0.0<br>%endblock kgrid_Monkhorst_Pack | %block kgrid_Monkhorst_Pack<br>  2 0 0 0.0<br>  0 4 0 0.0<br>  0 0 4 0.0<br>%endblock kgrid_Monkhorst_Pack | %block kgrid_Monkhorst_Pack<br>  2 0 0 0.0<br>  0 4 0 0.0<br>  0 0 4 0.0<br>%endblock kgrid_Monkhorst_Pack | %block kgrid_Monkhorst_Pack<br>  2 0 0 0.0<br>  0 4 0 0.0<br>  0 0 4 0.0<br>%endblock kgrid_Monkhorst_Pack | %block kgrid_Monkhorst_Pack<br>  2 0 0 0.0<br>  0 4 0 0.0<br>  0 0 4 0.0<br>%endblock kgrid_Monkhorst_Pack | %block kgrid_Monkhorst_Pack<br>  2 0 0 0.0<br>  0 4 0 0.0<br>  0 0 4 0.0<br>%endblock kgrid_Monkhorst_Pack | %block kgrid_Monkhorst_Pack<br>  2 0 0 0.0<br>  0 4 0 0.0<br>  0 0 4 0.0<br>%endblock kgrid_Monkhorst_Pack |
| OccupationFunction | FD | FD | FD | FD | FD | FD | NOT_EXPLICIT_IN_FDF |
| ElectronicTemperature | 300 K | 300 K | 300 K | 300 K | 300 K | 300 K | NOT_EXPLICIT_IN_FDF |
| MaxSCFIterations | 300 | 300 | 300 | 300 | 300 | 300 | 300 |
| SCF.MustConverge | true | true | true | true | true | true | true |
| SCF.Mix | Hamiltonian | Hamiltonian | Hamiltonian | Hamiltonian | Hamiltonian | Hamiltonian | Hamiltonian |
| SCF.Mix.First | NOT_EXPLICIT_IN_FDF | NOT_EXPLICIT_IN_FDF | NOT_EXPLICIT_IN_FDF | NOT_EXPLICIT_IN_FDF | NOT_EXPLICIT_IN_FDF | NOT_EXPLICIT_IN_FDF | NOT_EXPLICIT_IN_FDF |
| SCF.Mix.Spin | NOT_EXPLICIT_IN_FDF | NOT_EXPLICIT_IN_FDF | NOT_EXPLICIT_IN_FDF | NOT_EXPLICIT_IN_FDF | NOT_EXPLICIT_IN_FDF | NOT_EXPLICIT_IN_FDF | NOT_EXPLICIT_IN_FDF |
| SCF.Mixer.Method | Pulay | Pulay | Pulay | Pulay | Pulay | Pulay | Pulay |
| SCF.Mixer.Variant | NOT_EXPLICIT_IN_FDF | NOT_EXPLICIT_IN_FDF | NOT_EXPLICIT_IN_FDF | NOT_EXPLICIT_IN_FDF | NOT_EXPLICIT_IN_FDF | NOT_EXPLICIT_IN_FDF | NOT_EXPLICIT_IN_FDF |
| SCF.Mixer.Weight | 0.01 | 0.01 | 0.05 | 0.01 | 0.01 | 0.01 | 0.05 |
| SCF.Mixer.History | 8 | 8 | 8 | 8 | 8 | 8 | 8 |
| SCF.Mixer.Restart | NOT_EXPLICIT_IN_FDF | NOT_EXPLICIT_IN_FDF | NOT_EXPLICIT_IN_FDF | NOT_EXPLICIT_IN_FDF | NOT_EXPLICIT_IN_FDF | NOT_EXPLICIT_IN_FDF | NOT_EXPLICIT_IN_FDF |
| SCF.Mixer.Restart.Save | NOT_EXPLICIT_IN_FDF | NOT_EXPLICIT_IN_FDF | NOT_EXPLICIT_IN_FDF | NOT_EXPLICIT_IN_FDF | NOT_EXPLICIT_IN_FDF | NOT_EXPLICIT_IN_FDF | NOT_EXPLICIT_IN_FDF |
| SCF.Mixer.Kick | NOT_EXPLICIT_IN_FDF | NOT_EXPLICIT_IN_FDF | NOT_EXPLICIT_IN_FDF | NOT_EXPLICIT_IN_FDF | NOT_EXPLICIT_IN_FDF | NOT_EXPLICIT_IN_FDF | NOT_EXPLICIT_IN_FDF |
| DM.MixingWeight | 0.01 | 0.01 | 0.05 | 0.01 | 0.01 | 0.01 | 0.05 |
| DM.NumberPulay | 5 | 5 | 5 | 5 | 5 | 5 | 5 |
| DM.UseSaveDM | true | false | false | false | true | true | false |
| SCF.DM.Converge | true | true | true | true | true | true | true |
| SCF.DM.Tolerance | 1.0e-5 | 1.0e-5 | 1.0e-5 | 1.0e-5 | 1.0e-5 | 1.0e-5 | 1.0e-5 |
| SCF.H.Converge | true | true | true | true | true | true | true |
| SCF.H.Tolerance | 1.0e-4 eV | 1.0e-4 eV | 1.0e-4 eV | 1.0e-4 eV | 1.0e-4 eV | 1.0e-4 eV | 1.0e-4 eV |
| DM.InitSpin | %block DM.InitSpin<br>  1 +4.0<br>  2 -4.0<br>  3 0.0<br>  4 0.0<br>%endblock DM.InitSpin | %block DM.InitSpin<br>  1 +4.0<br>  2 -4.0<br>  3 0.0<br>  4 0.0<br>%endblock DM.InitSpin | %block DM.InitSpin<br>  1 +4.0<br>  2 -4.0<br>  3 0.0<br>  4 0.0<br>%endblock DM.InitSpin | %block DM.InitSpin<br>  1 +4.0<br>  2 -4.0<br>  3 0.0<br>  4 0.0<br>%endblock DM.InitSpin | %block DM.InitSpin<br>  1 +4.0<br>  2 -4.0<br>  3 0.0<br>  4 0.0<br>%endblock DM.InitSpin | %block DM.InitSpin<br>  1 +4.0<br>  2 -4.0<br>  3 0.0<br>  4 0.0<br>%endblock DM.InitSpin | %block DM.InitSpin<br>  1 +2.0<br>  2 -2.0<br>  3  0.0<br>  4  0.0<br>%endblock DM.InitSpin |
| DFTU.ProjectorGenerationMethod | 2 | 2 | 2 | 2 | 2 | 2 | 2 |
| DFTU.PotentialShift | false | false | false | false | false | false | false |
| DFTU.FirstIteration | true | true | true | true | true | true | true |
| DFTU.ThresholdTol | NOT_EXPLICIT_IN_FDF | NOT_EXPLICIT_IN_FDF | NOT_EXPLICIT_IN_FDF | NOT_EXPLICIT_IN_FDF | NOT_EXPLICIT_IN_FDF | NOT_EXPLICIT_IN_FDF | NOT_EXPLICIT_IN_FDF |
| DFTU.PopTol | NOT_EXPLICIT_IN_FDF | NOT_EXPLICIT_IN_FDF | NOT_EXPLICIT_IN_FDF | NOT_EXPLICIT_IN_FDF | NOT_EXPLICIT_IN_FDF | NOT_EXPLICIT_IN_FDF | NOT_EXPLICIT_IN_FDF |
| DFTU.Proj | %block DFTU.proj<br>  FeLR0 1<br>  3 2<br>  0.0000 0.0000<br>  3.0000 0.0500<br>  FeLR1 1<br>  3 2<br>  0.0000 0.0000<br>  3.0000 0.0500<br>%endblock DFTU.proj | %block DFTU.proj<br>  FeLR0 1<br>  3 2<br>  0.0000 0.0000<br>  3.0000 0.0500<br>  FeLR1 1<br>  3 2<br>  0.0000 0.0000<br>  3.0000 0.0500<br>%endblock DFTU.proj | %block DFTU.proj<br>  FeLR0 1<br>  3 2<br>  5.638281766243177  0.000000000000000<br>  3.0000 0.0500<br>  FeLR1 1<br>  3 2<br>  5.638315883828983  0.000000000000000<br>  3.0000 0.0500<br>%endblock DFTU.proj | %block DFTU.proj<br>  FeLR0 1<br>  3 2<br>  5.638281766243177  0.000000000000000<br>  3.0000 0.0500<br>  FeLR1 1<br>  3 2<br>  5.638315883828983  0.000000000000000<br>  3.0000 0.0500<br>%endblock DFTU.proj | %block DFTU.proj<br>  FeLR0 1<br>  3 2<br>  5.638281766243177  0.000000000000000<br>  3.0000 0.0500<br>  FeLR1 1<br>  3 2<br>  5.638315883828983  0.000000000000000<br>  3.0000 0.0500<br>%endblock DFTU.proj | %block DFTU.proj<br>  FeLR0 1<br>  3 2<br>  1.4095704415607942 0.000000000000000<br>  3.0000 0.0500<br>  FeLR1 1<br>  3 2<br>  1.4095789709572458 0.000000000000000<br>  3.0000 0.0500<br>%endblock DFTU.proj | %block DFTU.proj<br>  NiLR0  1<br>  3 2<br>  6.864267700049239  0.000000000000000<br>  3.0000 0.0500<br>  NiLR1  1<br>  3 2<br>  6.864387475210124  0.000000000000000<br>  3.0000 0.0500<br>%endblock DFTU.proj |

## Sintaxis literal de `%block DFTU.proj` FeO

Sintaxis observada en los cuatro FDF LR-U FeO (sin correcciones): cada especie aparece como etiqueta + cantidad de proyectores; después siguen `n l`, `U J` y `rc omega`. El FDF PBE contiene el mismo bloque con U=J=0. La notación siguiente solo separa literalmente los seis campos pedidos:

| Corrida | Especie | n_proj | n | l | U (eV) | J (eV) | rc | omega |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| FeO PBE converged (seedDM) | FeLR0 | 1 | 3 | 2 | 0.0000 | 0.0000 | 3.0000 | 0.0500 |
| FeO PBE converged (seedDM) | FeLR1 | 1 | 3 | 2 | 0.0000 | 0.0000 | 3.0000 | 0.0500 |
| FeO PBE mix001_both DM producer | FeLR0 | 1 | 3 | 2 | 0.0000 | 0.0000 | 3.0000 | 0.0500 |
| FeO PBE mix001_both DM producer | FeLR1 | 1 | 3 | 2 | 0.0000 | 0.0000 | 3.0000 | 0.0500 |
| FeO LR-U original (100%) | FeLR0 | 1 | 3 | 2 | 5.638281766243177 | 0.000000000000000 | 3.0000 | 0.0500 |
| FeO LR-U original (100%) | FeLR1 | 1 | 3 | 2 | 5.638315883828983 | 0.000000000000000 | 3.0000 | 0.0500 |
| FeO LR-U mix001_both (100%) | FeLR0 | 1 | 3 | 2 | 5.638281766243177 | 0.000000000000000 | 3.0000 | 0.0500 |
| FeO LR-U mix001_both (100%) | FeLR1 | 1 | 3 | 2 | 5.638315883828983 | 0.000000000000000 | 3.0000 | 0.0500 |
| FeO LR-U seedDM (100%) | FeLR0 | 1 | 3 | 2 | 5.638281766243177 | 0.000000000000000 | 3.0000 | 0.0500 |
| FeO LR-U seedDM (100%) | FeLR1 | 1 | 3 | 2 | 5.638315883828983 | 0.000000000000000 | 3.0000 | 0.0500 |
| FeO LR-U continuation (25%) | FeLR0 | 1 | 3 | 2 | 1.4095704415607942 | 0.000000000000000 | 3.0000 | 0.0500 |
| FeO LR-U continuation (25%) | FeLR1 | 1 | 3 | 2 | 1.4095789709572458 | 0.000000000000000 | 3.0000 | 0.0500 |

### Valores de U cambiantes entre niveles de FeO

Transcripción numérica de los U/J asociados a FeLR0 y FeLR1; no incluye valoración de corrección científica:

| Estado | FeLR0 U | FeLR0 J | FeLR1 U | FeLR1 J |
|---|---:|---:|---:|---:|
| FeO PBE converged (seedDM) | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| FeO LR-U continuation (25%) | 1.4095704415607942 | 0.000000000000000 | 1.4095789709572458 | 0.000000000000000 |
| FeO LR-U seedDM (100%) | 5.638281766243177 | 0.000000000000000 | 5.638315883828983 | 0.000000000000000 |

## Restart y archivos DM: evidencia

La existencia actual de un `.DM` no se tomó como prueba de lectura ni de presencia pre-lanzamiento. Para “presente antes del lanzamiento” se exige una ruta de origen en `run_record.json` o evidencia equivalente; cuando no está registrada se indica `UNKNOWN`. Ningún archivo binario `.DM` se incluyó en esta exportación.

| Corrida FeO | DM.UseSaveDM | SystemLabel | Archivo DM antes del lanzamiento | tamaño | Lectura reportada por SIESTA |
|---|---|---|---|---:|---|
| FeO PBE converged (seedDM) | true | FEO_PBE_REFERENCE | FEO_PBE_REFERENCE.DM | 2886548 | YES |
| FeO PBE mix001_both DM producer | false | FEO_PBE_REFERENCE | UNKNOWN (no prelaunch DM snapshot/seed path in run record) | UNKNOWN prelaunch; a file of this name is present in the post-run source directory | UNKNOWN (no explicit read result in siesta.out) |
| FeO LR-U original (100%) | false | FEO_PBE_REFERENCE | UNKNOWN (no prelaunch DM snapshot/seed path in run record) | UNKNOWN prelaunch; a file of this name is present in the post-run source directory | UNKNOWN (no explicit read result in siesta.out) |
| FeO LR-U mix001_both (100%) | false | FEO_PBE_REFERENCE | UNKNOWN (no prelaunch DM snapshot/seed path in run record) | UNKNOWN prelaunch; a file of this name is present in the post-run source directory | UNKNOWN (no explicit read result in siesta.out) |
| FeO LR-U seedDM (100%) | true | FEO_PBE_REFERENCE | FEO_PBE_REFERENCE.DM | 2886548 | YES |
| FeO LR-U continuation (25%) | true | FEO_PBE_REFERENCE | FEO_PBE_REFERENCE.DM | 2886548 (run_record DM source; actual binary omitted) | YES |

### Mensajes de salida relacionados con DM/restart

Extractos literales con dos líneas de contexto cuando existen; la salida completa se conserva junto a cada corrida.

#### FeO PBE converged (seedDM)
```text
892: redata: Using DFT-D3 dispersion                     =   F
893: redata: Using Saved Data (generic)                  =   F
894: redata: Use continuation files for DM               =   T
895: redata: Neglect nonoverlap interactions             =   F
896: redata: Method of Calculation                       = Diagonalization
996: 
997: Attempting to read DM from file... Succeeded...
998: DM from file:
999: <dSpData2D:IO-DM: FEO_PBE_REFERENCE.DM
1000:   <sparsity:IO-DM: FEO_PBE_REFERENCE.DM
```

#### FeO PBE mix001_both DM producer
```text
892: redata: Using DFT-D3 dispersion                     =   F
893: redata: Using Saved Data (generic)                  =   F
894: redata: Use continuation files for DM               =   F
895: redata: Neglect nonoverlap interactions             =   F
896: redata: Method of Calculation                       = Diagonalization
```

#### FeO LR-U original (100%)
```text
892: redata: Using DFT-D3 dispersion                     =   F
893: redata: Using Saved Data (generic)                  =   F
894: redata: Use continuation files for DM               =   F
895: redata: Neglect nonoverlap interactions             =   F
896: redata: Method of Calculation                       = Diagonalization
```

#### FeO LR-U mix001_both (100%)
```text
892: redata: Using DFT-D3 dispersion                     =   F
893: redata: Using Saved Data (generic)                  =   F
894: redata: Use continuation files for DM               =   F
895: redata: Neglect nonoverlap interactions             =   F
896: redata: Method of Calculation                       = Diagonalization
```

#### FeO LR-U seedDM (100%)
```text
892: redata: Using DFT-D3 dispersion                     =   F
893: redata: Using Saved Data (generic)                  =   F
894: redata: Use continuation files for DM               =   T
895: redata: Neglect nonoverlap interactions             =   F
896: redata: Method of Calculation                       = Diagonalization
996: 
997: Attempting to read DM from file... Succeeded...
998: DM from file:
999: <dSpData2D:IO-DM: FEO_PBE_REFERENCE.DM
1000:   <sparsity:IO-DM: FEO_PBE_REFERENCE.DM
```

#### FeO LR-U continuation (25%)
```text
892: redata: Using DFT-D3 dispersion                     =   F
893: redata: Using Saved Data (generic)                  =   F
894: redata: Use continuation files for DM               =   T
895: redata: Neglect nonoverlap interactions             =   F
896: redata: Method of Calculation                       = Diagonalization
996: 
997: Attempting to read DM from file... Succeeded...
998: DM from file:
999: <dSpData2D:IO-DM: FEO_PBE_REFERENCE.DM
1000:   <sparsity:IO-DM: FEO_PBE_REFERENCE.DM
```


## Resumen numérico del historial SCF fallido

La tabla informa mínimos por serie y fila final del historial impreso; no asigna una clasificación. En `SCF_HISTORY_COMPARISON.csv` están cada décima iteración y las últimas 20 consecutivas, sin duplicados. Energías en eV; dHmax en eV; momento = escalar final de `spin moment: {S}` cuando está impreso.

| Corrida | filas SCF | mínimo dDmax (iter.) | mínimo dHmax eV (iter.) | finales: iter / FreeEng / dDmax / Ef / dHmax / spin |
|---|---:|---|---|---|
| feo_lru_original | 300 | 0.000183 (279) | 0.019377 (293) | 300 / -7716.067219 / 0.015547 / -3.772752 / 0.052055 / -0.00000 |
| feo_lru_mix001 | 300 | 1.3e-05 (216) | 0.008327 (278) | 300 / -7714.148606 / 0.001225 / -3.630413 / 0.02193 / 0.00893 |
| feo_lru_seedDM | 300 | 2e-06 (167) | 0.014539 (241) | 300 / -7716.065312 / 0.003279 / -3.773887 / 0.03277 / -0.00000 |
| feo_lru_continuation_25pct | 300 | 0.000141 (5) | 0.023608 (298) | 300 / -7717.919576 / 0.001686 / -3.561140 / 0.026618 / -0.00000 |
