"""Single independent deterministic/stochastic closed-loop RPO simulation run (Section 12).

Randomness design
-----------------
All random inputs of a run are drawn *before* the scenario is applied, by
``sample_run_draws(seed, master_seed, n_steps)``. The draws do not depend on the
scenario or on any noise level: they are unit-scale standard normals and
uniforms, which the simulation rescales with the scenario/config sigmas. Hence:

* C0/C1/C2/C3 with the same seed face the same initial state, tumble axis,
  sensor-noise realisation and thruster errors (paired seeds, Handbook 4/10).
* Each subsystem has its own independent stream (``SeedSequence.spawn``), so
  adding a draw to one subsystem never shifts the random numbers of another.
* ``(master_seed, seed)`` alone reproduces a run exactly.
"""
from dataclasses import dataclass, replace
import math
from typing import Dict, List, Optional
import numpy as np
from .attitude import capture_point_kinematics_lvlh, propagate_attitude_rk4, quat_from_z_angle, wrap_pi
from .beacon import BeaconPacket, generate_beacon_packet_if_due
from .config import MODEL_VERSION, SCENARIOS, SimConfig
from .dynamics import propagate_cw_rk4
from .estimator import RPOEstimator
from .guidance import compute_guidance_command, compute_retreat_command
from .safety import check_truth_terminal_or_unsafe
from .sensors import sense_target_with_noise_and_occlusion

# Columns mandated by Handbook Section 12, in order. Extra diagnostics follow them.
CORE_COLUMNS = (
    "scenario", "seed", "tumble_deg_s", "vision_sigma_m", "beacon_enabled",
    "beacon_packet_loss", "beacon_rate_hz", "latency_s", "theta0_rad",
    "status", "terminal_pass", "aborted", "unsafe", "minimum_clearance_m",
    "capture_point_error_m", "relative_speed_mps", "delta_v_mps",
    "elapsed_s", "model_version", "config_hash",
)


@dataclass
class TruthState:
    t_s: float
    chaser_state_lvlh: np.ndarray
    target_quat_bl: np.ndarray
    target_omega_body: np.ndarray


@dataclass(frozen=True)
class RunDraws:
    """Every random number one run consumes, in unit scale (N(0,1) or U(0,1))."""
    theta0_u: float                  # U(0,1) -> initial client attitude angle
    chaser_pos_n: np.ndarray         # (3,) initial servicer position offset
    chaser_vel_n: np.ndarray         # (3,) initial servicer velocity offset
    tumble_tilt_n: np.ndarray        # (2,) spin-axis tilt about body x/y
    inertia_n: np.ndarray            # (3,) client inertia uncertainty
    thruster_gain_n: np.ndarray      # (3,) per-axis thrust gain bias
    thruster_misalign_n: np.ndarray  # (3,) thrust-vector misalignment rotation vector
    vis_uniform: np.ndarray          # (n,) camera dropout draws
    vis_pos_n: np.ndarray            # (n, 3) camera position noise
    vis_ang_n: np.ndarray            # (n,) camera attitude-angle noise
    beacon_uniform: np.ndarray       # (n,) packet-loss draws
    beacon_gyro_n: np.ndarray        # (n,) beacon rate-sensor noise
    thruster_n: np.ndarray           # (n, 3) per-step thrust execution noise

    @staticmethod
    def zero(n_steps: int) -> "RunDraws":
        """Noise-free draws: no dispersion, no dropouts, theta0 = 0."""
        return RunDraws(
            0.5, np.zeros(3), np.zeros(3), np.zeros(2), np.zeros(3), np.zeros(3), np.zeros(3),
            np.ones(n_steps), np.zeros((n_steps, 3)), np.zeros(n_steps),
            np.ones(n_steps), np.zeros(n_steps), np.zeros((n_steps, 3)),
        )


def sample_run_draws(seed: int, master_seed: int, n_steps: int) -> RunDraws:
    """Draw all random inputs for one run from independent per-subsystem streams."""
    root = np.random.SeedSequence(entropy=[int(master_seed), int(seed)])
    initial, target, vision, beacon, thruster = (np.random.default_rng(s) for s in root.spawn(5))
    return RunDraws(
        theta0_u=float(target.uniform()),
        chaser_pos_n=initial.standard_normal(3),
        chaser_vel_n=initial.standard_normal(3),
        tumble_tilt_n=target.standard_normal(2),
        inertia_n=target.standard_normal(3),
        thruster_gain_n=thruster.standard_normal(3),
        thruster_misalign_n=thruster.standard_normal(3),
        vis_uniform=vision.uniform(size=n_steps),
        vis_pos_n=vision.standard_normal((n_steps, 3)),
        vis_ang_n=vision.standard_normal(n_steps),
        beacon_uniform=beacon.uniform(size=n_steps),
        beacon_gyro_n=beacon.standard_normal(n_steps),
        thruster_n=thruster.standard_normal((n_steps, 3)),
    )


def rotation_from_rotvec(rotvec: np.ndarray) -> np.ndarray:
    """Rodrigues formula: rotation matrix for a rotation vector (axis * angle)."""
    angle = float(np.linalg.norm(rotvec))
    if angle < 1e-15:
        return np.eye(3)
    kx, ky, kz = rotvec / angle
    k_mat = np.array([[0.0, -kz, ky], [kz, 0.0, -kx], [-ky, kx, 0.0]])
    return np.eye(3) + math.sin(angle) * k_mat + (1.0 - math.cos(angle)) * (k_mat @ k_mat)


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
    trajectory: Optional[List[Dict[str, object]]] = None,
    master_seed: int = 0,
    omega_factor_override: Optional[float] = None,
) -> Dict[str, object]:
    """``omega_factor_override`` replaces the tier's spin factor (used to couple a physical IOS detumble); None keeps the tier value."""
    if scenario_name not in SCENARIOS:
        raise ValueError(f"unknown scenario: {scenario_name}")
    for name, value in (("seed", seed), ("master_seed", master_seed)):
        if isinstance(value, bool) or not isinstance(value, (int, np.integer)) or value < 0:
            raise ValueError(f"{name} must be a nonnegative integer")
    for name, value in (("tumble_deg_s", tumble_deg_s), ("vision_sigma_m", vision_sigma_m),
                        ("beacon_rate_hz", beacon_rate_hz), ("latency_s", latency_s)):
        if not math.isfinite(value) or value < 0:
            raise ValueError(f"{name} must be finite and nonnegative")
    if not math.isfinite(beacon_packet_loss) or not 0 <= beacon_packet_loss <= 1:
        raise ValueError("beacon_packet_loss must be in [0, 1]")
    beacon_step_interval = 0
    if beacon_rate_hz > 0:
        interval = 1.0 / (beacon_rate_hz * cfg.dt_s)
        if interval < 1 or not math.isclose(interval, round(interval), abs_tol=1e-9):
            raise ValueError("beacon period must be an integer multiple of dt_s; reduce dt_s")
        beacon_step_interval = int(round(interval))
    scen = SCENARIOS[scenario_name]
    n_steps = int(round(cfg.max_duration_s / cfg.dt_s))
    rho_cap_body = np.array(cfg.capture_offset_body_m, dtype=float)
    draws = RunDraws.zero(n_steps) if deterministic_zero_noise else sample_run_draws(seed, master_seed, n_steps)

    # --- Scale unit draws into physical dispersions --------------------------
    theta0_rad = 0.0 if deterministic_zero_noise else -math.pi + 2.0 * math.pi * draws.theta0_u
    pos_init_noise = cfg.chaser_pos_disp_sigma_m * draws.chaser_pos_n
    vel_init_noise = cfg.chaser_vel_disp_sigma_mps * draws.chaser_vel_n
    tilt_xy = cfg.tumble_axis_tilt_sigma_rad * draws.tumble_tilt_n
    tilt_rad = float(np.linalg.norm(tilt_xy))
    tilt_az = math.atan2(tilt_xy[1], tilt_xy[0]) if tilt_rad > 0 else 0.0
    tumble_axis = np.array([math.sin(tilt_rad) * math.cos(tilt_az), math.sin(tilt_rad) * math.sin(tilt_az), math.cos(tilt_rad)])
    inertia_diag = np.array(cfg.inertia_diag_kgm2, dtype=float) * np.clip(1.0 + cfg.inertia_sigma_frac * draws.inertia_n, 0.5, 1.5)
    thrust_gain = 1.0 + cfg.thruster_scale_sigma_frac * draws.thruster_gain_n
    misalign_rotvec = cfg.thruster_misalign_sigma_rad * draws.thruster_misalign_n
    thrust_misalign = rotation_from_rotvec(misalign_rotvec)

    omega_factor = scen.omega_factor if omega_factor_override is None else float(omega_factor_override)
    if not math.isfinite(omega_factor) or omega_factor < 0:
        raise ValueError("omega_factor_override must be finite and nonnegative")
    omega_true = math.radians(float(tumble_deg_s)) * omega_factor * tumble_axis
    q_init = quat_from_z_angle(theta0_rad)
    _, _, n_cap_init = capture_point_kinematics_lvlh(q_init, omega_true, rho_cap_body)
    chaser_pos_init = n_cap_init * cfg.chaser_start_distance_m + pos_init_noise
    truth = TruthState(0.0, np.concatenate([chaser_pos_init, vel_init_noise]), q_init, omega_true.copy())

    eff_pos_sigma = 0.0 if deterministic_zero_noise else (vision_sigma_m * scen.vision_pos_scale)
    eff_ang_sigma = 0.0 if deterministic_zero_noise else scen.vision_angle_sigma_rad
    estimator = RPOEstimator(
        init_pos_est=chaser_pos_init + eff_pos_sigma * draws.vis_pos_n[0],
        init_vel_est=np.zeros(3, dtype=float),
        init_theta_est=wrap_pi(theta0_rad + eff_ang_sigma * draws.vis_ang_n[0]),
        init_omega_est=0.0,
        vision_pos_sigma_m=max(eff_pos_sigma, 1e-4),
        vision_angle_sigma_rad=max(eff_ang_sigma, 1e-4),
        cfg=cfg,
    )

    beacon_queue: List[BeaconPacket] = []
    beacon_active = scen.beacon_enabled and beacon_step_interval > 0
    gyro_sigma = 0.0 if deterministic_zero_noise else cfg.gyro_noise_rad_s
    retreat_steps = int(round(cfg.retreat_duration_s / cfg.dt_s))
    extension = RunDraws.zero(retreat_steps) if deterministic_zero_noise else sample_run_draws(
        seed, master_seed + 2**64, retreat_steps)
    draws = replace(draws, **{
        field: np.concatenate([getattr(draws, field), getattr(extension, field)])
        for field in ("vis_uniform", "vis_pos_n", "vis_ang_n", "beacon_uniform", "beacon_gyro_n", "thruster_n")
    })

    min_clearance_m = float(np.linalg.norm(truth.chaser_state_lvlh[:3])) - cfg.keepout_radius_m
    delta_v_mps = 0.0
    dwell_accum_s = 0.0
    in_terminal_phase = False
    terminal_phase_entry_s = float("nan")
    pred_errors_m: List[float] = []
    vision_updates, rate_updates, steps_run = 0, 0, 0
    status, terminal_pass, aborted, unsafe, rel_speed_final, elapsed_s = "TIMEOUT", False, False, False, 0.0, 0.0

    abort_reason_saved = ""
    abort_time_s = float("nan")
    abort_delta_v_mps = 0.0
    retreat_complete = False
    retreat_reference = np.zeros(3)
    retreat_status = "NOT_REQUIRED"
    initial_unsafe = min_clearance_m < 0

    for k in range(n_steps + retreat_steps):
        if initial_unsafe:
            unsafe, status = True, "UNSAFE_KEEPOUT_VIOLATION"
            break
        if not aborted and k >= n_steps:
            break
        if aborted and k * cfg.dt_s - abort_time_s >= cfg.retreat_duration_s - 1e-9:
            if retreat_status == "IN_PROGRESS":
                retreat_status = "TIMEOUT"
            break
        t_s = k * cfg.dt_s
        elapsed_s = t_s
        steps_run = k + 1
        # --- Sense (truth -> noisy measurement) ------------------------------
        _, _, n_cap_true = capture_point_kinematics_lvlh(truth.target_quat_bl, truth.target_omega_body, rho_cap_body)
        obs = sense_target_with_noise_and_occlusion(
            truth.chaser_state_lvlh[:3], truth.target_quat_bl, n_cap_true,
            eff_pos_sigma, eff_ang_sigma, scen.vision_dropout_prob, cfg.fov_occlusion_cos_limit,
            float(draws.vis_uniform[k]), draws.vis_pos_n[k], float(draws.vis_ang_n[k]), deterministic_zero_noise
        )
        # Index zero already supplied the initial noisy pose observation.
        if obs is not None and k > 0:
            estimator.update_vision(obs[0], obs[1], max(eff_pos_sigma, 1e-4), max(eff_ang_sigma, 1e-4))
            vision_updates += 1

        pkt = generate_beacon_packet_if_due(
            k, t_s, max(beacon_step_interval, 1), beacon_active and k > 0, scen.beacon_has_rate,
            beacon_packet_loss, latency_s, float(truth.target_omega_body[2]), gyro_sigma,
            float(draws.beacon_uniform[k]), float(draws.beacon_gyro_n[k]), deterministic_zero_noise
        )
        if pkt is not None:
            beacon_queue.append(pkt)

        # --- Estimate: assimilate packets whose arrival time has passed -------
        rem_q: List[BeaconPacket] = []
        for p in beacon_queue:
            if p.arrival_time_s <= t_s + 1e-9:
                estimator.update_beacon_packet(p, t_s, gyro_sigma)
                rate_updates += int(p.has_rate)
            else:
                rem_q.append(p)
        beacon_queue = rem_q

        # Scoring only: compare predicted vs true future capture point over the
        # pre-gate characterisation window so all tiers are scored without survival bias.
        if cfg.prediction_metric_start_s <= t_s <= cfg.rate_gate_start_s:
            cp_hat, _, _ = estimator.predict_capture_point(cfg.prediction_horizon_s, rho_cap_body)
            q_fut, w_fut = propagate_attitude_rk4(truth.target_quat_bl, truth.target_omega_body, cfg.prediction_horizon_s, inertia_diag)
            cp_true, _, _ = capture_point_kinematics_lvlh(q_fut, w_fut, rho_cap_body)
            pred_errors_m.append(float(np.linalg.norm(cp_hat - cp_true)))

        # --- Guide & control (estimate only; never truth) --------------------
        if not aborted:
            a_cmd, in_terminal_phase, abort_trig, abort_reason = compute_guidance_command(
                estimator, cfg, rho_cap_body, t_s, delta_v_mps, in_terminal_phase
            )
            if in_terminal_phase and math.isnan(terminal_phase_entry_s):
                terminal_phase_entry_s = t_s
            if abort_trig:
                aborted, status = True, abort_reason
                abort_reason_saved, abort_time_s, abort_delta_v_mps = abort_reason, t_s, delta_v_mps
                retreat_status = "IN_PROGRESS"
                direction = estimator.s_hat[:3]
                norm = float(np.linalg.norm(direction))
                retreat_reference = cfg.chaser_start_distance_m * direction / max(norm, 1e-12)
                if norm < 1e-12:
                    retreat_reference = np.array([cfg.chaser_start_distance_m, 0.0, 0.0])
        if aborted:
            a_cmd = compute_retreat_command(estimator, cfg, retreat_reference)

        # --- Actuate: gain bias, misalignment and execution noise -------------
        a_applied = thrust_misalign @ (a_cmd * (thrust_gain + cfg.thruster_noise_sigma_frac * draws.thruster_n[k]))
        if float(np.linalg.norm(a_applied)) > cfg.a_max_mps2:
            a_applied = a_applied * (cfg.a_max_mps2 / float(np.linalg.norm(a_applied)))
        if aborted:
            reserve = max(0.0, cfg.retreat_delta_v_reserve_mps - (delta_v_mps - abort_delta_v_mps))
            scale = min(1.0, reserve / max(float(np.linalg.norm(a_applied)) * cfg.dt_s, 1e-12))
            a_applied *= scale
            a_cmd *= scale
        delta_v_mps += float(np.linalg.norm(a_applied)) * cfg.dt_s

        # --- Propagate truth and the estimator's prediction ------------------
        truth.chaser_state_lvlh = propagate_cw_rk4(truth.chaser_state_lvlh, a_applied, cfg.dt_s)
        truth.target_quat_bl, truth.target_omega_body = propagate_attitude_rk4(truth.target_quat_bl, truth.target_omega_body, cfg.dt_s, inertia_diag)
        truth.t_s = (k + 1) * cfg.dt_s
        elapsed_s = truth.t_s
        estimator.predict(cfg.dt_s, a_cmd)

        # --- Score against truth ---------------------------------------------
        clearance_m = float(np.linalg.norm(truth.chaser_state_lvlh[:3])) - cfg.keepout_radius_m
        min_clearance_m = min(min_clearance_m, clearance_m)
        r_cap_true, v_cap_true, n_cap_true = capture_point_kinematics_lvlh(truth.target_quat_bl, truth.target_omega_body, rho_cap_body)
        terminal_pass, unsafe, dwell_accum_s, rel_speed_final = check_truth_terminal_or_unsafe(
            truth.chaser_state_lvlh[:3], truth.chaser_state_lvlh[3:], r_cap_true, v_cap_true, n_cap_true, dwell_accum_s, cfg
        )
        if aborted:
            terminal_pass, dwell_accum_s = False, 0.0
            # Completion is commanded using estimates; truth is only used to score that decision.
            estimated_settled = (np.linalg.norm(estimator.s_hat[:3] - retreat_reference) <= cfg.retreat_position_tol_m
                                 and np.linalg.norm(estimator.s_hat[3:]) <= cfg.retreat_speed_tol_mps)
            if estimated_settled:
                retreat_complete = bool(np.linalg.norm(truth.chaser_state_lvlh[:3] - retreat_reference) <= cfg.retreat_position_tol_m
                                        and np.linalg.norm(truth.chaser_state_lvlh[3:]) <= cfg.retreat_speed_tol_mps)
                retreat_status = "COMPLETE" if retreat_complete else "ESTIMATE_MISMATCH"
            elif delta_v_mps - abort_delta_v_mps >= cfg.retreat_delta_v_reserve_mps - 1e-9:
                retreat_status = "RESERVE_EXHAUSTED"
        if trajectory is not None:
            trajectory.append({
                "time_s": elapsed_s,
                **{f"{axis}_m": float(truth.chaser_state_lvlh[i]) for i, axis in enumerate("xyz")},
                **{f"capture_{axis}_m": float(r_cap_true[i]) for i, axis in enumerate("xyz")},
                **{f"est_{axis}_m": float(estimator.s_hat[i]) for i, axis in enumerate("xyz")},
                "position_error_m": float(np.linalg.norm(truth.chaser_state_lvlh[:3] - r_cap_true)),
                "relative_speed_mps": rel_speed_final,
                "clearance_m": clearance_m,
                "acceleration_mps2": float(np.linalg.norm(a_applied)),
                "delta_v_mps": delta_v_mps,
                "terminal_phase": in_terminal_phase and not aborted,
                "retreat_phase": aborted,
                "dwell_s": dwell_accum_s,
                "angle_std_rad": estimator.angle_std_rad,
                "rate_est_deg_s": math.degrees(float(estimator.att_hat[1])),
                "rate_true_deg_s": math.degrees(float(truth.target_omega_body[2])),
            })
        if unsafe:
            status = "UNSAFE_KEEPOUT_VIOLATION"
            if aborted:
                retreat_status = "UNSAFE"
            break
        if aborted and retreat_status in {"COMPLETE", "ESTIMATE_MISMATCH"}:
            break
        if terminal_pass:
            status = "TERMINAL_CAPTURE_WINDOW_MET"
            break

    row: Dict[str, object] = {
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
        "aborted": bool(aborted and not unsafe),
        "unsafe": bool(unsafe),
        "minimum_clearance_m": float(min_clearance_m),
        "capture_point_error_m": float(np.sqrt(np.mean(np.square(pred_errors_m)))) if pred_errors_m else float("nan"),
        "relative_speed_mps": float(rel_speed_final),
        "delta_v_mps": float(delta_v_mps),
        "elapsed_s": float(elapsed_s),
        "model_version": MODEL_VERSION,
        "config_hash": cfg.config_hash(),
        # --- Diagnostics beyond the Handbook schema ---------------------------
        "master_seed": int(master_seed),
        "abort_triggered": bool(aborted),
        "abort_reason": abort_reason_saved,
        "abort_time_s": abort_time_s if aborted else None,
        "retreat_status": retreat_status,
        "retreat_complete": bool(retreat_complete and not unsafe),
        "retreat_elapsed_s": max(0.0, elapsed_s - abort_time_s) if aborted else 0.0,
        "approach_delta_v_mps": float(abort_delta_v_mps if aborted else delta_v_mps),
        "retreat_delta_v_mps": float(delta_v_mps - abort_delta_v_mps) if aborted else 0.0,
        "propellant_kg": cfg.propellant_kg(delta_v_mps),
        "terminal_phase_entry_s": terminal_phase_entry_s,
        "vision_update_fraction": vision_updates / max(steps_run - 1, 1),
        "beacon_rate_updates": int(rate_updates),
        "final_angle_std_deg": math.degrees(estimator.angle_std_rad),
        "final_rate_error_deg_s": math.degrees(abs(float(estimator.att_hat[1]) - float(truth.target_omega_body[2]))),
        "init_offset_m": float(np.linalg.norm(pos_init_noise)),
        "init_speed_mps": float(np.linalg.norm(vel_init_noise)),
        "tumble_axis_tilt_deg": math.degrees(tilt_rad),
        "thruster_gain_error_pct": 100.0 * float(np.sqrt(np.mean(np.square(thrust_gain - 1.0)))),
        "thruster_misalign_deg": math.degrees(float(np.linalg.norm(misalign_rotvec))),
    }
    return row
