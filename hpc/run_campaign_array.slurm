#!/bin/bash -l
#SBATCH --job-name=rpo_mc_chunk
#SBATCH --partition=cpu
#SBATCH --qos=default
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=128
#SBATCH --time=01:00:00
#SBATCH --array=0-7
#SBATCH --output=rpo_mc_chunk_%A_%a.log
#
# Very large campaigns only (e.g. >= 5000 runs per cell): split the campaign into chunks,
# one CPU node per chunk. Paired tiers always stay in the same chunk, and the merged result
# is byte-identical to a single-node run. For normal sizes use hpc/run_campaign.slurm.
#
# Submit from the repository root, then merge once every chunk has finished:
#     OUT=/project/scratch/p200000/rpo/v4_huge RUNS=10000 SWEEP_RUNS=2000 \
#         sbatch -A p200000 --parsable hpc/run_campaign_array.slurm        # prints <jobid>
#     OUT=/project/scratch/p200000/rpo/v4_huge \
#         sbatch -A p200000 --dependency=afterok:<jobid> hpc/merge.slurm
#
# NUM_CHUNKS (default 8) must equal the number of tasks in --array=0-7. Keep RUNS, SWEEP_RUNS, MASTER_SEED, OUT
# and NUM_CHUNKS identical for every chunk; the merge refuses chunks from different campaigns. A failed chunk
# can be rerun alone:  sbatch -A p200000 --array=5 hpc/run_campaign_array.slurm  (same variables).
set -eo pipefail

cd "${SLURM_SUBMIT_DIR:?submit this script with sbatch}"
source hpc/env.sh

RUNS="${RUNS:-1000}"
SWEEP_RUNS="${SWEEP_RUNS:-300}"
MASTER_SEED="${MASTER_SEED:-0}"
OUT="${OUT:?set OUT to a directory shared by all chunks, e.g. OUT=/project/scratch/<project>/rpo/run1}"
NUM_CHUNKS="${NUM_CHUNKS:-8}"   # not derived from the array: a single-chunk rerun must keep the original count

echo "Chunk $SLURM_ARRAY_TASK_ID/$NUM_CHUNKS on $(hostname): $SLURM_CPUS_PER_TASK cores, runs=$RUNS sweep_runs=$SWEEP_RUNS out=$OUT"
srun python -m rpo_project.montecarlo --mode "${MODE:-full}" --runs "$RUNS" --sweep-runs "$SWEEP_RUNS" \
    --master-seed "$MASTER_SEED" --workers "$SLURM_CPUS_PER_TASK" ${STUDIES:+--studies "$STUDIES"} \
    --chunk "$SLURM_ARRAY_TASK_ID" --num-chunks "$NUM_CHUNKS" --out "$OUT"
