"""Section 13 Verification & Validation Suite (the 10 mandatory checks, plus reproducibility).

Run standalone through the CLI (``python -m rpo_project.montecarlo --mode verify``)
or as unit tests (``python -m unittest discover -s rpo_project/tests -t .``).
"""
import math
from typing import Callable, List, Tuple
import unittest
import numpy as np
from ..attitude import capture_point_kinematics_lvlh, propagate_attitude_rk4, quat_from_z_angle, z_angle_from_quat
from ..beacon import BeaconPacket, generate_beacon_packet_if_due
from ..config import SimConfig
from ..dynamics import cw_state_transition_matrix, propagate_cw_rk4
from ..estimator import RPOEstimator
from ..simulate import run_single_simulation

CFG = SimConfig()
OUTCOME_FIELDS = ("status", "elapsed_s", "delta_v_mps", "capture_point_error_m", "minimum_clearance_m", "relative_speed_mps")


class VerificationError(AssertionError):
    pass


def _check(condition: bool, message: str) -> None:
    # Explicit check instead of `assert`, which `python -O` silently removes.
    if not condition:
        raise VerificationError(message)


def _same_outcome(a, b) -> bool:
    return all(a[f] == b[f] or (isinstance(a[f], float) and math.isnan(a[f]) and math.isnan(b[f])) for f in OUTCOME_FIELDS)


def check_cw_vs_stm() -> None:
    s0 = np.array([15.0, -25.0, 5.0, 0.02, -0.01, 0.005])
    s = s0.copy()
    for _ in range(500):
        s = propagate_cw_rk4(s, np.zeros(3), 0.1)
    err = float(np.linalg.norm(s - cw_state_transition_matrix(50.0) @ s0))
    _check(err < 1e-8, f"RK4 vs analytic CW STM differs by {err:.3e} m")


def check_stationary_perfect_sensors() -> None:
    for scen in ("C1_fiducials", "C2_beacon"):
        r = run_single_simulation(scen, seed=1, tumble_deg_s=0.0, cfg=CFG, deterministic_zero_noise=True)
        _check(r["terminal_pass"] and not r["unsafe"], f"{scen} noise-free stationary approach failed: {r['status']}")


def check_zero_beacon_equals_c1() -> None:
    for seed in range(3):
        c1 = run_single_simulation("C1_fiducials", seed, 1.5, beacon_packet_loss=1.0, cfg=CFG)
        c2 = run_single_simulation("C2_beacon", seed, 1.5, beacon_packet_loss=1.0, cfg=CFG)
        _check(_same_outcome(c1, c2), f"seed {seed}: C2 with every packet lost differs from C1")


def check_id_only_no_magic() -> None:
    for seed in range(3):
        c1 = run_single_simulation("C1_fiducials", seed, 1.5, beacon_packet_loss=0.0, cfg=CFG)
        c2id = run_single_simulation("C2_id_only", seed, 1.5, beacon_packet_loss=0.0, cfg=CFG)
        _check(_same_outcome(c1, c2id), f"seed {seed}: ID-only beacon changed navigation")


def check_packet_boundaries_and_latency() -> None:
    args = dict(step_k=4, t_s=1.0, step_interval=4, beacon_enabled=True, beacon_has_rate=True, latency_s=0.5,
                true_omega_z=0.03, gyro_sigma=0.0, gyro_noise_draw=0.0)
    for u in (0.0, 0.5, 0.999):
        _check(generate_beacon_packet_if_due(packet_loss_prob=1.0, u_draw=u, **args) is None, "loss=1 delivered a packet")
        pkt = generate_beacon_packet_if_due(packet_loss_prob=0.0, u_draw=u, **args)
        _check(pkt is not None and math.isclose(pkt.arrival_time_s, 1.5), "loss=0 dropped a packet or wrong arrival time")
    est = RPOEstimator(np.zeros(3), np.zeros(3), 0.0, 0.0, 0.05, 0.05, CFG)
    early = BeaconPacket(timestamp_s=1.0, arrival_time_s=1.5, authenticated_id="X", has_rate=True, omega_z_rad_s=0.03)
    try:
        est.update_beacon_packet(early, current_time_s=1.25, gyro_sigma_rad_s=0.001)
        _check(False, "estimator used a packet before it arrived")
    except ValueError:
        pass
    errs_c1 = [run_single_simulation("C1_fiducials", s, 1.5, cfg=CFG)["capture_point_error_m"] for s in range(4)]
    errs_c2 = [run_single_simulation("C2_beacon", s, 1.5, beacon_packet_loss=0.0, beacon_rate_hz=2.0, latency_s=0.25,
                                     cfg=CFG)["capture_point_error_m"] for s in range(4)]
    _check(np.mean(errs_c2) < np.mean(errs_c1), "delayed rate packets did not improve capture-point prediction")


def check_quaternion_and_frames() -> None:
    q, w = np.array([1.0, 0.0, 0.0, 0.0]), np.array([0.02, -0.01, 0.035])
    rho = np.array(CFG.capture_offset_body_m)
    for _ in range(200):
        q, w = propagate_attitude_rk4(q, w, 0.1, np.array(CFG.inertia_diag_kgm2))
        r_cap, _, _ = capture_point_kinematics_lvlh(q, w, rho)
        _check(abs(float(np.linalg.norm(r_cap)) - float(np.linalg.norm(rho))) < 1e-12, "capture point changed length")
    _check(abs(float(np.linalg.norm(q)) - 1.0) < 1e-14, "quaternion lost unit norm")
    q, w = quat_from_z_angle(0.0), np.array([0.0, 0.0, math.radians(2.0)])
    for _ in range(40):
        q, w = propagate_attitude_rk4(q, w, 0.25, np.array(CFG.inertia_diag_kgm2))
    _check(abs(z_angle_from_quat(q) - math.radians(20.0)) < 1e-9, "pure z spin did not rotate by omega * t")


def check_zero_rate_capture_velocity() -> None:
    _, v_cap, _ = capture_point_kinematics_lvlh(quat_from_z_angle(0.7), np.zeros(3), np.array(CFG.capture_offset_body_m))
    _check(float(np.linalg.norm(v_cap)) < 1e-15, "capture point moves although the client does not rotate")


def check_high_rate_aborts() -> None:
    for seed in range(5):
        r = run_single_simulation("C1_fiducials", seed, 5.0, cfg=CFG)
        _check(r["aborted"] and not r["unsafe"], f"seed {seed}: 5 deg/s did not abort safely ({r['status']})")


def check_dt_convergence() -> None:
    s0 = np.array([15.0, -25.0, 5.0, 0.02, -0.01, 0.005])
    a = np.array([0.005, -0.002, 0.001])
    s1, s2 = s0.copy(), s0.copy()
    for _ in range(100):
        s1 = propagate_cw_rk4(s1, a, 0.2)
    for _ in range(200):
        s2 = propagate_cw_rk4(s2, a, 0.1)
    _check(float(np.linalg.norm(s1 - s2)) < 1e-9, "integration does not converge as dt shrinks")


def check_paired_seeds_and_reproducibility() -> None:
    rows = [run_single_simulation(s, 99, 1.0, cfg=CFG) for s in ("C0_unprepared", "C1_fiducials", "C2_beacon")]
    for key in ("theta0_rad", "init_offset_m", "init_speed_mps", "tumble_axis_tilt_deg", "thruster_misalign_deg"):
        _check(len({r[key] for r in rows}) == 1, f"paired tiers do not share '{key}'")
    again = run_single_simulation("C1_fiducials", 99, 1.0, cfg=CFG)
    _check(again == rows[1], "same (master_seed, seed) did not reproduce the run exactly")
    other = run_single_simulation("C1_fiducials", 99, 1.0, cfg=CFG, master_seed=1)
    _check(other["theta0_rad"] != rows[1]["theta0_rad"], "master seed has no effect")


CHECKS: List[Tuple[str, Callable[[], None]]] = [
    ("CW zero-control check vs analytical STM", check_cw_vs_stm),
    ("Stationary, perfect sensors convergence", check_stationary_perfect_sensors),
    ("Zero beacon reduction check (C2 all packets lost == C1)", check_zero_beacon_equals_c1),
    ("Beacon ID-only gives no navigation benefit", check_id_only_no_magic),
    ("Packet delivery boundaries & timestamp latency", check_packet_boundaries_and_latency),
    ("Quaternion norm & body-to-LVLH frame consistency", check_quaternion_and_frames),
    ("Zero target rate capture-point velocity", check_zero_rate_capture_velocity),
    ("High angular rate safety abort", check_high_rate_aborts),
    ("Integrator dt convergence", check_dt_convergence),
    ("Paired seeds across tiers & exact reproducibility", check_paired_seeds_and_reproducibility),
]


def run_verification_suite() -> bool:
    print("Running Section 13 Verification & Validation Suite...")
    for i, (name, check) in enumerate(CHECKS, start=1):
        check()
        print(f"  [PASS] {i}. {name}")
    print()
    return True


class VerificationSuite(unittest.TestCase):
    def test_all_checks(self) -> None:
        for name, check in CHECKS:
            with self.subTest(check=name):
                check()


if __name__ == "__main__":
    unittest.main()
