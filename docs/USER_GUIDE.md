# User Guide — installing, running and reading the outputs

**Audience:** anyone who wants to run the simulator, from first-time users to HPC operators. No aerospace background needed; basic terminal use is assumed.

---

## 1. Install (once)

Requires Python 3.10 or newer.

```bash
git clone https://github.com/Siddharthpatni/Orbit_Observers.git
cd Orbit_Observers
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

All commands below are run from the repository root with the virtual environment active.

## 2. The five things you can do

| I want to… | Command | Time on a laptop |
|:--|:--|:--|
| Check the physics and code are correct | `python -m rpo_project.montecarlo --mode verify` | ~10 s |
| Run a quick campaign | `python -m rpo_project.montecarlo --mode pilot --runs 30 --out results/my_pilot` | ~1 min |
| Run a publication-size campaign | `python -m rpo_project.montecarlo --mode full --runs 500 --sweep-runs 200 --out results/my_full` | ~7 min (10 cores) |
| Look at one run in detail | `python -m rpo_project.replay --scenario C0_unprepared --seed 12 --tumble 3 --out results/replay` | ~1 s |
| Run the automated tests | `python -m unittest discover -s rpo_project/tests -t .` | ~10 s |

Every campaign first runs the 10-point V&V suite and stops if anything fails (skip with `--skip-verify`).

## 3. Campaign options

```
python -m rpo_project.montecarlo --mode {verify,pilot,full,merge,analyse} [options]
```

| Option | Default | Meaning |
|:--|:--|:--|
| `--runs N` | 30 | Paired seeds per cell of the `main` study. `full` mode enforces ≥ 200. |
| `--sweep-runs N` | max(10, runs/2) | Paired seeds per cell of the `ablation`, `envelope` and `latency` studies. |
| `--studies a,b` | all | Run a subset: `main`, `ablation`, `envelope`, `latency`. |
| `--workers N` | all cores (or `$SLURM_CPUS_PER_TASK`) | Parallel processes. Results do not depend on this. |
| `--master-seed N` | 0 | Change for an independent replication of the whole campaign. |
| `--out DIR` | `results_rpo` | Output folder. |
| `--chunk K --num-chunks N` | – | Run only slice *K* of *N* (HPC job arrays). |
| `--skip-verify` | off | Do not run the V&V suite first. |

Modes: `merge` combines HPC chunks then analyses; `analyse` rebuilds tables, figures and report from existing CSVs (e.g. after changing a plot).

Campaign size = Σ over studies of (cells × runs × tiers) = `35·runs + 88·sweep_runs` simulations with all four studies. Each takes ~50 ms on one core.

## 4. Running on MeluXina (or any Slurm cluster)

Everything for the LuxProvide supercomputer — SSH access, storage, one-time Python setup, job scripts, monitoring and troubleshooting — is in **[hpc/README.md](../hpc/README.md)**. In short:

```bash
salloc -A <project> -p cpu --qos test -N 1 -t 00:30:00 && bash hpc/setup_env.sh   # once
sbatch -A <project> hpc/run_campaign.slurm                                       # whole campaign on one 128-core node
```

For very large campaigns, `hpc/run_campaign_array.slurm` splits the work into chunks and `hpc/merge.slurm` combines them; the merge refuses incomplete or mixed chunk sets, and the merged result is identical to a single-node run.

## 5. What a campaign produces

| File | What it is | Who it is for |
|:--|:--|:--|
| `report.md` | Plain-language summary: headline tables, tier comparisons, safety, precision, limitations | Everyone — **start here** |
| `plot1_terminal_pass_vs_tumble.png` | Pass rate vs tumble rate, one line per tier, 95% bands | Everyone |
| `plot2_c2_beacon_ablation.png` | Beacon value vs packet loss and update rate | Beacon/comms team |
| `plot3_2d_servicing_envelope.png` | Map of where servicing works (tumble × optical noise) | Systems / requirements |
| `plot4_preparation_trade_curve.png` | Prediction error, abort rate and Δv per tier at 3°/s | Systems / proposal |
| `plot5_beacon_latency.png` | Beacon value vs delay | Beacon/comms team |
| `plot6_outcome_breakdown.png` | How every run ended | Everyone |
| `plot7_convergence.png` | Has the campaign run long enough? | Stats / reviewers |
| `summary_<study>.csv` | One row per tier and cell: rates with 95% intervals, means, worst-case clearance | Analysts |
| `paired_comparisons.csv` | Tier differences on identical seeds with McNemar p-values | Analysts |
| `outcome_breakdown.csv` | Count of each final status per tier and tumble rate | Analysts |
| `failure_cases.csv` | Every run that did not meet the terminal window, with what is needed to replay it | Engineers |
| `runs_<study>.csv` | One row per simulation | Analysts |
| `manifest.json` | Exact configuration, seeds, versions, git commit, timing | Reproducibility / audit |

### Columns of `runs_<study>.csv`

The first 20 columns follow Handbook §12 exactly:

| Column | Unit | Meaning |
|:--|:--|:--|
| `scenario` | – | Client tier (`C0_unprepared` … `C3_ios_mode`) |
| `seed` | – | Run seed (same seed = same disturbances across tiers) |
| `tumble_deg_s` | °/s | Client tumble rate |
| `vision_sigma_m` | m | Optical position noise before the tier scale |
| `beacon_enabled` | bool | Tier has a Service Beacon |
| `beacon_packet_loss` | 0–1 | Packet-loss probability (1.0 when no beacon) |
| `beacon_rate_hz` | Hz | Beacon update rate (0 when no beacon) |
| `latency_s` | s | Beacon delay (0 when no beacon) |
| `theta0_rad` | rad | Initial client orientation |
| `status` | – | `TERMINAL_CAPTURE_WINDOW_MET`, `ABORT_*`, `UNSAFE_KEEPOUT_VIOLATION` or `TIMEOUT` |
| `terminal_pass` / `aborted` / `unsafe` | bool | Outcome flags |
| `minimum_clearance_m` | m | Closest approach to the keep-out sphere surface (negative = violation) |
| `capture_point_error_m` | m | RMS error predicting the capture point 2 s ahead |
| `relative_speed_mps` | m/s | Speed relative to the capture point at the end |
| `delta_v_mps` | m/s | Fuel used, as velocity change |
| `elapsed_s` | s | Time at the end of the run |
| `model_version`, `config_hash` | – | Which model and exact assumptions produced the row |

Additional diagnostics follow: `master_seed`, `propellant_kg`, `terminal_phase_entry_s`, `vision_update_fraction`, `beacon_rate_updates`, `final_angle_std_deg`, `final_rate_error_deg_s`, the sampled dispersions (`init_offset_m`, `init_speed_mps`, `tumble_axis_tilt_deg`, `thruster_gain_error_pct`, `thruster_misalign_deg`), and the `study` and `cell` the run belongs to.

## 6. Investigating a failure

1. Open `failure_cases.csv` and pick a row.
2. Replay it with the same inputs (all columns are in the row):
   ```bash
   python -m rpo_project.replay --scenario C0_unprepared --seed 12 --tumble 3 \
       --vision-sigma 0.05 --packet-loss 0.2 --beacon-rate 1 --latency 0.1 --master-seed 0 --out results/replay
   ```
3. The PNG shows the path around the client, distances, relative speed and the tumble-rate estimate against the abort threshold; the CSV has every time step.

## 7. Changing assumptions

* **A model number** (thrust limit, sensor noise, gates …): edit `SimConfig` in `rpo_project/config/__init__.py`. The `config_hash` in every output row changes automatically, so old and new results can never be confused.
* **A client tier**: edit or add a `ScenarioSpec` in the same file.
* **A study grid**: edit or add a `Study` in `STUDIES` in `rpo_project/montecarlo.py`.
* Re-run `--mode verify` and the unit tests after any change.

## 8. Troubleshooting

| Symptom | Fix |
|:--|:--|
| `ModuleNotFoundError: numpy` | Activate the virtual environment: `source .venv/bin/activate`. |
| `beacon period must be an integer multiple of dt_s` | 1 / (beacon rate × 0.25 s) must be a whole number, e.g. 0.1, 0.5, 1, 2 or 4 Hz. |
| `missing chunks [...]` during merge | Rerun those array indices, then merge again. |
| `chunk N disagrees on 'config_hash'` | Chunks were produced with different code/config; rerun them all from one version. |
| Matplotlib font-cache warnings on a cluster | `export MPLCONFIGDIR=$TMPDIR/mpl` before running. |
