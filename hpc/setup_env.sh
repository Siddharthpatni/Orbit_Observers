#!/bin/bash -l
# One-time setup of the Python environment on MeluXina. Run on a COMPUTE node:
#     salloc -A <project> -p cpu --qos test -N 1 -t 00:30:00
#     bash hpc/setup_env.sh
set -eo pipefail   # no 'set -u': Lmod's module function is not nounset-safe
HPC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$HPC_DIR/.." && pwd)"
MLUX_VENV="${MLUX_VENV:-$REPO_DIR/.venv-meluxina}"

command -v module >/dev/null 2>&1 || { echo "Run this on a compute node (salloc first); modules are not available on login nodes." >&2; exit 1; }
module purge
module load "${MLUX_PYTHON_MODULE:-Python}"
echo "Using $(python3 --version) from $(command -v python3)"
python3 -c 'import sys; sys.exit(sys.version_info < (3, 10))' \
    || { echo "Python >= 3.10 required; pick a newer module (module avail Python) and set MLUX_PYTHON_MODULE." >&2; exit 1; }

if [ ! -d "$MLUX_VENV" ]; then
    python3 -m venv "$MLUX_VENV"
fi
source "$MLUX_VENV/bin/activate"
if ! { pip install --upgrade pip && pip install -r "$REPO_DIR/requirements.txt"; }; then
    echo "pip install failed (no internet from this node?). Use the module-only environment instead:" >&2
    echo "    export MLUX_ENV=modules   # then: source hpc/env.sh" >&2
    exit 1
fi
deactivate

source "$HPC_DIR/env.sh"
python -m rpo_project.montecarlo --mode verify
echo
echo "Setup complete: virtualenv at $MLUX_VENV and V&V suite passed."
