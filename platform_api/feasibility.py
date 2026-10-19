"""Feasibility lookup from a stored Monte Carlo campaign (no simulation is run here)."""
import json
from pathlib import Path

DEFAULT_FILE = Path(__file__).resolve().parents[1] / "satellite-ops-platform" / "src" / "data" / "feasibility.json"

TIER_ALIASES = {
    "C0": "C0_unprepared", "C1": "C1_fiducials", "C2-ID": "C2_id_only",
    "C2": "C2_beacon", "C3": "C3_ios_mode",
}


class FeasibilityTable:
    def __init__(self, path: Path = DEFAULT_FILE):
        self.data = json.loads(Path(path).read_text())
        self.cells = self.data["cells"]

    def tiers(self) -> list[str]:
        return sorted({c["tier"] for c in self.cells})

    def grid(self, tier: str) -> list[float]:
        return sorted(c["tumble_deg_s"] for c in self.cells if c["tier"] == tier)

    def query(self, tier: str, tumble_deg_s: float) -> dict:
        tier = TIER_ALIASES.get(tier, tier)
        pts = [c for c in self.cells if c["tier"] == tier]
        if not pts:
            raise KeyError(f"unknown tier {tier!r}; known: {self.tiers()}")
        grid = self.grid(tier)
        lo, hi = grid[0], grid[-1]
        cell = min(pts, key=lambda c: abs(c["tumble_deg_s"] - tumble_deg_s))
        notes = []
        if tumble_deg_s > hi:
            notes.append(f"requested {tumble_deg_s} deg/s is above the tested range (max {hi}); no evidence")
        elif tumble_deg_s < lo:
            notes.append(f"requested {tumble_deg_s} deg/s is below the tested range")
        elif abs(cell["tumble_deg_s"] - tumble_deg_s) > 1e-9:
            notes.append(f"nearest tested grid point {cell['tumble_deg_s']} deg/s used (no interpolation)")
        if tier == "C3_ios_mode":
            notes.append("C3 assumes a 95% initial-spin reduction; IOS handover controller is not coupled to this result")
        return {
            "tier": tier, "requested_tumble_deg_s": tumble_deg_s, "cell_tumble_deg_s": cell["tumble_deg_s"],
            "within_tested_range": lo <= tumble_deg_s <= hi, "cell": cell, "notes": notes,
            "provenance": {k: self.data[k] for k in ("model_version", "config_hash", "master_seed", "paired_seeds_per_cell", "campaign")},
            "caveat": self.data["caveat"],
        }
