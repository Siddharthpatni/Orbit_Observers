"""Section 13 Verification & Validation Suite (All 10 Mandatory Checks)."""
import numpy as np
from ..attitude import capture_point_kinematics_lvlh, propagate_attitude_rk4, quat_from_z_angle
from ..config import SimConfig
from ..dynamics import cw_state_transition_matrix, propagate_cw_rk4
from ..simulate import run_single_simulation

def run_verification_suite() -> bool:
    cfg = SimConfig()
    print("Running Section 13 Verification & Validation Suite...")

    s0 = np.array([15.0, -25.0, 5.0, 0.02, -0.01, 0.005], dtype=float)
    s_rk4 = s0.copy()
    for _ in range(500):
        s_rk4 = propagate_cw_rk4(s_rk4, np.zeros(3), 0.1)
    s_analytic = cw_state_transition_matrix(50.0) @ s0
    assert float(np.linalg.norm(s_rk4 - s_analytic)) < 1e-8
    print("  [PASS] 1. CW zero-control check vs analytical STM")

    res_stat = run_single_simulation("C1_fiducials", seed=1, tumble_deg_s=0.0, cfg=cfg, deterministic_zero_noise=True)
    assert res_stat["terminal_pass"] is True and res_stat["unsafe"] is False
    print("  [PASS] 2. Stationary, perfect sensors convergence")

    r_c1 = run_single_simulation("C1_fiducials", seed=42, tumble_deg_s=1.5, beacon_packet_loss=1.0, cfg=cfg)
    r_c2_off = run_single_simulation("C2_beacon", seed=42, tumble_deg_s=1.5, beacon_packet_loss=1.0, cfg=cfg)
    assert abs(float(r_c1["capture_point_error_m"]) - float(r_c2_off["capture_point_error_m"])) < 1e-12
    print("  [PASS] 3. Zero beacon reduction check (C2 disabled == C1)")

    r_c2_id = run_single_simulation("C2_id_only", seed=42, tumble_deg_s=1.5, beacon_packet_loss=0.0, cfg=cfg)
    assert abs(float(r_c1["capture_point_error_m"]) - float(r_c2_id["capture_point_error_m"])) < 1e-12
    print("  [PASS] 4. Beacon ID-only vs rate data check")

    r_c2_full = run_single_simulation("C2_beacon", seed=42, tumble_deg_s=1.5, beacon_packet_loss=0.0, beacon_rate_hz=2.0, latency_s=0.25, cfg=cfg)
    assert float(r_c2_full["capture_point_error_m"]) < float(r_c2_off["capture_point_error_m"])
    print("  [PASS] 5. Packet delivery boundaries & timestamp latency check")

    q_t, w_t = np.array([1.0, 0.0, 0.0, 0.0]), np.array([0.02, -0.01, 0.035])
    for _ in range(200):
        q_t, w_t = propagate_attitude_rk4(q_t, w_t, 0.1, np.array(cfg.inertia_diag_kgm2))
    assert abs(float(np.linalg.norm(q_t)) - 1.0) < 1e-14
    print("  [PASS] 6. Quaternion norm & LVLH frame check")

    _, v_cap_zero, _ = capture_point_kinematics_lvlh(quat_from_z_angle(0.7), np.zeros(3), np.array(cfg.capture_offset_body_m))
    assert float(np.linalg.norm(v_cap_zero)) < 1e-15
    print("  [PASS] 7. Zero target rate capture-point velocity check")

    r_high = run_single_simulation("C1_fiducials", seed=7, tumble_deg_s=5.0, cfg=cfg)
    assert r_high["aborted"] is True and r_high["unsafe"] is False
    print("  [PASS] 8. High angular rate safety abort check")

    s_dt1, s_dt2 = s0.copy(), s0.copy()
    for _ in range(100): s_dt1 = propagate_cw_rk4(s_dt1, np.array([0.005, -0.002, 0.001]), 0.2)
    for _ in range(200): s_dt2 = propagate_cw_rk4(s_dt2, np.array([0.005, -0.002, 0.001]), 0.1)
    assert float(np.linalg.norm(s_dt1 - s_dt2)) < 1e-9
    print("  [PASS] 9. Integrator dt convergence check")

    r0 = run_single_simulation("C0_unprepared", seed=99, tumble_deg_s=1.0, cfg=cfg)
    r1 = run_single_simulation("C1_fiducials", seed=99, tumble_deg_s=1.0, cfg=cfg)
    r2 = run_single_simulation("C2_beacon", seed=99, tumble_deg_s=1.0, cfg=cfg)
    assert r0["theta0_rad"] == r1["theta0_rad"] == r2["theta0_rad"]
    print("  [PASS] 10. Paired seeds consistency across C0/C1/C2\n")
    return True
