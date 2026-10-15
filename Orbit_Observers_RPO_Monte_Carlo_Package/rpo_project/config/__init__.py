"""Units, scenario variants, and explicit model assumptions (Handbook Sections 4, 5, 6, 12)."""
from dataclasses import dataclass, asdict
import hashlib
import json
import math
from typing import Dict, Tuple

MODEL_VERSION = "Phase2-RPO-MC-v2.1"
MU_EARTH_M3_S2: float = 3.986004418e14
A_GEO_M: float = 42164.0e3
N_GEO_RAD_S: float = math.sqrt(MU_EARTH_M3_S2 / (A_GEO_M ** 3))

@dataclass(frozen=True)
class SimConfig:
    dt_s: float = 0.25
    max_duration_s: float = 120.0
    prediction_horizon_s: float = 2.0
    target_mass_kg: float = 3500.0
    inertia_diag_kgm2: Tuple[float, float, float] = (2400.0, 2800.0, 3100.0)
    capture_offset_body_m: Tuple[float, float, float] = (1.5, 0.0, 0.0)
    keepout_radius_m: float = 1.35
    hold_distance_m: float = 4.0
    chaser_start_distance_m: float = 12.0
    chaser_pos_disp_sigma_m: float = 0.50
    chaser_vel_disp_sigma_mps: float = 0.015
    a_max_mps2: float = 0.040
    thruster_noise_sigma_frac: float = 0.02
    kp_pos: float = 0.085
    kd_vel: float = 0.420
    gyro_noise_rad_s: float = math.radians(0.08)
    fov_occlusion_cos_limit: float = -0.35
    terminal_pos_tol_m: float = 0.20
    terminal_vel_tol_mps: float = 0.055
    terminal_align_tol_rad: float = math.radians(15.0)
    terminal_dwell_s: float = 2.0
    max_safe_target_omega_rad_s: float = math.radians(3.2)
    max_allowed_angle_std_rad: float = math.radians(18.0)
    max_delta_v_mps: float = 2.50

    def config_hash(self) -> str:
        payload = json.dumps(asdict(self), sort_keys=True).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()[:10]

@dataclass(frozen=True)
class ScenarioSpec:
    name: str
    vision_angle_sigma_rad: float
    vision_pos_scale: float
    vision_dropout_prob: float
    beacon_enabled: bool
    beacon_has_rate: bool
    omega_factor: float

SCENARIOS: Dict[str, ScenarioSpec] = {
    "C0_unprepared": ScenarioSpec("C0_unprepared", math.radians(12.0), 2.5, 0.30, False, False, 1.0),
    "C1_fiducials": ScenarioSpec("C1_fiducials", math.radians(3.0), 1.0, 0.08, False, False, 1.0),
    "C2_id_only": ScenarioSpec("C2_id_only", math.radians(3.0), 1.0, 0.08, True, False, 1.0),
    "C2_beacon": ScenarioSpec("C2_beacon", math.radians(3.0), 1.0, 0.08, True, True, 1.0),
    "C3_ios_mode": ScenarioSpec("C3_ios_mode", math.radians(3.0), 1.0, 0.08, True, True, 0.05),
}
