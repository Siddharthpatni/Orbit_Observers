"""IOS fault injection and engineering-model boundaries, independent of the RPO campaign."""
from dataclasses import replace
import math
import unittest

from ..ios import IOSCommand, IOSState, IOSStateMachine, evaluate_beacon_engineering_budget, simulate_ios_detumbling


class IOSTests(unittest.TestCase):
    def setUp(self):
        self.machine = IOSStateMachine(expected_token="test-credential")
        self.seq = 0
        self.now = 0.0

    def step(self, state, **kwargs):
        self.seq += 1
        self.now += 1.0
        options = dict(servicer_ack=True, client_ack=True, client_damping_passive=True)
        options.update(kwargs)
        return self.machine.step(IOSCommand(state, self.seq, self.now, "test-credential", **options), self.now)

    def approach(self):
        self.assertTrue(self.step(IOSState.SERVICE_STANDBY).accepted)
        self.assertTrue(self.step(IOSState.APPROACH_PERMITTED).accepted)

    def mate(self):
        self.approach()
        self.assertTrue(self.step(IOSState.IOS_HANDOVER).accepted)
        self.assertTrue(self.step(IOSState.MATED_SERVICING, latch_confirmed=True, load_path_verified=True).accepted)

    def test_nominal_cycle_requires_physical_separation_before_client_authority(self):
        self.mate()
        self.assertTrue(self.step(IOSState.VERIFICATION).accepted)
        self.assertFalse(self.step(IOSState.RELEASE).accepted)
        self.assertTrue(self.step(IOSState.RELEASE, connectors_isolated=True).accepted)
        self.assertTrue(self.machine.servicer_stack_authority)
        self.assertFalse(self.step(IOSState.NORMAL).accepted)
        self.assertTrue(self.step(IOSState.NORMAL, connectors_isolated=True, separation_confirmed=True).accepted)
        self.assertTrue(self.machine.client_attitude_authority)
        self.assertFalse(self.machine.servicer_stack_authority)
        self.assertTrue(all(not (r.client_attitude_authority and r.servicer_stack_authority) for r in self.machine.history))

    def test_unauthorized_abort_and_nonfinite_commands_do_not_change_state(self):
        self.approach()
        cmd = IOSCommand(IOSState.ABORT_SAFE, 3, self.now, "wrong")
        self.assertFalse(self.machine.step(cmd, self.now).accepted)
        self.assertEqual(self.machine.state, IOSState.APPROACH_PERMITTED)
        for change in ({"timestamp_s": math.nan}, {"client_rate_deg_s": math.nan},
                       {"sequence_id": 2}, {"timestamp_s": self.now + 1}, {"servicer_ack": "false"}):
            invalid = replace(cmd, auth_token="test-credential", **change)
            self.assertFalse(self.machine.step(invalid, self.now).accepted)
        with self.assertRaises(ValueError):
            self.machine.check_heartbeat(math.nan)

    def test_heartbeat_refresh_and_timeout_cannot_be_bypassed_by_late_command(self):
        self.approach()
        self.now += 7
        self.assertTrue(self.step(IOSState.APPROACH_PERMITTED).accepted)
        self.now += 11
        result = self.step(IOSState.IOS_HANDOVER)
        self.assertEqual(result.reason, "ACK_TIMEOUT_ABORT")
        self.assertEqual(self.machine.state, IOSState.ABORT_SAFE)

    def test_docked_abort_and_failed_load_check_retain_stack_authority(self):
        self.mate()
        self.assertTrue(self.step(IOSState.ABORT_SAFE).accepted)
        self.assertTrue(self.machine.servicer_stack_authority)
        self.assertFalse(self.machine.client_attitude_authority)
        self.assertFalse(self.step(IOSState.NORMAL).accepted)
        self.machine = IOSStateMachine(expected_token="test-credential")
        self.approach()
        self.step(IOSState.IOS_HANDOVER)
        result = self.step(IOSState.MATED_SERVICING, latch_confirmed=True, load_path_verified=False)
        self.assertFalse(result.accepted)
        self.assertTrue(result.servicer_stack_authority)
        self.assertFalse(result.client_attitude_authority)

    def test_handover_faults_abort_and_commands_cannot_be_replayed(self):
        for fault in ({"client_ack": False}, {"client_damping_passive": False}, {"client_rate_deg_s": 5.0}):
            self.machine = IOSStateMachine(expected_token="test-credential")
            self.approach()
            self.assertFalse(self.step(IOSState.IOS_HANDOVER, **fault).accepted)
            self.assertEqual(self.machine.state, IOSState.ABORT_SAFE)
            replay = IOSCommand(IOSState.NORMAL, self.seq, self.now, "test-credential")
            self.assertFalse(self.machine.step(replay, self.now).accepted)

    def test_engineering_models_validate_inputs_and_report_unreached_targets(self):
        for args in ({"rate_hz": -1}, {"rate_hz": 100}, {"freq_mhz": 0}, {"range_m": math.nan}):
            with self.subTest(args=args), self.assertRaises(ValueError):
                evaluate_beacon_engineering_budget(**args)
        budget = evaluate_beacon_engineering_budget()
        self.assertAlmostEqual(budget["net_energy_wh"], 20.52)
        self.assertGreater(budget["required_nameplate_wh"], budget["net_energy_wh"])
        farther = evaluate_beacon_engineering_budget(range_m=2000)
        self.assertAlmostEqual(budget["link_margin_db"] - farther["link_margin_db"], 20 * math.log10(2))
        for args in ({"initial_tumble_deg_s": -1}, {"initial_tumble_deg_s": 5, "client_isp_s": 0}):
            with self.assertRaises(ValueError):
                simulate_ios_detumbling(**args)
        result = simulate_ios_detumbling(5, max_time_s=0.3)
        self.assertLessEqual(result["detumble_time_s"], 0.3)
        self.assertFalse(result["residual_target_met"])
        self.assertFalse(result["handover_ready"])
        final = simulate_ios_detumbling(5)
        self.assertTrue(final["residual_target_met"])
        self.assertGreater(final["client_rcs_propellant_kg"], 0)


if __name__ == "__main__":
    unittest.main()
