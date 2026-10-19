#!/bin/bash -l
#SBATCH --job-name=rpo_mc
#SBATCH --partition=cpu
#SBATCH --qos=default
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=128
#SBATCH --time=00:30:00
#SBATCH --output=rpo_mc_%j.log
#
# Recommended MeluXina job: the whole campaign on ONE CPU node, one worker per core.
# A 1000/300-run campaign (~61 000 simulations) needs roughly 1 core-hour, i.e. well under
# 5 minutes on 128 cores - one node is enough for almost every study.
#
# Submit from the repository root, giving your project account:
#     sbatch -A p200000 hpc/run_campaign.slurm
# Optional settings (environment variables, passed through by sbatch):
#     RUNS=2000 SWEEP_RUNS=500 MASTER_SEED=1 OUT=/project/scratch/p200000/rpo/v4_big \
#         sbatch -A p200000 hpc/run_campaign.slurm
# First time? A small, fast test on the high-priority test QOS (max 30 min):
#     MODE=pilot RUNS=30 sbatch -A p200000 --qos=test hpc/run_campaign.slurm
# MODE=pilot allows RUNS < 200 (full mode enforces >= 200); STUDIES=main,latency runs a subset.
set -eo pipefail

cd "${SLURM_SUBMIT_DIR:?submit this script with sbatch}"
source hpc/env.sh

RUNS="${RUNS:-1000}"
SWEEP_RUNS="${SWEEP_RUNS:-300}"
MASTER_SEED="${MASTER_SEED:-0}"
OUT="${OUT:-results/meluxina_${SLURM_JOB_ID}}"

echo "Job $SLURM_JOB_ID on $(hostname): $SLURM_CPUS_PER_TASK cores, runs=$RUNS sweep_runs=$SWEEP_RUNS master_seed=$MASTER_SEED out=$OUT"
srun python -m rpo_project.montecarlo --mode "${MODE:-full}" --runs "$RUNS" --sweep-runs "$SWEEP_RUNS" \
    --master-seed "$MASTER_SEED" --workers "$SLURM_CPUS_PER_TASK" ${STUDIES:+--studies "$STUDIES"} --out "$OUT"
echo "Done. Report: $OUT/report.md"
