# Python environment for the RPO Monte Carlo on MeluXina. Source it on a COMPUTE node:
#     source hpc/env.sh
# (The `module` command does not exist on login nodes.)
#
# Two ways to provide numpy/pandas/matplotlib, chosen with MLUX_ENV:
#   venv    (default) project virtualenv built once by hpc/setup_env.sh
#   modules           MUSE modules only (SciPy-bundle + matplotlib); no pip/internet needed
# Override module names if `module avail` shows different ones, e.g.
#     export MLUX_PYTHON_MODULE=Python/3.12.3-GCCcore-13.3.0

HPC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$HPC_DIR/.." && pwd)"
MLUX_ENV="${MLUX_ENV:-venv}"
MLUX_VENV="${MLUX_VENV:-$REPO_DIR/.venv-meluxina}"

if ! command -v module >/dev/null 2>&1; then
    echo "env.sh: 'module' not found - are you on a login node? Run 'salloc ...' first (see hpc/README.md)." >&2
    return 1 2>/dev/null || exit 1
fi

module purge
module load "${MLUX_PYTHON_MODULE:-Python}"
if [ "$MLUX_ENV" = "modules" ]; then
    module load "${MLUX_SCIPY_MODULE:-SciPy-bundle}" "${MLUX_MPL_MODULE:-matplotlib}"
else
    if [ ! -f "$MLUX_VENV/bin/activate" ]; then
        echo "env.sh: no virtualenv at $MLUX_VENV - run 'bash hpc/setup_env.sh' once (or export MLUX_ENV=modules)." >&2
        return 1 2>/dev/null || exit 1
    fi
    # The venv links to the module's Python, so the same module must stay loaded.
    source "$MLUX_VENV/bin/activate"
fi

# One process per core: stop numpy's maths libraries from starting extra threads in each worker.
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
# Matplotlib cache on fast node-local storage instead of the small HOME quota.
export MPLCONFIGDIR="${TMPDIR:-/tmp}/mpl-${USER:-rpo}"
export PYTHONPATH="$REPO_DIR${PYTHONPATH:+:$PYTHONPATH}"
cd "$REPO_DIR"
