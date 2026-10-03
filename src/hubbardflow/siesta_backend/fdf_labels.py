"""SIESTA label identity, distinct from HubbardFlow's managed spellings.

SIESTA ignores punctuation in labels. Writers retain their audited literal
spellings; recognizing an alias therefore does not authorize rewriting it.
"""

from __future__ import annotations


def canonical_fdf_label(text: str) -> str:
    """Return the SIESTA identity of a label (case and -_. are ignored)."""
    return text.casefold().translate(str.maketrans("", "", "-_."))


MANAGED_FDF_LABELS = (
    "AtomicCoordinatesFormat",
    "AtomicCoordinatesAndAtomicSpecies",
    "ChemicalSpeciesLabel",
    "DFTU.FirstIteration",
    "DFTU.Method",
    "DFTU.PotentialShift",
    "DFTU.ProjectorGenerationMethod",
    "DFTU.proj",
    "LDAU.proj",
    "DM.InitSpin",
    "DM.Tolerance",
    "DM.UseSaveDM",
    "File.DM.Init",
    "LatticeConstant",
    "LatticeParameters",
    "LatticeVectors",
    "MaxSCFIterations",
    "MeshCutoff",
    "MD.NumCGsteps",
    "MD.TypeOfRun",
    "NonCollinearSpin",
    "NumberOfAtoms",
    "NumberOfSpecies",
    "PAO.Basis",
    "PAO.BasisSize",
    "PAO.BasisType",
    "SCF.Mix",
    "SCF.Mixer.Method",
    "SCF.Mixer.Weight",
    "SCF.Mixer.History",
    "SCF.MustConverge",
    "SCF.DM.Converge",
    "SCF.H.Converge",
    "SCF.DM.Tolerance",
    "SCF.H.Tolerance",
    "Spin",
    "SpinOrbit",
    "SpinPolarized",
    "SystemLabel",
    "kgrid_cutoff",
    "kgrid_Monkhorst_Pack",
)
