"""Export the main-study feasibility table of a campaign to JSON for the ops platform.

Usage: python tools/export_feasibility.py [campaign_dir] [out.json]
Reads summary_main.csv + manifest.json; no simulation is run.
"""
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CAMPAIGN = ROOT / "results" / "v4_1_validation"
DEFAULT_OUT = ROOT / "satellite-ops-platform" / "src" / "data" / "feasibility.json"

FIELDS = [
    "n_runs", "n_pass", "n_abort", "n_unsafe", "n_timeout",
    "p_terminal_pass", "p_terminal_pass_ci95_low", "p_terminal_pass_ci95_high",
    "p_abort", "p_unsafe", "mean_delta_v_mps", "mean_time_to_capture_s",
]


def build(campaign: Path) -> dict:
    manifest = json.loads((campaign / "manifest.json").read_text())
    cells = []
    with open(campaign / "summary_main.csv", newline="") as f:
        for row in csv.DictReader(f):
            cell = {"tier": row["scenario"], "tumble_deg_s": float(row["tumble_deg_s"])}
            for k in FIELDS:
                v = row.get(k, "")
                cell[k] = float(v) if v not in ("", None) else None
            cells.append(cell)
    return {
        "model_version": manifest["model_version"],
        "config_hash": manifest["config_hash"],
        "master_seed": manifest["master_seed"],
        "paired_seeds_per_cell": manifest["runs_per_cell"],
        "source_sha256": manifest.get("source_sha256"),
        "campaign": campaign.name,
        "caveat": "Model result under stated assumptions. 'Pass' = terminal window met, not physical capture. "
                  "Seeds are paired across tiers; not a flight safety guarantee.",
        "cells": cells,
    }


if __name__ == "__main__":
    campaign = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_CAMPAIGN
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_OUT
    data = build(campaign)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=1) + "\n")
    print(f"wrote {out} ({len(data['cells'])} cells, {data['model_version']}, {data['config_hash']})")
