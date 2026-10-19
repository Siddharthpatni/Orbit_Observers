# Running the RPO Monte Carlo on MeluXina

**Audience:** team members with a MeluXina account who want to run this project's Monte Carlo campaigns on the LuxProvide supercomputer. You need basic terminal skills; no prior HPC experience is assumed.

Based on the *MeluXina Onboarding Workshop* (LuxProvide, 13 Oct 2026) and the official documentation at **https://docs.lxp.lu**. Where this guide and the official docs disagree, the docs win.

> **Do you even need MeluXina?** A publication-size campaign (500 runs per main cell, ~35 000 simulations) takes about 7 minutes on a 10-core laptop. MeluXina is worth it for **≥ 1 000 runs per cell, many independent replications (`--master-seed`), or large new parameter grids** — and then a single node usually suffices.

---

## 0. What you need

| Item | Example | Where it comes from |
|:--|:--|:--|
| User ID | `u101234` | LuxProvide account e-mail |
| Project (account) ID | `p200567` | Your project allocation; check with `myquota` |
| Ed25519 SSH key registered with LuxProvide | `~/.ssh/id_ed25519_mlux` | Step 1 |

Throughout this guide replace `u101234` and `p200567` with your own IDs.

## 1. SSH access (once, on your laptop)

MeluXina only accepts **Ed25519 key pairs**. Create one and register the *public* key as described in https://docs.lxp.lu/first-steps/connecting/:

```bash
ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519_mlux        # choose a passphrase
cat ~/.ssh/id_ed25519_mlux.pub                          # this is what you register
```

Add this block to `~/.ssh/config` so that `ssh meluxina` just works (port **8822**):

```
Host meluxina
    User u101234
    Port 8822
    Hostname login.lxp.lu
    IdentityFile ~/.ssh/id_ed25519_mlux
    ConnectTimeout 15
    ServerAliveCountMax 30
    ServerAliveInterval 60
```

Test it, and look at your allocation:

```bash
ssh meluxina
myquota          # compute node-hours and storage per project
```

Windows users: use MobaXterm or WSL. Prefer a GUI? VS Code *Remote – SSH* (https://docs.lxp.lu/howto/VSCodeOnMeluxina/) or the web portal https://portal.lxp.lu (OpenOnDemand, MFA login).

## 2. Know the two kinds of nodes

| | Login nodes (where `ssh` lands) | Compute nodes (via Slurm) |
|:--|:--|:--|
| Use for | editing, `git`, copying files, submitting jobs | running Python and simulations |
| `module` command / Python modules | **not available** | available |
| Heavy computation | **not allowed** | yes |

Everything that runs Python — including environment setup — happens on a compute node, reached with `salloc` (interactive) or `sbatch` (batch).

## 3. Put the code in the right place

| Storage | Path | Use for this project |
|:--|:--|:--|
| Personal home | `/home/users/u101234` | small personal files |
| Project home (permanent, small quota) | `/project/home/p200567` | **the repository and its virtualenv** |
| Project scratch (large, fast, **not backed up**) | `/project/scratch/p200567` | **campaign outputs**; copy results you need elsewhere |

On a login node:

```bash
mkdir -p /project/home/p200567/$USER && cd /project/home/p200567/$USER
git clone https://github.com/Siddharthpatni/Orbit_Observers.git
cd Orbit_Observers
```

…or push your local working copy from your laptop (useful for uncommitted changes):

```bash
rsync -az --exclude .venv --exclude .git --exclude 'results/' \
    ./ meluxina:/project/home/p200567/$USER/Orbit_Observers/
```

> The workshop slide on `rsync` shows `ssh -p 2222`; MeluXina's SSH port is **8822**. With the `~/.ssh/config` alias above you never need to type the port.

## 4. Set up Python (once)

Get an interactive compute node on the high-priority `test` QOS (max 30 min), then run the setup script from the repository root:

```bash
salloc -A p200567 -p cpu --qos test -N 1 -t 00:30:00
cd /project/home/p200567/$USER/Orbit_Observers
bash hpc/setup_env.sh
exit                                   # release the node
```

`setup_env.sh` loads the MUSE `Python` module, creates `.venv-meluxina/` inside the repository, installs `requirements.txt`, and runs the 10-point V&V suite. It ends with `Setup complete … V&V suite passed`.

**If `pip install` fails** (no internet from the node), use the pre-installed MUSE packages instead — no virtualenv needed. Before any `source hpc/env.sh` or `sbatch`, run:

```bash
export MLUX_ENV=modules          # loads Python + SciPy-bundle (numpy, pandas) + matplotlib modules
```

**If a module name differs** on your software release (check with `module avail Python`, `module spider matplotlib`), override it, e.g. `export MLUX_PYTHON_MODULE=Python/3.12.3-GCCcore-13.3.0`. Python ≥ 3.10 is required.

A third option is a container (Apptainer, `module load Apptainer`; https://docs.lxp.lu/containerization/apptainer/) — not needed for this project.

## 5. First run: a small test

From the repository root on a login node:

```bash
MODE=pilot RUNS=30 sbatch -A p200567 --qos=test hpc/run_campaign.slurm
squeue -u $USER                         # PD = waiting, R = running
cat rpo_mc_<jobid>.log                  # progress and the summary table
```

The results land in `results/meluxina_<jobid>/` with `report.md`, the figures and CSVs (see the [User Guide](../docs/USER_GUIDE.md#5-what-a-campaign-produces)).

## 6. Production campaigns: one node

```bash
OUT=/project/scratch/p200567/rpo/v4_1000 RUNS=1000 SWEEP_RUNS=300 \
    sbatch -A p200567 hpc/run_campaign.slurm
```

`run_campaign.slurm` takes one full CPU node (`--cpus-per-task=128`) and runs one simulation worker per core. Settings are passed as environment variables:

| Variable | Default | Meaning |
|:--|:--|:--|
| `RUNS` | 1000 | paired seeds per cell of the main study |
| `SWEEP_RUNS` | 300 | paired seeds per cell of the other studies |
| `MASTER_SEED` | 0 | change for an independent replication |
| `OUT` | `results/meluxina_<jobid>` | output folder (use scratch for big runs) |
| `MODE` | `full` | `pilot` allows `RUNS` < 200 |
| `STUDIES` | all | e.g. `main,latency` |

Approximate size and run time (simulations ≈ `35·RUNS + 88·SWEEP_RUNS`, ~0.05–0.1 core-seconds each):

| RUNS / SWEEP_RUNS | Simulations | Core-hours | Wall time on 1 node (128 cores) |
|--:|--:|--:|:--|
| 500 / 200 | 35 100 | ~0.6–1 | ~1 min |
| 1 000 / 300 | 61 400 | ~1–2 | ~1–2 min |
| 2 000 / 1 000 | 158 000 | ~2–4 | ~2–5 min |
| 10 000 / 2 000 | 526 000 | ~8–15 | ~5–10 min |

Each campaign also spends ~10 s on the V&V suite and up to a minute on tables and figures. The default `--time=00:30:00` is ample; add time only for very large grids. Billing is in node-hours, so one well-used node is cheaper than many partly used ones.

## 7. Very large campaigns: job arrays (optional)

Split the work into chunks, one node each, then merge:

```bash
export OUT=/project/scratch/p200567/rpo/v4_huge RUNS=20000 SWEEP_RUNS=5000
jid=$(sbatch -A p200567 --parsable hpc/run_campaign_array.slurm)          # 8 chunks
sbatch -A p200567 --dependency=afterok:$jid hpc/merge.slurm               # runs when all succeed
```

* `NUM_CHUNKS` (default 8) must match `#SBATCH --array=0-7` in the script.
* Keep `RUNS`, `SWEEP_RUNS`, `MASTER_SEED`, `OUT` and `NUM_CHUNKS` identical for every chunk — the merge refuses mixed or incomplete chunk sets.
* Rerun a failed chunk alone with the same variables: `sbatch -A p200567 --array=5 hpc/run_campaign_array.slurm`, then submit `hpc/merge.slurm` again.
* The merged output is byte-identical to a single-node run of the same campaign.

## 8. Monitoring and control

| Command (login or compute node) | What it does |
|:--|:--|
| `squeue -u $USER` | your pending/running jobs and the node they run on |
| `ssh mel2017` then `htop` | watch a running job's node (use the node name from `squeue`) |
| `sacct -j <jobid> -o jobid,jobname,state,elapsed,maxrss` | finished-job history and memory used |
| `scontrol show job <jobid>` | full details of a pending/running job (≤ 5 min after it ends) |
| `scancel <jobid>` | cancel a job |
| `myquota` | node-hours used this month, storage and file counts |

QOS cheat-sheet from the workshop: `test` ≤ 30 min (high priority, 1 job/user) · `short` ≤ 6 h · `default` ≤ 48 h (production) · `long` ≤ 144 h (1 job/user). Override at submission: `sbatch --qos=short …`.

## 9. Bring results home

On your laptop:

```bash
rsync -az meluxina:/project/scratch/p200567/rpo/v4_1000/ results/v4_1000/
```

Scratch is not backed up: copy anything you want to keep. Commit summaries, figures and `report.md`; large `runs_*.csv` files are fine to keep on project storage instead.

## 10. Troubleshooting

| Symptom | Cause / fix |
|:--|:--|
| `env.sh: 'module' not found` | You are on a login node. Use `salloc …` or `sbatch`. |
| `no virtualenv at …/.venv-meluxina` | Run `bash hpc/setup_env.sh` once on a compute node, or `export MLUX_ENV=modules`. |
| `pip install failed` | No internet from the node: `export MLUX_ENV=modules`. |
| `Lmod has detected the following error: … not found` | Module name differs: `module avail Python`, then set `MLUX_PYTHON_MODULE` / `MLUX_SCIPY_MODULE` / `MLUX_MPL_MODULE`. |
| `ImportError … libpython` after loading other modules | The virtualenv must use the same Python module it was built with; `source hpc/env.sh` handles this. Rebuild after changing `MLUX_PYTHON_MODULE`: `rm -rf .venv-meluxina && bash hpc/setup_env.sh`. |
| Job stays `PD` with reason `QOSMaxJobsPerUserLimit` | `test`/`dev` allow one job per user; wait or use `--qos=short`. |
| `Invalid account or account/partition combination` | Wrong project ID in `-A`; check `myquota`. |
| `missing chunks [...]` at merge | Rerun those array indices (§7), then merge again. |
| Job much slower than expected | Check `htop`: all 128 cores should be busy. `env.sh` sets `OMP_NUM_THREADS=1` to prevent thread oversubscription; don't override it. |

Support: MeluXina service desk https://servicedesk.lxp.lu · documentation https://docs.lxp.lu.

## Files in this folder

| File | Purpose |
|:--|:--|
| `env.sh` | Loads modules, activates the environment, sets threading/cache variables. Sourced by every job. |
| `setup_env.sh` | One-time virtualenv creation + V&V check (run on a compute node). |
| `run_campaign.slurm` | **Recommended** batch job: whole campaign on one node. |
| `run_campaign_array.slurm` | Optional: chunked campaign as a job array. |
| `merge.slurm` | Combine array chunks and produce the report. |

> These scripts follow the workshop material but have only been tested off-cluster (with Slurm and Lmod stubbed out). Run the §5 test job before submitting a large campaign.
