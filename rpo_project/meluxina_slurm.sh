#!/bin/bash
#SBATCH --job-name=GEO_RPO
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --array=0-31
#SBATCH --time=00:45:00
# Account, partition and environment depend on LuxProvide MeluXina onboarding guidance.

python -m rpo_project.montecarlo --mode full --runs 500 --chunk ${SLURM_ARRAY_TASK_ID} --num-chunks 32 --out results_meluxina
