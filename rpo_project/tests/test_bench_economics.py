import math
import unittest
from dataclasses import replace
from pathlib import Path

from .. import bench, economics as eco

SUMMARY = Path(__file__).resolve().parents[2] / "results" / "v4_1_validation" / "summary_main.csv"


class BenchTests(unittest.TestCase):
    def test_guide_example_is_reproduced(self):
        p = bench.average_power_w(0.01, 0.01, 2.0, 0.10, 0.03)
        self.assertAlmostEqual(p, 0.033)
        self.assertAlmostEqual(bench.required_nameplate_wh(p, 30, 1.0, 1.0), 23.76)

    def test_duty_validation(self):
        with self.assertRaises(ValueError):
            bench.average_power_w(0.01, 1.5, 2.0, 0.1, 0.03)

    def test_wake_on_command_uses_less_energy(self):
        t = bench.wake_mode_trade()
        self.assertLess(t["wake_on_command"]["energy_wh"], t["periodic"]["energy_wh"])

    def test_coverage_and_packets(self):
        self.assertAlmostEqual(bench.coverage_probability(60, 2), 0.5)
        self.assertEqual(bench.coverage_probability(120, 2), 1.0)
        self.assertGreater(bench.packets_for_confidence(0.5, 0.75), bench.packets_for_confidence(0.5, 0.0))

    def test_evaluate_bench_pass_fail_and_not_run(self):
        res = bench.evaluate_bench({"B1": 1.0, "B3": 20.0})
        self.assertEqual(res["B1"]["status"], "PASS")
        self.assertEqual(res["B3"]["status"], "FAIL")
        self.assertEqual(res["B2"]["status"], "NOT_RUN")

    def test_virtual_bench_is_reproducible_and_bounded(self):
        a, b = bench.virtual_bench(2000, 1), bench.virtual_bench(2000, 1)
        self.assertEqual(a, b)
        self.assertTrue(all(0.0 <= v["p_pass"] <= 1.0 for v in a.values()))


@unittest.skipUnless(SUMMARY.exists(), "stored campaign not available")
class EconomicsTests(unittest.TestCase):
    def setUp(self):
        self.s = eco.load_main_summary(SUMMARY)
        self.a = eco.EconAssumptions()

    def test_outcome_probabilities_sum_to_one(self):
        for t in eco.TIERS:
            o = eco.attempt_outcomes(self.s[(t, 3.0)])
            self.assertAlmostEqual(sum(o.values()), 1.0, places=9)

    def test_preparation_never_lowers_success_at_3deg(self):
        ps = [eco.servicing_outcome(self.s[(t, 3.0)], self.a)["p_success"] for t in eco.TIERS]
        self.assertEqual(ps, sorted(ps))

    def test_unservable_cell_has_zero_benefit_and_infinite_price(self):
        cell = self.s[("C0_unprepared", 5.0)]
        self.assertEqual(eco.servicing_outcome(cell, self.a)["p_success"], 0.0)
        self.assertTrue(math.isinf(eco.servicer_throughput("C0_unprepared", cell, self.a)["breakeven_price_per_success_eur"]))

    def test_rocket_equation_round_trip(self):
        kg = eco.propellant_for_dv(60.0, 3500.0, 320.0)
        self.assertAlmostEqual(kg, 3500 * (1 - math.exp(-60 / (320 * 9.80665))), places=6)

    def test_addon_cost_is_cumulative(self):
        c = [eco.addon_cost(t, self.a)["total_eur"] for t in eco.TIERS]
        self.assertEqual(c, sorted(c))
        self.assertEqual(c[0], 0.0)

    def test_breakeven_matches_zero_net_gain(self):
        p = eco.breakeven_p_needs_rescue("C2_beacon", "C0_unprepared", self.s, 3.0, self.a)
        a = replace(self.a, p_needs_rescue=p)
        net = (eco.expected_value("C2_beacon", self.s[("C2_beacon", 3.0)], a)["net_eur"]
               - eco.expected_value("C0_unprepared", self.s[("C0_unprepared", 3.0)], a)["net_eur"])
        self.assertAlmostEqual(net, 0.0, delta=1.0)


if __name__ == "__main__":
    unittest.main()
