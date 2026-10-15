"""3D Clohessy-Wiltshire (CW) relative orbital dynamics and RK4 integrator (Handbook Section 6)."""
import math
import numpy as np
from .config import N_GEO_RAD_S

def cw_derivative(state: np.ndarray, accel_lvlh: np.ndarray, n: float = N_GEO_RAD_S) -> np.ndarray:
    x, y, z, vx, vy, vz = state
    ax, ay, az = accel_lvlh
    x_ddot = 3.0 * (n ** 2) * x + 2.0 * n * vy + ax
    y_ddot = -2.0 * n * vx + ay
    z_ddot = -(n ** 2) * z + az
    return np.array([vx, vy, vz, x_ddot, y_ddot, z_ddot], dtype=float)

def propagate_cw_rk4(state: np.ndarray, accel_lvlh: np.ndarray, dt: float, n: float = N_GEO_RAD_S) -> np.ndarray:
    k1 = cw_derivative(state, accel_lvlh, n)
    k2 = cw_derivative(state + 0.5 * dt * k1, accel_lvlh, n)
    k3 = cw_derivative(state + 0.5 * dt * k2, accel_lvlh, n)
    k4 = cw_derivative(state + dt * k3, accel_lvlh, n)
    return state + (dt / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)

def cw_state_transition_matrix(t: float, n: float = N_GEO_RAD_S) -> np.ndarray:
    nt = n * t
    c, s = math.cos(nt), math.sin(nt)
    phi = np.zeros((6, 6), dtype=float)
    phi[0, 0], phi[0, 3], phi[0, 4] = 4.0 - 3.0 * c, s / n, (2.0 / n) * (1.0 - c)
    phi[1, 0], phi[1, 1], phi[1, 3], phi[1, 4] = 6.0 * (s - nt), 1.0, -(2.0 / n) * (1.0 - c), (4.0 * s - 3.0 * nt) / n
    phi[2, 2], phi[2, 5] = c, s / n
    phi[3, 0], phi[3, 3], phi[3, 4] = 3.0 * n * s, c, 2.0 * s
    phi[4, 0], phi[4, 3], phi[4, 4] = -6.0 * n * (1.0 - c), -2.0 * s, 4.0 * c - 3.0
    phi[5, 2], phi[5, 5] = -n * s, c
    return phi
