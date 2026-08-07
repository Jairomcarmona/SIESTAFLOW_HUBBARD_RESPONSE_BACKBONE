# SIESTA 5.4.2 DFTU.Proj Grammar — Method 2

**Contract Identity:** `SIESTA_5_4_2_SOURCE_CONTRACT`
**Normative Source:** `Src/dftu_specs.f` (lines 467-592) from official SIESTA 5.4.2 GitLab tag
**Status:** `SIESTA_542_GRAMMAR_CONFIRMED`

---

## Block Format (Method 2)

When `DFTU.ProjectorGenerationMethod` is `2`, each species entry in `%block DFTU.Proj` consists of a header line followed by up to 4 lines per shell (the 4th is optional).

```fdf
%block DFTU.Proj
<SpeciesLabel>  <NumberOfShells>
<n>  <l>
<U_eV>  <J_eV>
<rc>  <omega>
<lambda>            # Optional contraction factor
%endblock DFTU.Proj
```

| Line | Content | Units | Description |
|------|---------|-------|-------------|
| 1 | `SpeciesLabel  NumberOfShells` | — | Species label from `Chemical_Species_Label` block; integer shell count |
| 2 | `n  l` | — | Principal quantum number, angular momentum quantum number |
| 3 | `U  J` | eV | Hubbard U and Hund's exchange J |
| 4 | `rc  omega` | Bohr | Cutoff radius and Fermi-function smearing parameter |
| 5 (opt)| `lambda` | — | Optional scale/contraction factor |

### Source Verification (`Src/dftu_specs.f`)
- **n, l**: Parsed around line 467 (`if (fdf_bmatch(pline,'nii')) ...`)
- **U, J**: Parsed around line 544 (`if (fdf_bmatch(pline,'vv')) ...`)
- **rc, omega**: Parsed around line 560 (`dftu%rc = fdf_bvalues(pline,1)`, `dftu%width = fdf_bvalues(pline,2)`)
- **lambda**: Parsed around line 588 (`dftu%lambda = fdf_breals(pline,1)`). If the line is not a real number, the parser backspaces and considers the shell definition complete.

---

## Comparison with Current (Broken) Serializer

The current SIESTAFLOW serializer outputs a **5-line** format:

```
%block DFTU.proj
  Mn   1          
  3  2             
  {rc}  {width}    
  {u_val}  {alpha} 
  {j_val}          
%endblock DFTU.proj
```

### Critical Parsing Failure

Because the parser accepts an optional 4th line (`lambda`), the output is **SYNTACTICALLY VALID but SEMANTICALLY INVALID**. SIESTA consumes all values but maps them to the wrong physical parameters:

| Serialized Value | SIESTA Fortran Variable (`dftu_specs.f`) | Physical Interpretation by SIESTA |
|------------------|------------------------------------------|-----------------------------------|
| `{rc}` | `dftu%u` | Hubbard U parameter |
| `{width}` | `dftu%j` | Hund's J parameter |
| `{u_val}` | `dftu%rc` | Projector cutoff radius |
| `{alpha}` | `dftu%width` (`omega`) | Fermi smearing parameter |
| `{j_val}` | `dftu%lambda` | Contraction factor |

This means any U calculation run with the current codebase is scientifically invalid.

---

## DFTU.FirstIteration Internal Forcing

According to `Src/dftu_specs.f` (lines 402-409):
```fortran
dftu_init = fdf_get('DFTU.FirstIteration', dftu_init )
if ( dftu_shift ) dftu_init = .true.
```
When `DFTU.PotentialShift = true`, SIESTA internally forces the first iteration to evaluate the Hubbard terms. Therefore, the lack of an explicit `DFTU.FirstIteration T` in our current codebase is an **auditability/explicit-contract deficiency**, not a demonstrated physical failure. However, it MUST be made explicit in the new FDF materializer.
