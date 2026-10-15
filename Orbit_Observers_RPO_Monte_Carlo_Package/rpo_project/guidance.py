"""Two-stage hold-point and terminal capture-point trajectory feedback control (Section 9)."""
import math
from typing import Tuple
import numpy as np
from .config import SimConfig
from .estimator import RPOEstimator
from .safety import check_estimator_abort_gates

def compute_guidance_command(
    estimator: RPOEstimator,
    cfg: SimConfig,
    rho_cap_body: np.ndarray,
    elapsed_s: float,
    delta_v_used_mps: float,
    in_terminal_phase: bool,
) -> Tuple[np.ndarray, bool, bool, str]:
    abort_trig, abort_reason = check_estimator_abort_gates(estimator, cfg, elapsed_s, delta_v_used_mps)
    if abort_trig:
        return np.zeros(3), in_terminal_phase, True, abort_reason

    r_hat = estimator.s_hat[:3]
    v_hat = estimator.s_hat[3:]
    r_cap_hat, v_cap_hat, n_cap_hat = estimator.predict_capture_point(0.0, rho_cap_body)
    ang_std = estimator.angle_std_rad
    est_dist_to_origin = float(np.linalg.norm(r_hat))

    omega_vec_hat = np.array([0.0, 0.0, float(estimator.att_hat[1])], dtype=float)
    r_hold_ref = n_cap_hat * cfg.hold_distance_m
    v_hold_ref = np.cross(omega_vec_hat, r_hold_ref)

    hold_err = float(np.linalg.norm(r_hat - r_hold_ref))
    hold_speed = float(np.linalg.norm(v_hat - v_hold_ref))
    # Settle at the hold point before moving the reference inward; otherwise
    # the saturated controller can accelerate again before finishing braking.
    if not in_terminal_phase and elapsed_s >= 8.0 and hold_err < 1.25 and hold_speed <= cfg.terminal_vel_tol_mps and ang_std < math.radians(8.0):
        in_terminal_phase = True

    if not in_terminal_phase:
        r_ref, v_ref = r_hold_ref, v_hold_ref
    else:
        if est_dist_to_origin < 2.8:
            cos_align = float(np.dot(r_hat / max(est_dist_to_origin, 1e-6), n_cap_hat))
            if cos_align < math.cos(math.radians(55.0)) or ang_std > math.radians(10.0):
                return np.zeros(3), in_terminal_phase, True, "ABORT_CORRIDOR_MISALIGNMENT"
        r_ref, v_ref = r_cap_hat, v_cap_hat

    cos_side = float(np.dot(r_hat / max(est_dist_to_origin, 1e-6), r_ref / max(float(np.linalg.norm(r_ref)), 1e-6)))
    if cos_side < 0.15 and est_dist_to_origin < cfg.hold_distance_m + 1.5:
        tangent = np.array([-r_hat[1], r_hat[0], 0.0], dtype=float)
        t_norm = float(np.linalg.norm(tangent))
        tangent = tangent / t_norm if t_norm > 1e-6 else np.array([0.0, 1.0, 0.0], dtype=float)
        r_ref = (r_hat / max(est_dist_to_origin, 1e-6)) * cfg.hold_distance_m + 2.5 * tangent
        v_ref = np.zeros(3, dtype=float)

    a_cmd = -cfg.kp_pos * (r_hat - r_ref) - cfg.kd_vel * (v_hat - v_ref)
    safety_margin_m = 1.48
    if est_dist_to_origin < safety_margin_m:
        radial_unit = r_hat / max(est_dist_to_origin, 1e-6)
        a_cmd = a_cmd + 0.06 * ((safety_margin_m - est_dist_to_origin) / 0.15) * radial_unit

    a_norm = float(np.linalg.norm(a_cmd))
    if a_norm > cfg.a_max_mps2:
        a_cmd = a_cmd * (cfg.a_max_mps2 / a_norm)
    return a_cmd, in_terminal_phase, False, "NOMINAL"
