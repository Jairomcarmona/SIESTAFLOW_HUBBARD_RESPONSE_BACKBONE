# Thesis protocol context: linear-response Hubbard U with SIESTA

## How Prism should use this document

This is the authoritative context for writing the thesis protocol. It must
separate demonstrated facts from pending validation and must never call the
reported result a universal elemental Hubbard parameter. Use the expression
"effective Hubbard interaction obtained by linear response for the declared
localized subspace".

The thesis has two linked contributions:

1. It applies first-principles DFT plus linear-response Hubbard methodology
   to the materials under study, including ordered K-birnessite.
2. It develops a scientific runtime that makes this methodology reproducible,
   traceable, restartable and mathematically auditable on top of SIESTA.

SIESTA remains the electronic-structure backend. The developed software is
the layer that defines the campaign, controls its electronic dependencies,
extracts occupations, validates the results and reconstructs the interaction.

## Scientific motivation

Semi-local DFT approximations can inadequately represent localized transition
metal states. DFT+U introduces a correction on an explicitly selected
localized subspace. The numerical parameter must not be selected only to fit
an experimental property; it can be obtained from the response of the same
localized occupation used by the correction. This is the central proposal of
Cococcioni and de Gironcoli [Cococcioni2005].

The value is conditional, not universal:

$$
U^{\mathrm{LR-DFT}} =
U[\mathrm{functional}, \mathrm{structure}, \mathrm{magnetic\ state},
\hat P, r_c, \omega, \mathrm{pseudos}, \mathbf{k}, \mathrm{basis}, L].
$$

Changing the localized projector changes the object whose response is
measured. Therefore results calculated with different projectors must not be
silently averaged or treated as a numerical convergence sequence.

## Localized occupations and perturbations

For every correlated site $I$, define the total localized occupation as

$$
n_I = \sum_{\sigma\mathbf{k}\nu} f_{\mathbf{k}\nu}^{\sigma}
\langle\psi_{\mathbf{k}\nu}^{\sigma}|\hat P_I|
\psi_{\mathbf{k}\nu}^{\sigma}\rangle.
$$

Here $\hat P_I$ is the projector defining the correlated subspace. In the
birnessite application this is Mn-3d, specified through the SIESTA DFT+U
projector. Its definition includes the orbital channel, projector-generation
method, radial cutoff $r_c$, radial smoothing $\omega$, pseudopotential and
the physical site identity.

After obtaining a converged DFT reference density $\rho_{\mathrm{ref}}$, the
Hamiltonian is perturbed locally at a single site $J$:

$$
\hat H^{\alpha_J}=\hat H_{\mathrm{KS}}[\rho_{\mathrm{ref}}]
 + \alpha_J\hat P_J.
$$

Both $+\alpha$ and $-\alpha$ perturbations are evaluated. Every perturbation
records the occupation vector of all correlated sites,

$$
\mathbf n(\alpha_J)=[n_1(\alpha_J),\ldots,n_{N_{\mathrm{corr}}}(\alpha_J)]^T,
$$

so the method retains intersite response rather than using only a local scalar
occupation.

## Response matrices and Hubbard interaction

The bare and screened response matrices are defined by

$$
\chi^0_{IJ}=\frac{\partial n_I^{(0)}}{\partial\alpha_J},
\qquad
\chi_{IJ}=\frac{\partial n_I}{\partial\alpha_J}.
$$

Rows correspond to observed sites $I$ and columns to perturbed sites $J$.
They are estimated with central finite differences:

$$
\chi^0_{IJ}\approx
\frac{n_I^{(0)}(+\alpha_J)-n_I^{(0)}(-\alpha_J)}{2\alpha},
\qquad
\chi_{IJ}\approx
\frac{n_I(+\alpha_J)-n_I(-\alpha_J)}{2\alpha}.
$$

The interaction kernel and site-local interaction are

$$
K=(\chi^0)^{-1}-\chi^{-1},
\qquad U_I=K_{II}.
$$

Off-diagonal entries $K_{IJ}$ are preserved because they represent coupling
between sites. The workflow uses direct inversion only. A rank-deficient
matrix is invalid evidence: no pseudoinverse, diagonal-only approximation or
automatic regularization is permitted.

## What the developed scientific runtime does

### Scientific-contract compilation

The input is a scientific contract, not merely a shell command. It declares
geometry, species, correlated sites, magnetic state, functional, basis,
k-grid, real-space mesh, pseudopotentials, projector definition, perturbation
amplitudes and acceptance policies. The runtime deterministically materializes
SIESTA FDF inputs, metadata and the dependency graph from this contract.

### Electronic-state DAG

The campaign has the following physical dependency graph:

$$
\text{scientific input}
\rightarrow\text{reference SCF}
\rightarrow\text{common parent DM}
\rightarrow\{\mathrm{BARE},\mathrm{SCREENED}\}_{J,\pm\alpha}
\rightarrow\chi^0,\chi\rightarrow K\rightarrow U.
$$

The converged reference produces a parent density matrix (DM). Each child
calculation begins from that same electronic state. Thus a response is not
contaminated by unrelated initial densities, metastable solutions or different
magnetic histories.

For $N_{\mathrm{corr}}$ correlated sites and one magnitude $\alpha$, the
minimum complete campaign has $1+4N_{\mathrm{corr}}$ calculations: one
reference and BARE/SCREENED branches at both signs for each site. Six explicit
Mn sites therefore require 25 calculations.

### Scheduler execution and recovery

The runtime launches the DAG in a single Slurm allocation. It retains the
allocation while sequentially executing dependent SIESTA nodes, rather than
returning to the queue after every calculation. Nodes leave durable artifacts,
so the campaign is restartable. On resume, existing nodes are validated and
only missing or invalid nodes are rerun.

Job completion is not scientific success. A node must also satisfy the
configured convergence and output-evidence gate before downstream tasks can
use it.

### Semantic parsing of native output

Native SIESTA output is parsed into Hubbard population events rather than
treated as arbitrary text. The parser retains site identity, spin-resolved
occupation matrices, traces, SCF iteration, event occurrence and source line
interval. This preserves the trail from an entry of $\chi$ back to the
specific SIESTA output that supplied its occupation.

### Acceptance gates

The runtime rejects a claimed result if any of these conditions fails:

1. converged electronic and magnetic reference;
2. available, declared parent DM for every child;
3. complete signed perturbations for every correlated site;
4. normal completion and SCF convergence for SCREENED runs;
5. unambiguous semantic occupation extraction;
6. complete square response matrices;
7. full numerical rank, declared matrix-selection policy, direct-inverse
   residuals and condition diagnostics;
8. projector/pseudopotential compatibility between the LR campaign and any
   subsequent DFT+U calculation.

### Reproducible evidence

The final artifact contains the scientific contract, FDF inputs, projector and
pseudopotential identity, native SIESTA outputs, occupation vectors, raw and
selected response matrices, inversion diagnostics, kernel $K$ and $U_I$.
An independent audit can reconstruct the chain

$$
\{\mathrm{SIESTA\ outputs}\}\rightarrow\{\mathrm{occupations}\}
\rightarrow\{\chi^0,\chi\}\rightarrow K\rightarrow U.
$$

This is the relevant software contribution. It makes an otherwise manual and
error-prone protocol an evidence-bearing scientific workflow for SIESTA.

## Birnessite case study: demonstrated result

The ordered K-birnessite campaign explicitly treated six Mn sites. The
reference setup used PBE, Mn-3d, SIESTA projector Method 2, $r_c=3.0$ Bohr and
$\omega=0.05$ Bohr. The operational result was

$$
U_{\mathrm{Mn}}^{\mathrm{LR-DFT}}\approx5.23\ \mathrm{eV}.
$$

The following validation controls were completed:

| Control | Result | Interpretation |
|---|---:|---|
| $\alpha=0.025$, 0.050, 0.100 eV | 5.230--5.247 eV | stable within tested perturbative window |
| k-grid control | about 5.25 eV | modest change in tested sampling |
| TZP basis control | about 5.13 eV | modest basis sensitivity |
| alternate magnetic order | about 5.23 eV | stable for the tested alternative |
| projector $r_c=2.5$ Bohr | about 7.36 eV | distinct Mn-3d subspace; do not average with $r_c=3.0$ |

For the reported campaigns, both response matrices were full rank (6/6) and
direct inversions had residuals of order $10^{-16}$.

The defensible statement is therefore: an effective interaction of roughly
5.23 eV was reproducibly obtained for the explicitly declared Mn-3d SIESTA
subspace. It is not a universal Mn value.

## Explicit scientific limits

### BARE semantic limit

The operational BARE branch is reproducible, but an SCF iteration number alone
does not prove the exact internal SIESTA ordering needed for the ideal
Cococcioni $\chi^0$. A complete certification requires version-specific native
trace or source-level evidence showing

$$
\rho_{\mathrm{ref}}
\rightarrow H_{\mathrm{KS}}[\rho_{\mathrm{ref}}]+\alpha P_J
\rightarrow n_I^{(0)}
\rightarrow\text{later Hxc rebuild}.
$$

Until this is demonstrated, describe the workflow as an operational
finite-difference LR implementation with a candidate BARE semantic selection,
not as final proof of the internal timing of SIESTA.

### Supercell limit

Periodic perturbations interact with their periodic images. A single cell
defines a valid cell-specific result, but convergence toward an isolated
perturbation requires a size series $U(L)$. Do not claim supercell convergence
for birnessite until that comparison is completed.

### Subsequent use in DFT+U

Any DFT+U production calculation must use the same projector definition and
pseudopotential family used in the LR campaign. Its usefulness is evaluated
through independent material properties: structural stability, magnetic
moments, density of states, band structure, relative energies and, when
relevant, dielectric or optical observables.

## Recommended thesis organization

1. Correlation problem and DFT+U background.
2. Localized occupations and projector dependence.
3. Cococcioni linear-response formalism.
4. Developed scientific runtime: contract, DAG, parent DM, semantic parser,
   numerical gates, recovery and evidence.
5. Validation on benchmark materials and ordered K-birnessite.
6. Application of the declared $U$ to subsequent DFT+U properties.
7. Limits, convergence studies and future work.

## Approved contribution statement

Use language equivalent to this:

> A reproducible scientific runtime was developed to implement finite-
> difference Hubbard linear-response campaigns on SIESTA. It compiles a
> physical contract into a dependency-aware workflow, preserves reference
> electronic-state lineage, extracts Hubbard occupations from native outputs,
> validates complete matrix response and direct inversion, and produces
> independently auditable evidence from output files to the reported
> interaction.

Avoid claiming that the runtime finds a universal U, proves physical accuracy
without property validation, or replaces the electronic-structure engine.

## Core references

```bibtex
@article{Cococcioni2005,
  author  = {Cococcioni, Matteo and de Gironcoli, Stefano},
  title   = {Linear response approach to the calculation of the effective interaction parameters in the LDA+U method},
  journal = {Physical Review B}, volume = {71}, pages = {035105}, year = {2005},
  doi = {10.1103/PhysRevB.71.035105}
}

@article{Timrov2022,
  author  = {Timrov, Iurii and Marzari, Nicola and Cococcioni, Matteo},
  title   = {HP: A code for the calculation of Hubbard parameters using density-functional perturbation theory},
  journal = {Computer Physics Communications}, volume = {279}, pages = {108455}, year = {2022},
  doi = {10.1016/j.cpc.2022.108455}
}

@manual{SiestaManual,
  title = {SIESTA Documentation: DFT+U reference},
  organization = {SIESTA Developers},
  url = {https://docs.siesta-project.org/projects/siesta/en/latest/reference/siesta.html}
}
```
