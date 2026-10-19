# Orbit Observers / ClearSpace Phase 2 — RPO Monte Carlo Simulator

**How much does preparing a satellite for servicing make a future rescue safer?**
This package simulates a robotic servicer approaching a possibly tumbling client satellite in geostationary orbit, and runs that approach tens of thousands of times with random disturbances (a *Monte Carlo* study) to measure how client preparation — visual markers, a radio Service Beacon, a cooperative servicing mode — changes the odds of a safe terminal approach.

**Model maturity:** early-stage, scenario-based, low-to-medium-fidelity RPO robustness assessment (Handbook §13). Results are conditional on stated assumptions; "terminal window met" is **not** physical capture.

---

## Current development version: v4.1

v4.1 adds propagated abort retreat, a position-covariance gate, tested IOS command transitions, and source snapshots for campaign reproducibility. See [implementation status](docs/IMPLEMENTATION_STATUS.md) and the [new-seed validation campaign](results/v4_1_validation/report.md). The 35,100-run v4.0 results below are historical evidence and are not relabeled as v4.1 results.

## Start here

| You are… | Read |
|:--|:--|
| New to the project, or non-technical | [docs/GUIDE_FOR_EVERYONE.md](docs/GUIDE_FOR_EVERYONE.md) — the problem, the tiers, what Monte Carlo means, how to read the results |
| Assessing Phase 2 completion | [Project assessment](docs/PROJECT_ASSESSMENT.md) · [Proposal draft and acceptance gates](docs/PHASE2_PROPOSAL.md) |
| Preparing a presentation | [Corrected pitch script](docs/PLAIN_LANGUAGE_PITCH_DECK.md) — existing PDF/PPTX exports still need synchronization |
| Looking for the latest results | [results/v4_0/report.md](results/v4_0/report.md) — auto-generated campaign report with figures |
| Wanting to run the code | [docs/USER_GUIDE.md](docs/USER_GUIDE.md) — install, commands, output files, troubleshooting |
| Running on the MeluXina supercomputer | [hpc/README.md](hpc/README.md) — SSH, storage, Python setup, Slurm jobs, monitoring |
| Wanting to understand how it is built | [docs/SYSTEM_ARCHITECTURE.md](docs/SYSTEM_ARCHITECTURE.md) — subsystems and flight modes, no background assumed |
| Scope: what the study must show |  [docs/SCOPE_ARCHITECTURE.md](docs/SCOPE_ARCHITECTURE.md) — client states, layered elements, tiers, workstreams, roadmap (from the decks and guide) |
| Costs and break-even (assumption-based) | [docs/ECONOMICS_MODEL.md](docs/ECONOMICS_MODEL.md) · [docs/BEACON_BENCH_PLAN.md](docs/BEACON_BENCH_PLAN.md) |
| Seeing the full platform design | [docs/PLATFORM_ARCHITECTURE.md](docs/PLATFORM_ARCHITECTURE.md) — ground platform + RPO simulator target architecture |
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

| Finding | Recorded evidence and limit |
|:--|:--|
| No observed keep-out violations | 0 / 35,100 runs; worst sampled clearance +2.9 mm. Seeds are reused across cells and tiers, so no pooled binomial risk bound is claimed. |
| Markers provide the largest gain at 3°/s | C0: 208/500 (41.6%, Wilson 95% interval 37.36–45.97%); C1: 459/500 (91.8%, 89.06–93.90%). |
| Rate telemetry adds value | C2: 500/500 (100% observed, 99.24–100%); C2-ID has the same pass outcomes as C1. |
| Better prediction and lower successful-approach delta-v | C1 → C2 at 3°/s: RMS prediction error 0.0781 → 0.0447 m; mean delta-v 1.524 → 1.482 m/s. |
| Link degradation is explored | At 1 Hz: 200/200 C2 passes at each tested loss level through 50%, 199/200 at 75%. Separate latency cells through 2 s give 200/200; combined worst cases are untested. |
| Cooperation changes the feasible case | At the tested 5°/s, C0–C2 abort and C3 passes after an assumed 95% reduction in initial spin. No 10°/s cell exists in this campaign. |

**Interpretation:** these results support further validation of passive markers and rate telemetry for the tested approach scenarios. They establish neither guaranteed capture nor a fleet-wide servicing probability. Zero violations in one 500-seed cell gives a one-sided 95% model-risk upper bound of about 0.60%; a 200-seed cell gives about 1.49%. These are pointwise bounds.

**Engineering estimates:** assumed beacon loads yield 28.5 mW average and 20.52 Wh over 30 days. Battery mass and link performance need hardware validation. The propellant illustration assumes independent retries and a fixed abort cost; it excludes capture, servicing and transfer costs and is not a forecast of completed rescues.

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

* **Selected uncertainties are randomised in every run** — servicer start state, client orientation, spin axis and inertia, camera noise and dropouts, beacon losses, thruster bias, misalignment and noise.
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
  replay.py       re-fly and plot a run with manifest/source checks
  ios.py          standalone IOS transitions, detumbling and beacon engineering estimates
  tests/          V&V suite + unit tests
hpc/              MeluXina setup guide, environment and Slurm job scripts
results/          v4_1_validation (development validation), v4_0 (historical), optimized_v3_0, baseline_v2_1, smoke_v2_1 (historical)
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
* Zero keep-out violations in *N* independent seeds within one tier/grid cell bounds its modeled rate (≈ 3/N). Reused seeds prevent applying that bound to the pooled campaign count; no flight safety guarantee follows.
* All numbers are illustrative study assumptions, not ClearSpace hardware data. See [MODEL_REFERENCE.md §11](docs/MODEL_REFERENCE.md#11-known-limitations).

Developed for the Orbit Observers / ClearSpace Phase 2 study. Questions and contributions: open an issue or pull request on [GitHub](https://github.com/Siddharthpatni/Orbit_Observers).
