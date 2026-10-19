"""Preparation-tier economics and servicer throughput (Guide §16, Phase 2 deck: product tiers 1-4).

EVERY monetary, mass, price and probability input below is an ASSUMPTION chosen to be plausible for a
GEO study; none comes from ClearSpace, a vendor quote or a customer. What IS model-derived: the per-attempt
outcome probabilities, delta-v and propellant, read from a stored Monte Carlo campaign (``summary_main.csv``),
and the beacon mass/energy from ``ios.evaluate_beacon_engineering_budget``. Change ``EconAssumptions`` and
re-run to test sensitivity. Outputs are expected values with stated inputs, not forecasts.
"""
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Dict, List
import csv
import math

from .config import G0_MPS2, SimConfig
from .ios import evaluate_beacon_engineering_budget

TIERS = ["C0_unprepared", "C1_fiducials", "C2_beacon", "C3_ios_mode"]


@dataclass(frozen=True)
class EconAssumptions:
    # --- GEO client value (ASSUMED) ---
    client_annual_revenue_eur: float = 40e6
    contribution_margin: float = 0.60        # share of revenue that is retained profit
    extension_years: float = 5.0
    service_year: float = 10.0               # year of life at which the rescue is needed
    discount_rate: float = 0.08
    servicing_price_eur: float = 75e6        # price paid to the servicer per life-extension visit
    p_needs_rescue: float = 0.10             # P(client degrades enough to need rescue during life)
    max_attempts: int = 3                    # approach attempts the servicer will make
    p_collision_given_incomplete_retreat: float = 0.02
    servicer_loss_eur: float = 150e6         # cost borne if an incomplete retreat ends in collision
    # --- Client-side add-ons: recurring unit cost, mass, NRE (ASSUMED except beacon mass = model) ---
    launch_cost_eur_per_kg: float = 30_000.0
    units_for_nre_amortisation: int = 20
    fiducials_unit_eur: float = 20_000.0
    fiducials_mass_kg: float = 0.5
    fiducials_nre_eur: float = 0.2e6
    beacon_unit_eur: float = 250_000.0       # space-qualified RF + MCU + primary cells
    beacon_nre_eur: float = 2.0e6
    ios_unit_eur: float = 400_000.0          # interface, software, wiring harness
    ios_mass_kg: float = 1.5
    ios_nre_eur: float = 6.0e6
    # --- Product tiers beyond RPO (deck slide 9): extra recurring cost and mass (ASSUMED) ---
    capture_fixture_unit_eur: float = 150_000.0   # MICE-like grapple/capture provision
    capture_fixture_mass_kg: float = 3.0
    capture_fixture_nre_eur: float = 1.5e6
    refuel_port_unit_eur: float = 600_000.0
    refuel_port_mass_kg: float = 4.0
    osan_unit_eur: float = 3.0e6
    osan_mass_kg: float = 25.0
    osan_nre_eur: float = 15.0e6
    # --- Servicer vehicle (ASSUMED) ---
    servicer_wet_kg: float = 3500.0
    servicer_prop_usable_kg: float = 1500.0
    servicer_isp_s: float = 320.0
    transfer_dv_mps: float = 60.0            # GEO phasing between clients
    servicer_capex_eur: float = 250e6
    servicer_ops_eur_per_year: float = 15e6
    servicer_life_years: float = 12.0
    visit_duration_days: float = 45.0


def load_main_summary(path: Path) -> Dict[tuple, Dict[str, float]]:
    out = {}
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            out[(row["scenario"], float(row["tumble_deg_s"]))] = {k: (float(v) if v not in ("", None) else 0.0)
                                                                   for k, v in row.items() if k != "scenario"}
    return out


def dv_from_propellant(prop_kg: float, cfg: SimConfig = SimConfig()) -> float:
    """Invert the campaign's rocket equation (500 kg servicer) to recover delta-v."""
    if prop_kg <= 0:
        return 0.0
    return -math.log(1.0 - prop_kg / cfg.servicer_mass_kg) * cfg.servicer_isp_s * G0_MPS2


def propellant_for_dv(dv: float, wet_kg: float, isp_s: float) -> float:
    return wet_kg * (1.0 - math.exp(-dv / (isp_s * G0_MPS2)))


def attempt_outcomes(cell: Dict[str, float]) -> Dict[str, float]:
    n = cell["n_runs"]
    p = cell["n_pass"] / n
    q_c = cell["n_retreat_complete"] / n
    q_i = (cell["n_abort"] - cell["n_retreat_complete"]) / n
    u = cell["n_unsafe"] / n
    return {"pass": p, "abort_complete": q_c, "abort_incomplete": max(q_i, 0.0), "unsafe": u}


def servicing_outcome(cell: Dict[str, float], a: EconAssumptions) -> Dict[str, float]:
    """Markov over up to ``max_attempts``: retry only after a COMPLETE retreat; incomplete retreat/unsafe ends the mission."""
    o = attempt_outcomes(cell)
    p_success = p_incomplete = 0.0
    expected_attempts = 0.0
    alive = 1.0
    for _ in range(a.max_attempts):
        expected_attempts += alive
        p_success += alive * o["pass"]
        p_incomplete += alive * (o["abort_incomplete"] + o["unsafe"])
        alive *= o["abort_complete"]
    pass_dv = cell["mean_delta_v_mps"] if cell["n_pass"] else 0.0
    abort_dv = dv_from_propellant(cell.get("mean_abort_propellant_kg", 0.0))
    exp_dv = expected_attempts and (p_success * pass_dv + (expected_attempts - p_success) * abort_dv)
    return {"p_success": p_success, "p_incomplete_or_unsafe": p_incomplete, "expected_attempts": expected_attempts,
            "expected_rpo_dv_mps": exp_dv}


def addon_cost(tier: str, a: EconAssumptions) -> Dict[str, float]:
    """Cumulative client-side cost of each preparation tier: recurring + launch + amortised NRE."""
    beacon_mass = evaluate_beacon_engineering_budget()["packaged_unit_mass_g"] / 1000.0   # model-derived
    parts = {"fiducials": (a.fiducials_unit_eur, a.fiducials_mass_kg, a.fiducials_nre_eur),
             "beacon": (a.beacon_unit_eur, beacon_mass, a.beacon_nre_eur),
             "ios": (a.ios_unit_eur, a.ios_mass_kg, a.ios_nre_eur)}
    use = {"C0_unprepared": [], "C1_fiducials": ["fiducials"], "C2_beacon": ["fiducials", "beacon"],
           "C3_ios_mode": ["fiducials", "beacon", "ios"]}[tier]
    unit = sum(parts[k][0] for k in use)
    mass = sum(parts[k][1] for k in use)
    nre = sum(parts[k][2] for k in use) / a.units_for_nre_amortisation
    return {"unit_eur": unit, "mass_kg": mass, "launch_eur": mass * a.launch_cost_eur_per_kg, "nre_share_eur": nre,
            "total_eur": unit + mass * a.launch_cost_eur_per_kg + nre}


def net_value_of_success(a: EconAssumptions) -> float:
    gross = a.client_annual_revenue_eur * a.contribution_margin * a.extension_years
    return (gross - a.servicing_price_eur) / (1.0 + a.discount_rate) ** a.service_year


def expected_value(tier: str, cell: Dict[str, float], a: EconAssumptions) -> Dict[str, float]:
    o = servicing_outcome(cell, a)
    v = net_value_of_success(a)
    risk_cost = (o["p_incomplete_or_unsafe"] * a.p_collision_given_incomplete_retreat * a.servicer_loss_eur
                 / (1.0 + a.discount_rate) ** a.service_year)
    benefit = a.p_needs_rescue * (o["p_success"] * v - risk_cost)
    cost = addon_cost(tier, a)["total_eur"]
    return {**o, "benefit_eur": benefit, "addon_cost_eur": cost, "net_eur": benefit - cost, "value_if_success_eur": v}


def breakeven_p_needs_rescue(tier: str, base_tier: str, summary, tumble: float, a: EconAssumptions) -> float:
    """P(needs rescue) at which the tier's extra cost equals its extra expected benefit versus ``base_tier``."""
    a1 = replace(a, p_needs_rescue=1.0)
    gain = (expected_value(tier, summary[(tier, tumble)], a1)["benefit_eur"]
            - expected_value(base_tier, summary[(base_tier, tumble)], a1)["benefit_eur"])
    extra = addon_cost(tier, a)["total_eur"] - addon_cost(base_tier, a)["total_eur"]
    return math.inf if gain <= 0 else extra / gain


def servicer_throughput(tier: str, cell: Dict[str, float], a: EconAssumptions) -> Dict[str, float]:
    o = servicing_outcome(cell, a)
    transfer = propellant_for_dv(a.transfer_dv_mps, a.servicer_wet_kg, a.servicer_isp_s)
    rpo = propellant_for_dv(o["expected_rpo_dv_mps"], a.servicer_wet_kg, a.servicer_isp_s)
    per_visit = transfer + rpo
    by_fuel = int(a.servicer_prop_usable_kg // per_visit)
    by_time = int(a.servicer_life_years * 365.0 // a.visit_duration_days)
    n = min(by_fuel, by_time)
    lifecycle_cost = a.servicer_capex_eur + a.servicer_ops_eur_per_year * a.servicer_life_years
    served = n * o["p_success"]
    return {"prop_per_visit_kg": per_visit, "visits_by_fuel": by_fuel, "visits_by_time": by_time, "visits": n,
            "expected_successful_services": served, "breakeven_price_per_success_eur": lifecycle_cost / served if served else math.inf,
            "limit": "fuel" if by_fuel < by_time else "time"}


PRODUCT_TIERS = {1: "EOL-ready", 2: "Service-ready", 3: "Life-extension-ready", 4: "Augmentation-ready"}


def product_tier_cost(tier: int, a: EconAssumptions) -> Dict[str, float]:
    """Cumulative cost of the deck's four product tiers (slide 9). T1 capture+fiducials; T2 +IOS+beacon; T3 +refuel port; T4 +OSAN."""
    beacon_mass = evaluate_beacon_engineering_budget()["packaged_unit_mass_g"] / 1000.0
    items = [(a.capture_fixture_unit_eur, a.capture_fixture_mass_kg, a.capture_fixture_nre_eur),
             (a.fiducials_unit_eur, a.fiducials_mass_kg, a.fiducials_nre_eur)]
    if tier >= 2:
        items += [(a.ios_unit_eur, a.ios_mass_kg, a.ios_nre_eur), (a.beacon_unit_eur, beacon_mass, a.beacon_nre_eur)]
    if tier >= 3:
        items += [(a.refuel_port_unit_eur, a.refuel_port_mass_kg, 0.0)]
    if tier >= 4:
        items += [(a.osan_unit_eur, a.osan_mass_kg, a.osan_nre_eur)]
    unit = sum(i[0] for i in items)
    mass = sum(i[1] for i in items)
    nre = sum(i[2] for i in items) / a.units_for_nre_amortisation
    return {"unit_eur": unit, "mass_kg": mass, "launch_eur": mass * a.launch_cost_eur_per_kg, "nre_share_eur": nre,
            "total_eur": unit + mass * a.launch_cost_eur_per_kg + nre}
