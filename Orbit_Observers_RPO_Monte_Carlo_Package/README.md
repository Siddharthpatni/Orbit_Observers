# Orbit Observers / ClearSpace Phase 2 — RPO Monte Carlo Simulation Package

**Model Maturity Label:** Early-stage, scenario-based, low-to-medium-fidelity RPO robustness assessment (Handbook Section 13).

Python model `v2.1` requires the estimated velocity relative to the moving hold point
to fall within `terminal_vel_tol_mps` before entering terminal approach. This fixes
the stationary, perfect-sensor verification case, which previously crossed the keep-out
boundary after switching to terminal approach before braking finished. The MATLAB
implementation has not been updated to this controller revision.

## Contents of This ZIP Archive
1. `matlab/rpo_monte_carlo_sim.m` — Complete standalone MATLAB simulator (requires zero paid toolboxes).
2. `matlab/run_and_export_all.m` — One-click MATLAB runner script that executes all 10 V&V tests, runs the paired-seed campaign, and saves all CSVs and 4 OSIP plots.
3. `rpo_project/` — Full multi-file Python architecture matching Section 12 of the Handbook:
   - `config/__init__.py` — GEO constants, spacecraft geometry, and client preparation tiers (`C0`-`C3`).
   - `dynamics.py` — 3D Clohessy-Wiltshire (CW) equations, RK4 integrator, and analytical 6x6 STM.
   - `attitude.py` — 3D quaternion kinematics, rigid-body Euler equations, and LVLH capture-point velocity.
   - `sensors.py` — Camera/fiducial pose & position observations with occlusion and dropout.
   - `beacon.py` — Independent Service Beacon packet generator with timestamps, Bernoulli loss, and latency.
   - `estimator.py` — Strictly separated Translation & Attitude/Rate Kalman Filter with timestamp latency compensation.
   - `guidance.py` — Two-stage hold-point and terminal capture-point PD controller with thrust saturation.
   - `safety.py` — Keep-out sphere barrier, covariance/rate abort gates, and terminal capture window dwell logic.
   - `simulate.py` — Single closed-loop simulation run returning the exact 20-column schema (Section 12).
   - `analyse.py` — Wilson 95% binomial confidence intervals and the 4 publishable plots (Section 11).
   - `montecarlo.py` — Paired-seed sweep runner with MeluXina HPC `--chunk` support (Section 14).
   - `tests/test_vv.py` — Automated test suite verifying all 10 mandatory V&V checks (Section 13).
   - `rpo_beacon_information_pilot.py` — Original Stage-I 2D information-value pilot script for reference.
   - `meluxina_slurm.sh` — Slurm job array batch script for LuxProvide MeluXina HPC.

---

## How to Run in MATLAB
1. Extract this ZIP archive and open the `matlab/` folder in MATLAB.
2. Run in the MATLAB Command Window:
   ```matlab
   rpo_monte_carlo_sim('pilot', 30, 'results_matlab')
   ```
   Or open `run_and_export_all.m` and click **Run**.

---

## How to Run in Python
1. From the starter package directory, enter this package and install dependencies in a virtual environment (macOS/Linux):
   ```bash
   cd Orbit_Observers_RPO_Monte_Carlo_Package
   python3 -m venv .venv
   source .venv/bin/activate
   python -m pip install -r requirements.txt
   ```
2. Run the 10-point Verification & Validation suite:
   ```bash
   python -m rpo_project.montecarlo --mode verify
   ```
3. Start with a quick smoke campaign (89 simulations, all 4 plots):
   ```bash
   python -u -m rpo_project.montecarlo --mode pilot --runs 1 --sweep-runs 1 --out results_smoke
   ```
   This checks the workflow; one run per cell is insufficient for research conclusions.
4. Run the paired-seed Monte Carlo campaign and generate all 4 plots:
   ```bash
   python -m rpo_project.montecarlo --mode pilot --runs 30 --out results_rpo
   ```
   The default campaign runs 1,050 main simulations and 810 ablation/envelope simulations.
   `--runs` controls main-sweep runs per cell; `--sweep-runs` controls ablation/envelope runs per cell
   and defaults to `max(10, runs // 2)`. Each campaign first runs the 10 V&V checks.
   Progress is printed during the main sweep and at the start of each secondary sweep.
   CSVs and PNG plots are saved under `--out`. Chunked runs export only their main-sweep CSV.

   Run the runner regression checks with:
   ```bash
   python -m unittest rpo_project.tests.test_montecarlo
   ```

---

## Research Integrity & Non-Hallucination Guardrails (Handbook Section 1)
- `p_terminal_pass` measures conditional terminal-window feasibility (position, relative velocity, alignment, and keep-out compliance over the dwell window). It does **not** verify physical latch contact forces or fleet-wide GEO tumble incidence.
- All guidance and safety decisions operate strictly on `RPOEstimator` states without truth leakage.
