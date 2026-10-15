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
    "ABORT": ("#fab219", "Safe abort"),
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
        dv, dv_lo, dv_hi = mean_interval(grp["delta_v_mps"])
        passed = grp[grp["terminal_pass"].astype(bool)]
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
            "mean_elapsed_s": float(grp["elapsed_s"].mean()),
            "mean_time_to_capture_s": ttc, "mean_time_to_capture_ci95_low": ttc_lo, "mean_time_to_capture_ci95_high": ttc_hi,
        })
        if "propellant_kg" in grp:
            row["mean_propellant_kg"] = float(grp["propellant_kg"].mean())
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
    fig, ax = plt.subplots(figsize=(8.5, 5))
    tiers = _order_scenarios(summary["scenario"])
    subs = {t: summary[summary["scenario"] == t].sort_values("tumble_deg_s") for t in tiers}
    labels = _overlap_labels({t: subs[t]["p_terminal_pass"].to_numpy() for t in tiers})
    for scen in tiers:
        sub = subs[scen]
        color, marker = TIER_STYLE[scen]
        ax.fill_between(sub["tumble_deg_s"], sub["p_terminal_pass_ci95_low"], sub["p_terminal_pass_ci95_high"],
                        color=color, alpha=0.12, linewidth=0)
        ax.plot(sub["tumble_deg_s"], sub["p_terminal_pass"], marker=marker, color=color, linewidth=2,
                markersize=8, markeredgecolor="white", markeredgewidth=1.5,
                linestyle="--" if scen == "C3_ios_mode" else "-", label=labels[scen])
    ax.set(title="Terminal-window pass rate vs. tumble rate (bands: Wilson 95% CI)",
           xlabel="Client tumble rate [deg/s]", ylabel="P(terminal window met)", ylim=(-0.03, 1.03))
    _style_axes(ax)
    ax.legend(loc="lower left", frameon=False)
    ax.text(0.99, 0.01, "*C3 slows the tumble itself (different dynamics)", transform=ax.transAxes,
            ha="right", va="bottom", fontsize=8, color=INK_2)
    _save(fig, path)


def _beacon_panels(summary: pd.DataFrame, x_col: str, series_col: Optional[str], x_label: str,
                   title: str, path: Path) -> None:
    """Two panels sharing x: information value (RMS error) and outcome (pass rate)."""
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.6))
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
    axes[1].legend(loc="lower left", frameon=False, fontsize=9)
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
    fig.suptitle("Servicing envelope: where the terminal window is reached", color=INK)
    fig.savefig(path, dpi=180, facecolor="white", bbox_inches="tight")
    plt.close(fig)


def plot_trade(summary: pd.DataFrame, tumble: float, path: Path) -> None:
    sub = summary[np.isclose(summary["tumble_deg_s"], tumble)]
    tiers = _order_scenarios(sub["scenario"])
    sub = sub.set_index("scenario").loc[tiers]
    x = np.arange(len(tiers))
    colors = [TIER_STYLE[t][0] for t in tiers]
    panels = (
        ("rms_capture_point_error_m", None, None, "RMS capture-point error [m]"),
        ("p_abort", "p_abort_ci95_low", "p_abort_ci95_high", "P(abort)"),
        ("mean_delta_v_mps", "mean_delta_v_ci95_low", "mean_delta_v_ci95_high", "Mean delta-v [m/s]"),
    )
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.4))
    for ax, (metric, lo, hi, ylabel) in zip(axes, panels):
        vals = sub[metric].to_numpy(dtype=float)
        err = None
        if lo:
            err = np.vstack([vals - sub[lo].to_numpy(dtype=float), sub[hi].to_numpy(dtype=float) - vals])
            err = np.nan_to_num(np.clip(err, 0, None))
        ax.bar(x, vals, color=colors, width=0.62, edgecolor="white", linewidth=2, yerr=err,
               error_kw={"ecolor": INK_2, "capsize": 3, "linewidth": 1})
        ax.set_xticks(x, [TIER_SHORT[t] for t in tiers], fontsize=8)
        ax.set_ylabel(ylabel)
        _style_axes(ax)
        ax.grid(axis="x", visible=False)
    fig.suptitle(f"Client preparation trade at {tumble:g} deg/s tumble (whiskers: 95% CI)", color=INK)
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
    fig.suptitle("How every run ended, by tier and tumble rate", color=INK)
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
    lines = [
        "# Monte Carlo campaign report",
        "",
        "> Auto-generated by `rpo_project/analyse.py`. Model maturity: *early-stage, scenario-based, "
        "low-to-medium-fidelity RPO robustness assessment*. \"Terminal window met\" means the servicer held "
        "position, speed and alignment limits near the capture point for the dwell time — it is **not** a "
        "simulation of physical capture or contact.",
        "",
        "## Campaign at a glance",
        "",
        _md_table(["Item", "Value"], [
            ["Model version", manifest.get("model_version")],
            ["Config hash", f"`{manifest.get('config_hash')}`"],
            ["Master seed", manifest.get("master_seed")],
            ["Simulations", f"{n_total:,}"],
            ["Paired seeds per main cell / other cells", f"{manifest.get('runs_per_cell')} / {manifest.get('sweep_runs_per_cell')}"],
            ["Git commit", f"`{(manifest.get('git_commit') or 'unknown')[:10]}`" + (" (uncommitted changes)" if manifest.get("git_dirty") else "")],
            ["Started (UTC)", manifest.get("started_utc")],
            ["Wall time", f"{manifest.get('wall_time_s', manifest.get('wall_time_s_sum_over_chunks', 'n/a'))} s"],
        ]),
        "",
        "**How to read the numbers.** `97% [91–99%]` means 97% of runs met the terminal window; with 95% "
        "confidence the true rate *under this model* lies between 91% and 99%. A narrower bracket needs more runs.",
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
                      "every seed. ✱ = statistically significant (exact McNemar test, p < 0.05).", "",
                      _md_table(["Comparison"] + [f"{t:g}°/s" for t in tumbles], rows), ""]
        outcome = frames["main"].assign(status=frames["main"]["status"].astype(str))
        counts = outcome.groupby(["scenario", "status"]).size().unstack(fill_value=0)
        counts = counts.loc[_order_scenarios(counts.index)]
        lines += ["### How runs ended (all tumble rates pooled)", "",
                  _md_table(["Tier"] + list(counts.columns),
                            [[TIER_LABEL[i]] + list(r) for i, r in counts.iterrows()]), "",
                  "An abort is the safety system working as designed (the servicer refused an unsafe approach); "
                  "a keep-out violation is a genuine safety failure.", ""]

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
                          _pivot_md(sub, col), ""]
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

    lines += ["## 5. Safety events", ""]
    safety_rows = []
    for name, f in frames.items():
        n, k = len(f), int(f["unsafe"].sum())
        bound = zero_event_upper_bound(n) if k == 0 else wilson_interval(k, n)[2]
        safety_rows.append([name, f"{n:,}", k, f"{100 * bound:.2g}%"])
    lines += [_md_table(["Study", "Runs", "Keep-out violations", "95% upper bound on rate"], safety_rows), ""]
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
    lines += ["Zero violations does **not** prove flight-level safety: the bound only covers failure physics "
              "that the model contains (Handbook §10).", ""]

    if "main" in summaries:
        s = summaries["main"]
        worst_hw = float(((s["p_terminal_pass_ci95_high"] - s["p_terminal_pass_ci95_low"]) / 2).max())
        n_cell = int(s["n_runs"].min())
        lines += ["## 6. Statistical precision", "",
                  f"* Main study: {n_cell} paired seeds per cell; the widest 95% interval on a pass rate is "
                  f"±{100 * worst_hw:.0f} pp.",
                  f"* To guarantee ±5 pp on any rate: {runs_for_half_width(0.5, 0.05)} runs per cell; "
                  f"±2 pp: {runs_for_half_width(0.5, 0.02)} runs per cell (worst case p = 50%).",
                  "* See `plot7_convergence.png`: once the running estimate stays inside its band, more runs "
                  "change the answer only within that band.", ""]

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
        if path.exists():
            frames[name] = pd.read_csv(path, dtype={"config_hash": str, "status": str}, float_precision="round_trip")
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
        figures += [("plot1_terminal_pass_vs_tumble.png", "pass rate vs tumble rate for every tier"),
                    ("plot4_preparation_trade_curve.png", f"error, abort rate and delta-v per tier at {focus:g} deg/s"),
                    ("plot6_outcome_breakdown.png", "how every run ended (pass / abort / timeout / unsafe)"),
                    ("plot7_convergence.png", "has the Monte Carlo run long enough?")]
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
