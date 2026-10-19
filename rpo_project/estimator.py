"""Separated Translation & Attitude/Rate Kalman Estimator (Handbook Section 8 & 12)."""
import math
from typing import Tuple
import numpy as np
from .attitude import capture_point_kinematics_lvlh, quat_from_z_angle, wrap_pi
from .beacon import BeaconPacket
from .config import SimConfig
from .dynamics import cw_state_transition_matrix, propagate_cw_rk4

class RPOEstimator:
    def __init__(
        self,
        init_pos_est: np.ndarray,
        init_vel_est: np.ndarray,
        init_theta_est: float,
        init_omega_est: float,
        vision_pos_sigma_m: float,
        vision_angle_sigma_rad: float,
        cfg: SimConfig = SimConfig(),
    ) -> None:
        self.cfg = cfg
        self.s_hat = np.concatenate([init_pos_est, init_vel_est]).astype(float)
        pos_var = max(vision_pos_sigma_m ** 2, cfg.est_min_pos_sigma_m ** 2)
        vel_var = cfg.est_init_vel_sigma_mps ** 2
        self.P_trans = np.diag([pos_var, pos_var, pos_var, vel_var, vel_var, vel_var])

        self.att_hat = np.array([wrap_pi(init_theta_est), init_omega_est], dtype=float)
        ang_var = max(vision_angle_sigma_rad ** 2, cfg.est_min_angle_sigma_rad ** 2)
        rate_var = cfg.est_init_rate_sigma_rad_s ** 2
        self.P_att = np.diag([ang_var, rate_var])
        self._cached_dt = cfg.dt_s
        self._cached_phi = cw_state_transition_matrix(cfg.dt_s)
        q_pos = (cfg.est_pos_process_noise_mps * cfg.dt_s) ** 2
        q_vel = (cfg.est_vel_process_noise_mps15 * math.sqrt(cfg.dt_s)) ** 2
        self._cached_q_trans = np.diag([q_pos, q_pos, q_pos, q_vel, q_vel, q_vel])
        self._cached_f_att = np.array([[1.0, cfg.dt_s], [0.0, 1.0]], dtype=float)
        q_omega = cfg.est_rate_process_noise_rad_s15 ** 2
        self._cached_q_att = q_omega * np.array(
            [[(cfg.dt_s ** 3) / 3.0, (cfg.dt_s ** 2) / 2.0], [(cfg.dt_s ** 2) / 2.0, cfg.dt_s]], dtype=float
        )

    def predict(self, dt: float, u_cmd_lvlh: np.ndarray) -> None:
        self.s_hat = propagate_cw_rk4(self.s_hat, u_cmd_lvlh, dt)
        if dt == self._cached_dt:
            phi = self._cached_phi
            q_trans = self._cached_q_trans
            F_att = self._cached_f_att
            Q_att = self._cached_q_att
        else:
            phi = cw_state_transition_matrix(dt)
            q_pos = (self.cfg.est_pos_process_noise_mps * dt) ** 2
            q_vel = (self.cfg.est_vel_process_noise_mps15 * math.sqrt(dt)) ** 2
            q_trans = np.diag([q_pos, q_pos, q_pos, q_vel, q_vel, q_vel])
            F_att = np.array([[1.0, dt], [0.0, 1.0]], dtype=float)
            q_omega = self.cfg.est_rate_process_noise_rad_s15 ** 2
            Q_att = q_omega * np.array([[(dt ** 3) / 3.0, (dt ** 2) / 2.0], [(dt ** 2) / 2.0, dt]], dtype=float)
        self.P_trans = phi @ self.P_trans @ phi.T + q_trans
        self.att_hat = np.array([wrap_pi(self.att_hat[0] + self.att_hat[1] * dt), self.att_hat[1]], dtype=float)
        self.P_att = F_att @ self.P_att @ F_att.T + Q_att

    def update_vision(self, meas_chaser_pos_lvlh: np.ndarray, meas_theta_rad: float, pos_sigma_m: float, angle_sigma_rad: float) -> None:
        H_t = np.zeros((3, 6), dtype=float)
        H_t[0, 0] = H_t[1, 1] = H_t[2, 2] = 1.0
        R_t = np.eye(3, dtype=float) * max(pos_sigma_m ** 2, 1e-6)
        y_t = meas_chaser_pos_lvlh - (H_t @ self.s_hat)
        S_t = H_t @ self.P_trans @ H_t.T + R_t
        K_t = np.linalg.solve(S_t, H_t @ self.P_trans).T
        self.s_hat = self.s_hat + K_t @ y_t
        A_t = np.eye(6) - K_t @ H_t
        self.P_trans = A_t @ self.P_trans @ A_t.T + K_t @ R_t @ K_t.T

        h_a = np.array([1.0, 0.0], dtype=float)
        r_a = max(angle_sigma_rad ** 2, 1e-8)
        residual = wrap_pi(meas_theta_rad - self.att_hat[0])
        s_a = float(h_a @ self.P_att @ h_a + r_a)
        k_a = (self.P_att @ h_a) / s_a
        self.att_hat = np.array([wrap_pi(self.att_hat[0] + k_a[0] * residual), self.att_hat[1] + k_a[1] * residual], dtype=float)
        A_a = np.eye(2) - np.outer(k_a, h_a)
        self.P_att = A_a @ self.P_att @ A_a.T + r_a * np.outer(k_a, k_a)

    def update_beacon_packet(self, packet: BeaconPacket, current_time_s: float, gyro_sigma_rad_s: float) -> None:
        if not packet.has_rate or packet.omega_z_rad_s is None:
            return
        if packet.timestamp_s > current_time_s + 1e-9 or packet.arrival_time_s > current_time_s + 1e-9:
            raise ValueError("cannot assimilate a beacon packet before its timestamp/arrival")
        age_s = max(0.0, current_time_s - packet.timestamp_s)
        q_omega = self.cfg.est_rate_process_noise_rad_s15 ** 2
        # Approximate stale-rate fusion for the constant-rate study. Inflate
        # noise with age; this is not an exact out-of-sequence filter.
        effective_var = max((gyro_sigma_rad_s ** 2) + q_omega * age_s, 1e-10)
        h_r = np.array([0.0, 1.0], dtype=float)
        residual = packet.omega_z_rad_s - self.att_hat[1]
        s_r = float(h_r @ self.P_att @ h_r + effective_var)
        k_r = (self.P_att @ h_r) / s_r
        self.att_hat = np.array([
            wrap_pi(self.att_hat[0] + k_r[0] * residual),
            self.att_hat[1] + k_r[1] * residual,
        ], dtype=float)
        A_r = np.eye(2) - np.outer(k_r, h_r)
        self.P_att = A_r @ self.P_att @ A_r.T + effective_var * np.outer(k_r, k_r)

    def predict_capture_point(self, horizon_s: float, rho_cap_body: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        theta_pred = wrap_pi(self.att_hat[0] + self.att_hat[1] * horizon_s)
        q_pred = quat_from_z_angle(theta_pred)
        omega_pred = np.array([0.0, 0.0, self.att_hat[1]], dtype=float)
        return capture_point_kinematics_lvlh(q_pred, omega_pred, rho_cap_body)

    @property
    def angle_std_rad(self) -> float:
        return math.sqrt(max(0.0, float(self.P_att[0, 0])))

    @property
    def position_std_m(self) -> float:
        """Largest principal-axis position uncertainty, including cross-covariance."""
        covariance = self.P_trans[:3, :3]
        return math.sqrt(max(0.0, float(np.linalg.eigvalsh((covariance + covariance.T) / 2)[-1])))
