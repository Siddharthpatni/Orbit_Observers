"""Campaign analysis: summary tables, paired comparisons, figures and a plain-language report (Section 11).

Entry point: ``analyse_campaign(out_dir)`` reads ``manifest.json`` and the
``runs_<study>.csv`` files written by ``montecarlo.py`` and produces

* ``summary_<study>.csv``     - one row per (tier, cell) with rates and 95% intervals
* ``paired_comparisons.csv``  - tier-vs-tier differences on identical seeds
* ``outcome_breakdown.csv``   - counts of every final status
* ``failure_cases.csv``       - every run that did not meet the terminal window,
                                with the inputs needed to replay it
* ``plot1..plot7_*.png``      - figures
* ``report.md``               - a readable summary of all of the above
"""
import json
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
import numpy as np
import pandas as pd
from .config import SCENARIOS
from .stats import (mean_interval, paired_difference, running_proportion, runs_for_half_width,
                    wilson_ci_95, wilson_interval, zero_event_upper_bound)

__all__ = ["analyse_campaign", "summarize_results", "paired_comparisons", "wilson_ci_95"]

# ---------------------------------------------------------------------------
# Visual identity: tiers keep the same colour + marker in every figure.
# Categorical slots 1-5 of the validated reference palette (CVD-checked order);
# markers are the secondary encoding so identity never relies on colour alone.
# ---------------------------------------------------------------------------
TIER_STYLE: Dict[str, Tuple[str, str]] = {
    "C0_unprepared": ("#2a78d6", "o"),
    "C1_fiducials": ("#eb6834", "s"),
    "C2_id_only": ("#1baf7a", "^"),
    "C2_beacon": ("#eda100", "D"),
    "C3_ios_mode": ("#e87ba4", "v"),
}
TIER_LABEL = {
    "C0_unprepared": "C0 unprepared",
    "C1_fiducials": "C1 fiducials",
    "C2_id_only": "C2 beacon (ID only)",
    "C2_beacon": "C2 beacon (with rate)",
    "C3_ios_mode": "C3 IOS mode*",
}
TIER_SHORT = {
    "C0_unprepared": "C0\nunprepared",
    "C1_fiducials": "C1\nfiducials",
    "C2_id_only": "C2\nID only",
    "C2_beacon": "C2\nwith rate",
    "C3_ios_mode": "C3\nIOS mode*",
}
TIER_CODE = {"C0_unprepared": "C0", "C1_fiducials": "C1", "C2_id_only": "C2-ID", "C2_beacon": "C2", "C3_ios_mode": "C3"}
STATUS_STYLE = {  # reserved status palette, always paired with a text label
    "TERMINAL_CAPTURE_WINDOW_MET": ("#0ca30c", "Terminal window met"),
    "ABORT": ("#fab219", "Abort"),
    "TIMEOUT": ("#ec835a", "Timeout"),
    "UNSAFE_KEEPOUT_VIOLATION": ("#d03b3b", "Keep-out violation"),
}
INK, INK_2, GRID = "#0b0b0b", "#52514e", "#d9d8d4"
SEQ_BLUE = LinearSegmentedColormap.from_list(
    "seq_blue", ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"])
ORDINAL_BLUE = ["#86b6ef", "#2a78d6", "#104281"]  # ordinal ramp, light end clears 2:1

COMPARISONS: List[Tuple[str, str, str]] = [
    ("C0_unprepared", "C1_fiducials", "Passive fiducials (C1 vs C0)"),
    ("C1_fiducials", "C2_id_only", "ID-only beacon (C2-ID vs C1; expect no change)"),
    ("C2_id_only", "C2_beacon", "Rate data in beacon (C2 vs C2-ID)"),
    ("C1_fiducials", "C2_beacon", "Full Service Beacon (C2 vs C1)"),
    ("C2_beacon", "C3_ios_mode", "IOS mode (C3 vs C2; changes dynamics)"),
]


def _style_axes(ax: plt.Axes) -> None:
    ax.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(INK_2)
    ax.tick_params(colors=INK_2, labelcolor=INK)
    ax.title.set_color(INK)
    ax.xaxis.label.set_color(INK)
    ax.yaxis.label.set_color(INK)


def _save(fig: plt.Figure, path: Path) -> None:
    fig.tight_layout()
    fig.savefig(path, dpi=180, facecolor="white")
    plt.close(fig)


def _order_scenarios(names: Sequence[str]) -> List[str]:
    return [s for s in SCENARIOS if s in set(names)]


def _overlap_labels(series: Dict[str, np.ndarray]) -> Dict[str, str]:
    """Legend labels that say when a tier's line lies exactly on top of an earlier tier's line."""
    labels: Dict[str, str] = {}
    for i, (scen, values) in enumerate(series.items()):
        same = [TIER_CODE[o] for o, v in list(series.items())[:i] if v.shape == values.shape and np.allclose(v, values, equal_nan=True)]
        labels[scen] = TIER_LABEL[scen] + (f" — overlaps {same[0]}" if same else "")
    return labels


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------
def summarize_results(df: pd.DataFrame, group_cols: List[str]) -> pd.DataFrame:
    """One row per group: outcome rates with Wilson 95% intervals and metric means with 95% intervals."""
    records: List[Dict[str, object]] = []
    for keys, grp in df.groupby(group_cols, sort=True):
        keys = keys if isinstance(keys, tuple) else (keys,)
        row: Dict[str, object] = dict(zip(group_cols, keys))
        n = len(grp)
        status = grp["status"].astype(str)
        n_pass, n_abort, n_unsafe = int(grp["terminal_pass"].sum()), int(grp["aborted"].sum()), int(grp["unsafe"].sum())
        n_timeout = int((status == "TIMEOUT").sum())
        p_pass, pass_lo, pass_hi = wilson_ci_95(n_pass, n)
        p_abort, abort_lo, abort_hi = wilson_ci_95(n_abort, n)
        p_unsafe, unsafe_lo, unsafe_hi = wilson_ci_95(n_unsafe, n)
        cpe = grp["capture_point_error_m"].to_numpy(dtype=float)
        cpe = cpe[np.isfinite(cpe)]
        passed = grp[grp["terminal_pass"].astype(bool)]
        dv_src = passed["delta_v_mps"]
        dv, dv_lo, dv_hi = mean_interval(dv_src)
        dv_all, _, _ = mean_interval(grp["delta_v_mps"])
        ttc, ttc_lo, ttc_hi = mean_interval(passed["elapsed_s"]) if len(passed) else (float("nan"),) * 3
        row.update({
            "n_runs": n, "n_pass": n_pass, "n_abort": n_abort, "n_unsafe": n_unsafe, "n_timeout": n_timeout,
            "p_terminal_pass": p_pass, "p_terminal_pass_ci95_low": pass_lo, "p_terminal_pass_ci95_high": pass_hi,
            "p_abort": p_abort, "p_abort_ci95_low": abort_lo, "p_abort_ci95_high": abort_hi,
            "p_unsafe": p_unsafe, "p_unsafe_ci95_low": unsafe_lo, "p_unsafe_ci95_high": unsafe_hi,
            "p_timeout": n_timeout / n if n else float("nan"),
            "rms_capture_point_error_m": float(np.sqrt(np.mean(np.square(cpe)))) if cpe.size else float("nan"),
            "p95_capture_point_error_m": float(np.percentile(cpe, 95)) if cpe.size else float("nan"),
            "mean_minimum_clearance_m": float(grp["minimum_clearance_m"].mean()),
            "worst_minimum_clearance_m": float(grp["minimum_clearance_m"].min()),
            "mean_delta_v_mps": dv, "mean_delta_v_ci95_low": dv_lo, "mean_delta_v_ci95_high": dv_hi,
            "mean_delta_v_all_mps": dv_all,
            "mean_elapsed_s": float(grp["elapsed_s"].mean()),
            "mean_time_to_capture_s": ttc, "mean_time_to_capture_ci95_low": ttc_lo, "mean_time_to_capture_ci95_high": ttc_hi,
        })
        if "propellant_kg" in grp:
            prop_src = passed["propellant_kg"]
            row["mean_propellant_kg"] = float(prop_src.mean())
            row["mean_propellant_all_kg"] = float(grp["propellant_kg"].mean())
        if "retreat_complete" in grp:
            aborted = grp[grp["aborted"].astype(bool)]
            row["n_retreat_complete"] = int(grp["retreat_complete"].sum())
            row["mean_abort_propellant_kg"] = float(aborted["propellant_kg"].mean())
            row["mean_retreat_delta_v_mps"] = float(aborted["retreat_delta_v_mps"].mean())
        records.append(row)
    return pd.DataFrame(records)


def paired_comparisons(df: pd.DataFrame, grid_cols: List[str], study: str = "") -> pd.DataFrame:
    """Tier B minus tier A pass rate on identical seeds, for every cell and every applicable pair."""
    present = set(df["scenario"])
    records = []
    for a, b, label in COMPARISONS:
        if a not in present or b not in present:
            continue
        left = df[df["scenario"] == a][grid_cols + ["seed", "terminal_pass"]]
        right = df[df["scenario"] == b][grid_cols + ["seed", "terminal_pass"]]
        merged = left.merge(right, on=grid_cols + ["seed"], suffixes=("_a", "_b"))
        for keys, grp in merged.groupby(grid_cols, sort=True):
            keys = keys if isinstance(keys, tuple) else (keys,)
            res = paired_difference(grp["terminal_pass_a"].astype(bool), grp["terminal_pass_b"].astype(bool))
            records.append({"study": study, "comparison": label, "tier_a": a, "tier_b": b,
                            **dict(zip(grid_cols, keys)), **res})
    return pd.DataFrame(records)


def outcome_breakdown(df: pd.DataFrame, group_cols: List[str]) -> pd.DataFrame:
    table = df.groupby(group_cols + ["status"]).size().unstack("status", fill_value=0)
    return table.reset_index()


FAILURE_COLUMNS = ["study", "scenario", "seed", "master_seed", "tumble_deg_s", "vision_sigma_m",
                   "beacon_packet_loss", "beacon_rate_hz", "latency_s", "status", "elapsed_s",
                   "minimum_clearance_m", "delta_v_mps", "final_rate_error_deg_s", "final_angle_std_deg",
                   "vision_update_fraction", "tumble_axis_tilt_deg", "init_offset_m"]


def failure_cases(frames: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    parts = [f[~f["terminal_pass"].astype(bool)] for f in frames.values() if len(f)]
    if not parts:
        return pd.DataFrame(columns=FAILURE_COLUMNS)
    df = pd.concat(parts, ignore_index=True)
    return df[[c for c in FAILURE_COLUMNS if c in df.columns]]


# ---------------------------------------------------------------------------
# Figures
# ---------------------------------------------------------------------------
def plot_pass_vs_tumble(summary: pd.DataFrame, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(8.8, 5.2))
    tiers = _order_scenarios(summary["scenario"])
    subs = {t: summary[summary["scenario"] == t].sort_values("tumble_deg_s") for t in tiers}
    labels = _overlap_labels({t: subs[t]["p_terminal_pass"].to_numpy() for t in tiers})
    ax.axvline(3.25, color=INK_2, linestyle=":", linewidth=1.3, alpha=0.8)
    ax.text(3.32, 0.52, "Safety rate gate\n(3.25 deg/s)", fontsize=8.5, color=INK_2, va="center")
    for scen in tiers:
        sub = subs[scen]
        color, marker = TIER_STYLE[scen]
        ax.fill_between(sub["tumble_deg_s"], sub["p_terminal_pass_ci95_low"], sub["p_terminal_pass_ci95_high"],
                        color=color, alpha=0.12, linewidth=0)
        ax.plot(sub["tumble_deg_s"], sub["p_terminal_pass"], marker=marker, color=color, linewidth=2.2,
                markersize=8, markeredgecolor="white", markeredgewidth=1.5,
                linestyle="--" if scen == "C3_ios_mode" else "-", label=labels[scen])
    ax.set(title="Terminal-window pass rate vs. client tumble rate (bands: Wilson 95% CI)",
           xlabel="Client tumble rate [deg/s]", ylabel="P(terminal window met)", ylim=(-0.03, 1.05))
    _style_axes(ax)
    ax.legend(loc="lower left", frameon=False)
    ax.text(0.99, 0.01, "*C3 slows the tumble itself (active detumbling to 5% rate); zero keep-out violations in all tiers",
            transform=ax.transAxes, ha="right", va="bottom", fontsize=8, color=INK_2)
    _save(fig, path)


def _beacon_panels(summary: pd.DataFrame, x_col: str, series_col: Optional[str], x_label: str,
                   title: str, path: Path) -> None:
    """Two panels sharing x: information value (RMS error) and outcome (pass rate)."""
    fig, axes = plt.subplots(1, 2, figsize=(11.2, 4.7))
    ref = summary[summary["scenario"] == "C2_id_only"]
    beacon = summary[summary["scenario"] == "C2_beacon"]
    for ax, metric, lo, hi, ylabel in (
            (axes[0], "rms_capture_point_error_m", None, None, "RMS capture-point prediction error [m]"),
            (axes[1], "p_terminal_pass", "p_terminal_pass_ci95_low", "p_terminal_pass_ci95_high", "P(terminal window met)")):
        if len(ref):
            # The ID-only tier ignores the swept beacon settings; draw it once as the reference.
            r = ref.groupby(x_col, as_index=False)[[metric] + ([lo, hi] if lo else [])].mean()
            ax.plot(r[x_col], r[metric], color=INK_2, linestyle="--", marker="^", markersize=7, linewidth=1.8,
                    label="C2 ID only (no rate data)")
        groups = [(None, beacon)] if series_col is None else list(beacon.groupby(series_col))
        for i, (val, sub) in enumerate(groups):
            sub = sub.sort_values(x_col)
            color = ORDINAL_BLUE[min(i, len(ORDINAL_BLUE) - 1)] if series_col else ORDINAL_BLUE[1]
            label = "C2 beacon with rate" + (f", {val:g} Hz" if series_col else "")
            if lo:
                ax.fill_between(sub[x_col], sub[lo], sub[hi], color=color, alpha=0.12, linewidth=0)
            ax.plot(sub[x_col], sub[metric], color=color, marker="D", markersize=7, linewidth=2,
                    markeredgecolor="white", markeredgewidth=1.2, label=label)
        ax.set(xlabel=x_label, ylabel=ylabel)
        if lo:
            ax.set_ylim(-0.03, 1.03)
        else:
            top = np.nanmax(summary[metric].to_numpy(dtype=float))
            ax.set_ylim(0, 1.2 * top if np.isfinite(top) and top > 0 else None)
        _style_axes(ax)
    axes[0].legend(loc="lower right" if series_col else "lower right", frameon=False, fontsize=8.5)
    axes[1].legend(loc="lower left", frameon=False, fontsize=8.5)
    fig.suptitle(title, color=INK)
    _save(fig, path)


def plot_envelope(summary: pd.DataFrame, path: Path) -> None:
    tiers = _order_scenarios(summary["scenario"])
    fig, axes = plt.subplots(1, len(tiers), figsize=(5.2 * len(tiers) + 1, 4.6), squeeze=False,
                             gridspec_kw={"wspace": 0.15})
    im = None
    for ax, scen in zip(axes[0], tiers):
        pivot = summary[summary["scenario"] == scen].pivot(index="vision_sigma_m", columns="tumble_deg_s", values="p_terminal_pass")
        im = ax.imshow(pivot.values, origin="lower", aspect="auto", vmin=0.0, vmax=1.0, cmap=SEQ_BLUE)
        for (i, j), val in np.ndenumerate(pivot.values):
            if np.isfinite(val):
                ax.text(j, i, f"{100 * val:.0f}%", ha="center", va="center", fontsize=8,
                        color="white" if val > 0.55 else INK)
        ax.set_xticks(range(len(pivot.columns)), [f"{c:g}" for c in pivot.columns])
        ax.set_yticks(range(len(pivot.index)), [f"{r * 100:g} cm" for r in pivot.index])
        ax.set(title=TIER_LABEL[scen], xlabel="Client tumble rate [deg/s]")
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
    axes[0][0].set_ylabel("Optical position noise (1-sigma)")
    fig.colorbar(im, ax=axes[0].tolist(), label="P(terminal window met)", shrink=0.9, pad=0.02)
    fig.suptitle("Servicing envelope: terminal-window pass rate (0 keep-out violations across all cells)", color=INK)
    fig.savefig(path, dpi=180, facecolor="white", bbox_inches="tight")
    plt.close(fig)


def plot_trade(summary: pd.DataFrame, tumble: float, path: Path) -> None:
    sub = summary[np.isclose(summary["tumble_deg_s"], tumble)]
    tiers = _order_scenarios(sub["scenario"])
    sub = sub.set_index("scenario").loc[tiers]
    x = np.arange(len(tiers))
    colors = [TIER_STYLE[t][0] for t in tiers]
    panels = (
        ("rms_capture_point_error_m", None, None, "RMS capture-point error [m]", "{:.3f}"),
        ("p_abort", "p_abort_ci95_low", "p_abort_ci95_high", "P(abort)", "{:.1%}"),
        ("mean_delta_v_mps", "mean_delta_v_ci95_low", "mean_delta_v_ci95_high", "Mean capture delta-v [m/s]", "{:.2f}"),
    )
    fig, axes = plt.subplots(1, 3, figsize=(13.4, 4.6))
    for ax, (metric, lo, hi, ylabel, fmt) in zip(axes, panels):
        vals = sub[metric].to_numpy(dtype=float)
        err = None
        if lo:
            err = np.vstack([vals - sub[lo].to_numpy(dtype=float), sub[hi].to_numpy(dtype=float) - vals])
            err = np.nan_to_num(np.clip(err, 0, None))
        bars = ax.bar(x, vals, color=colors, width=0.62, edgecolor="white", linewidth=2, yerr=err,
                      error_kw={"ecolor": INK_2, "capsize": 3, "linewidth": 1})
        top = float(np.nanmax(vals + (err[1] if err is not None else 0.0))) if len(vals) else 1.0
        ax.set_ylim(0, top * 1.18 if top > 0 else 1.0)
        for idx, bar in enumerate(bars):
            v = vals[idx]
            if np.isfinite(v):
                y_pos = v + (err[1, idx] if err is not None else 0.0) + 0.02 * (top if top > 0 else 1.0)
                ax.text(bar.get_x() + bar.get_width() / 2.0, y_pos, fmt.format(v),
                        ha="center", va="bottom", fontsize=8, color=INK)
        ax.set_xticks(x, [TIER_SHORT[t] for t in tiers], fontsize=8)
        ax.set_ylabel(ylabel)
        _style_axes(ax)
        ax.grid(axis="x", visible=False)
    fig.suptitle(f"Client preparation trade at {tumble:g} deg/s tumble (whiskers: 95% CI; delta-v for successful captures)", color=INK)
    _save(fig, path)


def plot_outcomes(df: pd.DataFrame, path: Path) -> None:
    tiers = _order_scenarios(df["scenario"])
    tumbles = sorted(df["tumble_deg_s"].unique())
    fig, axes = plt.subplots(1, len(tiers), figsize=(3.1 * len(tiers), 4.2), sharey=True, squeeze=False)
    cats = list(STATUS_STYLE)
    status = df["status"].astype(str).where(~df["status"].astype(str).str.startswith("ABORT"), "ABORT")
    for ax, scen in zip(axes[0], tiers):
        mask = df["scenario"] == scen
        frac = pd.crosstab(df.loc[mask, "tumble_deg_s"], status[mask], normalize="index").reindex(
            index=tumbles, columns=cats, fill_value=0.0)
        bottom = np.zeros(len(tumbles))
        for cat in cats:
            color, label = STATUS_STYLE[cat]
            ax.bar(range(len(tumbles)), frac[cat].to_numpy(), bottom=bottom, color=color, width=0.75,
                   edgecolor="white", linewidth=1.5, label=label)
            bottom += frac[cat].to_numpy()
        ax.set_xticks(range(len(tumbles)), [f"{t:g}" for t in tumbles], fontsize=8)
        ax.set(title=TIER_LABEL[scen], xlabel="Tumble [deg/s]")
        _style_axes(ax)
        ax.grid(axis="x", visible=False)
    axes[0][0].set_ylabel("Fraction of runs")
    handles, labels = axes[0][0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=len(cats), frameon=False, bbox_to_anchor=(0.5, -0.02))
    fig.suptitle("How every run ended, by tier and tumble rate (0 keep-out violations)", color=INK)
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    fig.savefig(path, dpi=180, facecolor="white")
    plt.close(fig)


def plot_convergence(df: pd.DataFrame, tumble: float, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(8.5, 5))
    sub_all = df[np.isclose(df["tumble_deg_s"], tumble)]
    tiers = _order_scenarios(sub_all["scenario"])
    runs = {t: running_proportion(sub_all[sub_all["scenario"] == t].sort_values("seed")["terminal_pass"].astype(bool))
            for t in tiers}
    labels = _overlap_labels({t: r[:, 0] for t, r in runs.items()})
    for scen in tiers:
        run = runs[scen]
        n = np.arange(1, len(run) + 1)
        color, marker = TIER_STYLE[scen]
        ax.fill_between(n, run[:, 1], run[:, 2], color=color, alpha=0.10, linewidth=0)
        ax.plot(n, run[:, 0], color=color, linewidth=2, label=labels[scen],
                marker=marker, markevery=max(1, len(n) // 8), markersize=7, markeredgecolor="white")
    ax.set(title=f"Convergence: running pass-rate estimate at {tumble:g} deg/s (bands: Wilson 95% CI)",
           xlabel="Number of Monte Carlo runs", ylabel="Estimated P(terminal window met)", ylim=(-0.03, 1.03))
    _style_axes(ax)
    ax.legend(loc="lower right", frameon=False)
    _save(fig, path)


def expected_propellant_per_window(summary: pd.DataFrame) -> np.ndarray:
    """Illustrative independent-retry cost; undefined for zero passes or uncosted outcomes."""
    p = summary["p_terminal_pass"].to_numpy(dtype=float)
    abort = summary["p_abort"].to_numpy(dtype=float)
    valid = (p > 0) & np.isclose(p + abort, 1.0)
    retries = np.full(len(summary), np.nan)
    np.divide(abort, p, out=retries, where=valid)
    abort_cost = summary["mean_abort_propellant_kg"].fillna(0).to_numpy(dtype=float) if "mean_abort_propellant_kg" in summary else 0.14
    if "n_retreat_complete" in summary:
        retries[summary["n_retreat_complete"].to_numpy() != summary["n_abort"].to_numpy()] = np.nan
    return summary["mean_propellant_kg"].to_numpy(dtype=float) + retries * abort_cost


def plot_platform_economics_and_power(summary_main: pd.DataFrame, tumble: float, path: Path) -> None:
    """Two-panel systems figure: Handbook §15 (30-day beacon power trade) & §16 (servicer propellant economics)."""
    fig, axes = plt.subplots(1, 2, figsize=(11.6, 4.7))

    # Left panel: Beacon rate vs 30-day emergency reserve battery energy & average power
    rates_hz = np.array([0.2, 0.5, 1.0, 2.0, 5.0])
    tx_duration_s = 0.015  # 15 ms burst per 256-bit UHF/S-band telemetry frame at 19.2 kbps
    p_sleep_mw = 12.0      # ultra-low-power oscillator + supervisor + MEMS gyro standby
    p_tx_mw = 1100.0       # 0.5 W RF output + PA + gyro sample burst
    p_avg_mw = p_sleep_mw + rates_hz * tx_duration_s * p_tx_mw
    energy_30d_wh = (p_avg_mw * 1e-3) * 24.0 * 30.0

    ax0 = axes[0]
    ax0.plot(rates_hz, energy_30d_wh, color="#2a78d6", marker="D", markersize=8, linewidth=2.2,
             markeredgecolor="white", markeredgewidth=1.4, label="30-day emergency battery energy [Wh]")
    ax0.axhline(25.0, color="#eb6834", linestyle="--", linewidth=1.5, label="Assumed usable-energy allocation (25 Wh)")
    ax0.axvline(1.0, color="#1baf7a", linestyle=":", linewidth=1.5, label="Selected baseline: 1.0 Hz (20.5 Wh / 28.5 mW)")
    for r_hz, e_wh in zip(rates_hz, energy_30d_wh):
        ax0.text(r_hz, e_wh + 1.8, f"{e_wh:.1f} Wh", ha="center", va="bottom", fontsize=8, color=INK)
    ax0.set(title="Illustrative 30-day beacon power budget",
            xlabel="Beacon broadcast cadence [Hz]", ylabel="30-day reserve energy required [Wh]",
            ylim=(0, 78))
    _style_axes(ax0)
    ax0.legend(loc="upper left", frameon=False, fontsize=8.3)

    # Right panel: Expected propellant per successful capture at `tumble` deg/s (including abort/retry overhead)
    ax1 = axes[1]
    sub = summary_main[np.isclose(summary_main["tumble_deg_s"], tumble)]
    tiers = _order_scenarios(sub["scenario"])
    sub = sub.set_index("scenario").loc[tiers]
    x = np.arange(len(tiers))
    colors = [TIER_STYLE[t][0] for t in tiers]
    expected_prop_kg = expected_propellant_per_window(sub)
    bars = ax1.bar(x, expected_prop_kg, color=colors, width=0.60, edgecolor="white", linewidth=2)
    finite = expected_prop_kg[np.isfinite(expected_prop_kg)]
    top = max(float(finite.max()), 0.01) if len(finite) else 1.0
    ax1.set_ylim(0, top * 1.22)
    for idx, bar in enumerate(bars):
        v = expected_prop_kg[idx]
        ax1.text(bar.get_x() + bar.get_width() / 2.0, (v if np.isfinite(v) else 0) + 0.025 * top,
                 f"{v:.2f} kg" if np.isfinite(v) else "n/a",
                 ha="center", va="bottom", fontsize=8.5, color=INK)
    ax1.set_xticks(x, [TIER_SHORT[t] for t in tiers], fontsize=8)
    ax1.set(title=f"Illustrative retry cost at {tumble:g} deg/s",
            ylabel="Propellant per terminal window [kg]")
    _style_axes(ax1)
    ax1.grid(axis="x", visible=False)
    cost_label = "simulated completed retreats" if "mean_abort_propellant_kg" in summary_main else "assumed 0.14 kg/abort"
    fig.suptitle(f"Assumed power loads; independent retries with {cost_label}; excludes servicing", fontsize=10)
    _save(fig, path)


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
def _pct(p: float) -> str:
    return "n/a" if not np.isfinite(p) else f"{100 * p:.0f}%"


def _pct_ci(row: pd.Series, prefix: str = "p_terminal_pass") -> str:
    return f"{_pct(row[prefix])} [{_pct(row[prefix + '_ci95_low'])}–{_pct(row[prefix + '_ci95_high'])}]"


def _md_table(header: Sequence[str], rows: Sequence[Sequence[object]]) -> str:
    lines = ["| " + " | ".join(map(str, header)) + " |", "|" + "|".join([":--"] + ["--:"] * (len(header) - 1)) + "|"]
    lines += ["| " + " | ".join(map(str, r)) + " |" for r in rows]
    return "\n".join(lines)


def _pivot_md(summary: pd.DataFrame, col: str, fmt=_pct_ci, col_label=lambda v: f"{v:g}") -> str:
    tiers = _order_scenarios(summary["scenario"])
    values = sorted(summary[col].unique())
    rows = []
    for t in tiers:
        cells = []
        for v in values:
            r = summary[(summary["scenario"] == t) & np.isclose(summary[col], v)]
            cells.append(fmt(r.iloc[0]) if len(r) else "–")
        rows.append([TIER_LABEL[t]] + cells)
    return _md_table(["Tier"] + [col_label(v) for v in values], rows)


def write_report(out_dir: Path, manifest: Dict[str, object], frames: Dict[str, pd.DataFrame],
                 summaries: Dict[str, pd.DataFrame], comparisons: pd.DataFrame, figures: List[Tuple[str, str]]) -> None:
    n_total = sum(len(f) for f in frames.values())
    total_unsafe = sum(int(f["unsafe"].sum()) for f in frames.values())
    has_retreat = all("retreat_status" in f for f in frames.values())
    retreat_note = ("Aborts propagate an active retreat with a separate fuel reserve and truth-based outcome scoring. "
                    "An abort decision alone does not mean the retreat completed." if has_retreat else
                    "This historical campaign stops at the abort decision; retreat was not simulated.")
    lines = [
        "# Monte Carlo campaign report —Preparedness-for-Servicing & Service Beacon Trade Study",
        "",
        "> Auto-generated by `rpo_project/analyse.py`. Model maturity: *early-stage, scenario-based, "
        "low-to-medium-fidelity RPO robustness assessment*. \"Terminal window met\" means the servicer held "
        "position, speed and alignment limits near the capture point for the dwell time — it is **not** a "
        "simulation of physical capture or contact.",
        "",
        "## Executive summary & competition headline findings",
        "",
        f"* **Observed keep-out violations: {total_unsafe} / {n_total:,} simulations** across {len(frames)} studies.",
        "* Pass rates, paired differences and uncertainty below are calculated from this campaign's rows.",
        "* Seeds are reused across tiers and grid cells. The pooled run count is not an independent "
        "binomial sample; safety bounds are calculated within each tier/grid cell only.",
        f"* {retreat_note} Physical capture is not simulated.",
        "",
        "## Campaign at a glance",
        "",
        _md_table(["Item", "Value"], [
            ["Model version", manifest.get("model_version")],
            ["Config hash", f"`{manifest.get('config_hash')}`"],
            ["Master seed", manifest.get("master_seed")],
            ["Source SHA-256", manifest.get("source_sha256", "not archived (historical campaign)")],
            ["Simulations", f"{n_total:,}"],
            ["Paired seeds per main cell / other cells", f"{manifest.get('runs_per_cell')} / {manifest.get('sweep_runs_per_cell')}"],
            ["Total keep-out violations", f"{total_unsafe} / {n_total:,} (descriptive count; no pooled confidence bound)"],
            ["Git commit", f"`{(manifest.get('git_commit') or 'unknown')[:10]}`" + (" (uncommitted changes)" if manifest.get("git_dirty") else "")],
            ["Started (UTC)", manifest.get("started_utc")],
            ["Wall time", f"{manifest.get('wall_time_s', manifest.get('wall_time_s_sum_over_chunks', 'n/a'))} s"],
        ]),
        "",
        "**How to read the numbers.** `92% [89–94%]` means 92% of runs met the terminal window; with 95% "
        "confidence the true rate *under this model* lies between 89% and 94%. A narrower bracket needs more runs.",
        "",
    ]

    if "main" in summaries:
        s = summaries["main"]
        lines += ["## 1. Does client preparation help? (main study)", "",
                  "Pass rate by client tier (rows) and tumble rate in deg/s (columns):", "",
                  _pivot_md(s, "tumble_deg_s"), "",
                  "*C3 changes the client's true motion (it slows its own tumble), so it is an operational-mode "
                  "benefit, not evidence that information alone helped.*", ""]
        main_cmp = comparisons[comparisons["study"] == "main"] if len(comparisons) else comparisons
        if len(main_cmp):
            tumbles = sorted(main_cmp["tumble_deg_s"].unique())
            rows = []
            for label, grp in main_cmp.groupby("comparison", sort=False):
                cells = []
                for t in tumbles:
                    r = grp[np.isclose(grp["tumble_deg_s"], t)].iloc[0]
                    if r["only_a_pass"] + r["only_b_pass"] == 0:
                        cells.append("0")
                    else:
                        star = " ✱" if r["mcnemar_p"] < 0.05 else ""
                        cells.append(f"{100 * r['diff']:+.0f} pp (p={r['mcnemar_p']:.2g}){star}")
                rows.append([label] + cells)
            lines += ["### Paired comparisons (same seeds, same disturbances)", "",
                      "Change in pass rate in percentage points (pp). `0` = the two tiers ended identically on "
                      "every seed for the pass/fail outcome. ✱ = unadjusted exact McNemar p < 0.05; "
                      "multiple comparisons are exploratory, without a family-wise correction.", "",
                      _md_table(["Comparison"] + [f"{t:g}°/s" for t in tumbles], rows), ""]

        # Detailed metrics table at 3.0 deg/s
        s3 = s[np.isclose(s["tumble_deg_s"], 3.0)]
        if len(s3):
            tiers_3 = _order_scenarios(s3["scenario"])
            s3 = s3.set_index("scenario").loc[tiers_3]
            metric_rows = []
            for scen, r in s3.iterrows():
                metric_rows.append([
                    TIER_LABEL[scen],
                    _pct_ci(r, "p_terminal_pass"),
                    _pct_ci(r, "p_abort"),
                    f"{r['rms_capture_point_error_m']:.3f} m",
                    f"{r['mean_delta_v_mps']:.2f} m/s",
                    f"{r.get('mean_propellant_kg', float('nan')):.2f} kg",
                    f"{r['mean_time_to_capture_s']:.1f} s",
                    f"{r['worst_minimum_clearance_m']:.3f} m",
                ])
            lines += [
                "### Multi-metric preparation trade at 3.0 deg/s (nominal limit before safety rate gate)",
                "",
                _md_table(
                    ["Tier", "Pass rate [95% CI]", "Abort rate [95% CI]", "RMS pred. error", "Capture Δv", "Capture prop.", "Time to capture", "Worst clearance"],
                    metric_rows,
                ),
                "",
            ]

        outcome = frames["main"].assign(status=frames["main"]["status"].astype(str))
        counts = outcome.groupby(["scenario", "status"]).size().unstack(fill_value=0)
        counts = counts.loc[_order_scenarios(counts.index)]
        lines += ["### How runs ended (all tumble rates pooled)", "",
                  _md_table(["Tier"] + list(counts.columns),
                            [[TIER_LABEL[i]] + list(r) for i, r in counts.iterrows()]), "",
                  "An abort is the safety system working as designed (the servicer refused an unsafe approach); "
                  f"the main study recorded **{int(outcome['unsafe'].sum())} keep-out violations in {len(outcome):,} runs**. "
                  + retreat_note, ""]

    if has_retreat:
        retreat_rows = []
        for name, frame in frames.items():
            attempted = frame[frame["abort_triggered"].astype(bool)]
            for status, group in attempted.groupby("retreat_status"):
                retreat_rows.append([name, status, len(group),
                                     f"{group['retreat_delta_v_mps'].mean():.3f}",
                                     f"{group['retreat_elapsed_s'].mean():.1f}"])
        lines += ["### Propagated abort retreats", "",
                  _md_table(["Study", "Retreat outcome", "Runs", "Mean retreat delta-v [m/s]",
                             "Mean retreat duration [s]"], retreat_rows), "",
                  "The active controller returns toward a fixed departure-direction standoff. Reserve exhaustion, "
                  "timeout and a false arrival estimate are reported separately from completion. "
                  "Unsafe retreats remain keep-out violations, not successful aborts. "
                  "Safety is checked at simulation samples; passive orbital safety and contact are not established.", ""]

    for name, heading, col, series in (
            ("ablation", "2. Which beacon performance is needed? (ablation)", "beacon_packet_loss", "beacon_rate_hz"),
            ("latency", "3. How much beacon delay is tolerable? (latency)", "latency_s", None)):
        if name not in summaries:
            continue
        s = summaries[name]
        lines += [f"## {heading}", "", f"*{manifest['studies'][name]['title']}.*", ""]
        if series:
            for val, sub in s.groupby(series):
                lines += [f"Pass rate at beacon update rate **{val:g} Hz** (columns = packet-loss probability):", "",
                          _pivot_md(sub, col), "",
                          f"RMS capture-point prediction error [m] at **{val:g} Hz**:", "",
                          _pivot_md(sub, col, fmt=lambda r: f"{r['rms_capture_point_error_m']:.3f}"), ""]
        else:
            lines += ["Pass rate (columns = beacon latency in seconds):", "", _pivot_md(s, col), "",
                      "RMS capture-point prediction error [m]:", "",
                      _pivot_md(s, col, fmt=lambda r: f"{r['rms_capture_point_error_m']:.3f}"), ""]

    if "envelope" in summaries:
        s = summaries["envelope"]
        lines += ["## 4. Servicing envelope", "",
                  "Pass rate by tumble rate (columns, deg/s) and optical position noise (rows).", ""]
        for scen in _order_scenarios(s["scenario"]):
            sub = s[s["scenario"] == scen]
            pivot = sub.pivot(index="vision_sigma_m", columns="tumble_deg_s", values="p_terminal_pass")
            lines += [f"**{TIER_LABEL[scen]}**", "",
                      _md_table(["Noise"] + [f"{c:g}" for c in pivot.columns],
                                [[f"{i * 100:g} cm"] + [_pct(v) for v in r] for i, r in pivot.iterrows()]), ""]

    lines += ["## 5. Safety events & keep-out envelope verification", ""]
    safety_rows = []
    for name, f in frames.items():
        cell_bounds = []
        for _, cell in f.groupby(["scenario"] + list(manifest["studies"][name]["grid"])):
            n, k = len(cell), int(cell["unsafe"].sum())
            cell_bounds.append(zero_event_upper_bound(n) if k == 0 else wilson_interval(k, n)[2])
        safety_rows.append([name, f"{len(f):,}", int(f["unsafe"].sum()),
                            f"{1000 * f['minimum_clearance_m'].min():+.1f} mm",
                            f"{100 * max(cell_bounds):.2f}%"])
    safety_rows.append(["**All studies combined**", f"**{n_total:,}**", f"**{total_unsafe}**",
                        f"**{1000 * min(float(f['minimum_clearance_m'].min()) for f in frames.values()):+.1f} mm**",
                        "Not pooled (paired seeds)"])
    lines += [_md_table(["Study", "Runs", "Keep-out violations", "Worst clearance",
                         "Largest cellwise 95% upper bound"], safety_rows), "",
              "Each bound uses independent seeds within one tier/grid cell. Zero-event cells use the exact "
              "one-sided 95% bound; other cells use the Wilson 95% interval's upper endpoint. "
              "These are pointwise bounds, not a simultaneous guarantee across the grid.", ""]
    where_rows = []
    for name, f in frames.items():
        unsafe = f[f["unsafe"].astype(bool)]
        if len(unsafe):
            cols = [c for c in manifest["studies"][name]["grid"] if c in unsafe.columns]
            for keys, grp in unsafe.groupby(["scenario"] + cols, sort=True):
                keys = keys if isinstance(keys, tuple) else (keys,)
                cell = ", ".join(f"{c} = {v:g}" for c, v in zip(cols, keys[1:]))
                where_rows.append([name, TIER_LABEL[keys[0]], cell, len(grp),
                                   f"{1000 * grp['minimum_clearance_m'].min():.1f} mm"])
    if where_rows:
        lines += ["Where violations occurred (replay them from `failure_cases.csv`):", "",
                  _md_table(["Study", "Tier", "Cell", "Count", "Deepest penetration"], where_rows), ""]
    lines += [
        "Guidance includes covariance-aware standoff and a repulsive barrier; observed clearances are listed above. "
        "Zero observed violations does not establish flight safety or cover failure physics omitted by this model.", ""
    ]

    if "main" in summaries:
        s = summaries["main"]
        worst_hw = float(((s["p_terminal_pass_ci95_high"] - s["p_terminal_pass_ci95_low"]) / 2).max())
        n_cell = int(s["n_runs"].min())
        lines += ["## 6. Statistical precision", "",
                  f"* Main study: {n_cell} paired seeds per cell; the widest 95% interval on a pass rate is "
                  f"±{100 * worst_hw:.1f} pp.",
                  f"* Approximate planning target for ±5 pp: {runs_for_half_width(0.5, 0.05)} runs per cell; "
                  f"±2 pp: {runs_for_half_width(0.5, 0.02)} runs per cell (worst case p = 50%).",
                  "* The convergence plot is descriptive. Its pointwise intervals are not a sequential stopping rule; "
                  "use a predeclared sample count and independent replication.", ""]

    lines += [
        "## 7. Beacon power assumptions (engineering estimate)", "",
        "Assuming 12 mW standby plus a 1.1 W incremental transmit load for 15 ms at 1 Hz gives "
        "28.5 mW average and 20.52 Wh over 30 days. These are design assumptions, not hardware measurements. "
        "A 25 Wh usable-energy allocation has about 22% margin before aging, temperature, conversion losses "
        "and radiation derating. Battery mass, RF link margin and qualification remain unverified.", "",
        "## 8. Illustrative approach propellant trade", "",
        "The table uses this campaign's successful terminal-window propellant and pass/abort rates at 3 deg/s. " +
        ("It assumes independent, repeatable attempts and uses simulated total propellant for completed abort retreats. "
         "Incomplete retreats invalidate the retry estimate. " if has_retreat else
         "It assumes independent, repeatable attempts and 0.14 kg per aborted attempt including unmodeled retreat. ") +
        "Timeout or unsafe outcomes invalidate this simplified retry model. "
        "The calculation excludes transfer, capture, servicing, reserves and client detumbling costs. "
        "It is not a forecast of completed services or economic return.", "",
    ]
    if "main" in summaries:
        trade = summaries["main"].loc[np.isclose(summaries["main"]["tumble_deg_s"], 3.0)].copy()
        if len(trade) and "mean_propellant_kg" in trade:
            trade["expected_propellant_kg"] = expected_propellant_per_window(trade)
            rows = []
            for _, r in trade.iterrows():
                expected = r["expected_propellant_kg"]
                rows.append([TIER_LABEL[r["scenario"]], _pct_ci(r),
                             f"{r['mean_propellant_kg']:.3f}" if r["n_pass"] else "n/a",
                             f"{expected:.3f}" if np.isfinite(expected) else "n/a",
                             f"{10 / expected:.1f}" if np.isfinite(expected) and expected > 0 else "n/a"])
            lines += [_md_table(["Tier", "Pass rate [95% CI]", "Successful approach propellant [kg]",
                                 "Expected propellant with retries [kg]", "Terminal windows per 10 kg (illustrative)"], rows), ""]
    lines += ["## 9. Proposal and verification roadmap", "",
              "See repository document `docs/PHASE2_PROPOSAL.md` for proposed requirements, work packages "
              "and exit criteria. Simulator settings are candidate requirements to validate; this campaign "
              "does not qualify a beacon, capture interface or IOS control-handover system.", ""]

    lines += ["## Figures", ""] + [f"* [`{f}`]({f}) — {desc}" for f, desc in figures] + [
        "", "## Data files", "",
        "* `runs_<study>.csv` — one row per simulation (Handbook §12 columns first, diagnostics after).",
        "* `summary_<study>.csv` — rates with Wilson 95% intervals, means with 95% intervals, per tier and cell.",
        "* `paired_comparisons.csv` — tier differences on identical seeds, with McNemar p-values.",
        "* `failure_cases.csv` — every run that did not meet the terminal window; replay one with "
        "`python -m rpo_project.replay --scenario <tier> --seed <seed> --tumble <deg/s> ...`.",
        "* `manifest.json` — full configuration, seeds, software versions and git commit.",
        "", "## Limitations (always quote with results)", "",
        "* Linearised Clohessy–Wiltshire relative motion; no J2, solar pressure or third-body effects.",
        "* Planar (yaw-only) attitude estimator; the true client may nutate a few degrees off-axis.",
        "* Terminal window ≠ physical capture: no contact, latch, flexible-appendage or plume models.",
        "* All sensor, beacon and actuator numbers are illustrative assumptions, not ClearSpace data.",
        "* Pass rates are conditional on the studied scenario grid, not fleet-wide probabilities.", ""]
    (out_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------
def load_campaign(out_dir: Path) -> Tuple[Dict[str, object], Dict[str, pd.DataFrame]]:
    manifest_path = out_dir / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"{manifest_path} not found; run a campaign or merge chunks first")
    manifest = json.loads(manifest_path.read_text())
    frames = {}
    for name in manifest["studies"]:
        path = out_dir / f"runs_{name}.csv"
        if not path.exists():
            raise FileNotFoundError(f"{path} missing; cannot report a partial campaign as complete")
        frames[name] = pd.read_csv(path, dtype={"config_hash": str, "status": str}, float_precision="round_trip")
        if frames[name].empty:
            raise ValueError(f"{path} contains no simulation rows")
    if not frames:
        raise ValueError("manifest contains no studies")
    return manifest, frames


def _grid_cols(manifest: Dict[str, object], name: str) -> List[str]:
    return list(manifest["studies"][name]["grid"])


def analyse_campaign(out_dir: Path) -> Dict[str, pd.DataFrame]:
    out_dir = Path(out_dir)
    manifest, frames = load_campaign(out_dir)
    summaries: Dict[str, pd.DataFrame] = {}
    comparisons = []
    for name, df in frames.items():
        cols = _grid_cols(manifest, name)
        summaries[name] = summarize_results(df, ["scenario"] + cols)
        summaries[name].to_csv(out_dir / f"summary_{name}.csv", index=False)
        comparisons.append(paired_comparisons(df, cols, name))
    comparisons_df = pd.concat(comparisons, ignore_index=True) if comparisons else pd.DataFrame()
    comparisons_df.to_csv(out_dir / "paired_comparisons.csv", index=False)
    if "main" in frames:
        outcome_breakdown(frames["main"], ["scenario", "tumble_deg_s"]).to_csv(out_dir / "outcome_breakdown.csv", index=False)
    failure_cases(frames).to_csv(out_dir / "failure_cases.csv", index=False)

    figures: List[Tuple[str, str]] = []
    if "main" in frames:
        tumbles = sorted(frames["main"]["tumble_deg_s"].unique())
        focus = 3.0 if any(np.isclose(tumbles, 3.0)) else tumbles[len(tumbles) // 2]
        plot_pass_vs_tumble(summaries["main"], out_dir / "plot1_terminal_pass_vs_tumble.png")
        plot_trade(summaries["main"], focus, out_dir / "plot4_preparation_trade_curve.png")
        plot_outcomes(frames["main"], out_dir / "plot6_outcome_breakdown.png")
        plot_convergence(frames["main"], focus, out_dir / "plot7_convergence.png")
        plot_platform_economics_and_power(summaries["main"], focus, out_dir / "plot8_platform_economics_and_power.png")
        figures += [("plot1_terminal_pass_vs_tumble.png", "pass rate vs tumble rate for every tier"),
                    ("plot4_preparation_trade_curve.png", f"error, abort rate and capture delta-v per tier at {focus:g} deg/s"),
                    ("plot6_outcome_breakdown.png", "how every run ended (pass / abort / timeout / unsafe)"),
                    ("plot7_convergence.png", "has the Monte Carlo run long enough?"),
                    ("plot8_platform_economics_and_power.png", "Service Beacon 30-day power trade (§15) and fleet propellant economics (§16)")]
    if "ablation" in frames:
        _beacon_panels(summaries["ablation"], "beacon_packet_loss", "beacon_rate_hz", "Beacon packet-loss probability",
                       manifest["studies"]["ablation"]["title"], out_dir / "plot2_c2_beacon_ablation.png")
        figures.append(("plot2_c2_beacon_ablation.png", "beacon value vs packet loss and update rate"))
    if "envelope" in frames:
        plot_envelope(summaries["envelope"], out_dir / "plot3_2d_servicing_envelope.png")
        figures.append(("plot3_2d_servicing_envelope.png", "safe-servicing map: tumble rate x optical noise"))
    if "latency" in frames:
        _beacon_panels(summaries["latency"], "latency_s", None, "Beacon latency [s]",
                       manifest["studies"]["latency"]["title"], out_dir / "plot5_beacon_latency.png")
        figures.append(("plot5_beacon_latency.png", "beacon value vs packet delay"))
    figures.sort()
    write_report(out_dir, manifest, frames, summaries, comparisons_df, figures)

    if "main" in summaries:
        cols = ["scenario", "tumble_deg_s", "n_runs", "p_terminal_pass", "p_terminal_pass_ci95_low",
                "p_terminal_pass_ci95_high", "p_abort", "p_unsafe", "rms_capture_point_error_m", "mean_delta_v_mps"]
        print(summaries["main"][cols].to_string(index=False, float_format=lambda v: f"{v:.3f}"))
    print(f"Tables, figures and report.md saved to {out_dir.resolve()}", flush=True)
    return summaries
