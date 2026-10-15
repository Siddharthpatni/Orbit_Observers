# Changelog

## v4.0 — Monte Carlo framework (`Phase2-RPO-MC-v4.0`)

Results from v4.0 are **not numerically comparable** with v3.0: new dispersions and a new seeding scheme change every random realisation. Use `config_hash` / `model_version` in each row to tell them apart.

### Monte Carlo
- **Full dispersion set (Handbook §10).** In addition to initial state, client orientation and sensor/thruster noise, every run now randomises the client spin-axis tilt (σ = 2°), client inertia (σ = 5%), thruster gain bias (σ = 2%) and thrust-vector misalignment (σ = 0.5°).
- **Stream-isolated, scenario-independent seeding.** All random inputs are drawn up front from five independent `SeedSequence` streams (initial, target, vision, beacon, thruster) in unit scale; tiers only rescale them. Pairing across C0–C3 is guaranteed by construction, and `(master_seed, seed)` reproduces any run.
- **Declarative studies.** `main`, `ablation`, `envelope` and new `latency` study, each with its own seed block. Beacon studies now run at 3°/s, where the beacon matters; the envelope now compares C1 and C2.
- **Parallel execution** over all CPU cores (`--workers`); results are byte-identical to serial runs.
- **Working HPC workflow.** Chunks now cover *all* studies (previously only the main sweep) and keep paired tiers together; new `--mode merge` validates completeness and consistency and then analyses. The Slurm script uses every allocated core.
- **Provenance.** `manifest.json` per campaign: configuration, tiers, study definitions, seed ranges, git commit, software versions, timing.

### Statistics and outputs
- New `stats.py`: Wilson intervals (now clamped so an interval always contains its estimate), mean intervals, exact McNemar test with Agresti–Min interval for paired tier comparisons, zero-event upper bound, sample-size planning, running estimates.
- Summaries add outcome counts, worst-case clearance, Δv and time-to-capture intervals, propellant mass.
- New outputs: `paired_comparisons.csv`, `outcome_breakdown.csv`, `failure_cases.csv`, `report.md`, and plots 5 (latency), 6 (outcome breakdown) and 7 (convergence). Plot 4 no longer uses a dual y-axis. Colour-blind-checked tier palette with markers as second encoding.
- CSV round-trips are bit-exact (`float_precision="round_trip"`).
- New `python -m rpo_project.replay` re-flies and plots any single run.

### Model and code quality
- Every previously hard-coded guidance, safety and estimator constant moved into `SimConfig`, documented and covered by `config_hash` (verified bit-identical behaviour before the dispersion changes). `config_hash` now also covers tier definitions and model version.
- Extra diagnostic columns after the 20 Handbook columns (dispersions drawn, filter health, terminal-phase entry time, propellant).
- V&V suite strengthened (multi-seed checks, packet boundary and latency checks, frame consistency, exact reproducibility) and no longer relies on `assert` (disabled under `python -O`); runnable with `unittest`.
- New unit tests for statistics and the campaign runner (chunk/merge integrity, pairing, parallel = serial).

### HPC (MeluXina)
- New `hpc/` folder: setup guide (`hpc/README.md`) based on the LuxProvide onboarding workshop, `env.sh` (modules + virtualenv or module-only environment, single-threaded maths libraries), `setup_env.sh` (one-time setup + V&V), `run_campaign.slurm` (recommended: whole campaign on one 128-core node), `run_campaign_array.slurm` (chunked, replaces `rpo_project/meluxina_slurm.sh`) and `merge.slurm`.

### Findings surfaced by the larger campaign
- 23 shallow (≤ 1 cm) keep-out violations in 35 100 runs, all with optical position noise ≥ 12.5 cm — not visible in the earlier 30-seed campaigns. Documented in the report, README and model limitations.

### Documentation
- New: `docs/GUIDE_FOR_EVERYONE.md`, `docs/MODEL_REFERENCE.md`, `docs/MONTE_CARLO_METHOD.md`, `docs/USER_GUIDE.md`, `hpc/README.md`, this changelog.
- Updated: `README.md`, `docs/SYSTEM_ARCHITECTURE.md` (broken absolute links fixed, Monte Carlo layer added); `docs/PERFORMANCE_AUDIT.md` marked historical.

## v3.0 — `braking_pd` controller
Closing-speed limiter with reserved braking authority, corrected clearance/error/Δv metrics. See `docs/PERFORMANCE_AUDIT.md`.

## v2.1 — baseline
First closed-loop paired-seed campaign with `legacy_pd`. Archived in `results/baseline_v2_1/`.
