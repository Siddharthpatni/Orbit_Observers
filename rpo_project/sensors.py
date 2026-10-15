"""Optical camera/fiducial visibility and noisy observation model (Handbook Section 8)."""
from typing import Optional, Tuple
import numpy as np
from .attitude import wrap_pi, z_angle_from_quat

def sense_target_with_noise_and_occlusion(
    chaser_pos_true: np.ndarray,
    target_quat_true: np.ndarray,
    n_cap_true: np.ndarray,
    eff_pos_sigma: float,
    eff_ang_sigma: float,
    dropout_prob: float,
    fov_cos_limit: float,
    u_draw: float,
    pos_noise_draw: np.ndarray,
    ang_noise_draw: float,
    deterministic_zero_noise: bool = False,
) -> Optional[Tuple[np.ndarray, float]]:
    chaser_unit = chaser_pos_true / max(float(np.linalg.norm(chaser_pos_true)), 1e-6)
    los_cos = float(np.dot(chaser_unit, n_cap_true))
    occluded = (los_cos < fov_cos_limit) and not deterministic_zero_noise
    if occluded or (u_draw < dropout_prob and not deterministic_zero_noise):
        return None
    true_yaw = z_angle_from_quat(target_quat_true)
    meas_yaw = wrap_pi(true_yaw + eff_ang_sigma * ang_noise_draw)
    meas_pos = chaser_pos_true + eff_pos_sigma * pos_noise_draw
    return meas_pos, meas_yaw
