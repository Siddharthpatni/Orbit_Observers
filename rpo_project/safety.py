"""Exclusion zone, GO/NO-GO abort triggers, and terminal capture window checks (Section 9)."""
import math
from typing import Tuple
import numpy as np
from .config import SimConfig
from .estimator import RPOEstimator

def check_estimator_abort_gates(
    estimator: RPOEstimator,
    cfg: SimConfig,
    elapsed_s: float,
    delta_v_used_mps: float,
) -> Tuple[bool, str]:
    omega_hat = abs(float(estimator.att_hat[1]))
    ang_std = estimator.angle_std_rad
    if elapsed_s >= cfg.rate_gate_start_s and omega_hat > cfg.max_safe_target_omega_rad_s:
        return True, "ABORT_EXCESS_TUMBLE_RATE"
    if elapsed_s >= cfg.covariance_gate_start_s and ang_std > cfg.max_allowed_angle_std_rad:
        return True, "ABORT_NAVIGATION_COVARIANCE"
    if delta_v_used_mps >= cfg.max_delta_v_mps:
        return True, "ABORT_DELTA_V_BUDGET"
    return False, "NOMINAL"

def check_truth_terminal_or_unsafe(
    chaser_pos: np.ndarray,
    chaser_vel: np.ndarray,
    r_cap_true: np.ndarray,
    v_cap_true: np.ndarray,
    n_cap_true: np.ndarray,
    dwell_accum_s: float,
    cfg: SimConfig,
) -> Tuple[bool, bool, float, float]:
    dist_origin = float(np.linalg.norm(chaser_pos))
    pos_err_cap = float(np.linalg.norm(chaser_pos - r_cap_true))
    rel_speed = float(np.linalg.norm(chaser_vel - v_cap_true))
    if dist_origin < cfg.keepout_radius_m:
        return False, True, dwell_accum_s, rel_speed

    cos_align = float(np.dot(chaser_pos / max(dist_origin, 1e-6), n_cap_true))
    align_err_rad = math.acos(max(-1.0, min(1.0, cos_align)))
    if (
        pos_err_cap <= cfg.terminal_pos_tol_m
        and rel_speed <= cfg.terminal_vel_tol_mps
        and align_err_rad <= cfg.terminal_align_tol_rad
    ):
        dwell_accum_s += cfg.dt_s
        if dwell_accum_s >= cfg.terminal_dwell_s:
            return True, False, dwell_accum_s, rel_speed
    else:
        dwell_accum_s = 0.0
    return False, False, dwell_accum_s, rel_speed
