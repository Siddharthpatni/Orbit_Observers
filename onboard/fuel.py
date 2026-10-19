"""Propellant gauging for a pressure-fed tank (stdlib only, runs on board).

Two independent estimates are fused:
  * Book-keeping: integrate thruster firings (commanded burn -> propellant used). Smooth, but its error grows with use because
    the true Isp differs from nominal (a constant, unknown bias) and valve timing is imperfect.
  * PVT gauging: measure tank pressure and temperature. The pressurant (helium) amount is fixed, so ullage volume = n R T / P and
    propellant mass = rho(T) * (V_tank - V_ullage). Error is set by the ullage volume, so it is best when the tank is full and
    degrades as it empties.
A 2-state Kalman filter [propellant mass, Isp-bias] uses book-keeping to predict and PVT to correct, so the bias is learned. A
persistent innovation (PVT disagreeing with the prediction) raises a flag: possible leak, or a stuck/failed pressure sensor.

All parameters below are assumptions for a study, not data from a spacecraft. Ideal-gas helium, no propellant vapour or helium
solubility, one lumped tank.
"""
from dataclasses import dataclass
from typing import Dict, List, Optional
import math
import random

R_GAS = 8.314462618
G0 = 9.80665


@dataclass(frozen=True)
class Tank:
    prop_load_kg: float          # propellant at beginning of life
    dry_mass_kg: float           # spacecraft mass without propellant
    isp_s: float                 # nominal specific impulse
    rho0_kg_m3: float = 1004.0   # hydrazine-like density at 293 K
    fill_fraction: float = 0.90  # tank volume used at beginning of life
    p_bol_pa: float = 1.8e6      # pressure at 293 K when full
    t_ref_k: float = 293.0

    @property
    def volume_m3(self) -> float:
        return self.prop_load_kg / self.rho0_kg_m3 / self.fill_fraction

    def rho(self, t_k: float) -> float:
        return self.rho0_kg_m3 * (1.0 - 8.5e-4 * (t_k - self.t_ref_k))

    @property
    def helium_mol(self) -> float:
        v_u0 = self.volume_m3 - self.prop_load_kg / self.rho0_kg_m3
        return self.p_bol_pa * v_u0 / (R_GAS * self.t_ref_k)


# 1-sigma sensor / knowledge assumptions (relative unless stated)
SIG_P, SIG_T_K = 0.0025, 0.5                 # random, per reading
SIG_N, SIG_V, SIG_PBIAS = 0.003, 0.001, 0.001  # systematic: helium loading, tank volume, pressure transducer offset
SIG_ISP_BIAS, SIG_BURN, SIG_FILL = 0.015, 0.005, 0.005


def pvt_mass(tank: Tank, p_pa: float, t_k: float, n_mol: Optional[float] = None) -> Dict[str, float]:
    """Propellant mass from one pressure/temperature reading, with random and systematic 1-sigma separated.

    Systematic terms (helium loading, tank volume, transducer offset) do not average out over days, so the filter treats
    them as a slowly varying bias instead of independent noise.
    """
    n = tank.helium_mol if n_mol is None else n_mol
    v_u = n * R_GAS * t_k / p_pa
    rho = tank.rho(t_k)
    m = rho * (tank.volume_m3 - v_u)
    rand = rho * v_u * math.sqrt(SIG_P ** 2 + (SIG_T_K / t_k) ** 2)
    sysm = rho * math.sqrt((v_u * math.sqrt(SIG_N ** 2 + SIG_PBIAS ** 2)) ** 2 + (tank.volume_m3 * SIG_V) ** 2)
    return {"mass_kg": m, "sigma_random_kg": rand, "sigma_sys_kg": sysm, "sigma_kg": math.hypot(rand, sysm), "ullage_m3": v_u}


def delta_v_remaining(tank: Tank, prop_kg: float) -> float:
    return tank.isp_s * G0 * math.log((tank.dry_mass_kg + prop_kg) / tank.dry_mass_kg) if prop_kg > 0 else 0.0


def burn_mass(tank: Tank, prop_kg: float, dv_mps: float, isp_s: Optional[float] = None) -> float:
    """Propellant used by a burn of dv_mps starting with prop_kg on board (rocket equation)."""
    isp = tank.isp_s if isp_s is None else isp_s
    return (tank.dry_mass_kg + prop_kg) * (1.0 - math.exp(-dv_mps / (isp * G0)))


def _mm(A, B):
    return [[sum(A[i][k] * B[k][j] for k in range(len(B))) for j in range(len(B[0]))] for i in range(len(A))]


def _t(A):
    return [list(r) for r in zip(*A)]


class FuelGauge:
    """3-state filter x = [mass_kg, isp_bias, pvt_bias_kg].

    Use per burn: mass -= booked * (1 + isp_bias). PVT reading: z = mass + pvt_bias + noise. The Isp bias is a constant, the PVT bias
    a slowly varying offset. A leak or a failed pressure sensor is *not* absorbed: single readings beyond the gate are rejected and a
    run of same-sign innovations raises ``flag = 'disagree'``.
    """

    def __init__(self, tank: Tank, initial_mass_kg: float, sys_sigma_kg: float):
        self.tank = tank
        self.x = [initial_mass_kg, 0.0, 0.0]
        sm = SIG_FILL * initial_mass_kg
        self.P = [[sm * sm, 0.0, 0.0], [0.0, SIG_ISP_BIAS ** 2, 0.0], [0.0, 0.0, sys_sigma_kg ** 2]]
        self.sys0 = sys_sigma_kg
        self.booked_only = initial_mass_kg
        self.recent: List[float] = []
        self.flag = "ok"

    def predict(self, booked_use_kg: float) -> None:
        self.booked_only -= booked_use_kg
        self.x[0] -= booked_use_kg * (1.0 + self.x[1])
        F = [[1.0, -booked_use_kg, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
        Q = [[(SIG_BURN * booked_use_kg) ** 2, 0, 0], [0, 0, 0], [0, 0, 0]]
        P = _mm(_mm(F, self.P), _t(F))
        self.P = [[P[i][j] + Q[i][j] for j in range(3)] for i in range(3)]

    def update(self, z_kg: float, r_var: float, gate_sigma: float = 3.0, window: int = 7, mean_z_flag: float = 2.0) -> Dict[str, float]:
        self.P[2][2] += (0.02 * self.sys0) ** 2                    # PVT bias may drift as ullage changes
        H = [1.0, 0.0, 1.0]
        PH = [sum(self.P[i][j] * H[j] for j in range(3)) for i in range(3)]
        S = sum(H[i] * PH[i] for i in range(3)) + r_var
        y = z_kg - (self.x[0] + self.x[2])
        z = y / math.sqrt(S)
        self.recent = (self.recent + [z])[-window:]
        if len(self.recent) == window and abs(sum(self.recent) / window) > mean_z_flag:
            self.flag = "disagree"
        elif len(self.recent) == window and abs(sum(self.recent) / window) < 0.5 * mean_z_flag:
            self.flag = "ok"
        if abs(z) <= gate_sigma and self.flag == "ok":              # while flagged, stop learning from PVT
            K = [PH[i] / S for i in range(3)]
            self.x = [self.x[i] + K[i] * y for i in range(3)]
            self.P = [[self.P[i][j] - K[i] * PH[j] for j in range(3)] for i in range(3)]
        return {"innovation_kg": y, "z": z}

    @property
    def mass_kg(self) -> float:
        return self.x[0]

    @property
    def sigma_kg(self) -> float:
        return math.sqrt(max(self.P[0][0], 0.0))


def simulate_history(tank: Tank, start_mass_kg: float, burns: Dict[int, float], days: int, seed: int,
                     leak_from: Optional[int] = None, leak_kg_day: float = 0.0, stuck_from: Optional[int] = None) -> List[Dict[str, float]]:
    """Daily truth, book-keeping only, PVT only and fused estimates. burns maps day -> delta-v (m/s)."""
    rng = random.Random(seed)
    isp_bias = rng.gauss(0.0, SIG_ISP_BIAS)               # true Isp = nominal / (1 + bias): unknown to the gauge
    n_true = tank.helium_mol * (1 + rng.gauss(0.0, SIG_N))  # gauge assumes nominal n: loading error is a real bias
    p_bias = rng.gauss(0.0, 0.001)
    m_true = start_mass_kg
    gauge = FuelGauge(tank, start_mass_kg * (1 + rng.gauss(0.0, SIG_FILL)),
                      pvt_mass(tank, tank.p_bol_pa, tank.t_ref_k)["sigma_sys_kg"])
    out, frozen_p = [], None
    for d in range(days):
        t_k = 290.0 + 8.0 * math.sin(2 * math.pi * d / 365.0) + rng.gauss(0.0, 1.5)
        dv = burns.get(d, 0.0)
        if dv > 0:
            booked = burn_mass(tank, m_true, dv)                     # what the flight software books at nominal Isp
            m_true -= booked * (1.0 + isp_bias) * (1.0 + rng.gauss(0.0, SIG_BURN))
            gauge.predict(booked)
        if leak_from is not None and d >= leak_from:
            m_true -= leak_kg_day
        m_true = max(m_true, 0.0)
        v_u = tank.volume_m3 - m_true / tank.rho(t_k)
        p_true = n_true * R_GAS * t_k / v_u
        p_meas = p_true * (1 + p_bias + rng.gauss(0.0, SIG_P))
        if stuck_from is not None and d >= stuck_from:
            frozen_p = p_meas if frozen_p is None else frozen_p
            p_meas = frozen_p
        t_meas = t_k + rng.gauss(0.0, SIG_T_K)
        pvt = pvt_mass(tank, p_meas, t_meas)
        upd = gauge.update(pvt["mass_kg"], pvt["sigma_random_kg"] ** 2)
        out.append({"day": d, "true": m_true, "booked": gauge.booked_only, "pvt": pvt["mass_kg"], "pvt_sigma": pvt["sigma_kg"],
                    "fused": gauge.mass_kg, "sigma": gauge.sigma_kg, "bias": gauge.x[1], "pvt_bias": gauge.x[2], "z": upd["z"], "flag": gauge.flag, "dv": dv})
    return out
