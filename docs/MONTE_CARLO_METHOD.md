# Monte Carlo Method — experiment design and statistics

**Audience:** anyone who needs to judge whether the numbers are trustworthy — engineers, reviewers, statisticians.
**Implements:** Handbook Sections 10 (experiment design), 11 (metrics and uncertainty) and 14 (HPC).

---

## 1. What the Monte Carlo is for

A single simulation answers "what happens on *this* day, with *this* noise". The Monte Carlo runs the same closed-loop simulation thousands of times, each time with different — but reproducible — random disturbances, and reports **how often** each outcome occurs and **how sure** we are of that frequency.

It estimates *conditional* performance: "given these assumptions about sensors, thrusters and client motion, tier C2 reaches the terminal window in X% of runs at 3°/s". It does **not** say how often real GEO satellites tumble, and zero failures in N runs does not prove flight-level safety (Handbook §10).

## 2. Two kinds of inputs

| | Design variables (the *grid*) | Uncertain disturbances (the *dispersions*) |
|:--|:--|:--|
| Meaning | Conditions we want to compare | Things we cannot control or know exactly |
| How chosen | Fixed list of values per study | Random, freshly drawn in every run |
| Examples | Tier C0–C3, tumble rate, optical noise level, beacon loss / rate / latency | Initial position and velocity, client orientation, spin-axis tilt, inertia, sensor noise, dropouts, packet loss, thruster bias, misalignment and noise |

### Dispersions drawn in every run

| Quantity | Distribution | Stream |
|:--|:--|:--|
| Initial client yaw | U(−180°, 180°) | target |
| Spin-axis tilt from body *z* | N(0, 2°) on each of two axes | target |
| Client principal inertias | nominal × (1 + 0.05·N(0,1)), clipped to [0.5, 1.5] | target |
| Initial servicer position offset | N(0, 0.5 m) per axis | initial |
| Initial servicer velocity | N(0, 0.015 m/s) per axis | initial |
| Camera dropout | Bernoulli(p_drop of tier) per frame | vision |
| Camera position / yaw noise | N(0, σ_pos) per axis / N(0, σ_θ) per frame | vision |
| Beacon packet loss | Bernoulli(p_loss) per packet | beacon |
| Beacon rate-sensor noise | N(0, 0.08°/s) per packet | beacon |
| Thruster gain bias | N(0, 2%) per axis, fixed for the run | thruster |
| Thruster misalignment | rotation vector N(0, 0.5°) per axis, fixed for the run | thruster |
| Thruster execution noise | N(0, 2%) per axis, per step | thruster |

## 3. The four studies

Each study is defined declaratively in `STUDIES` in [`rpo_project/montecarlo.py`](../rpo_project/montecarlo.py). Values not swept use the nominal inputs: optical noise 5 cm, packet loss 20%, beacon 1 Hz, latency 0.1 s.

| Study | Question | Tiers | Grid | Fixed | Runs per cell |
|:--|:--|:--|:--|:--|:--|
| `main` | Does client preparation help, and up to what tumble rate? | all five | tumble 0, 0.25, 0.5, 1, 2, 3, 5 °/s | – | `--runs` |
| `ablation` | Which beacon packet loss and update rate are good enough? | C2-ID, C2 | loss 0–75% × rate 0.5, 1, 2 Hz | tumble 3 °/s | `--sweep-runs` |
| `envelope` | Where in (tumble × optical noise) is servicing feasible? | C1, C2 | tumble 0–5 °/s × noise 2–25 cm | – | `--sweep-runs` |
| `latency` | How much beacon delay is tolerable? | C2-ID, C2 | latency 0, 0.1, 0.5, 1, 2 s | tumble 3 °/s | `--sweep-runs` |

The beacon studies run at 3 °/s because at lower rates every tier passes, so nothing could be learned about beacon requirements there. Adding a study is a matter of adding one `Study(...)` entry.

## 4. Seeds: pairing, independence, reproducibility

```
seed = study.seed_offset + i          (main: 0…, ablation: 1 000 000…, envelope: 2 000 000…, latency: 3 000 000…)
SeedSequence([master_seed, seed]) ──spawn──► initial | target | vision | beacon | thruster   (five independent streams)
```

* **Paired across tiers.** All random numbers are drawn *before* the tier is applied, in unit scale (N(0,1), U(0,1)); the tier only rescales them. C0, C1, C2 and C3 with the same seed therefore face the identical initial state, spin axis, noise sequence and thruster errors. Differences between tiers are caused by the tier, not by luck. (V&V check 10 enforces this.)
* **Common random numbers across cells.** Inside a study, seed *i* is reused in every grid cell, so neighbouring cells differ only by the swept parameter — curves are smoother and cell-to-cell differences more precise.
* **Independent across studies.** Different seed blocks per study.
* **Stream isolation.** Each subsystem has its own stream, so adding a new random effect to (say) the thrusters never changes the camera noise of existing runs.
* **Exact reproducibility.** `(master_seed, seed)` plus the row's grid inputs re-create a run bit-for-bit, regardless of worker count or HPC chunking (tested). Use `--master-seed` for an independent replication of a whole campaign.

## 5. Execution: parallel and HPC

* The unit of work is a **task group** = (study, cell, seed) running *every* tier of the study. Groups are distributed over `--workers` processes, and over HPC chunks with `--chunk k --num-chunks N` (round-robin). Pairs are never split.
* Results are written in a fixed order, so serial, parallel and chunked-then-merged campaigns produce **byte-identical** CSVs (tested).
* `--mode merge` refuses chunk sets that are incomplete, duplicated, or come from different campaigns (different config hash, seeds, run counts or studies).
* Each campaign writes `manifest.json`: model version, config hash, full configuration, tier definitions, study definitions with seed ranges, git commit (+ uncommitted-changes flag), software versions, command line, start time and wall time.

## 6. Metrics (per run → per cell)

| Metric | Per run | Per cell |
|:--|:--|:--|
| Terminal window met / abort / unsafe / timeout | outcome flags | rate with **Wilson 95% interval** |
| Capture-point prediction error | RMS over the run of ‖predicted − true capture point 2 s ahead‖ | RMS over runs, 95th percentile |
| Minimum clearance | closest approach to the keep-out sphere surface | mean and **worst case** |
| Δv, propellant | integral of applied ‖a‖ dt; rocket equation (500 kg, 220 s) | mean with 95% interval |
| Time to terminal window | elapsed time of passing runs | mean with 95% interval |

Diagnostic columns (vision update fraction, beacon updates, final rate error, sampled dispersions) let failures be explained, not just counted.

## 7. Statistics

### Pass-rate uncertainty — Wilson score interval
For *k* passes in *n* runs, `p̂ = k/n`; the Wilson 95% interval is used instead of `p̂ ± 1.96·√(p̂(1−p̂)/n)` because the latter collapses to zero width at 0% or 100% and can leave [0, 1] (Handbook §11).

### Comparing two tiers — paired analysis
Because tiers share seeds, each seed gives a *pair* of outcomes. Only **discordant** pairs carry information:

* *b* = seeds where only tier A met the window, *c* = seeds where only tier B did.
* Difference in pass rate: `(c − b)/n`, with the **Agresti–Min** adjusted 95% interval.
* Significance: **exact McNemar test** (two-sided binomial test of *b* vs *c*). `paired_comparisons.csv` and the report flag p < 0.05.

A paired test is far more sensitive than comparing two independent pass rates: 10 seeds where C2 passes and C1 fails, and none the other way, is already significant (p = 0.002), even if both rates are close to 100%.

### Zero-event bound
With 0 keep-out violations in *n* independent seeds **within one tier/grid cell**, the exact one-sided 95% upper bound is `1 − 0.05^(1/n)` ≈ 3/n ("rule of three"). The report shows the largest cellwise upper bound per study. Seeds are reused across tiers and grid cells, so the pooled campaign row count is not an independent binomial sample and receives no pooled bound. For 500 seeds the zero-event bound is about 0.60%; for 200 seeds it is about 1.49%. These are pointwise bounds within the model, not simultaneous grid coverage or flight safety certification.

### How many runs?
Runs needed for a ±*h* interval on a rate near *p*: `n ≈ 1.96²·p(1−p)/h²`.

| Target half-width | p = 50% (worst case) | p = 90% | p = 99% |
|:--|--:|--:|--:|
| ±10 pp | 97 | 35 | 4 |
| ±5 pp | 385 | 139 | 16 |
| ±2 pp | 2 401 | 865 | 96 |

Handbook guidance: 25–100 runs per cell while debugging, 500–2 000 for key cells. `plot7_convergence.png` shows the running estimate and its pointwise band as runs accumulate. This is a descriptive diagnostic, not proof that future estimates will stay inside the current band.

### Rare events
A probability around 10⁻³ needs ~3 000 runs to observe even a few events. Do not report rare-event probabilities from these campaigns; the Handbook asks for them to be kept separate (e.g. importance sampling) — future work.

## 8. Guarding against misleading results (Handbook §11)

* The same servicer design (controller gains, gates) is used for every tier — no per-tier tuning.
* Only C3 changes the client's true motion; it is labelled as an operational-mode benefit in every plot and the report.
* C2-ID-only is included so a beacon that carries no rate information is shown to give **no** navigation benefit (V&V check 4).
* Abort ≠ unsafe ≠ terminal window: reported separately everywhere.
* Every figure shows its uncertainty band; every report carries the model's limitations.

Paired McNemar p-values are unadjusted exploratory comparisons. The convergence figure shows pointwise intervals, not a sequential stopping rule; freeze the sample count before running and use a new master seed for independent confirmation.

## v4.1 replication and retreat

New campaigns record the exact package source files in a ZIP with SHA-256 hashes, including uncommitted code. The approach retains its original random draw arrays; extra retreat samples come from a separate deterministic stream. Retreat fuel and keep-out checks continue after abort. A new master seed tests different random realizations, but a small validation campaign is not hardware validation or a precise risk certification. Historical v4.0 CSVs retain their original stop-at-abort semantics.
