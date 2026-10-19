"""IOS <-> RPO coupling: ground gate, handover envelope, abort, authority invariant, regression."""
import unittest
from pathlib import Path

import pandas as pd

from ..config import SCENARIOS
from ..ios_coupling import run_ios_servicing_episode
from ..simulate import run_single_simulation


class IOSCouplingTests(unittest.TestCase):
    def test_no_ground_approval_means_no_ios_command(self):
        e = run_ios_servicing_episode("C2_beacon", 1, 3.0, ground_approved=False)
        self.assertEqual(e.outcome, "NOT_AUTHORIZED")
        self.assertEqual(e.final_ios_state, "NORMAL")
        self.assertIsNone(e.rpo)

    def test_nominal_cycle_returns_authority_to_client(self):
        e = run_ios_servicing_episode("C2_beacon", 1, 3.0, ground_approved=True)
        self.assertEqual(e.outcome, "SERVICED_AND_RELEASED")
        self.assertEqual(e.final_ios_state, "NORMAL")
        self.assertTrue(e.authority_invariant_held)

    def test_excess_tumble_aborts_to_safe_state(self):
        e = run_ios_servicing_episode("C2_beacon", 1, 5.0, ground_approved=True)
        self.assertEqual(e.outcome, "ABORTED_SAFE")
        self.assertEqual(e.final_ios_state, "ABORT_SAFE")

    def test_c3_uses_physical_detumble(self):
        e = run_ios_servicing_episode("C3_ios_mode", 1, 3.0, ground_approved=True)
        self.assertIsNotNone(e.detumble)
        self.assertTrue(e.detumble["residual_target_met"])
        self.assertAlmostEqual(e.effective_omega_factor, 0.05, delta=0.01)
        self.assertGreater(e.detumble["detumble_time_s"], 0)

    def test_bad_token_is_rejected(self):
        e = run_ios_servicing_episode("C2_beacon", 1, 3.0, ground_approved=True, token="wrong")
        self.assertEqual(e.outcome, "IOS_REFUSED_APPROACH")

    def test_unverified_latch_aborts(self):
        e = run_ios_servicing_episode("C2_beacon", 1, 3.0, ground_approved=True, latch_confirmed=False)
        self.assertEqual(e.outcome, "MATING_FAILED_ABORT_SAFE")
        self.assertEqual(e.final_ios_state, "ABORT_SAFE")

    def test_override_none_is_bit_identical_to_tier_value(self):
        a = run_single_simulation("C3_ios_mode", 3, 3.0)
        b = run_single_simulation("C3_ios_mode", 3, 3.0, omega_factor_override=SCENARIOS["C3_ios_mode"].omega_factor)
        self.assertEqual(a, b)

    def test_default_run_reproduces_stored_v41_row(self):
        path = Path(__file__).resolve().parents[2] / "results" / "v4_1_validation" / "runs_main.csv"
        if not path.exists():
            self.skipTest("stored campaign not available")
        row = pd.read_csv(path, float_precision="round_trip").iloc[0]
        new = run_single_simulation(row["scenario"], int(row["seed"]), float(row["tumble_deg_s"]),
                                    vision_sigma_m=float(row["vision_sigma_m"]),
                                    beacon_packet_loss=float(row["beacon_packet_loss"]) if row["beacon_enabled"] else 0.2,
                                    master_seed=int(row["master_seed"]))
        self.assertEqual(new["status"], row["status"])
        self.assertAlmostEqual(new["delta_v_mps"], row["delta_v_mps"], places=9)


if __name__ == "__main__":
    unittest.main()
