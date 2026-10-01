## FeO PBE converged vs FeO LR-U 100% (seedDM)

```diff
--- FeO PBE converged/input.fdf

+++ FeO LR-U 100% (seedDM)/input.fdf

@@ -67,10 +67,10 @@

 %block DFTU.proj

   FeLR0 1

   3 2

-  0.0000 0.0000

+  5.638281766243177  0.000000000000000

   3.0000 0.0500

   FeLR1 1

   3 2

-  0.0000 0.0000

+  5.638315883828983  0.000000000000000

   3.0000 0.0500

 %endblock DFTU.proj

```

## FeO LR-U original vs FeO LR-U seedDM

```diff
--- FeO LR-U original/input.fdf

+++ FeO LR-U seedDM/input.fdf

@@ -39,7 +39,7 @@

 OccupationFunction FD

 ElectronicTemperature 300 K

 MaxSCFIterations 300

-DM.MixingWeight 0.05

+DM.MixingWeight 0.01

 DM.NumberPulay 5

 Spin polarized

 %block DM.InitSpin

@@ -51,14 +51,14 @@

 DFTU.ProjectorGenerationMethod 2

 DFTU.PotentialShift false

 DFTU.FirstIteration true

-DM.UseSaveDM false

+DM.UseSaveDM true

 WriteMullikenPop 1

 WriteDM true

 MD.NumCGsteps 0

 SCF.MustConverge true

 SCF.Mix Hamiltonian

 SCF.Mixer.Method Pulay

-SCF.Mixer.Weight 0.05

+SCF.Mixer.Weight 0.01

 SCF.Mixer.History 8

 SCF.DM.Converge true

 SCF.H.Converge true

```

## FeO LR-U seedDM vs FeO LR-U continuation 25%

```diff
--- FeO LR-U seedDM/input.fdf

+++ FeO LR-U continuation 25%/input.fdf

@@ -1,4 +1,4 @@

-SystemName FeO ideal AFM-II PBE Stage U-A

+SystemName FeO ideal AFM-II PBE U continuation 25 percent

 SystemLabel FEO_PBE_REFERENCE

 

 NumberOfAtoms 4

@@ -67,10 +67,10 @@

 %block DFTU.proj

   FeLR0 1

   3 2

-  5.638281766243177  0.000000000000000

+  1.4095704415607942 0.000000000000000

   3.0000 0.0500

   FeLR1 1

   3 2

-  5.638315883828983  0.000000000000000

+  1.4095789709572458 0.000000000000000

   3.0000 0.0500

 %endblock DFTU.proj

```

## NiO LR-U converged vs FeO LR-U 100% (seedDM)

```diff
--- NiO LR-U converged/input.fdf

+++ FeO LR-U 100% (seedDM)/input.fdf

@@ -1,80 +1,76 @@

-SystemName          NiO AFM-II PBE seven-point reference

-SystemLabel         NIO_PBE_REFERENCE

+SystemName FeO ideal AFM-II PBE Stage U-A

+SystemLabel FEO_PBE_REFERENCE

 

-NumberOfAtoms       4

-NumberOfSpecies     3

-

+NumberOfAtoms 4

+NumberOfSpecies 3

 %block ChemicalSpeciesLabel

-  1  28  NiLR0

-  2  28  NiLR1

-  3   8  O

+  1 26 FeLR0

+  2 26 FeLR1

+  3 8 O

 %endblock ChemicalSpeciesLabel

 

-LatticeConstant     4.17 Ang

+LatticeConstant 4.334 Ang

 %block LatticeVectors

-  0.0  1.0  1.0

-  0.5  0.0  0.5

-  0.5  0.5  0.0

+  0.0 1.0 1.0

+  0.5 0.0 0.5

+  0.5 0.5 0.0

 %endblock LatticeVectors

 

 AtomicCoordinatesFormat Fractional

 %block AtomicCoordinatesAndAtomicSpecies

-  0.00  0.00  0.00  1  # NiLR0

-  0.50  0.00  0.00  2  # NiLR1

-  0.25  0.50  0.50  3  # O

-  0.75  0.50  0.50  3  # O

+  0.00 0.00 0.00 1 # FeLR0 / AFM-II A

+  0.50 0.00 0.00 2 # FeLR1 / AFM-II B

+  0.25 0.50 0.50 3 # O

+  0.75 0.50 0.50 3 # O

 %endblock AtomicCoordinatesAndAtomicSpecies

 

 XC.Functional GGA

 XC.Authors PBE

-

-PAO.BasisSize       DZP

-PAO.EnergyShift     0.005 Ry

-PAO.SplitNorm       0.15

-PAO.BasisType       split

-MeshCutoff          200 Ry

+PAO.BasisSize DZP

+PAO.EnergyShift 0.005 Ry

+PAO.SplitNorm 0.15

+PAO.BasisType split

+MeshCutoff 200 Ry

 %block kgrid_Monkhorst_Pack

   2 0 0 0.0

   0 4 0 0.0

   0 0 4 0.0

 %endblock kgrid_Monkhorst_Pack

-

-MaxSCFIterations    300

-DM.MixingWeight     0.05

-DM.NumberPulay      5

+OccupationFunction FD

+ElectronicTemperature 300 K

+MaxSCFIterations 300

+DM.MixingWeight 0.01

+DM.NumberPulay 5

 Spin polarized

 %block DM.InitSpin

-  1 +2.0

-  2 -2.0

-  3  0.0

-  4  0.0

+  1 +4.0

+  2 -4.0

+  3 0.0

+  4 0.0

 %endblock DM.InitSpin

-

 DFTU.ProjectorGenerationMethod 2

 DFTU.PotentialShift false

 DFTU.FirstIteration true

-DM.UseSaveDM false

+DM.UseSaveDM true

 WriteMullikenPop 1

-WriteForces true

 WriteDM true

 MD.NumCGsteps 0

-%block DFTU.proj

-  NiLR0  1

-  3 2

-  6.864267700049239  0.000000000000000

-  3.0000 0.0500

-  NiLR1  1

-  3 2

-  6.864387475210124  0.000000000000000

-  3.0000 0.0500

-%endblock DFTU.proj

-

 SCF.MustConverge true

 SCF.Mix Hamiltonian

 SCF.Mixer.Method Pulay

-SCF.Mixer.Weight 0.05

+SCF.Mixer.Weight 0.01

 SCF.Mixer.History 8

 SCF.DM.Converge true

 SCF.H.Converge true

 SCF.DM.Tolerance 1.0e-5

 SCF.H.Tolerance 1.0e-4 eV

+%block DFTU.proj

+  FeLR0 1

+  3 2

+  5.638281766243177  0.000000000000000

+  3.0000 0.0500

+  FeLR1 1

+  3 2

+  5.638315883828983  0.000000000000000

+  3.0000 0.0500

+%endblock DFTU.proj

```
