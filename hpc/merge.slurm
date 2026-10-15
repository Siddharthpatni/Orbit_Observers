#!/bin/bash -l
#SBATCH --job-name=rpo_mc_merge
#SBATCH --partition=cpu
#SBATCH --qos=default
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --time=00:20:00
#SBATCH --output=rpo_mc_merge_%j.log
#
# Combine the chunks written by hpc/run_campaign_array.slurm, check they are complete and
# consistent, then write the tables, figures and report.md. Submit with a dependency:
#     OUT=/project/scratch/p200000/rpo/v4_huge sbatch -A p200000 --dependency=afterok:<jobid> hpc/merge.slurm
set -eo pipefail

cd "${SLURM_SUBMIT_DIR:?submit this script with sbatch}"
source hpc/env.sh
OUT="${OUT:?set OUT to the same directory the chunks wrote to}"

srun python -m rpo_project.montecarlo --mode merge --out "$OUT"
echo "Done. Report: $OUT/report.md"
