# Orbit Observers / ClearSpace Phase 2 — RPO Monte Carlo Simulator

**How much does preparing a satellite for servicing make a future rescue safer?**
This package simulates a robotic servicer approaching a possibly tumbling client satellite in geostationary orbit, and runs that approach tens of thousands of times with random disturbances (a *Monte Carlo* study) to measure how client preparation — visual markers, a radio Service Beacon, a cooperative servicing mode — changes the odds of a safe terminal approach.

**Model maturity:** early-stage, scenario-based, low-to-medium-fidelity RPO robustness assessment (Handbook §13). Results are conditional on stated assumptions; "terminal window met" is **not** physical capture.

---

## Start here

| You are… | Read |
|:--|:--|
| New to the project, or non-technical | [docs/GUIDE_FOR_EVERYONE.md](docs/GUIDE_FOR_EVERYONE.md) — the problem, the tiers, what Monte Carlo means, how to read the results |
| Looking for the latest results | [results/v4_0/report.md](results/v4_0/report.md) — auto-generated campaign report with figures |
| Wanting to run the code | [docs/USER_GUIDE.md](docs/USER_GUIDE.md) — install, commands, output files, troubleshooting |
| Running on the MeluXina supercomputer | [hpc/README.md](hpc/README.md) — SSH, storage, Python setup, Slurm jobs, monitoring |
| Wanting to understand how it is built | [docs/SYSTEM_ARCHITECTURE.md](docs/SYSTEM_ARCHITECTURE.md) — subsystems and flight modes, no background assumed |
| Reviewing the statistics | [docs/MONTE_CARLO_METHOD.md](docs/MONTE_CARLO_METHOD.md) — dispersions, paired seeds, studies, confidence intervals, sample sizes |
| Reviewing the physics | [docs/MODEL_REFERENCE.md](docs/MODEL_REFERENCE.md) — every equation, parameter and limitation |
| Tracing what changed | [CHANGELOG.md](CHANGELOG.md) · historical [docs/PERFORMANCE_AUDIT.md](docs/PERFORMANCE_AUDIT.md) |

## Quick start

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python -m rpo_project.montecarlo --mode verify                       # 10-point V&V suite (~10 s)
python -m rpo_project.montecarlo --mode pilot --runs 30 --out results/pilot   # quick campaign (~1 min)
open results/pilot/report.md                                         # or any Markdown viewer
```

Publication-size campaign and replaying single runs: see the [User Guide](docs/USER_GUIDE.md). MeluXina: see [hpc/README.md](hpc/README.md).

## Headline results (v4.0)

35 100 closed-loop simulations, 500 paired seeds per main cell (200 for the other studies), master seed 0. Full report: [results/v4_0/report.md](results/v4_0/report.md).

![Terminal-window pass rate vs tumble rate](results/v4_0/plot1_terminal_pass_vs_tumble.png)

| # | Finding | Evidence (95% intervals; paired McNemar tests) |
|:-:|:--|:--|
| 1 | Below ~1°/s tumble, **every tier** reaches the terminal window. | ≥ 99.6% for all tiers at 0–1°/s |
| 2 | **Passive fiducials (C1) matter from 2°/s.** | 2°/s: C0 95% [92–96] → C1 100% (+5 pp, p ≈ 10⁻⁸). 3°/s: C0 35% [31–39] → C1 83% [79–86] (+48 pp) |
| 3 | **A beacon carrying the spin rate (C2) closes the gap at 3°/s; an ID-only beacon does nothing.** | 3°/s: C2 100% [99–100] vs C1 83% (+17 pp, p ≈ 10⁻²⁶); C2-ID = C1 on every seed |
| 4 | The beacon's value is in the **abort decision**, not in prediction accuracy: rate packets stop the early rate-estimate overshoot that triggers false "tumbling too fast" aborts. | 3°/s: P(abort) 17% (C1) → 0% (C2); RMS capture-point error 0.073 vs 0.074 m |
| 5 | **Beacon requirements are modest** under a steady tumble. | ≥ 1 Hz: 100% up to 75% packet loss; 0.5 Hz: 96% at 75% loss; latency up to 2 s: no effect |
| 6 | **At 5°/s every non-cooperative tier aborts safely** (3.2°/s gate, by design); only C3, where the client slows itself, proceeds. | C0–C2: 0% pass, 100% abort, 0 unsafe; C3: 100% |
| 7 | **Rare, shallow keep-out violations appear when optical position noise is large** — invisible in earlier 30-seed campaigns. | 23 of 35 100 runs, all ≤ 1 cm deep, all with noise ≥ 12.5 cm (C0, or the 25 cm envelope row); none at ≤ 10 cm |

**What this suggests (to be confirmed):** fiducials are the single most valuable provision; a rate-carrying beacon at ≥ 1 Hz extends the safe envelope to ~3°/s; terminal approach should require optical position accuracy of ~10 cm or better, or add an abort gate on position uncertainty (not yet modelled — the capture fixture sits only 15 cm outside the keep-out sphere). The latency result holds only for a steady tumble. All numbers are conditional on the model's illustrative assumptions.

## Client preparation tiers

| Tier | Client provisions | Model effect |
|:--|:--|:--|
| `C0_unprepared` | none | 12° attitude noise, 2.5× position noise, 30% camera dropouts |
| `C1_fiducials` | markers / retro-reflectors | 3° attitude noise, 8% dropouts |
| `C2_id_only` | C1 + beacon carrying identity only | navigation identical to C1 (ablation control) |
| `C2_beacon` | C1 + beacon carrying the spin rate | time-stamped rate packets with loss and latency |
| `C3_ios_mode` | C2 + cooperative IOS mode | client slows its own tumble to 5% — **changes dynamics**, reported separately |

C0, C1 and C2 are always compared on identical random conditions (paired seeds), so differences are caused by the preparation, not by luck.

## What a proper Monte Carlo means here

* **Everything uncertain is randomised in every run** — servicer start state, client orientation, spin axis and inertia, camera noise and dropouts, beacon losses, thruster bias, misalignment and noise.
* **Paired, reproducible seeds** from independent random streams: any row of any CSV can be re-flown exactly (`python -m rpo_project.replay`).
* **Four studies:** tier vs tumble rate, beacon loss × rate ablation, tumble × camera-noise envelope, beacon latency.
* **Honest uncertainty:** Wilson 95% intervals on every rate, exact McNemar tests for tier-vs-tier differences, convergence plot, zero-event upper bounds.
* **Scales from laptop to MeluXina:** parallel workers, Slurm chunking and a validated merge, with identical results however the work is split; `manifest.json` records exactly how results were produced.

## Repository layout

```
rpo_project/
  config/         every model assumption (SimConfig) and the tier definitions
  dynamics.py     Clohessy–Wiltshire relative orbit motion (RK4 + analytic STM)
  attitude.py     quaternion rigid-body tumble, capture-point geometry
  sensors.py      camera/fiducial measurements with noise, dropouts, occlusion
  beacon.py       Service Beacon packets with loss, latency and timestamps
  estimator.py    Kalman filters for position/velocity and angle/rate
  guidance.py     hold point → terminal approach, braking PD controller
  safety.py       abort gates, keep-out check, terminal-window scoring
  simulate.py     one closed-loop run; all random draws made up front
  montecarlo.py   studies, paired seeds, parallel/HPC execution, merge, CLI
  stats.py        Wilson, McNemar, paired differences, sample-size planning
  analyse.py      summary tables, figures, report.md
  replay.py       re-fly and plot any single run
  tests/          V&V suite + unit tests
hpc/              MeluXina setup guide, environment and Slurm job scripts
results/          v4_0 (current), optimized_v3_0, baseline_v2_1, smoke_v2_1 (historical)
docs/             guides listed above + reference material (Handbook PDF, slides)
examples/stage1/  original Stage-I information-value pilot
archive/          earlier MATLAB / Python prototypes
```

## Tests

```bash
python -m unittest discover -s rpo_project/tests -t .
```

Covers the 10 Handbook §13 verification checks, the statistics against hand-computed values, and the campaign runner (pairing, chunk/merge integrity, parallel = serial).

## Research integrity

* Guidance and abort logic see only estimates, never the true state.
* Abort, unsafe and terminal-window outcomes are reported separately; an abort is the safety system working.
* C3 changes the client's motion and is never presented as evidence that information alone helped.
* Zero keep-out violations in *N* runs bounds the rate only within the model (≈ 3/N), not flight safety.
* All numbers are illustrative study assumptions, not ClearSpace hardware data. See [MODEL_REFERENCE.md §11](docs/MODEL_REFERENCE.md#11-known-limitations).

Developed for the Orbit Observers / ClearSpace Phase 2 study. Questions and contributions: open an issue or pull request on [GitHub](https://github.com/Siddharthpatni/Orbit_Observers).
