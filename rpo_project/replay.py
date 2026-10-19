"""Replay one Monte Carlo run and plot its trajectory (Handbook Section 13, validation step V2).

Every row of a campaign CSV can be reproduced exactly from its scenario, seed,
master seed and the swept inputs. Typical use, after spotting a failure in
``failure_cases.csv``::

    python -m rpo_project.replay --scenario C0_unprepared --seed 12 --tumble 3.0 --out results/replay
"""
import argparse
import math
import json
from pathlib import Path
from typing import Dict, List, Optional, Sequence
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from .analyse import INK, INK_2, STATUS_STYLE, _style_axes
from .config import MODEL_VERSION, SCENARIOS, SimConfig
from .simulate import run_single_simulation


def replay(scenario: str, seed: int, tumble_deg_s: float, out_dir: Path, vision_sigma_m: float = 0.05,
           beacon_packet_loss: float = 0.20, beacon_rate_hz: float = 1.0, latency_s: float = 0.10,
           master_seed: int = 0, cfg: Optional[SimConfig] = None) -> Dict[str, object]:
    cfg = cfg or SimConfig()
    trajectory: List[Dict[str, object]] = []
    row = run_single_simulation(scenario, seed, tumble_deg_s, vision_sigma_m, beacon_packet_loss, beacon_rate_hz,
                                latency_s, cfg, trajectory=trajectory, master_seed=master_seed)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"replay_{scenario}_seed{seed}_tumble{tumble_deg_s:g}"
    traj = pd.DataFrame(trajectory)
    traj.to_csv(out_dir / f"{stem}.csv", index=False)
    if len(traj):
        plot_trajectory(traj, row, cfg, out_dir / f"{stem}.png")
    return row


def plot_trajectory(traj: pd.DataFrame, row: Dict[str, object], cfg: SimConfig, path: Path) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(11, 8.5))
    status = str(row["status"])
    status_color = STATUS_STYLE.get(status, STATUS_STYLE["ABORT"])[0]

    ax = axes[0, 0]
    circle = np.linspace(0, 2 * math.pi, 200)
    ax.fill(cfg.keepout_radius_m * np.cos(circle), cfg.keepout_radius_m * np.sin(circle), color="#d03b3b", alpha=0.15)
    ax.plot(cfg.keepout_radius_m * np.cos(circle), cfg.keepout_radius_m * np.sin(circle), color="#d03b3b", linewidth=1,
            label="Keep-out sphere")
    ax.plot(traj["capture_x_m"], traj["capture_y_m"], color=INK_2, linewidth=1, linestyle=":", label="Capture point (truth)")
    ax.plot(traj["x_m"], traj["y_m"], color="#2a78d6", linewidth=2, label="Servicer (truth)")
    ax.plot(traj["est_x_m"], traj["est_y_m"], color="#eb6834", linewidth=1, alpha=0.7, label="Servicer (estimate)")
    ax.plot(traj["x_m"].iloc[0], traj["y_m"].iloc[0], "o", color="#2a78d6", markersize=8)
    ax.plot(traj["x_m"].iloc[-1], traj["y_m"].iloc[-1], "X", color=status_color, markersize=11, markeredgecolor=INK)
    ax.set(title="Path in the orbit plane (LVLH)", xlabel="Radial x [m]", ylabel="Along-track y [m]")
    ax.set_aspect("equal", adjustable="datalim")
    _style_axes(ax)
    ax.legend(loc="best", frameon=False, fontsize=8)

    ax = axes[0, 1]
    ax.plot(traj["time_s"], traj["position_error_m"], color="#2a78d6", linewidth=2, label="Distance to capture point")
    ax.plot(traj["time_s"], traj["clearance_m"], color="#d03b3b", linewidth=1.5, label="Clearance to keep-out")
    ax.axhline(cfg.terminal_pos_tol_m, color=INK_2, linestyle="--", linewidth=1, label="Terminal tolerance")
    ax.axhline(0.0, color="#d03b3b", linewidth=0.8)
    ax.set(title="Distances", xlabel="Time [s]", ylabel="[m]")
    _style_axes(ax)
    ax.legend(loc="best", frameon=False, fontsize=8)

    ax = axes[1, 0]
    ax.plot(traj["time_s"], traj["relative_speed_mps"], color="#2a78d6", linewidth=2, label="Speed relative to capture point")
    ax.axhline(cfg.terminal_vel_tol_mps, color=INK_2, linestyle="--", linewidth=1, label="Terminal tolerance")
    ax.set(title="Relative speed", xlabel="Time [s]", ylabel="[m/s]")
    _style_axes(ax)
    ax.legend(loc="best", frameon=False, fontsize=8)

    ax = axes[1, 1]
    ax.plot(traj["time_s"], traj["rate_true_deg_s"], color=INK_2, linewidth=1.5, linestyle="--", label="True tumble rate")
    ax.plot(traj["time_s"], traj["rate_est_deg_s"], color="#eb6834", linewidth=2, label="Estimated tumble rate")
    ax.axhline(math.degrees(cfg.max_safe_target_omega_rad_s), color="#d03b3b", linewidth=1, label="Abort threshold")
    ax.set(title="Tumble-rate knowledge", xlabel="Time [s]", ylabel="[deg/s]")
    _style_axes(ax)
    ax.legend(loc="best", frameon=False, fontsize=8)

    fig.suptitle(f"{row['scenario']}  seed {row['seed']}  tumble {row['tumble_deg_s']:g} deg/s  →  {status} "
                 f"at {row['elapsed_s']:.1f} s, delta-v {row['delta_v_mps']:.2f} m/s", color=INK)
    fig.tight_layout()
    fig.savefig(path, dpi=150, facecolor="white")
    plt.close(fig)


def main(argv: Optional[Sequence[str]] = None) -> None:
    p = argparse.ArgumentParser(description="Replay and plot a single RPO Monte Carlo run")
    p.add_argument("--scenario", required=True, choices=list(SCENARIOS))
    p.add_argument("--seed", type=int, required=True)
    p.add_argument("--tumble", type=float, required=True, help="client tumble rate [deg/s]")
    p.add_argument("--vision-sigma", type=float, default=0.05)
    p.add_argument("--packet-loss", type=float, default=0.20)
    p.add_argument("--beacon-rate", type=float, default=1.0)
    p.add_argument("--latency", type=float, default=0.10)
    p.add_argument("--master-seed", type=int, default=None)
    p.add_argument("--manifest", type=Path, help="use the campaign config and seed; requires matching model/source")
    p.add_argument("--out", type=str, default="results_replay")
    args = p.parse_args(argv)
    cfg = SimConfig()
    master_seed = args.master_seed if args.master_seed is not None else 0
    if args.manifest is not None:
        manifest = json.loads(args.manifest.read_text())
        cfg = SimConfig(**manifest["config"])
        if manifest["model_version"] != MODEL_VERSION or manifest["config_hash"] != cfg.config_hash():
            p.error("manifest model/config differs; replay with the campaign's archived source and environment")
        if manifest.get("source_files_sha256"):
            import hashlib
            root = Path(__file__).resolve().parent.parent
            for name, digest in manifest["source_files_sha256"].items():
                relative = Path(name)
                if relative.is_absolute() or ".." in relative.parts:
                    p.error("manifest source path must stay within the project")
                path = root / relative
                if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                    p.error("source differs from manifest; use the campaign's source archive")
        if args.master_seed is not None and args.master_seed != manifest["master_seed"]:
            p.error("--master-seed conflicts with the manifest")
        master_seed = manifest["master_seed"]
    row = replay(args.scenario, args.seed, args.tumble, Path(args.out), args.vision_sigma, args.packet_loss,
                 args.beacon_rate, args.latency, master_seed, cfg)
    for key in ("status", "elapsed_s", "minimum_clearance_m", "delta_v_mps", "capture_point_error_m",
                "final_rate_error_deg_s"):
        print(f"{key:>24}: {row[key]}")
    print(f"Trajectory CSV and plot saved to {Path(args.out).resolve()}")


if __name__ == "__main__":
    main()
