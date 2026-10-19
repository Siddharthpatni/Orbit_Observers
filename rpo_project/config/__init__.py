"""Units, scenario variants, and explicit model assumptions (Handbook Sections 4, 5, 6, 12).

Every number that influences a simulation outcome lives in this module, so that
it is visible, documented and covered by ``config_hash()``. All values are
illustrative study assumptions, not measured ClearSpace hardware data.

Units: SI throughout (m, s, kg, rad). Angles are radians in code; degrees appear
only in names that end in ``_deg``.
"""
from dataclasses import dataclass, asdict
import hashlib
import json
import math
from typing import Dict, Tuple

MODEL_VERSION = "Phase2-RPO-MC-v4.1"
MU_EARTH_M3_S2: float = 3.986004418e14
A_GEO_M: float = 42164.0e3
N_GEO_RAD_S: float = math.sqrt(MU_EARTH_M3_S2 / (A_GEO_M ** 3))
G0_MPS2: float = 9.80665


@dataclass(frozen=True)
class SimConfig:
    # --- Time ---------------------------------------------------------------
    dt_s: float = 0.25
    max_duration_s: float = 120.0
    prediction_horizon_s: float = 2.0          # capture-point prediction look-ahead
    prediction_metric_start_s: float = 1.0     # evaluate prediction over [1.0 s, rate_gate_start_s]

    # --- Client (target) geometry -------------------------------------------
    target_mass_kg: float = 3500.0
    inertia_diag_kgm2: Tuple[float, float, float] = (2400.0, 2800.0, 3100.0)
    capture_offset_body_m: Tuple[float, float, float] = (1.5, 0.0, 0.0)
    keepout_radius_m: float = 1.35
    hold_distance_m: float = 4.0

    # --- Servicer (chaser) ----------------------------------------------------
    chaser_start_distance_m: float = 12.0
    a_max_mps2: float = 0.040
    servicer_mass_kg: float = 500.0            # illustrative, for delta-v -> propellant only
    servicer_isp_s: float = 220.0              # illustrative monopropellant Isp

    # --- Monte Carlo dispersions (randomised in every run, 1-sigma) ---------
    chaser_pos_disp_sigma_m: float = 0.50
    chaser_vel_disp_sigma_mps: float = 0.015
    thruster_noise_sigma_frac: float = 0.02         # per-step, per-axis execution noise
    thruster_scale_sigma_frac: float = 0.02         # per-run, per-axis gain bias
    thruster_misalign_sigma_rad: float = math.radians(0.5)  # per-run thrust-vector misalignment
    tumble_axis_tilt_sigma_rad: float = math.radians(2.0)   # spin-axis tilt from body z (nutation)
    inertia_sigma_frac: float = 0.05                # per-axis uncertainty of the true client inertia

    # --- Navigation sensors ---------------------------------------------------
    gyro_noise_rad_s: float = math.radians(0.08)    # beacon rate-sensor noise
    fov_occlusion_cos_limit: float = -0.35          # fiducials hidden when viewed from behind

    # --- Estimator tuning -----------------------------------------------------
    est_min_pos_sigma_m: float = 0.05
    est_init_vel_sigma_mps: float = 0.03
    est_min_angle_sigma_rad: float = math.radians(1.0)
    est_init_rate_sigma_rad_s: float = math.radians(3.0)
    est_pos_process_noise_mps: float = 0.005
    est_vel_process_noise_mps15: float = 0.003
    est_rate_process_noise_rad_s15: float = math.radians(0.015)

    # --- Guidance ---------------------------------------------------------------
    controller: str = "braking_pd"
    kp_pos: float = 0.085
    kd_vel: float = 0.420
    max_closing_speed_mps: float = 0.30
    braking_accel_fraction: float = 0.50
    terminal_entry_min_time_s: float = 8.0          # hold at least this long before closing in
    terminal_entry_pos_tol_m: float = 1.25
    terminal_entry_max_angle_std_rad: float = math.radians(8.0)
    corridor_check_radius_m: float = 2.8            # corridor checked inside this range
    corridor_half_angle_rad: float = math.radians(55.0)
    corridor_max_angle_std_rad: float = math.radians(10.0)
    flyaround_cos_limit: float = 0.15               # wrong side of the client -> fly around
    flyaround_extra_radius_m: float = 1.5
    flyaround_tangent_offset_m: float = 2.5
    barrier_radius_m: float = 1.48                  # repulsive barrier starts here
    barrier_gain_mps2: float = 0.06
    barrier_scale_m: float = 0.15
    terminal_pos_std_thresh_m: float = 0.020        # pos-sigma threshold for covariance-aware margin
    terminal_standoff_gain: float = 1.65            # radial capture standoff per excess pos-sigma
    terminal_standoff_max_m: float = 0.065          # max radial capture standoff (within 0.20 m window)
    barrier_pos_std_gain: float = 2.5               # barrier inflation per excess pos-sigma
    corot_rate_conf_sigma_rad_s: float = math.radians(0.05)  # rate-std scale for co-rotation shaping
    corot_far_gain: float = 0.55                    # far-range tangential speed reduction when rate known
    corot_far_span_m: float = 5.0                   # range span outside hold sphere for co-rotation ramp

    # --- Safety / abort gates -------------------------------------------------
    max_safe_target_omega_rad_s: float = math.radians(3.25)
    rate_gate_start_s: float = 10.0
    max_allowed_angle_std_rad: float = math.radians(18.0)
    covariance_gate_start_s: float = 12.0
    max_delta_v_mps: float = 2.50             # approach budget; retreat reserve is separate
    max_allowed_position_std_m: float = 0.30
    retreat_duration_s: float = 120.0         # maximum additional time after abort
    retreat_delta_v_reserve_mps: float = 1.50
    retreat_position_tol_m: float = 0.25
    retreat_speed_tol_mps: float = 0.055

    # --- Terminal capture window (NOT physical latch verification) ------------
    terminal_pos_tol_m: float = 0.20
    terminal_vel_tol_mps: float = 0.055
    terminal_align_tol_rad: float = math.radians(15.0)
    terminal_dwell_s: float = 2.0

    def __post_init__(self) -> None:
        if self.controller not in {"legacy_pd", "braking_pd"}:
            raise ValueError("controller must be legacy_pd or braking_pd")
        positive = ("dt_s", "max_duration_s", "prediction_horizon_s", "a_max_mps2",
                    "kp_pos", "kd_vel", "keepout_radius_m", "terminal_pos_tol_m",
                    "terminal_vel_tol_mps", "terminal_dwell_s", "max_delta_v_mps",
                    "max_closing_speed_mps", "servicer_mass_kg", "servicer_isp_s",
                    "barrier_scale_m", "est_min_pos_sigma_m", "est_min_angle_sigma_rad",
                    "max_allowed_position_std_m", "retreat_duration_s", "retreat_delta_v_reserve_mps",
                    "retreat_position_tol_m", "retreat_speed_tol_mps")
        for name in positive:
            value = getattr(self, name)
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be finite and positive")
        nonnegative = ("chaser_pos_disp_sigma_m", "chaser_vel_disp_sigma_mps",
                       "thruster_noise_sigma_frac", "thruster_scale_sigma_frac",
                       "thruster_misalign_sigma_rad", "tumble_axis_tilt_sigma_rad",
                       "inertia_sigma_frac", "gyro_noise_rad_s", "prediction_metric_start_s",
                       "terminal_entry_min_time_s", "rate_gate_start_s", "covariance_gate_start_s")
        for name in nonnegative:
            value = getattr(self, name)
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and nonnegative")
        if self.inertia_sigma_frac >= 0.2:
            raise ValueError("inertia_sigma_frac must be < 0.2 to keep sampled inertias positive")
        if not 0 < self.braking_accel_fraction <= 1:
            raise ValueError("braking_accel_fraction must be in (0, 1]")
        steps = self.max_duration_s / self.dt_s
        if steps < 1 or not math.isclose(steps, round(steps), abs_tol=1e-9):
            raise ValueError("max_duration_s must be a positive multiple of dt_s")
        retreat_steps = self.retreat_duration_s / self.dt_s
        if retreat_steps < 1 or not math.isclose(retreat_steps, round(retreat_steps), abs_tol=1e-9):
            raise ValueError("retreat_duration_s must be a positive multiple of dt_s")
        if len(self.inertia_diag_kgm2) != 3 or any(not math.isfinite(x) or x <= 0 for x in self.inertia_diag_kgm2):
            raise ValueError("inertia_diag_kgm2 must contain three positive finite values")
        if len(self.capture_offset_body_m) != 3 or any(not math.isfinite(x) for x in self.capture_offset_body_m):
            raise ValueError("capture_offset_body_m must contain three finite values")
        capture_radius = math.sqrt(sum(x*x for x in self.capture_offset_body_m))
        if not self.keepout_radius_m < capture_radius < self.hold_distance_m < self.chaser_start_distance_m:
            raise ValueError("geometry must satisfy keepout < capture radius < hold < start")

    def config_hash(self) -> str:
        """Short fingerprint of every model assumption, including scenario definitions."""
        payload = json.dumps({
            "model_version": MODEL_VERSION,
            "config": asdict(self),
            "scenarios": {name: asdict(spec) for name, spec in SCENARIOS.items()},
        }, sort_keys=True).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()[:10]

    def propellant_kg(self, delta_v_mps: float) -> float:
        """Rocket equation: propellant burned by a servicer of ``servicer_mass_kg``."""
        return self.servicer_mass_kg * (1.0 - math.exp(-delta_v_mps / (self.servicer_isp_s * G0_MPS2)))


@dataclass(frozen=True)
class ScenarioSpec:
    """One client-preparation tier. Only C3 changes the client's true motion."""
    name: str
    vision_angle_sigma_rad: float   # optical attitude-angle noise (1-sigma)
    vision_pos_scale: float         # multiplier on the study's optical position noise
    vision_dropout_prob: float      # chance a camera frame yields no pose
    beacon_enabled: bool            # Service Beacon present (identity at minimum)
    beacon_has_rate: bool           # beacon packets carry the client's angular rate
    omega_factor: float             # C3 IOS mode: client actively slows its own tumble


SCENARIOS: Dict[str, ScenarioSpec] = {
    "C0_unprepared": ScenarioSpec("C0_unprepared", math.radians(12.0), 2.5, 0.30, False, False, 1.0),
    "C1_fiducials": ScenarioSpec("C1_fiducials", math.radians(3.0), 1.0, 0.08, False, False, 1.0),
    "C2_id_only": ScenarioSpec("C2_id_only", math.radians(3.0), 1.0, 0.08, True, False, 1.0),
    "C2_beacon": ScenarioSpec("C2_beacon", math.radians(3.0), 1.0, 0.08, True, True, 1.0),
    "C3_ios_mode": ScenarioSpec("C3_ios_mode", math.radians(3.0), 1.0, 0.08, True, True, 0.05),
}
