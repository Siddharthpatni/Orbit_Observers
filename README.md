# Orbit Observers / ClearSpace Phase 2 — RPO Monte Carlo Simulation Package

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![Status: Verified](https://img.shields.io/badge/V%26V%20Suite-10%2F10%20Passing-brightgreen.svg)](rpo_project/tests/test_vv.py)
[![License: Open Research](https://img.shields.io/badge/license-Research%20Open-lightgrey.svg)](README.md)

**Model Maturity Label:** Early-stage, scenario-based, low-to-medium-fidelity Rendezvous and Proximity Operations (RPO) robustness assessment adhering to Handbook Sections 1–14.

---

## Table of Contents
- [Executive Overview](#executive-overview)
- [Client Preparation Tiers (C0–C3)](#client-preparation-tiers-c0c3)
- [Model Architecture & Innovations (v3.0)](#model-architecture--innovations-v30)
- [Repository Structure](#repository-structure)
- [Installation & Setup](#installation--setup)
- [Execution Guide](#execution-guide)
  - [1. Verification & Validation (V&V) Suite](#1-verification--validation-vv-suite)
  - [2. Runner Regression Tests](#2-runner-regression-tests)
  - [3. Fast Smoke Campaign](#3-fast-smoke-campaign)
  - [4. Full Paired-Seed Monte Carlo Campaign](#4-full-paired-seed-monte-carlo-campaign)
  - [5. MeluXina HPC Distributed Execution](#5-meluxina-hpc-distributed-execution)
- [Outputs & Core Publication Plots](#outputs--core-publication-plots)
- [20-Column Simulation Schema](#20-column-simulation-schema)
- [Research Integrity & Guardrails](#research-integrity--guardrails)

---

## Executive Overview

The **Orbit Observers RPO Monte Carlo Package** evaluates the operational safety, fuel expenditure ($\Delta V$), and mission feasibility of close-proximity inspection and capture operations in Geostationary Orbit (GEO). 

The primary research objective is to rigorously quantify the performance delta between uncooperative active debris removal (ADR) targets and prepared, cooperative client satellites across varying initial tumble rates ($\omega \in [0.0^\circ, 5.0^\circ/\text{s}]$), optical vision noise, and RF beacon communication impairments.

All campaign comparisons utilize **paired pseudo-random seeds**, ensuring that identical initial position/velocity dispersions, random tumble axes, sensor noise realizations, and timing offsets are tested across all preparation tiers.

---

## Client Preparation Tiers (C0–C3)

The simulation models four standardized client preparation tiers (Handbook Section 4):

| Tier | Identifier | Visual Sensor Specs | RF Beacon Telemetry | Cooperative Assist | Description |
|:-----|:-----------|:--------------------|:--------------------|:-------------------|:------------|
| **C0** | `C0_unprepared` | $\sigma_\theta = 12.0^\circ$, $2.5\times$ pos noise, $30\%$ dropout | None (disabled) | None ($1.0\times\ \omega$) | Non-cooperative legacy spacecraft. Unfavorable visual features, high occlusions, no broadcast data. |
| **C1** | `C1_fiducials` | $\sigma_\theta = 3.0^\circ$, $1.0\times$ pos noise, $8\%$ dropout | None (disabled) | None ($1.0\times\ \omega$) | Passive cooperative markers (optical fiducials/retro-reflectors). High-accuracy pose estimation. |
| **C2-ID** | `C2_id_only` | $\sigma_\theta = 3.0^\circ$, $1.0\times$ pos noise, $8\%$ dropout | Active ID only (no angular rate) | None ($1.0\times\ \omega$) | Optical markers + active RF identification beacon without dynamic attitude state. |
| **C2** | `C2_beacon` | $\sigma_\theta = 3.0^\circ$, $1.0\times$ pos noise, $8\%$ dropout | Full rate telemetry with packet loss & latency | None ($1.0\times\ \omega$) | Active Service Beacon transmitting angular rate $\omega_z$, subject to Bernoulli packet drops and latency. |
| **C3** | `C3_ios_mode` | $\sigma_\theta = 3.0^\circ$, $1.0\times$ pos noise, $8\%$ dropout | Active rate telemetry | Detumbling assist ($0.05\times\ \omega$) | In-Orbit Servicing interface with capture fixture, beacon telemetry, and residual tumble suppression. |

---

## Model Architecture & Innovations (v3.0)

The simulation engine is implemented in modular Python under [`rpo_project/`](rpo_project/):

```
rpo_project/
├── config/             # GEO orbital parameters, spacecraft inertia, thresholds, scenarios
├── dynamics.py         # 3D Clohessy-Wiltshire (CW) RK4 propagation & 6x6 analytical STM
├── attitude.py         # Quaternion kinematics, Euler torque-free equations, capture kinematics
├── sensors.py          # Optical camera pose/position observation, FOV occlusions, dropouts
├── beacon.py           # Independent Service Beacon packet generator with latency & packet loss
├── estimator.py        # Separated Translation (CW-KF) & Attitude/Rate Kalman Filters
├── guidance.py         # Two-stage standoff & terminal tracking controller (braking_pd / legacy_pd)
├── safety.py           # Keep-out sphere monitoring, covariance/rate abort gates, dwell logic
├── simulate.py         # Single closed-loop simulation returning 20-column schema
├── analyse.py          # Wilson 95% binomial confidence intervals & publication plot generator
├── montecarlo.py       # Campaign parameter sweep runner with paired seeds & HPC chunking
├── tests/              # Verification & Validation (V&V) test suite & regression tests
└── meluxina_slurm.sh   # Slurm job array script for LuxProvide MeluXina supercomputer
```

### Key Enhancements in `v3.0`:
1. **Closing Speed Limiter (`braking_pd`)**:
   In high-tumble or stationary convergence cases, classical PD controllers can saturate thrusters prematurely when transitioning from hold-point to terminal capture point, leading to overshoot. `braking_pd` caps closing velocity and reserves $\ge 50\%$ acceleration authority for braking and trajectory tracking.
2. **Accurate Distance Clearance Calculation**:
   `minimum_clearance_m` is strictly evaluated as surface margin: $\|\mathbf{r}_{\text{chaser}}\| - R_{\text{keepout}}$, eliminating ambiguous center-to-center distance metrics.
3. **Capture-Point Prediction Error**:
   `capture_point_error_m` calculates true temporal RMS error over the observation horizon rather than simple scalar mean error.
4. **Physically Grounded Fuel Tracking**:
   Removes unpropagated delta-v penalties on abort decisions; records exact thruster actuation integrals $\int \|\mathbf{a}_{\text{cmd}}\| dt$.

---

## Repository Structure

```
.
├── README.md                           # Master project documentation
├── requirements.txt                    # Python runtime dependencies
├── rpo_project/                        # Production Python simulation package
│   ├── __init__.py
│   ├── config/
│   │   └── __init__.py                 # Simulation constants & SimConfig dataclass
│   ├── dynamics.py
│   ├── attitude.py
│   ├── sensors.py
│   ├── beacon.py
│   ├── estimator.py
│   ├── guidance.py
│   ├── safety.py
│   ├── simulate.py
│   ├── analyse.py
│   ├── montecarlo.py
│   ├── meluxina_slurm.sh
│   └── tests/
│       ├── test_montecarlo.py          # Runner regression tests
│       └── test_vv.py                  # 10-point V&V test suite
├── results/                            # Simulation output archives
│   ├── baseline_v2_1/                  # Historical v2.1 baseline results & manifest
│   │   ├── manifest.json
│   │   ├── summary_main.csv
│   │   ├── runs_main.csv
│   │   ├── runs_ablation.csv
│   │   ├── runs_envelope.csv
│   │   └── plot[1-4]*.png
│   └── smoke_v2_1/                     # Smoke test sample dataset
├── docs/                               # Project documentation & reference material
│   └── reference/
│       ├── Orbit_Observers_RPO_Monte_Carlo_Project_Guide.pdf
│       ├── Phase2_ClearSpace_Call.pptx
│       └── Phase2_Serviceability.pptx
├── examples/                           # Example workflows & legacy pilots
│   └── stage1/
│       ├── README.txt
│       └── rpo_beacon_information_pilot.py
└── archive/                            # Archived prototypes & MATLAB implementation
    ├── matlab/
    │   ├── rpo_monte_carlo_sim.m       # Standalone MATLAB RPO simulator
    │   └── run_and_export_all.m        # MATLAB automated runner
    └── python/
        └── incomplete_stage1_reference.py
```

---

## Installation & Setup

### Prerequisites
- Python 3.10, 3.11, 3.12, 3.13, or 3.14
- Operating System: macOS, Linux, or Windows WSL

### Setup Instructions
Clone the repository and initialize the Python virtual environment:

```bash
git clone https://github.com/Siddharthpatni/Orbit_Observers.git
cd Orbit_Observers

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate        # On Windows: .venv\Scripts\activate

# Install required dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

---

## Execution Guide

### 1. Verification & Validation (V&V) Suite
Run the 10-point V&V suite to verify physics propagation, Kalman filter convergence, sensor models, and safety abort triggers:

```bash
python -m rpo_project.montecarlo --mode verify
```

**Verified Checks:**
1. Zero-control CW trajectory vs. analytical 6×6 STM ($< 10^{-8}\text{ m}$)
2. Stationary client, zero-noise terminal capture convergence
3. Zero-beacon reduction equivalence ($C_2 \equiv C_1$ when packet loss = 100%)
4. Beacon ID-only parity against rate data
5. Packet delivery boundaries and timestamp latency handling
6. Quaternion unit-norm conservation ($|\|\mathbf{q}\| - 1| < 10^{-14}$)
7. Capture-point kinematic velocity at zero tumble
8. High angular rate safety gate abort trigger ($\omega > 3.2^\circ/\text{s}$)
9. Integrator step-size $\Delta t$ convergence ($< 10^{-9}\text{ m}$)
10. Paired-seed determinism across $C_0$, $C_1$, and $C_2$

### 2. Runner Regression Tests
Execute mock-runner regression tests for sweep partitioning and options validation:

```bash
python -m unittest rpo_project.tests.test_montecarlo
```

### 3. Fast Smoke Campaign
Run a fast smoke test (89 simulations total: 35 main, 30 ablation, 24 envelope) to verify the full execution, summary generation, and plotting pipeline:

```bash
python -m rpo_project.montecarlo --mode pilot --runs 1 --sweep-runs 1 --out results/smoke_run
```

### 4. Full Paired-Seed Monte Carlo Campaign
Execute the standard research pilot campaign (1,050 main simulations, 450 ablation runs, 360 envelope runs):

```bash
python -m rpo_project.montecarlo --mode pilot --runs 30 --out results/pilot_v3
```

- `--runs`: Number of paired seeds per tumble rate cell in the main sweep (default: 30).
- `--sweep-runs`: Seeds per cell in ablation/envelope sweeps (default: `max(10, runs // 2)`).
- `--out`: Target directory for CSV datasets and generated figures.

### 5. MeluXina HPC Distributed Execution
To distribute large Monte Carlo campaigns across HPC clusters, use the chunking interface:

```bash
# Example: Running chunk 0 out of 32 chunks on MeluXina
python -m rpo_project.montecarlo --mode full --runs 500 --chunk 0 --num-chunks 32 --out results_hpc
```

Or submit the Slurm batch array job:
```bash
sbatch rpo_project/meluxina_slurm.sh
```

---

## Outputs & Core Publication Plots

Upon completion, four high-resolution publication figures are generated in the output directory:

| Figure | Filename | Description |
|:-------|:---------|:------------|
| **Plot 1** | `plot1_terminal_pass_vs_tumble.png` | **Terminal Pass Rate vs. Tumble Rate** with Wilson 95% confidence intervals across preparation tiers ($C_0$ to $C_3$). |
| **Plot 2** | `plot2_c2_beacon_ablation.png` | **C2 Beacon Ablation Study** illustrating pass rate sensitivity across packet loss rates ($0\%$ to $75\%$) and transmission frequencies ($0.5$, $1.0$, $2.0\text{ Hz}$). |
| **Plot 3** | `plot3_2d_servicing_envelope.png` | **2D Servicing Envelope** mapping capture feasibility as a 2D contour over vision noise $\sigma_{\text{pos}}$ vs. client tumble rate $\omega$. |
| **Plot 4** | `plot4_preparation_trade_curve.png` | **Preparation Trade Curve** showing mean $\Delta V$ consumption [m/s] and time-to-capture [s] across tiers. |

---

## 20-Column Simulation Schema

Each simulation run generates a structured record containing the exact 20-column schema defined in Handbook Section 12:

```csv
scenario,seed,tumble_deg_s,vision_sigma_m,beacon_enabled,beacon_packet_loss,beacon_rate_hz,latency_s,theta0_rad,status,terminal_pass,aborted,unsafe,minimum_clearance_m,capture_point_error_m,relative_speed_mps,delta_v_mps,elapsed_s,model_version,config_hash
```

| Field Name | Type | Description |
|:-----------|:-----|:------------|
| `scenario` | string | Preparation tier identifier (`C0_unprepared`, `C1_fiducials`, `C2_beacon`, etc.) |
| `seed` | int | Paired random seed index |
| `tumble_deg_s` | float | Target satellite initial tumble rate [deg/s] |
| `vision_sigma_m` | float | Optical sensor 1-$\sigma$ position noise [m] |
| `beacon_enabled` | bool | Boolean flag indicating active RF beacon state |
| `beacon_packet_loss`| float | Bernoulli packet dropout probability ($[0.0, 1.0]$) |
| `beacon_rate_hz` | float | Beacon transmission frequency [Hz] |
| `latency_s` | float | RF broadcast transmission and processing delay [s] |
| `theta0_rad` | float | Initial client attitude angle in orbit plane [rad] |
| `status` | string | Terminal status (`TERMINAL_CAPTURE_WINDOW_MET`, `ABORT_*`, `UNSAFE_*`, `TIMEOUT`) |
| `terminal_pass` | bool | `True` if position, velocity, and alignment criteria satisfied for dwell window |
| `aborted` | bool | `True` if safe abort gate triggered (rate limit, covariance limit, or line-of-sight) |
| `unsafe` | bool | `True` if chaser violated keep-out zone barrier ($r < R_{\text{keepout}}$) |
| `minimum_clearance_m`| float | Minimum distance margin relative to keep-out sphere surface [m] |
| `capture_point_error_m`| float | Temporal RMS capture-point prediction error [m] over prediction horizon |
| `relative_speed_mps` | float | Relative speed between chaser and capture fixture at terminal/abort instant [m/s] |
| `delta_v_mps` | float | Cumulative translational velocity increment expended [m/s] |
| `elapsed_s` | float | Total simulation duration until termination [s] |
| `model_version` | string | Version identifier (e.g. `Phase2-RPO-MC-v3.0`) |
| `config_hash` | string | 10-character SHA-256 hash of configuration parameters |

---

## Research Integrity & Guardrails

To prevent data hallucination and ensure scientific defensibility (Handbook Section 1):
- **Terminal Window Condition vs. Contact Dynamics:**
  `terminal_pass` evaluates conditional terminal-window dwell feasibility (position within $0.20\text{ m}$, relative velocity $< 0.055\text{ m/s}$, capture axis alignment within $15^\circ$, and zero keep-out violations maintained for $\ge 2.0\text{ s}$). It does **not** simulate physical latch contact dynamics, mechanical compliance, or structural rebound.
- **Strict Information Separation (No Truth Leakage):**
  Guidance, control, and abort logic operate strictly on state estimates from `RPOEstimator`. Ground truth states from physics integrators are strictly sequestered for metric scoring and collision barrier verification.
- **Scope of Conclusions:**
  Results assess relative robustness benefits between preparation tiers under modeled conditions; they should not be extrapolated as absolute mission success probabilities for operational flight readiness without higher-fidelity orbital perturbation modeling (e.g., $J_2$, SRP, third-body gravity).

---

## Authors & Citation

Developed for the **Orbit Observers / ClearSpace Phase 2** research consortium.
For questions, contributions, or reporting anomalies, please open an issue or pull request on [GitHub](https://github.com/Siddharthpatni/Orbit_Observers).
