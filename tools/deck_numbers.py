"""Numbers for the customer/money deck, computed from the economics model (so slides cannot drift). Writes docs/presentation/numbers.json.

Every monetary input is an ASSUMPTION (see rpo_project/economics.py); outcomes (pass, abort, delta-v) come from the stored campaign.
"""
import json
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from rpo_project import economics as eco  # noqa: E402

S = eco.load_main_summary(ROOT / "results" / "v4_1_validation" / "summary_main.csv")
A = eco.EconAssumptions()
M = 1e6
out = {"assumptions": {"revenue_m": A.client_annual_revenue_eur / M, "margin": A.contribution_margin, "years": A.extension_years, "service_year": A.service_year,
                       "discount": A.discount_rate, "price_m": A.servicing_price_eur / M, "p_need": A.p_needs_rescue, "attempts": A.max_attempts}}
gross = A.client_annual_revenue_eur * A.contribution_margin * A.extension_years
out["rescue"] = {"gross_value_m": gross / M, "price_m": A.servicing_price_eur / M, "net_m": (gross - A.servicing_price_eur) / M, "net_discounted_m": eco.net_value_of_success(A) / M}

tiers = eco.TIERS
def tier_row(t, tum, a=A):
    e = eco.expected_value(t, S[(t, tum)], a); th = eco.servicer_throughput(t, S[(t, tum)], a)
    return {"p_success": e["p_success"], "p_lost": e["p_incomplete_or_unsafe"], "benefit_m": e["benefit_eur"] / M, "cost_m": e["addon_cost_eur"] / M, "net_m": e["net_eur"] / M,
            "visits": th["visits"], "successes": th["expected_successful_services"], "breakeven_price_m": None if th["breakeven_price_per_success_eur"] == float("inf") else th["breakeven_price_per_success_eur"] / M}
out["at3"] = {t: tier_row(t, 3.0) for t in tiers}
out["at5"] = {t: tier_row(t, 5.0) for t in tiers}
base = out["at3"]["C0_unprepared"]
inc = {}
for t in tiers[1:]:
    d_b = out["at3"][t]["benefit_m"] - base["benefit_m"]; d_c = out["at3"][t]["cost_m"] - base["cost_m"]
    inc[t] = {"extra_benefit_m": d_b, "extra_cost_m": d_c, "roi_x": d_b / d_c if d_c else None, "net_m": d_b - d_c}
out["incremental_vs_c0_at3"] = inc
b5 = out["at5"]["C0_unprepared"]; c3 = out["at5"]["C3_ios_mode"]
out["ios_at5_vs_c0"] = {"extra_benefit_m": c3["benefit_m"] - b5["benefit_m"], "extra_cost_m": c3["cost_m"] - b5["cost_m"], "net_m": (c3["benefit_m"] - b5["benefit_m"]) - (c3["cost_m"] - b5["cost_m"])}
ps = [0.01, 0.02, 0.05, 0.10, 0.20]
out["sens_p"] = {"p": ps, "c1_vs_c0_net_m": [], "c3_vs_c0_at5_net_m": []}
for p in ps:
    a = replace(A, p_needs_rescue=p)
    c1 = eco.expected_value("C1_fiducials", S[("C1_fiducials", 3.0)], a); c0 = eco.expected_value("C0_unprepared", S[("C0_unprepared", 3.0)], a)
    out["sens_p"]["c1_vs_c0_net_m"].append((c1["net_eur"] - c0["net_eur"]) / M)
    c3_ = eco.expected_value("C3_ios_mode", S[("C3_ios_mode", 5.0)], a); c05 = eco.expected_value("C0_unprepared", S[("C0_unprepared", 5.0)], a)
    out["sens_p"]["c3_vs_c0_at5_net_m"].append((c3_["net_eur"] - c05["net_eur"]) / M)
life = (A.servicer_capex_eur + A.servicer_ops_eur_per_year * A.servicer_life_years) / M
out["servicer"] = {"lifecycle_cost_m": life, "price_m": A.servicing_price_eur / M,
                   "profit_m": {t: out["at3"][t]["successes"] * A.servicing_price_eur / M - life for t in tiers}}
out["product_tiers"] = {n: {k: v / M if k.endswith("eur") else v for k, v in eco.product_tier_cost(n, A).items()} for n in eco.PRODUCT_TIERS}
out["fleet10"] = {"c1_extra_cost_m": 10 * inc["C1_fiducials"]["extra_cost_m"], "c1_extra_benefit_m": 10 * inc["C1_fiducials"]["extra_benefit_m"]}
(ROOT / "docs" / "presentation" / "numbers.json").write_text(json.dumps(out, indent=1))
print(json.dumps({k: out[k] for k in ("rescue", "incremental_vs_c0_at3", "ios_at5_vs_c0", "sens_p", "servicer", "fleet10")}, indent=1))
