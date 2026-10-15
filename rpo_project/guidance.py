"""Two-stage hold-point and terminal capture-point trajectory feedback control (Section 9)."""
import math
from typing import Tuple
import numpy as np
from .config import SimConfig
from .estimator import RPOEstimator
from .dynamics import cw_derivative
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
    if (not in_terminal_phase and elapsed_s >= cfg.terminal_entry_min_time_s
            and hold_err < cfg.terminal_entry_pos_tol_m and hold_speed <= cfg.terminal_vel_tol_mps
            and ang_std < cfg.terminal_entry_max_angle_std_rad):
        in_terminal_phase = True

    if not in_terminal_phase:
        r_ref, v_ref = r_hold_ref, v_hold_ref
    else:
        if est_dist_to_origin < cfg.corridor_check_radius_m:
            cos_align = float(np.dot(r_hat / max(est_dist_to_origin, 1e-6), n_cap_hat))
            if cos_align < math.cos(cfg.corridor_half_angle_rad) or ang_std > cfg.corridor_max_angle_std_rad:
                return np.zeros(3), in_terminal_phase, True, "ABORT_CORRIDOR_MISALIGNMENT"
        r_ref, v_ref = r_cap_hat, v_cap_hat

    cos_side = float(np.dot(r_hat / max(est_dist_to_origin, 1e-6), r_ref / max(float(np.linalg.norm(r_ref)), 1e-6)))
    if cos_side < cfg.flyaround_cos_limit and est_dist_to_origin < cfg.hold_distance_m + cfg.flyaround_extra_radius_m:
        tangent = np.array([-r_hat[1], r_hat[0], 0.0], dtype=float)
        t_norm = float(np.linalg.norm(tangent))
        tangent = tangent / t_norm if t_norm > 1e-6 else np.array([0.0, 1.0, 0.0], dtype=float)
        r_ref = (r_hat / max(est_dist_to_origin, 1e-6)) * cfg.hold_distance_m + cfg.flyaround_tangent_offset_m * tangent
        v_ref = np.zeros(3, dtype=float)

    if cfg.controller == "legacy_pd":
        a_cmd = -cfg.kp_pos * (r_hat - r_ref) - cfg.kd_vel * (v_hat - v_ref)
    else:
        # Limit the closing reference before saturation destroys PD damping.
        # Reserve half the acceleration for braking/tracking by default.
        error = r_ref - r_hat
        distance = float(np.linalg.norm(error))
        closing_speed = min(
            cfg.max_closing_speed_mps,
            cfg.kp_pos / cfg.kd_vel * distance,
            math.sqrt(2.0 * cfg.braking_accel_fraction * cfg.a_max_mps2 * distance),
        )
        closing_velocity = error * (closing_speed / max(distance, 1e-12))
        # Constant-rate rotating-reference acceleration, using estimated rate.
        a_ref = np.cross(omega_vec_hat, v_ref)
        a_cmd = cfg.kd_vel * (v_ref + closing_velocity - v_hat) + a_ref
        a_cmd -= cw_derivative(estimator.s_hat, np.zeros(3))[3:]
    # Repulsive barrier just outside the keep-out sphere (acts on the estimate).
    if est_dist_to_origin < cfg.barrier_radius_m:
        radial_unit = r_hat / max(est_dist_to_origin, 1e-6)
        a_cmd = a_cmd + cfg.barrier_gain_mps2 * ((cfg.barrier_radius_m - est_dist_to_origin) / cfg.barrier_scale_m) * radial_unit

    a_norm = float(np.linalg.norm(a_cmd))
    if a_norm > cfg.a_max_mps2:
        a_cmd = a_cmd * (cfg.a_max_mps2 / a_norm)
    return a_cmd, in_terminal_phase, False, "NOMINAL"
