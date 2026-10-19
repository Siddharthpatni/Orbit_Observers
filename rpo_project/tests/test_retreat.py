"""Abort propagation, fuel accounting and all-axis covariance regressions."""
from dataclasses import replace
import unittest
from unittest.mock import patch

import numpy as np

from ..config import SimConfig
from ..estimator import RPOEstimator
from ..guidance import compute_retreat_command
from ..safety import check_estimator_abort_gates
from ..simulate import run_single_simulation


class RetreatTests(unittest.TestCase):
    def test_high_rate_retreat_completes_and_accounts_for_applied_thrust(self):
        cfg = SimConfig()
        trajectory = []
        row = run_single_simulation("C1_fiducials", 0, 5.0, cfg=cfg,
                                    deterministic_zero_noise=True, trajectory=trajectory)
        self.assertTrue(row["aborted"])
        self.assertTrue(row["retreat_complete"])
        self.assertFalse(row["unsafe"] or row["terminal_pass"])
        self.assertGreater(row["elapsed_s"], row["abort_time_s"])
        self.assertAlmostEqual(row["approach_delta_v_mps"] + row["retreat_delta_v_mps"], row["delta_v_mps"])
        self.assertAlmostEqual(sum(p["acceleration_mps2"] * cfg.dt_s for p in trajectory), row["delta_v_mps"])
        self.assertAlmostEqual(row["propellant_kg"], cfg.propellant_kg(row["delta_v_mps"]))
        self.assertTrue(any(p["retreat_phase"] for p in trajectory))

    def test_reserve_exhaustion_coasts_to_end_without_claiming_completion(self):
        cfg = replace(SimConfig(), retreat_delta_v_reserve_mps=0.01)
        row = run_single_simulation("C1_fiducials", 0, 5.0, cfg=cfg, deterministic_zero_noise=True)
        self.assertEqual(row["retreat_status"], "RESERVE_EXHAUSTED")
        self.assertFalse(row["retreat_complete"])
        self.assertLessEqual(row["retreat_delta_v_mps"], 0.0100000001)
        self.assertAlmostEqual(row["retreat_elapsed_s"], cfg.retreat_duration_s)

    def test_retreat_timeout_and_keepout_violation_are_not_success(self):
        short = replace(SimConfig(), retreat_duration_s=0.25)
        row = run_single_simulation("C1_fiducials", 0, 5.0, cfg=short, deterministic_zero_noise=True)
        self.assertEqual(row["retreat_status"], "TIMEOUT")
        with patch("rpo_project.simulate.compute_guidance_command", return_value=(np.zeros(3), False, True, "ABORT_TEST")), \
                patch("rpo_project.simulate.check_truth_terminal_or_unsafe", return_value=(False, True, 0.0, 0.1)):
            row = run_single_simulation("C1_fiducials", 0, 0)
        self.assertTrue(row["unsafe"] and row["abort_triggered"])
        self.assertFalse(row["aborted"] or row["terminal_pass"] or row["retreat_complete"])
        self.assertEqual(row["retreat_status"], "UNSAFE")

    def test_covariance_gate_uses_correlated_uncertainty_in_every_axis(self):
        cfg = SimConfig()
        est = RPOEstimator(np.array([4.0, 0, 0]), np.zeros(3), 0, 0, 0.05, 0.05, cfg)
        est.P_trans[:3, :3] = [[0.001, 0, 0], [0, 0.06, 0.05], [0, 0.05, 0.06]]
        self.assertAlmostEqual(est.position_std_m, np.sqrt(0.11))
        self.assertEqual(check_estimator_abort_gates(est, cfg, 0, 0), (True, "ABORT_POSITION_COVARIANCE"))
        cmd = compute_retreat_command(est, cfg, np.array([12.0, 0, 0]))
        self.assertGreater(cmd[0], 0)
        self.assertLessEqual(np.linalg.norm(cmd), cfg.a_max_mps2 + 1e-12)

    def test_invalid_retreat_configuration_is_rejected(self):
        for change in ({"retreat_duration_s": 0.3}, {"retreat_delta_v_reserve_mps": 0},
                       {"max_allowed_position_std_m": float("nan")}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                replace(SimConfig(), **change)


if __name__ == "__main__":
    unittest.main()
