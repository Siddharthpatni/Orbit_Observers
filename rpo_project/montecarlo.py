"""Monte Carlo campaign runner: studies, paired seeds, parallel workers, HPC chunks (Sections 10, 12, 14).

Vocabulary
----------
* **Study** - one experiment: which client tiers are compared, which design
  parameters are swept (the *grid*) and which are held fixed.
* **Cell** - one combination of grid values, e.g. tumble = 3 deg/s.
* **Task group** - (study, cell, seed index). It runs *every* tier of the study
  on the same seed, so paired comparisons are never split across workers or
  HPC chunks. Groups are the unit of parallelism and of chunking.

Seeds: run ``i`` of a study uses ``seed = study.seed_offset + i``. Studies are
therefore statistically independent of each other, while inside a study the
same seed is reused across cells (common random numbers: cells differ only in
the swept parameter) and across tiers (paired comparison). Together with
``--master-seed`` this reproduces any single row exactly.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import itertools
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
import zipfile
from typing import Dict, Iterable, List, Optional, Sequence, Tuple
import numpy as np
import pandas as pd
from .config import MODEL_VERSION, SCENARIOS, SimConfig
from .simulate import run_single_simulation

# Run-level inputs a study may sweep, with the value used when it does not.
NOMINAL_INPUTS: Dict[str, float] = {
    "tumble_deg_s": 0.0,
    "vision_sigma_m": 0.05,
    "beacon_packet_loss": 0.20,
    "beacon_rate_hz": 1.0,
    "latency_s": 0.10,
}
SEED_BLOCK = 1_000_000  # spacing of study seed offsets; caps runs per cell


@dataclass(frozen=True)
class Study:
    name: str
    title: str
    scenarios: Tuple[str, ...]
    grid: Tuple[Tuple[str, Tuple[float, ...]], ...]
    fixed: Tuple[Tuple[str, float], ...] = ()
    seed_offset: int = 0
    sweep: bool = True  # True: uses --sweep-runs per cell; False: uses --runs

    @property
    def grid_columns(self) -> List[str]:
        return [name for name, _ in self.grid]

    def cells(self) -> List[Dict[str, float]]:
        cells = []
        for values in itertools.product(*(vals for _, vals in self.grid)):
            cell = dict(NOMINAL_INPUTS)
            cell.update(dict(self.fixed))
            cell.update(zip(self.grid_columns, values))
            cells.append(cell)
        return cells

    def describe(self, n_runs: int) -> Dict[str, object]:
        return {
            "title": self.title,
            "scenarios": list(self.scenarios),
            "grid": {name: list(vals) for name, vals in self.grid},
            "fixed": {**NOMINAL_INPUTS, **dict(self.fixed), **{name: "swept" for name in self.grid_columns}},
            "runs_per_cell": n_runs,
            "seed_range": [self.seed_offset, self.seed_offset + n_runs - 1],
            "n_cells": len(self.cells()),
            "n_simulations": len(self.cells()) * n_runs * len(self.scenarios),
        }


STUDIES: Dict[str, Study] = {
    "main": Study(
        "main", "Client preparation tier vs. tumble rate", tuple(SCENARIOS),
        (("tumble_deg_s", (0.0, 0.25, 0.5, 1.0, 2.0, 3.0, 5.0)),),
        seed_offset=0, sweep=False),
    "ablation": Study(
        "ablation", "Service Beacon ablation: packet loss x update rate (3 deg/s tumble)",
        ("C2_id_only", "C2_beacon"),
        (("beacon_packet_loss", (0.0, 0.1, 0.25, 0.5, 0.75)), ("beacon_rate_hz", (0.5, 1.0, 2.0))),
        (("tumble_deg_s", 3.0),), seed_offset=1 * SEED_BLOCK),
    "envelope": Study(
        "envelope", "Servicing envelope: tumble rate x optical noise",
        ("C1_fiducials", "C2_beacon"),
        (("tumble_deg_s", (0.0, 0.5, 1.0, 2.0, 3.0, 5.0)), ("vision_sigma_m", (0.02, 0.05, 0.10, 0.25))),
        seed_offset=2 * SEED_BLOCK),
    "latency": Study(
        "latency", "Service Beacon latency sensitivity (3 deg/s tumble)",
        ("C2_id_only", "C2_beacon"),
        (("latency_s", (0.0, 0.1, 0.5, 1.0, 2.0)),),
        (("tumble_deg_s", 3.0),), seed_offset=3 * SEED_BLOCK),
}

TaskGroup = Tuple[Study, int, int]  # (study, cell index, seed index)


def build_task_groups(studies: Sequence[Study], runs: int, sweep_runs: int) -> List[TaskGroup]:
    groups: List[TaskGroup] = []
    for study in studies:
        n_runs = sweep_runs if study.sweep else runs
        for cell_index in range(len(study.cells())):
            groups.extend((study, cell_index, i) for i in range(n_runs))
    return groups


def run_task_group(group: TaskGroup, cfg: SimConfig, master_seed: int) -> List[Dict[str, object]]:
    """Run every tier of one study cell on one seed (top-level so workers can pickle it)."""
    study, cell_index, seed_index = group
    cell = study.cells()[cell_index]
    seed = study.seed_offset + seed_index
    rows = []
    for scenario in study.scenarios:
        row = run_single_simulation(
            scenario, seed, cell["tumble_deg_s"], cell["vision_sigma_m"], cell["beacon_packet_loss"],
            cell["beacon_rate_hz"], cell["latency_s"], cfg, master_seed=master_seed)
        row["study"] = study.name
        row["cell"] = cell_index
        rows.append(row)
    return rows


def execute_groups(groups: List[TaskGroup], cfg: SimConfig, master_seed: int, workers: int) -> List[Dict[str, object]]:
    """Run task groups serially or on a process pool; output order equals input order."""
    n_sims = sum(len(g[0].scenarios) for g in groups)
    print(f"Running {n_sims} simulations ({len(groups)} paired seed groups) on {workers} worker(s)", flush=True)
    rows: List[Dict[str, object]] = []
    report_every = max(1, len(groups) // 20)
    start = time.perf_counter()

    def consume(results: Iterable[List[Dict[str, object]]]) -> None:
        for done, group_rows in enumerate(results, start=1):
            rows.extend(group_rows)
            if done % report_every == 0 or done == len(groups):
                elapsed = time.perf_counter() - start
                eta = elapsed / done * (len(groups) - done)
                print(f"  {done}/{len(groups)} groups ({100.0 * done / len(groups):.0f}%), "
                      f"elapsed {elapsed:.0f} s, ETA {eta:.0f} s", flush=True)

    if workers <= 1:
        consume(run_task_group(g, cfg, master_seed) for g in groups)
    else:
        chunksize = max(1, len(groups) // (workers * 16))
        with ProcessPoolExecutor(max_workers=workers) as pool:
            consume(pool.map(run_task_group, groups, itertools.repeat(cfg), itertools.repeat(master_seed), chunksize=chunksize))
    return rows


def _git_info() -> Dict[str, object]:
    root = Path(__file__).resolve().parent.parent
    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, timeout=10).stdout.strip()
        dirty = bool(subprocess.run(["git", "status", "--porcelain"], cwd=root, capture_output=True, text=True, timeout=10).stdout.strip())
        return {"git_commit": commit or None, "git_dirty": dirty if commit else None}
    except (OSError, subprocess.SubprocessError):
        return {"git_commit": None, "git_dirty": None}


def build_manifest(studies: Sequence[Study], runs: int, sweep_runs: int, cfg: SimConfig, master_seed: int,
                   workers: int, chunk_id: Optional[int], num_chunks: int) -> Dict[str, object]:
    return {
        "model_version": MODEL_VERSION,
        "config_hash": cfg.config_hash(),
        "master_seed": master_seed,
        "runs_per_cell": runs,
        "sweep_runs_per_cell": sweep_runs,
        "studies": {s.name: s.describe(sweep_runs if s.sweep else runs) for s in studies},
        "chunk": None if chunk_id is None else {"id": chunk_id, "num_chunks": num_chunks},
        "workers": workers,
        "command": " ".join(sys.argv),
        "started_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        **_git_info(),
        "python": platform.python_version(),
        "numpy": np.__version__,
        "pandas": pd.__version__,
        "platform": platform.platform(),
        "config": asdict(cfg),
        "scenarios": {name: asdict(spec) for name, spec in SCENARIOS.items()},
    }


def write_study_csvs(rows: List[Dict[str, object]], studies: Sequence[Study], out_dir: Path) -> Dict[str, pd.DataFrame]:
    df = pd.DataFrame(rows)
    frames = {}
    for study in studies:
        frames[study.name] = df[df["study"] == study.name].reset_index(drop=True)
        frames[study.name].to_csv(out_dir / f"runs_{study.name}.csv", index=False)
    return frames


def resolve_studies(names: Optional[Sequence[str]]) -> List[Study]:
    if not names:
        return list(STUDIES.values())
    unknown = [n for n in names if n not in STUDIES]
    if unknown:
        raise ValueError(f"unknown studies {unknown}; choose from {list(STUDIES)}")
    return [STUDIES[n] for n in STUDIES if n in names]


def run_campaign(runs_per_cell: int, out_dir: Path, chunk_id: Optional[int] = None, num_chunks: int = 1,
                 sweep_runs: Optional[int] = None, workers: int = 1, master_seed: int = 0,
                 studies: Optional[Sequence[str]] = None, cfg: Optional[SimConfig] = None) -> None:
    """Run a campaign. With ``chunk_id`` only that slice of task groups is run and saved."""
    if runs_per_cell < 1:
        raise ValueError("runs must be at least 1")
    if sweep_runs is None:
        sweep_runs = max(10, runs_per_cell // 2)
    if sweep_runs < 1:
        raise ValueError("sweep-runs must be at least 1")
    if max(runs_per_cell, sweep_runs) >= SEED_BLOCK:
        raise ValueError(f"runs per cell must be below {SEED_BLOCK}")
    if num_chunks < 1:
        raise ValueError("num-chunks must be at least 1")
    if chunk_id is not None and not 0 <= chunk_id < num_chunks:
        raise ValueError("chunk must satisfy 0 <= chunk < num-chunks")
    if master_seed < 0:
        raise ValueError("master-seed must be nonnegative")
    cfg = cfg or SimConfig()
    selected = resolve_studies(studies)
    groups = build_task_groups(selected, runs_per_cell, sweep_runs)
    if chunk_id is not None:
        groups = groups[chunk_id::num_chunks]
    if not groups:
        raise ValueError("chunk has no simulations; reduce num-chunks or increase runs")
    workers = max(1, min(workers, len(groups)))
    out_dir.mkdir(parents=True, exist_ok=True)

    manifest = build_manifest(selected, runs_per_cell, sweep_runs, cfg, master_seed, workers, chunk_id, num_chunks)
    root = Path(__file__).resolve().parent.parent
    sources = {str(p.relative_to(root)): p.read_bytes() for p in sorted((root / "rpo_project").rglob("*.py"))}
    sources["requirements.txt"] = (root / "requirements.txt").read_bytes()
    manifest["source_files_sha256"] = {name: hashlib.sha256(data).hexdigest() for name, data in sources.items()}
    manifest["source_sha256"] = hashlib.sha256(json.dumps(manifest["source_files_sha256"], sort_keys=True).encode()).hexdigest()
    archive = "source.zip" if chunk_id is None else f"source_chunk_{chunk_id:03d}.zip"
    with zipfile.ZipFile(out_dir / archive, "w", compression=zipfile.ZIP_DEFLATED) as snapshot:
        for name, data in sources.items():
            snapshot.writestr(name, data)
    manifest["source_archive"] = archive
    start = time.perf_counter()
    rows = execute_groups(groups, cfg, master_seed, workers)
    manifest["wall_time_s"] = round(time.perf_counter() - start, 1)
    manifest["n_simulations_run"] = len(rows)

    if chunk_id is not None:
        chunk_dir = out_dir / "chunks"
        chunk_dir.mkdir(exist_ok=True)
        pd.DataFrame(rows).to_csv(chunk_dir / f"runs_chunk_{chunk_id:03d}.csv", index=False)
        (chunk_dir / f"manifest_chunk_{chunk_id:03d}.json").write_text(json.dumps(manifest, indent=2))
        print(f"Chunk {chunk_id}/{num_chunks} saved to {chunk_dir.resolve()}; "
              f"run '--mode merge --out {out_dir}' once every chunk has finished.", flush=True)
        return

    write_study_csvs(rows, selected, out_dir)
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
    from .analyse import analyse_campaign
    analyse_campaign(out_dir)


# Manifest fields that must agree between chunks of one campaign.
_CAMPAIGN_KEYS = ("model_version", "config_hash", "master_seed", "runs_per_cell", "sweep_runs_per_cell", "studies", "source_sha256")


def merge_chunks(out_dir: Path, analyse: bool = True) -> None:
    """Validate and combine HPC chunk outputs into per-study CSVs, then analyse."""
    chunk_dir = out_dir / "chunks"
    manifests = {int(p.stem.rsplit("_", 1)[1]): json.loads(p.read_text())
                 for p in sorted(chunk_dir.glob("manifest_chunk_*.json"))}
    if not manifests:
        raise FileNotFoundError(f"no chunk manifests found in {chunk_dir}")
    first = next(iter(manifests.values()))
    for cid, m in manifests.items():
        for key in _CAMPAIGN_KEYS:
            if m.get(key) != first.get(key):
                raise ValueError(f"chunk {cid} disagrees on '{key}'; chunks come from different campaigns")
    num_chunks = first["chunk"]["num_chunks"]
    missing = sorted(set(range(num_chunks)) - set(manifests))
    if any(m["chunk"]["num_chunks"] != num_chunks or m["chunk"]["id"] != cid
           for cid, m in manifests.items()) or set(manifests) - set(range(num_chunks)):
        raise ValueError("inconsistent chunk identifiers or chunk counts")
    if missing:
        raise ValueError(f"missing chunks {missing} of {num_chunks}; rerun them before merging")

    df = pd.concat([pd.read_csv(chunk_dir / f"runs_chunk_{cid:03d}.csv", dtype={"config_hash": str}, float_precision="round_trip")
                    for cid in sorted(manifests)], ignore_index=True)
    key = ["study", "cell", "seed", "scenario"]
    if df.duplicated(key).any():
        raise ValueError("duplicate runs found across chunks")
    for name, info in first["studies"].items():
        got = int((df["study"] == name).sum())
        if got != info["n_simulations"]:
            raise ValueError(f"study '{name}' has {got} runs, expected {info['n_simulations']}")
    study_order = {name: i for i, name in enumerate(first["studies"])}
    scen_order = {name: i for i, name in enumerate(SCENARIOS)}
    df = df.sort_values(key, key=lambda col: col.map(study_order) if col.name == "study"
                        else col.map(scen_order) if col.name == "scenario" else col).reset_index(drop=True)
    for name in first["studies"]:
        df[df["study"] == name].to_csv(out_dir / f"runs_{name}.csv", index=False)

    merged = {k: v for k, v in first.items() if k not in ("chunk", "wall_time_s", "n_simulations_run", "workers")}
    merged.update({
        "merged_chunks": num_chunks,
        "n_simulations_run": int(len(df)),
        "wall_time_s_sum_over_chunks": round(sum(m.get("wall_time_s", 0.0) for m in manifests.values()), 1),
        "merged_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    })
    (out_dir / "manifest.json").write_text(json.dumps(merged, indent=2))
    print(f"Merged {num_chunks} chunks ({len(df)} simulations) into {out_dir.resolve()}", flush=True)
    if analyse:
        from .analyse import analyse_campaign
        analyse_campaign(out_dir)


def positive_int(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return number


def default_workers() -> int:
    return int(os.environ.get("SLURM_CPUS_PER_TASK", "0") or 0) or os.cpu_count() or 1


def main(argv: Optional[Sequence[str]] = None) -> None:
    p = argparse.ArgumentParser(
        description="Orbit Observers RPO Monte Carlo Runner",
        epilog="Modes: verify = V&V suite only; pilot = local campaign; full = pilot with >= 200 runs "
               "per main cell; merge = combine HPC chunks and analyse; analyse = rebuild tables/plots/report.")
    p.add_argument("--mode", choices=["verify", "pilot", "full", "merge", "analyse"], default="pilot")
    p.add_argument("--runs", type=positive_int, default=30, help="paired seeds per main-study cell (default: 30)")
    p.add_argument("--sweep-runs", type=positive_int, default=None,
                   help="paired seeds per cell of the other studies (default: max(10, runs // 2))")
    p.add_argument("--studies", type=str, default=None,
                   help=f"comma-separated subset of: {','.join(STUDIES)} (default: all)")
    p.add_argument("--out", type=str, default="results_rpo")
    p.add_argument("--workers", type=positive_int, default=None,
                   help="parallel processes (default: $SLURM_CPUS_PER_TASK or all CPU cores)")
    p.add_argument("--master-seed", type=int, default=0, help="campaign-level seed; change it for an independent replication")
    p.add_argument("--chunk", type=int, default=None, help="run only this slice of the campaign (HPC job arrays)")
    p.add_argument("--num-chunks", type=positive_int, default=32)
    p.add_argument("--skip-verify", action="store_true", help="do not run the V&V suite first")
    args = p.parse_args(argv)
    out = Path(args.out)

    if args.mode == "merge":
        merge_chunks(out)
        return
    if args.mode == "analyse":
        from .analyse import analyse_campaign
        analyse_campaign(out)
        return
    if args.chunk is not None and not 0 <= args.chunk < args.num_chunks:
        p.error("--chunk must satisfy 0 <= chunk < num-chunks")
    if not args.skip_verify or args.mode == "verify":
        from .tests.test_vv import run_verification_suite
        run_verification_suite()
    if args.mode == "verify":
        return
    runs = args.runs if args.mode == "pilot" else max(args.runs, 200)
    studies = [s.strip() for s in args.studies.split(",") if s.strip()] if args.studies else None
    try:
        run_campaign(runs, out, args.chunk, args.num_chunks if args.chunk is not None else 1, args.sweep_runs,
                     args.workers or default_workers(), args.master_seed, studies)
    except ValueError as exc:
        p.error(str(exc))


if __name__ == "__main__":
    main()
