"""Service Beacon bench plan, survival sizing and virtual-bench Monte Carlo (Guide §15; deck slide 5).

No hardware exists yet. This module (1) sizes the independent reserve with the Guide's formula, (2) compares
periodic-pulse and wake-on-command operation, (3) estimates antenna coverage under tumble, (4) defines the bench
tests with expected values and pass limits derived from the model, and (5) runs a *virtual bench*: component
tolerances (ASSUMED) are sampled to give the probability that a unit built to the design passes each test.
``evaluate_bench`` checks real measurements against the same limits once a bench exists.
"""
from dataclasses import dataclass, field
from typing import Dict, List
import math
import numpy as np

from .ios import evaluate_beacon_engineering_budget


# ---- 1. Survival sizing (Guide §15) ---------------------------------------------------------------
def average_power_w(p_sleep_w: float, duty_tx: float, p_tx_w: float, duty_sensor: float, p_sensor_w: float) -> float:
    for n, v in (("duty_tx", duty_tx), ("duty_sensor", duty_sensor)):
        if not 0 <= v <= 1:
            raise ValueError(f"{n} must be in [0, 1]")
    return p_sleep_w + duty_tx * p_tx_w + duty_sensor * p_sensor_w


def required_nameplate_wh(p_avg_w: float, survival_days: float, derating: float, margin: float = 1.2) -> float:
    """E_usable >= P_avg x T_survival; nameplate = E_usable / derating x design margin."""
    return p_avg_w * 24.0 * survival_days / derating * margin


def survival_sweep(days=(7, 14, 30, 60, 90), rates_hz=(0.1, 0.5, 1.0)) -> List[Dict[str, float]]:
    rows = []
    for d in days:
        for r in rates_hz:
            b = evaluate_beacon_engineering_budget(rate_hz=r, duration_days=d)
            rows.append({"survival_days": d, "rate_hz": r, "avg_power_mw": b["net_avg_power_mw"],
                         "ideal_wh": b["net_energy_wh"], "nameplate_wh": b["recommended_nameplate_wh"],
                         "packaged_mass_g": b["packaged_unit_mass_g"]})
    return rows


# ---- 2. Wake mode trade (ASSUMED radio figures) -----------------------------------------------------
def wake_mode_trade(survival_days=30.0, rx_listen_mw=18.0, rx_duty=0.02, tx_mw=1100.0, tx_s=0.015,
                    sleep_mw=12.0, beacon_period_s=1.0, wake_poll_s=5.0) -> Dict[str, Dict[str, float]]:
    periodic = sleep_mw + tx_mw * tx_s / beacon_period_s
    # wake-on-command: sleeps + low duty receiver; transmits only while interrogated (assume 10 min per day)
    interrogated = 600.0 / 86400.0
    wake = sleep_mw + rx_listen_mw * rx_duty + interrogated * tx_mw * tx_s / beacon_period_s
    h = survival_days * 24.0
    return {"periodic": {"avg_mw": periodic, "energy_wh": periodic * 1e-3 * h, "first_data_latency_s": beacon_period_s,
                         "note": "broadcasts without being asked; also helps a servicer find the client"},
            "wake_on_command": {"avg_mw": wake, "energy_wh": wake * 1e-3 * h, "first_data_latency_s": wake_poll_s + beacon_period_s,
                                "note": "needs the servicer to know when/where to interrogate; adds spoofing/authentication surface"}}


# ---- 3. Antenna coverage under tumble ---------------------------------------------------------------
def coverage_probability(half_angle_deg: float, n_patches: int = 2) -> float:
    """P(servicer lies inside at least one patch cone) for a random orientation: each cone covers (1-cos a)/2 of the sphere."""
    a = math.radians(half_angle_deg)
    one = (1.0 - math.cos(a)) / 2.0
    return min(1.0, n_patches * one)


def packets_for_confidence(p_cover: float, p_loss: float, confidence=0.95) -> int:
    """Packets needed so that P(at least one is received) >= confidence, treating packets as independent."""
    p = p_cover * (1.0 - p_loss)
    if p <= 0:
        return 10**9
    return math.ceil(math.log(1.0 - confidence) / math.log(1.0 - p)) if p < 1 else 1


# ---- 4. Bench test definitions ---------------------------------------------------------------------
@dataclass(frozen=True)
class BenchTest:
    id: str
    name: str
    measure: str
    unit: str
    expected: float
    limit: float
    direction: str       # "max": measured <= limit passes; "min": measured >= limit passes
    procedure: str


def bench_tests() -> List[BenchTest]:
    b = evaluate_beacon_engineering_budget()
    return [
        BenchTest("B1", "Sleep + duty-cycled average power", "average input power over 1 h at 1 Hz, nominal temp", "mW",
                  b["net_avg_power_mw"], 1.25 * b["net_avg_power_mw"], "max",
                  "Power from a 3.6 V source through a precision shunt; log 1 h; TX 15 ms at 1 Hz"),
        BenchTest("B2", "Main-bus short isolation leakage", "reserve-cell drain with main bus shorted to 0 ohm", "uA", 2.0, 10.0, "max",
                  "Short the main-bus input; measure reserve draw; repeat with over-voltage step to 1.25x nominal"),
        BenchTest("B3", "Transmit power at antenna port", "RF power at 401.5 MHz", "dBm", 27.0, 25.0, "min",
                  "Spectrum analyser through calibrated attenuator"),
        BenchTest("B4", "Link margin at 1 km equivalent", "Eb/N0 margin with attenuator emulating free-space loss + tumble gain -3 dBi", "dB",
                  b["link_margin_db"], 10.0, "min", "Attenuator set to FSPL(1 km)=%.1f dB; PRBS; measure BER <= 1e-5" % b["fspl_db"]),
        BenchTest("B5", "Cold usable capacity", "capacity delivered to cutoff at -20 C vs nameplate", "Wh",
                  0.85 * b["recommended_nameplate_wh"], 0.85 * b["required_nameplate_wh"], "min",
                  "Thermal chamber -20 C; constant-power discharge at the average load"),
        BenchTest("B6", "Packet timestamp / latency", "timestamp to RX latency jitter", "ms", 50.0, 250.0, "max",
                  "Loop-back with GPS-disciplined clock; 10,000 packets"),
        BenchTest("B7", "Replay / spoof rejection", "fraction of replayed or bad-token commands rejected", "%", 100.0, 100.0, "min",
                  "Inject 1,000 replayed and 1,000 bad-token commands; zero may be accepted"),
    ]


def evaluate_bench(measured: Dict[str, float]) -> Dict[str, Dict[str, object]]:
    out = {}
    for t in bench_tests():
        if t.id not in measured:
            out[t.id] = {"name": t.name, "status": "NOT_RUN"}
            continue
        m = measured[t.id]
        ok = m <= t.limit if t.direction == "max" else m >= t.limit
        out[t.id] = {"name": t.name, "status": "PASS" if ok else "FAIL", "measured": m, "limit": t.limit, "unit": t.unit}
    return out


# ---- 5. Virtual bench (ASSUMED tolerances) ----------------------------------------------------------
def virtual_bench(n: int = 20000, seed: int = 0) -> Dict[str, Dict[str, float]]:
    """Sample build-to-build variation and report P(pass) per test. Sigmas are assumptions, not vendor data."""
    rng = np.random.default_rng(seed)
    b = evaluate_beacon_engineering_budget()
    tests = {t.id: t for t in bench_tests()}
    sleep = 12.0 * rng.lognormal(0.0, 0.25, n)                       # mW, +-25 % (1 sigma)
    tx = 1100.0 * rng.lognormal(0.0, 0.12, n)                        # mW during TX
    avg = sleep + 0.015 * tx
    leak = 2.0 * rng.lognormal(0.0, 0.5, n)                          # uA
    rf_dbm = 27.0 + rng.normal(0.0, 0.8, n)
    margin = b["link_margin_db"] + rng.normal(0.0, 2.5, n) + (rf_dbm - 27.0)
    cold_factor = np.clip(rng.normal(0.85, 0.04, n), 0.5, 1.0)
    cap = b["recommended_nameplate_wh"] * cold_factor * rng.normal(1.0, 0.03, n)
    jitter = np.abs(rng.normal(50.0, 40.0, n))
    meas = {"B1": avg, "B2": leak, "B3": rf_dbm, "B4": margin, "B5": cap, "B6": jitter}
    out = {}
    for k, x in meas.items():
        t = tests[k]
        ok = x <= t.limit if t.direction == "max" else x >= t.limit
        out[k] = {"name": t.name, "p_pass": float(ok.mean()), "p5": float(np.percentile(x, 5)), "p95": float(np.percentile(x, 95))}
    return out
