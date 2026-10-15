"""Parameter sweeps, paired random seeds, and MeluXina HPC CLI entrypoint (Sections 10, 12, 14)."""
import argparse
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import pandas as pd
from .analyse import generate_four_core_plots, summarize_results
from .config import SCENARIOS, SimConfig
from .simulate import run_single_simulation
from .tests.test_vv import run_verification_suite

def run_campaign(runs_per_cell: int, out_dir: Path, chunk_id: Optional[int] = None, num_chunks: int = 1, sweep_runs: Optional[int] = None) -> None:
    if runs_per_cell < 1:
        raise ValueError("runs must be at least 1")
    if num_chunks < 1:
        raise ValueError("num-chunks must be at least 1")
    if chunk_id is not None and not 0 <= chunk_id < num_chunks:
        raise ValueError("chunk must satisfy 0 <= chunk < num-chunks")
    if sweep_runs is None:
        sweep_runs = max(10, runs_per_cell // 2)
    if sweep_runs < 1:
        raise ValueError("sweep-runs must be at least 1")
    cfg = SimConfig()
    tumble_grid = [0.0, 0.25, 0.5, 1.0, 2.0, 3.0, 5.0]
    tasks: List[Tuple[float, int]] = [(w, s) for w in tumble_grid for s in range(runs_per_cell)]
    if chunk_id is not None:
        tasks = [t for idx, t in enumerate(tasks) if (idx % num_chunks) == chunk_id]
    if not tasks:
        raise ValueError("chunk has no simulations; reduce num-chunks or increase runs")
    out_dir.mkdir(parents=True, exist_ok=True)

    main_rows: List[Dict[str, object]] = []
    print(f"Main sweep: {len(tasks) * len(SCENARIOS)} simulations", flush=True)
    for task_index, (omega, seed) in enumerate(tasks, start=1):
        for scen_name in SCENARIOS.keys():
            main_rows.append(run_single_simulation(scen_name, seed, omega, 0.05, 0.20, 1.0, 0.10, cfg))
        if task_index % 10 == 0 or task_index == len(tasks):
            print(f"  Main sweep: {task_index}/{len(tasks)} paired seed groups complete", flush=True)
    df_main = pd.DataFrame(main_rows)
    suffix = f"_chunk_{chunk_id:03d}" if chunk_id is not None else ""
    df_main.to_csv(out_dir / f"runs_main{suffix}.csv", index=False)
    if chunk_id is not None:
        print(f"Chunk results saved to {out_dir.resolve()}", flush=True)
        return

    summary_main = summarize_results(df_main, ["scenario", "tumble_deg_s"])
    summary_main.to_csv(out_dir / "summary_main.csv", index=False)

    print(f"Beacon ablation: {30 * sweep_runs} simulations", flush=True)
    abl_rows = [
        run_single_simulation(sc, s, 1.5, 0.05, loss, rate, 0.10, cfg)
        for loss in [0.0, 0.1, 0.25, 0.5, 0.75]
        for rate in [0.5, 1.0, 2.0]
        for s in range(sweep_runs)
        for sc in ["C2_id_only", "C2_beacon"]
    ]
    df_ablation = pd.DataFrame(abl_rows)
    df_ablation.to_csv(out_dir / "runs_ablation.csv", index=False)

    print(f"Servicing envelope: {24 * sweep_runs} simulations", flush=True)
    env_rows = [
        run_single_simulation("C2_beacon", s, w, sig, 0.20, 1.0, 0.10, cfg)
        for w in [0.0, 0.5, 1.0, 2.0, 3.0, 5.0]
        for sig in [0.02, 0.05, 0.10, 0.25]
        for s in range(sweep_runs)
    ]
    df_envelope = pd.DataFrame(env_rows)
    df_envelope.to_csv(out_dir / "runs_envelope.csv", index=False)

    generate_four_core_plots(df_main, df_ablation, df_envelope, out_dir)
    print(summary_main.to_string(index=False))
    print(f"Results and four plots saved to {out_dir.resolve()}", flush=True)

def positive_int(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return number

def main() -> None:
    p = argparse.ArgumentParser(description="Orbit Observers RPO Monte Carlo Runner")
    p.add_argument("--mode", choices=["verify", "pilot", "full"], default="pilot")
    p.add_argument("--runs", type=positive_int, default=30, help="runs per main-sweep cell (default: 30)")
    p.add_argument("--sweep-runs", type=positive_int, default=None, help="runs per ablation/envelope cell (default: max(10, runs // 2)); ignored for chunks")
    p.add_argument("--out", type=str, default="results_rpo")
    p.add_argument("--chunk", type=int, default=None)
    p.add_argument("--num-chunks", type=positive_int, default=32)
    args = p.parse_args()
    runs = args.runs if args.mode == "pilot" else max(args.runs, 200)
    if args.chunk is not None:
        if not 0 <= args.chunk < args.num_chunks:
            p.error("--chunk must satisfy 0 <= chunk < num-chunks")
        if args.mode != "verify" and args.chunk >= 7 * runs:
            p.error("--chunk has no simulations; reduce --num-chunks or increase --runs")
    run_verification_suite()
    if args.mode != "verify":
        run_campaign(runs, Path(args.out), args.chunk, args.num_chunks, args.sweep_runs)

if __name__ == "__main__":
    main()
