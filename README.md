# SIESTAFLOW Hubbard Response Backbone

**SIESTAFLOW** is a research framework for finite-difference linear-response calculations coupled to SIESTA. It includes execution, provenance, response-matrix analysis, and scientific acceptance gates. Its current MnO result is not a validated DFT+U parameter for production calculations.

**Current status (2026-09-25):** The archived MnO AFM-II campaign yields a numerical scalar charge-response estimate of 11.5320557 eV. Its strict signal gate reports `FAIL`, and the available perturbations do not establish equivalence with the spin-dependent `U-J` parameter applied by SIESTA. See the [Opus handoff and reproducibility guide](docs/OPUS_MNO_HANDOFF_20260925.md) before using or changing that number.

---

## 📖 User Manual & Documentation
For a complete guide on physics foundations, CLI commands, and technical transparency, see the [Technical User Manual](docs/USER_MANUAL.md).

* **User Manual:** [docs/USER_MANUAL.md](docs/USER_MANUAL.md)
* **Scope:** [docs/00_governance/SCOPE.md](docs/00_governance/SCOPE.md)
* **Physical Contracts:** [docs/01_science/PHYSICAL_CONTRACTS.md](docs/01_science/PHYSICAL_CONTRACTS.md)
* **Architecture Spec:** [docs/02_architecture/ARCHITECTURE.md](docs/02_architecture/ARCHITECTURE.md)
* **Publication boundary:** [docs/PUBLICATION_LAYOUT.md](docs/PUBLICATION_LAYOUT.md)

---

## 🚀 Quick Start & CLI Usage

### Installation & Verification
```bash
python -m pip install -e ".[test]"
python -m pytest tests/ -q
```

The full suite currently has known failures; the [MnO handoff](docs/OPUS_MNO_HANDOFF_20260925.md) records the verified subsets and open failures.

### 1. Audit an FDF File (Pre-flight Check)
```bash
siestaflow audit-fdf Cu3N.fdf --verbose
```

### 1b. Mandatory scientific-DAG preflight for a production LR-U campaign

Before submitting a production DAG, materialize and audit the real SIESTA
Method-2 projector, then let the resumable protocol validate the reference,
responses, algebra and evidence gates. See
[Scientific DAG Protocol](docs/SCIENTIFIC_DAG_PROTOCOL.md) and
[Method-2 Projector Preflight](docs/METHOD2_PROJECTOR_PREFLIGHT.md).

### 2. Initialize a Campaign
```bash
siestaflow init Cu3N.fdf --name Cu3N_Campaign
```

### 3. Automatic Convergence
```bash
siestaflow converge campaign.json
```

### 4. Run Linear Response Campaign
```bash
siestaflow run campaign.json --hpc-scheduler slurm
```

### 5. Resume Interrupted Computations
```bash
siestaflow resume campaign.json
```

### 6. Export Evidence Report (MD & HTML)
```bash
siestaflow report campaign.json --format md,html
```

---

## 🔬 Technical Debt Audit Summary (v0.1.0)

* **Resolved Items:**
  * Fixed `DFTU.proj` column order (`U` before `alpha`).
  * Fixed Windows/WSL CRLF line ending Fortran parser crashes.
  * Supported non-polarized spin mode occupation parsing.
* **Open Technical Debt Items (Documented in `docs/USER_MANUAL.md`):**
  * `TD-001`: Subspace Bijective Restriction ($P=N$, deferred $P \neq N$ to v0.2.0 via OD-007).
  * `TD-002`: Non-Collinear / Spin-Orbit Coupling $10\times 10$ complex block extraction.
  * `TD-003`: Remote SSH/SLURM Queue Transport Driver.
  * `TD-004`: Automatic Asymmetric Alpha Grid Selection for $d^{10}$ filled shells.
