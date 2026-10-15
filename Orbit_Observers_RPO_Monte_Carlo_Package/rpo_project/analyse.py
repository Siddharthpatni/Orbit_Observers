"""Wilson 95% confidence intervals, summary statistics, and 4 OSIP plots (Section 11)."""
import math
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from .config import SCENARIOS

def wilson_ci_95(k_success: int, n_total: int, z: float = 1.959963984540054) -> Tuple[float, float, float]:
    if n_total <= 0:
        return 0.0, 0.0, 0.0
    p_hat = float(k_success) / float(n_total)
    z2 = z * z
    denom = 1.0 + z2 / n_total
    center = (p_hat + z2 / (2.0 * n_total)) / denom
    half_width = (z / denom) * math.sqrt(max(0.0, (p_hat * (1.0 - p_hat) / n_total) + (z2 / (4.0 * (n_total ** 2)))))
    return p_hat, max(0.0, center - half_width), min(1.0, center + half_width)

def summarize_results(df: pd.DataFrame, group_cols: List[str]) -> pd.DataFrame:
    records: List[Dict[str, object]] = []
    for keys, grp in df.groupby(group_cols, as_index=False):
        if not isinstance(keys, tuple):
            keys = (keys,)
        row_dict = {col: val for col, val in zip(group_cols, keys)}
        n_runs = len(grp)
        p_pass, pass_lo, pass_hi = wilson_ci_95(int(grp["terminal_pass"].sum()), n_runs)
        p_abort, abort_lo, abort_hi = wilson_ci_95(int(grp["aborted"].sum()), n_runs)
        p_unsafe, unsafe_lo, unsafe_hi = wilson_ci_95(int(grp["unsafe"].sum()), n_runs)
        row_dict.update({
            "n_runs": n_runs,
            "p_terminal_pass": p_pass, "p_terminal_pass_ci95_low": pass_lo, "p_terminal_pass_ci95_high": pass_hi,
            "p_abort": p_abort, "p_abort_ci95_low": abort_lo, "p_abort_ci95_high": abort_hi,
            "p_unsafe": p_unsafe, "p_unsafe_ci95_low": unsafe_lo, "p_unsafe_ci95_high": unsafe_hi,
            "rms_capture_point_error_m": float(np.sqrt(np.mean(np.square(grp["capture_point_error_m"])))),
            "p95_capture_point_error_m": float(np.percentile(grp["capture_point_error_m"], 95)),
            "mean_minimum_clearance_m": float(grp["minimum_clearance_m"].mean()),
            "mean_delta_v_mps": float(grp["delta_v_mps"].mean()),
            "mean_elapsed_s": float(grp["elapsed_s"].mean()),
        })
        records.append(row_dict)
    return pd.DataFrame(records)

def generate_four_core_plots(df_main: pd.DataFrame, df_ablation: Optional[pd.DataFrame], df_envelope: Optional[pd.DataFrame], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    summary_main = summarize_results(df_main, ["scenario", "tumble_deg_s"])

    fig, ax = plt.subplots(figsize=(8, 5))
    for scen_name in SCENARIOS.keys():
        sub = summary_main[summary_main["scenario"] == scen_name].sort_values("tumble_deg_s")
        if sub.empty:
            continue
        ax.plot(sub["tumble_deg_s"], sub["p_terminal_pass"], marker="o", linewidth=2, label=scen_name)
        ax.fill_between(sub["tumble_deg_s"], sub["p_terminal_pass_ci95_low"], sub["p_terminal_pass_ci95_high"], alpha=0.18)
    ax.set(title="Plot 1: Terminal-Condition Pass Rate vs. Tumble Rate (95% Wilson CI)", xlabel="Initial Target Tumble Rate [deg/s]", ylabel="P(Terminal Condition Met)", ylim=(-0.03, 1.03))
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(out_dir / "plot1_terminal_pass_vs_tumble.png", dpi=180)
    plt.close(fig)

    if df_ablation is not None and not df_ablation.empty:
        sum_abl = summarize_results(df_ablation, ["scenario", "beacon_packet_loss", "beacon_rate_hz"])
        fig, ax = plt.subplots(figsize=(8, 5))
        for (scen_name, rate_hz), sub in sum_abl.groupby(["scenario", "beacon_rate_hz"]):
            sub = sub.sort_values("beacon_packet_loss")
            ax.plot(sub["beacon_packet_loss"], sub["rms_capture_point_error_m"], marker="s", label=f"{scen_name} ({rate_hz:.1f} Hz)")
        ax.set(title="Plot 2: C2 Beacon Ablation (ID-Only vs. Gyro Packets)", xlabel="Beacon Packet Loss Probability", ylabel="RMS Capture-Point Prediction Error [m]")
        ax.grid(True, alpha=0.3)
        ax.legend(loc="best")
        fig.tight_layout()
        fig.savefig(out_dir / "plot2_c2_beacon_ablation.png", dpi=180)
        plt.close(fig)

    if df_envelope is not None and not df_envelope.empty:
        sum_env = summarize_results(df_envelope, ["tumble_deg_s", "vision_sigma_m"])
        pivot = sum_env.pivot(index="vision_sigma_m", columns="tumble_deg_s", values="p_terminal_pass")
        fig, ax = plt.subplots(figsize=(7, 5))
        im = ax.imshow(pivot.values, origin="lower", aspect="auto", vmin=0.0, vmax=1.0, cmap="viridis")
        ax.set_xticks(range(len(pivot.columns)))
        ax.set_xticklabels([f"{c:.2f}" for c in pivot.columns])
        ax.set_yticks(range(len(pivot.index)))
        ax.set_yticklabels([f"{r * 100:.0f} cm" for r in pivot.index])
        ax.set(title="Plot 3: 2-D Safe Servicing Envelope (C2_beacon Pass Fraction)", xlabel="Target Tumble Rate [deg/s]", ylabel="Optical Position Noise Proxy")
        fig.colorbar(im, ax=ax, label="P(Terminal Condition Met)")
        fig.tight_layout()
        fig.savefig(out_dir / "plot3_2d_servicing_envelope.png", dpi=180)
        plt.close(fig)

    fig, ax1 = plt.subplots(figsize=(8, 5))
    sub_2deg = summary_main[np.isclose(summary_main["tumble_deg_s"], 2.0)].copy()
    order = ["C0_unprepared", "C1_fiducials", "C2_id_only", "C2_beacon", "C3_ios_mode"]
    sub_2deg["order"] = sub_2deg["scenario"].map({k: i for i, k in enumerate(order)})
    sub_2deg = sub_2deg.sort_values("order")
    ax1.plot(sub_2deg["scenario"], sub_2deg["rms_capture_point_error_m"], "o-", color="tab:blue", linewidth=2)
    ax1.set_ylabel("RMS Capture-Point Prediction Error [m]", color="tab:blue")
    ax1.grid(True, alpha=0.3)
    ax2 = ax1.twinx()
    ax2.plot(sub_2deg["scenario"], sub_2deg["p_abort"], "s--", color="tab:red", linewidth=2)
    ax2.set_ylabel("P(Abort)", color="tab:red")
    ax2.set_ylim(-0.05, 1.05)
    ax1.set_title("Plot 4: Client Preparation Trade Curve (Error & Abort Rate across Tiers)")
    fig.tight_layout()
    fig.savefig(out_dir / "plot4_preparation_trade_curve.png", dpi=180)
    plt.close(fig)
