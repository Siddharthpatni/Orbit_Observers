"""3D quaternion attitude, rigid-body Euler propagation, and capture-point geometry (Section 7)."""
import math
from typing import Optional, Tuple
import numpy as np

def wrap_pi(angle_rad: float) -> float:
    return float((angle_rad + math.pi) % (2.0 * math.pi) - math.pi)

def quat_normalize(q: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(q))
    return np.array([1.0, 0.0, 0.0, 0.0], dtype=float) if norm < 1e-15 else q / norm

def quat_from_z_angle(theta_rad: float) -> np.ndarray:
    half = 0.5 * theta_rad
    return np.array([math.cos(half), 0.0, 0.0, math.sin(half)], dtype=float)

def z_angle_from_quat(q: np.ndarray) -> float:
    qw, qx, qy, qz = quat_normalize(q)
    return math.atan2(2.0 * (qw * qz + qx * qy), 1.0 - 2.0 * (qy * qy + qz * qz))

def rotmat_from_quat(q: np.ndarray) -> np.ndarray:
    qw, qx, qy, qz = quat_normalize(q)
    return np.array([
        [1.0 - 2.0 * (qy * qy + qz * qz), 2.0 * (qx * qy - qw * qz),       2.0 * (qx * qz + qw * qy)],
        [2.0 * (qx * qy + qw * qz),       1.0 - 2.0 * (qx * qx + qz * qz), 2.0 * (qy * qz - qw * qx)],
        [2.0 * (qx * qz - qw * qy),       2.0 * (qy * qz + qw * qx),       1.0 - 2.0 * (qx * qx + qy * qy)],
    ], dtype=float)

def attitude_derivative(q: np.ndarray, omega_body: np.ndarray, inertia_diag: np.ndarray, tau_ext: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    wx, wy, wz = omega_body
    omega_mat = np.array([
        [0.0, -wx, -wy, -wz],
        [wx,  0.0,  wz, -wy],
        [wy, -wz,  0.0,  wx],
        [wz,  wy, -wx,  0.0],
    ], dtype=float)
    q_dot = 0.5 * (omega_mat @ q)
    omega_dot = (tau_ext - np.cross(omega_body, inertia_diag * omega_body)) / inertia_diag
    return q_dot, omega_dot

def propagate_attitude_rk4(q: np.ndarray, omega_body: np.ndarray, dt: float, inertia_diag: np.ndarray, tau_ext: Optional[np.ndarray] = None) -> Tuple[np.ndarray, np.ndarray]:
    if tau_ext is None:
        tau_ext = np.zeros(3, dtype=float)
    kq1, kw1 = attitude_derivative(q, omega_body, inertia_diag, tau_ext)
    kq2, kw2 = attitude_derivative(q + 0.5 * dt * kq1, omega_body + 0.5 * dt * kw1, inertia_diag, tau_ext)
    kq3, kw3 = attitude_derivative(q + 0.5 * dt * kq2, omega_body + 0.5 * dt * kw2, inertia_diag, tau_ext)
    kq4, kw4 = attitude_derivative(q + dt * kq3, omega_body + dt * kw3, inertia_diag, tau_ext)
    q_next = quat_normalize(q + (dt / 6.0) * (kq1 + 2.0 * kq2 + 2.0 * kq3 + kq4))
    w_next = omega_body + (dt / 6.0) * (kw1 + 2.0 * kw2 + 2.0 * kw3 + kw4)
    return q_next, w_next

def capture_point_kinematics_lvlh(q_bl: np.ndarray, omega_body_rel_lvlh: np.ndarray, rho_cap_body: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    r_mat = rotmat_from_quat(q_bl)
    r_cap_l = r_mat @ rho_cap_body
    omega_lvlh = r_mat @ omega_body_rel_lvlh
    v_cap_l = np.cross(omega_lvlh, r_cap_l)
    norm_rho = float(np.linalg.norm(r_cap_l))
    n_cap_l = r_cap_l / norm_rho if norm_rho > 1e-12 else np.array([1.0, 0.0, 0.0], dtype=float)
    return r_cap_l, v_cap_l, n_cap_l
