"""Simulate 24 h of on-board logging and downlink for the demo fleet and write JSON for the ops dashboard.

All traffic volumes, link rates, loss and outages are ASSUMPTIONS for a demonstration, not telemetry of any real spacecraft.
Usage: python tools/export_downlink_demo.py [out.json]
"""
import json
import random
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from onboard.recorder import ContactWindow, GroundArchive, OnboardRecorder, downlink  # noqa: E402

DAY = 86400.0
# regime -> (passes [(start_min)...], duration_s, rate_bps, loss, one-way delay s)
LINKS = {
    "LEO": ([0, 95, 190, 700, 795, 890], 480, 256_000, 0.02, 0.003),
    "SSO": ([30, 125, 220, 730, 825, 920], 480, 256_000, 0.02, 0.003),
    "MEO": ([0, 480, 960], 5400, 64_000, 0.03, 0.070),
    "GEO": ([15 * i for i in range(96)], 300, 19_200, 0.05, 0.120),
}
# sat id -> (regime, buffer bytes, missed pass ids, audit burst start s or None)
FLEET = {
    "SVC-01": ("LEO", 65536, [], None), "SVC-02": ("SSO", 65536, [], None), "SVC-03": ("MEO", 65536, [], 40000),
    "CS-101": ("GEO", 65536, [], None), "CS-102": ("GEO", 65536, [], None),
    "CS-201": ("SSO", 65536, [], None), "CS-202": ("SSO", 65536, [], None), "CS-203": ("SSO", 65536, [], 52000),
    "CS-301": ("MEO", 65536, [], 40000), "CS-302": ("MEO", 65536, [], None),
    "CS-401": ("GEO", 65536, [30, 31, 32, 33, 34, 35], None),
    "CS-501": ("LEO", 65536, [], None), "CS-502": ("LEO", 6144, [0, 1, 2], None),
}
AUDIT_TEXT = ["Command received and authenticated", "Mode change accepted", "Policy check: action allowed", "Approval token verified",
              "Configuration parameter written", "Safe-mode entry condition evaluated"]
EVENT_TEXT = ["Reaction wheel speed excursion", "Star tracker re-acquisition", "Battery cell balance event", "Thermal loop setpoint change",
              "Transceiver BER above nominal", "Memory scrub corrected 1 error"]


def simulate(sat: str) -> dict:
    regime, buf, missed, burst = FLEET[sat]
    rng = random.Random(zlib.crc32(sat.encode()))
    starts, dur, rate, loss, owd = LINKS[regime]
    rec = OnboardRecorder(sat, buf)
    ground = GroundArchive()
    events = []                                   # (t, kind, sev, text, size)
    t = rng.uniform(0, 900)
    while t < DAY:
        events.append((t, "housekeeping", "info", "HK: bus voltage, temperatures, mode OK", 96)); t += 900
    t = rng.expovariate(1 / 2400)
    while t < DAY:
        crit = rng.random() < 0.06
        events.append((t, "critical" if crit else "event", "high" if crit else rng.choice(["info", "low", "medium"]), rng.choice(EVENT_TEXT), 140)); t += rng.expovariate(1 / 2400)
    t = rng.expovariate(1 / 3600)
    while t < DAY:
        events.append((t, "audit", "info", rng.choice(AUDIT_TEXT), 232)); t += rng.expovariate(1 / 3600)
    if burst is not None:
        for i in range(14):
            events.append((burst + i * 45.0, "audit", "info", rng.choice(AUDIT_TEXT) + " (servicing operation)", 232))
    windows = [ContactWindow(i, m * 60.0, dur, rate, loss, owd, i not in missed) for i, m in enumerate(starts)]
    # interleave record creation and passes in time order
    timeline = sorted([(e[0], 0, e) for e in events] + [(w.start_s, 1, w) for w in windows], key=lambda x: (x[0], x[1]))
    passes = []
    for _, kind, item in timeline:
        if kind == 0:
            rec.append(item[1], item[2], item[3], round(item[0], 3), item[4])
        else:
            passes.append(downlink(rec, item, rng, ground))
    last = rec.records[-1].seq if rec.records else 0
    ver = ground.verify(last)
    dropped = [r.seq for r in rec.records if r.dropped_s is not None]
    return {
        "id": sat, "regime": regime, "buffer_bytes": buf, "rate_bps": rate, "loss": loss,
        "chain": {"ok": ver["ok"], "dropped": dropped,
                  "undelivered_not_dropped": [s for s in ver["missing_seq"] if s not in dropped]},
        "passes": passes,
        "records": [{"seq": r.seq, "kind": r.kind, "sev": r.severity, "text": r.text, "created": r.created_s, "bytes": r.size_b,
                     "sent": r.first_sent_s and round(r.first_sent_s, 2), "received": r.received_s and round(r.received_s, 3),
                     "attempts": r.attempts, "pass": r.pass_id, "status": r.status, "hash": r.hash[:12]} for r in rec.records],
    }


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "satellite-ops-platform" / "src" / "data" / "downlink.json"
    data = {"horizon_s": DAY, "note": "Simulated 24 h. Traffic, link rates, loss and outages are assumptions for demonstration.",
            "satellites": [simulate(s) for s in FLEET]}
    out.write_text(json.dumps(data, separators=(",", ":")) + "\n")
    n = sum(len(s["records"]) for s in data["satellites"])
    print(f"wrote {out} ({n} records, {out.stat().st_size/1024:.0f} KB)")
    for s in data["satellites"]:
        st = {}
        for r in s["records"]:
            st[r["status"]] = st.get(r["status"], 0) + 1
        print(s["id"], s["regime"], st, "chain ok" if s["chain"]["ok"] else "CHAIN BAD")
