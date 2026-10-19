"""Simulate one year of propellant gauging for the demo fleet and write JSON for the ops dashboard.

Tank sizes, loads, burn schedules, reserves and the two injected faults are ASSUMPTIONS for demonstration, not data from any spacecraft.
Usage: python tools/export_fuel_demo.py [out.json]
"""
import json
import math
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from onboard.fuel import Tank, delta_v_remaining, pvt_mass, simulate_history  # noqa: E402

DAYS = 365
# id: (regime, load kg, dry kg, isp s, start kg, burn dv m/s, every N days, reserve dv m/s, faults)
FLEET = {
    "SVC-01": ("LEO", 400, 900, 300, 330, 2.0, 20, 80, {}),
    "SVC-02": ("SSO", 400, 900, 300, 280, 2.0, 20, 80, {}),
    "SVC-03": ("MEO", 1500, 2000, 320, 1180, 2.0, 10, 80, {"transfers": [80, 200, 320]}),
    "CS-101": ("GEO", 900, 1800, 310, 560, 1.0, 7, 12, {}),
    "CS-102": ("GEO", 900, 1800, 310, 640, 1.0, 7, 12, {}),
    "CS-401": ("GEO", 900, 1800, 310, 300, 1.0, 7, 12, {"leak_from": 150, "leak_kg_day": 0.06}),
    "CS-201": ("SSO", 60, 400, 220, 41, 0.25, 12, 20, {}),
    "CS-202": ("SSO", 60, 400, 220, 38, 0.25, 12, 20, {}),
    "CS-203": ("SSO", 60, 400, 220, 44, 0.25, 12, 20, {}),
    "CS-301": ("MEO", 120, 700, 225, 82, 0.3, 30, 15, {}),
    "CS-302": ("MEO", 120, 700, 225, 90, 0.3, 30, 15, {}),
    "CS-501": ("LEO", 40, 350, 220, 12, 0.4, 8, 20, {}),
    "CS-502": ("LEO", 40, 350, 220, 28, 0.4, 8, 20, {"stuck_from": 200}),
}


def run(sat):
    regime, load, dry, isp, start, dv, every, reserve, faults = FLEET[sat]
    seed = zlib.crc32(sat.encode())
    tank = Tank(prop_load_kg=load, dry_mass_kg=dry, isp_s=isp)
    off = seed % every
    burns = {d: dv for d in range(off + 1, DAYS, every)}
    for d in faults.get("transfers", []):
        burns[d] = 60.0
    hist = simulate_history(tank, start, burns, DAYS, seed, leak_from=faults.get("leak_from"),
                            leak_kg_day=faults.get("leak_kg_day", 0.0), stuck_from=faults.get("stuck_from"))
    last = hist[-1]
    flagged = last["flag"] != "ok"
    # while the gauges disagree, plan on the lowest of the three figures (cautious whichever gauge is wrong)
    m_plan = min(last["fused"], last["pvt"], last["booked"]) if flagged else last["fused"]
    dv_now = delta_v_remaining(tank, m_plan)
    dv_hi = delta_v_remaining(tank, last["fused"] + 2 * last["sigma"])
    dv_lo = delta_v_remaining(tank, max(min(last["fused"] - 2 * last["sigma"], m_plan), 0))
    routine = [h["dv"] for h in hist[-90:] if 0 < h["dv"] < 30]          # exclude one-off transfers from the run rate
    rate = sum(routine) * 365.0 / 90.0 if routine else 0.0
    usable = max(dv_now - reserve, 0.0)
    years = usable / rate if rate > 0 else math.inf
    status = "critical" if (flagged or years < 1) else "warning" if years < 3 else "ok"
    msg = []
    if flagged:
        gap = last["pvt"] - last["booked"]
        # Heuristic, not a diagnosis: a leak makes PVT read BELOW book-keeping; a frozen or high-reading pressure sensor makes it read ABOVE.
        msg.append("PVT and book-keeping disagree" + (" - PVT reads above booked use: most likely a pressure-sensor fault; book-keeping is the more reliable figure"
                                                      if gap > 0 else " - PVT reads below booked use: most likely a leak; PVT is the cautious figure") + ". Planning on the lowest estimate")
    if years < 3:
        msg.append(f"{years:.1f} years of operational delta-v above the {reserve:g} m/s disposal reserve: refuel or replacement candidate")
    return {
        "id": sat, "regime": regime, "load_kg": load, "dry_kg": dry, "isp_s": isp, "reserve_dv": reserve,
        "summary": {"fused_kg": last["fused"], "sigma_kg": last["sigma"], "pct_load": 100 * last["fused"] / load, "dv_mps": dv_now, "dv_lo": dv_lo, "dv_hi": dv_hi,
                    "rate_mps_yr": rate, "years_to_reserve": None if math.isinf(years) else years, "status": status, "flag": last["flag"],
                    "booked_kg": last["booked"], "pvt_kg": last["pvt"], "true_kg": last["true"], "messages": msg},
        "series": [[h["day"], round(h["true"], 3), round(h["booked"], 3), round(h["pvt"], 3), round(h["fused"], 3), round(h["sigma"], 3), round(h["dv"], 2),
                    0 if h["flag"] == "ok" else 1] for h in hist],
    }


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "satellite-ops-platform" / "src" / "data" / "fuel.json"
    data = {"days": DAYS, "series_fields": ["day", "true_kg", "booked_kg", "pvt_kg", "fused_kg", "sigma_kg", "burn_dv_mps", "flag"],
            "note": "Simulated year. Tanks, loads, burns, reserves and faults are assumptions. 'True' mass is known only because this is a simulation.",
            "satellites": [run(s) for s in FLEET]}
    out.write_text(json.dumps(data, separators=(",", ":")) + "\n")
    print(f"wrote {out} ({out.stat().st_size/1024:.0f} KB)")
    for s in data["satellites"]:
        m = s["summary"]
        print(f"{s['id']:7} fused {m['fused_kg']:7.1f} +-{m['sigma_kg']:.2f} kg true {m['true_kg']:7.1f} dv {m['dv_mps']:6.1f} rate {m['rate_mps_yr']:5.1f} yrs {m['years_to_reserve']} {m['status']} {m['flag']}")
