"""Single independent deterministic/stochastic closed-loop RPO simulation run (Section 12)."""
from dataclasses import dataclass
import math
from typing import Dict, List
import numpy as np
from .attitude import capture_point_kinematics_lvlh, propagate_attitude_rk4, quat_from_z_angle, wrap_pi
from .beacon import BeaconPacket, generate_beacon_packet_if_due
from .config import MODEL_VERSION, SCENARIOS, SimConfig
from .dynamics import propagate_cw_rk4
from .estimator import RPOEstimator
from .guidance import compute_guidance_command
from .safety import check_truth_terminal_or_unsafe
from .sensors import sense_target_with_noise_and_occlusion

@dataclass
class TruthState:
    t_s: float
    chaser_state_lvlh: np.ndarray
    target_quat_bl: np.ndarray
    target_omega_body: np.ndarray

def run_single_simulation(
    scenario_name: str,
    seed: int,
    tumble_deg_s: float,
    vision_sigma_m: float = 0.05,
    beacon_packet_loss: float = 0.20,
    beacon_rate_hz: float = 1.0,
    latency_s: float = 0.0,
    cfg: SimConfig = SimConfig(),
    deterministic_zero_noise: bool = False,
) -> Dict[str, object]:
    scen = SCENARIOS[scenario_name]
    n_steps = int(round(cfg.max_duration_s / cfg.dt_s))
    rho_cap_body = np.array(cfg.capture_offset_body_m, dtype=float)
    inertia_diag = np.array(cfg.inertia_diag_kgm2, dtype=float)

    rng = np.random.default_rng(int(seed))
    theta0_rad = 0.0 if deterministic_zero_noise else float(rng.uniform(-math.pi, math.pi))
    pos_init_noise = np.zeros(3) if deterministic_zero_noise else rng.normal(0.0, cfg.chaser_pos_disp_sigma_m, size=3)
    vel_init_noise = np.zeros(3) if deterministic_zero_noise else rng.normal(0.0, cfg.chaser_vel_disp_sigma_mps, size=3)
    vis_pos_noise_seq = np.zeros((n_steps, 3)) if deterministic_zero_noise else rng.standard_normal((n_steps, 3))
    vis_ang_noise_seq = np.zeros(n_steps) if deterministic_zero_noise else rng.standard_normal(n_steps)
    vis_uniform_seq = np.ones(n_steps) if deterministic_zero_noise else rng.uniform(0.0, 1.0, size=n_steps)
    beacon_gyro_noise_seq = np.zeros(n_steps) if deterministic_zero_noise else rng.standard_normal(n_steps)
    beacon_uniform_seq = np.ones(n_steps) if deterministic_zero_noise else rng.uniform(0.0, 1.0, size=n_steps)
    thruster_noise_seq = np.zeros((n_steps, 3)) if deterministic_zero_noise else rng.normal(0.0, cfg.thruster_noise_sigma_frac, size=(n_steps, 3))

    omega_true_z = math.radians(float(tumble_deg_s)) * scen.omega_factor
    q_init = quat_from_z_angle(theta0_rad)
    _, _, n_cap_init = capture_point_kinematics_lvlh(q_init, np.array([0.0, 0.0, omega_true_z]), rho_cap_body)
    chaser_pos_init = n_cap_init * cfg.chaser_start_distance_m + pos_init_noise
    truth = TruthState(0.0, np.concatenate([chaser_pos_init, vel_init_noise]), q_init, np.array([0.0, 0.0, omega_true_z]))

    eff_pos_sigma = 0.0 if deterministic_zero_noise else (vision_sigma_m * scen.vision_pos_scale)
    eff_ang_sigma = 0.0 if deterministic_zero_noise else scen.vision_angle_sigma_rad
    estimator = RPOEstimator(
        init_pos_est=chaser_pos_init + eff_pos_sigma * vis_pos_noise_seq[0],
        init_vel_est=np.zeros(3, dtype=float),
        init_theta_est=wrap_pi(theta0_rad + eff_ang_sigma * vis_ang_noise_seq[0]),
        init_omega_est=0.0,
        vision_pos_sigma_m=max(eff_pos_sigma, 1e-4),
        vision_angle_sigma_rad=max(eff_ang_sigma, 1e-4),
    )

    beacon_queue: List[BeaconPacket] = []
    beacon_step_interval = max(1, int(round(1.0 / (max(beacon_rate_hz, 1e-6) * cfg.dt_s)))) if beacon_rate_hz > 0 else 999999

    min_clearance_m = float(np.linalg.norm(truth.chaser_state_lvlh[:3]))
    delta_v_mps = 0.0
    dwell_accum_s = 0.0
    in_terminal_phase = False
    pred_errors_m: List[float] = []
    status, terminal_pass, aborted, unsafe, rel_speed_final, elapsed_s = "TIMEOUT", False, False, False, 0.0, 0.0

    for k in range(1, n_steps):
        t_s = k * cfg.dt_s
        elapsed_s = t_s
        _, _, n_cap_true = capture_point_kinematics_lvlh(truth.target_quat_bl, truth.target_omega_body, rho_cap_body)
        obs = sense_target_with_noise_and_occlusion(
            truth.chaser_state_lvlh[:3], truth.target_quat_bl, n_cap_true,
            eff_pos_sigma, eff_ang_sigma, scen.vision_dropout_prob, cfg.fov_occlusion_cos_limit,
            float(vis_uniform_seq[k]), vis_pos_noise_seq[k], float(vis_ang_noise_seq[k]), deterministic_zero_noise
        )
        if obs is not None:
            estimator.update_vision(obs[0], obs[1], max(eff_pos_sigma, 1e-4), max(eff_ang_sigma, 1e-4))

        pkt = generate_beacon_packet_if_due(
            k, t_s, beacon_step_interval, scen.beacon_enabled, scen.beacon_has_rate,
            beacon_packet_loss, latency_s, float(truth.target_omega_body[2]), cfg.gyro_noise_rad_s,
            float(beacon_uniform_seq[k]), float(beacon_gyro_noise_seq[k]), deterministic_zero_noise
        )
        if pkt is not None:
            beacon_queue.append(pkt)

        rem_q: List[BeaconPacket] = []
        for p in beacon_queue:
            if p.arrival_time_s <= t_s + 1e-9:
                estimator.update_beacon_packet(p, t_s, 0.0 if deterministic_zero_noise else cfg.gyro_noise_rad_s)
            else:
                rem_q.append(p)
        beacon_queue = rem_q

        if t_s >= 4.0:
            cp_hat, _, _ = estimator.predict_capture_point(cfg.prediction_horizon_s, rho_cap_body)
            q_fut, w_fut = propagate_attitude_rk4(truth.target_quat_bl, truth.target_omega_body, cfg.prediction_horizon_s, inertia_diag)
            cp_true, _, _ = capture_point_kinematics_lvlh(q_fut, w_fut, rho_cap_body)
            pred_errors_m.append(float(np.linalg.norm(cp_hat - cp_true)))

        a_cmd, in_terminal_phase, abort_trig, abort_reason = compute_guidance_command(
            estimator, cfg, rho_cap_body, t_s, delta_v_mps, in_terminal_phase
        )
        if abort_trig:
            aborted, status = True, abort_reason
            delta_v_mps += 0.08
            _, v_cap_true, _ = capture_point_kinematics_lvlh(truth.target_quat_bl, truth.target_omega_body, rho_cap_body)
            rel_speed_final = float(np.linalg.norm(truth.chaser_state_lvlh[3:] - v_cap_true))
            break

        a_applied = a_cmd * (1.0 + thruster_noise_seq[k])
        if float(np.linalg.norm(a_applied)) > cfg.a_max_mps2:
            a_applied = a_applied * (cfg.a_max_mps2 / float(np.linalg.norm(a_applied)))
        delta_v_mps += float(np.linalg.norm(a_applied)) * cfg.dt_s

        truth.chaser_state_lvlh = propagate_cw_rk4(truth.chaser_state_lvlh, a_applied, cfg.dt_s)
        truth.target_quat_bl, truth.target_omega_body = propagate_attitude_rk4(truth.target_quat_bl, truth.target_omega_body, cfg.dt_s, inertia_diag)
        truth.t_s = t_s
        estimator.predict(cfg.dt_s, a_cmd)

        min_clearance_m = min(min_clearance_m, float(np.linalg.norm(truth.chaser_state_lvlh[:3])))
        r_cap_true, v_cap_true, n_cap_true = capture_point_kinematics_lvlh(truth.target_quat_bl, truth.target_omega_body, rho_cap_body)
        terminal_pass, unsafe, dwell_accum_s, rel_speed_final = check_truth_terminal_or_unsafe(
            truth.chaser_state_lvlh[:3], truth.chaser_state_lvlh[3:], r_cap_true, v_cap_true, n_cap_true, dwell_accum_s, cfg
        )
        if unsafe:
            status = "UNSAFE_KEEPOUT_VIOLATION"
            break
        if terminal_pass:
            status = "TERMINAL_CAPTURE_WINDOW_MET"
            break

    return {
        "scenario": scenario_name,
        "seed": int(seed),
        "tumble_deg_s": float(tumble_deg_s),
        "vision_sigma_m": float(vision_sigma_m),
        "beacon_enabled": bool(scen.beacon_enabled),
        "beacon_packet_loss": float(beacon_packet_loss if scen.beacon_enabled else 1.0),
        "beacon_rate_hz": float(beacon_rate_hz if scen.beacon_enabled else 0.0),
        "latency_s": float(latency_s if scen.beacon_enabled else 0.0),
        "theta0_rad": float(theta0_rad),
        "status": str(status),
        "terminal_pass": bool(terminal_pass),
        "aborted": bool(aborted),
        "unsafe": bool(unsafe),
        "minimum_clearance_m": float(min_clearance_m),
        "capture_point_error_m": float(np.mean(pred_errors_m)) if pred_errors_m else 0.0,
        "relative_speed_mps": float(rel_speed_final),
        "delta_v_mps": float(delta_v_mps),
        "elapsed_s": float(elapsed_s),
        "model_version": MODEL_VERSION,
        "config_hash": cfg.config_hash(),
    }
