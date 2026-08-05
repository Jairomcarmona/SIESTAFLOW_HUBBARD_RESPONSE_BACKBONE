# Modelo de dominio

## Entidades

- `MethodologyLock`
- `Campaign`
- `GeometryIdentity`
- `CorrelatedSubspace`
- `Observable`
- `PerturbationTarget`
- `ProjectorCandidate`
- `ReferenceState`
- `ResponseTask`
- `ResponseDataset`
- `RegressionResult`
- `MatrixBundle`
- `GateResult`
- `SensitivityReport`
- `EvidencePackage`
- `HumanDecision`

## Agregados

`Campaign` referencia la geometría y metodología. `Candidate` fija proyector y ventana alpha.
`MatrixBundle` sólo puede construirse desde un dataset completo de un mismo candidato.

## Identificadores

Los identificadores funcionales son legibles; los identificadores canónicos se derivan de hashes.


## Convenciones normativas

Las palabras **DEBE**, **NO DEBE**, **DEBERÍA**, **NO DEBERÍA** y **PUEDE** son normativas.  
Una regla marcada como DEBE es obligatoria para conformidad. Una regla marcada como DEBERÍA
puede omitirse sólo con una justificación registrada y auditable.
