# SIESTAFLOW Hubbard Response Backbone v0.1.0

**SIESTAFLOW** is a cryptographically audited, physically validated, and modular framework for determining ab-initio Hubbard $U$ (and inter-site $V$) parameters for SIESTA 5.4.2 via Linear Response Density Functional Theory (DFT+U).

---

## 📖 User Manual & Documentation
For a complete guide on physics foundations, CLI commands, and technical transparency, see the [Technical User Manual](file:///docs/USER_MANUAL.md).

* **User Manual:** [docs/USER_MANUAL.md](file:///docs/USER_MANUAL.md)
* **Scope:** [docs/00_governance/SCOPE.md](file:///docs/00_governance/SCOPE.md)
* **Physical Contracts:** [docs/01_science/PHYSICAL_CONTRACTS.md](file:///docs/01_science/PHYSICAL_CONTRACTS.md)
* **Architecture Spec:** [docs/02_architecture/ARCHITECTURE.md](file:///docs/02_architecture/ARCHITECTURE.md)

---

## 🚀 Quick Start & CLI Usage

### Installation & Verification
```bash
python -m pytest tests/ -v
# 79 passed in 0.47s
```

### 1. Audit an FDF File (Pre-flight Check)
```bash
siestaflow audit-fdf Cu3N.fdf --verbose
```

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