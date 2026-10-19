import math
import unittest

from onboard.fuel import G0, R_GAS, Tank, burn_mass, delta_v_remaining, pvt_mass, simulate_history

TANK = Tank(prop_load_kg=900, dry_mass_kg=1800, isp_s=310)
BURNS = {d: 1.0 for d in range(7, 365, 7)}


class FuelTests(unittest.TestCase):
    def test_pvt_inverts_exactly_without_noise(self):
        m_true, t = 500.0, 293.0
        v_u = TANK.volume_m3 - m_true / TANK.rho(t)
        p = TANK.helium_mol * R_GAS * t / v_u
        self.assertAlmostEqual(pvt_mass(TANK, p, t)["mass_kg"], m_true, places=6)

    def test_pvt_error_grows_as_tank_empties(self):
        def sigma(m):
            v_u = TANK.volume_m3 - m / TANK.rho(293.0)
            return pvt_mass(TANK, TANK.helium_mol * R_GAS * 293.0 / v_u, 293.0)["sigma_kg"]
        self.assertGreater(sigma(100.0), sigma(800.0))

    def test_rocket_equation_consistency(self):
        used = burn_mass(TANK, 500.0, 10.0)
        self.assertAlmostEqual(delta_v_remaining(TANK, 500.0) - delta_v_remaining(TANK, 500.0 - used), 10.0, places=6)
        self.assertEqual(delta_v_remaining(TANK, 0.0), 0.0)

    def test_fused_beats_bookkeeping_and_uncertainty_is_calibrated(self):
        fe, be, cover, n = [], [], 0, 0
        for seed in range(40):
            h = simulate_history(TANK, 800, BURNS, 365, seed)
            fe += [r["fused"] - r["true"] for r in h[60::15]]
            be += [r["booked"] - r["true"] for r in h[60::15]]
            for r in h[60::15]:
                n += 1
                cover += abs(r["fused"] - r["true"]) <= 2 * r["sigma"]
        rms = lambda a: math.sqrt(sum(x * x for x in a) / len(a))
        self.assertLess(rms(fe), rms(be))
        self.assertGreater(cover / n, 0.90)

    def test_leak_is_flagged_not_absorbed(self):
        h = simulate_history(TANK, 800, BURNS, 365, 3, leak_from=150, leak_kg_day=0.05)
        self.assertEqual(h[140]["flag"], "ok")
        self.assertEqual(h[-1]["flag"], "disagree")
        self.assertGreater(h[-1]["fused"] - h[-1]["true"], 2.0)       # estimate is stale while flagged: the UI says so

    def test_stuck_pressure_sensor_is_flagged_quickly(self):
        h = simulate_history(TANK, 800, BURNS, 365, 4, stuck_from=200)
        first = next(r["day"] for r in h if r["flag"] != "ok" and r["day"] >= 200)
        self.assertLess(first - 200, 40)

    def test_false_alarm_rate_is_low_without_faults(self):
        bad = sum(any(r["flag"] != "ok" for r in simulate_history(TANK, 800, BURNS, 365, s)) for s in range(40))
        self.assertLessEqual(bad, 8)

    def test_deterministic(self):
        self.assertEqual(simulate_history(TANK, 800, BURNS, 100, 5), simulate_history(TANK, 800, BURNS, 100, 5))


if __name__ == "__main__":
    unittest.main()
