"""Statistics helpers against hand-computed reference values."""
import math
import unittest
from ..stats import (mcnemar_exact_p, mean_interval, paired_difference, running_proportion, runs_for_half_width,
                     wilson_ci_95, wilson_interval, zero_event_upper_bound)


class WilsonTests(unittest.TestCase):
    def test_reference_values(self):
        p, lo, hi = wilson_interval(0, 10)
        self.assertEqual((p, lo), (0.0, 0.0))
        self.assertAlmostEqual(hi, 0.27753, places=4)
        p, lo, hi = wilson_interval(15, 20)
        self.assertAlmostEqual(lo, 0.53131, places=4)
        self.assertAlmostEqual(hi, 0.88814, places=4)

    def test_bounds_and_edge_cases(self):
        for k in range(0, 31):
            p, lo, hi = wilson_interval(k, 30)
            self.assertTrue(0.0 <= lo <= p <= hi <= 1.0)
        self.assertEqual(wilson_ci_95(0, 0), (0.0, 0.0, 0.0))
        with self.assertRaises(ValueError):
            wilson_interval(5, 3)


class PairedTests(unittest.TestCase):
    def test_mcnemar(self):
        self.assertEqual(mcnemar_exact_p(0, 0), 1.0)
        self.assertAlmostEqual(mcnemar_exact_p(0, 10), 2 * 0.5 ** 10)
        self.assertAlmostEqual(mcnemar_exact_p(3, 3), 1.0)
        self.assertAlmostEqual(mcnemar_exact_p(10, 0), mcnemar_exact_p(0, 10))
        self.assertLess(mcnemar_exact_p(0, 2000), 1e-12)  # large n must not overflow

    def test_paired_difference(self):
        a = [True] * 80 + [False] * 20
        b = [True] * 80 + [True] * 15 + [False] * 5
        res = paired_difference(a, b)
        self.assertAlmostEqual(res["diff"], 0.15)
        self.assertEqual((res["only_a_pass"], res["only_b_pass"]), (0, 15))
        self.assertLess(res["diff_ci95_low"], 0.15)
        self.assertGreater(res["diff_ci95_low"], 0.0)
        self.assertLess(res["mcnemar_p"], 0.001)
        same = paired_difference(a, a)
        self.assertEqual(same["diff"], 0.0)
        self.assertEqual(same["mcnemar_p"], 1.0)
        with self.assertRaises(ValueError):
            paired_difference([True], [True, False])


class PlanningTests(unittest.TestCase):
    def test_sample_size_and_zero_events(self):
        self.assertEqual(runs_for_half_width(0.5, 0.05), 385)
        self.assertAlmostEqual(zero_event_upper_bound(1000), 3 / 1000, delta=1e-4)

    def test_mean_interval_and_running(self):
        m, lo, hi = mean_interval([1.0, 2.0, 3.0, float("nan")])
        self.assertEqual(m, 2.0)
        self.assertAlmostEqual(hi - m, 1.959963984540054 / math.sqrt(3), places=12)
        run = running_proportion([True, False, True, True])
        self.assertEqual(run.shape, (4, 3))
        self.assertAlmostEqual(run[-1, 0], 0.75)


if __name__ == "__main__":
    unittest.main()
