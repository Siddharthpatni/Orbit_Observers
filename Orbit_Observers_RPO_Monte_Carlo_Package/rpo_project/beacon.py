"""Independent Service Beacon model with timestamps, Bernoulli packet loss, and latency (Section 8)."""
from dataclasses import dataclass
from typing import Optional

@dataclass
class BeaconPacket:
    timestamp_s: float
    arrival_time_s: float
    authenticated_id: str
    has_rate: bool
    omega_z_rad_s: Optional[float]

def generate_beacon_packet_if_due(
    step_k: int,
    t_s: float,
    step_interval: int,
    beacon_enabled: bool,
    beacon_has_rate: bool,
    packet_loss_prob: float,
    latency_s: float,
    true_omega_z: float,
    gyro_sigma: float,
    u_draw: float,
    gyro_noise_draw: float,
    deterministic_zero_noise: bool = False,
) -> Optional[BeaconPacket]:
    if (not beacon_enabled) or (step_k % step_interval != 0):
        return None
    if u_draw < packet_loss_prob and not deterministic_zero_noise:
        return None
    meas_omega = float(true_omega_z + (0.0 if deterministic_zero_noise else gyro_sigma) * gyro_noise_draw)
    return BeaconPacket(
        timestamp_s=t_s,
        arrival_time_s=t_s + max(0.0, latency_s),
        authenticated_id="GEO-CLIENT-01",
        has_rate=beacon_has_rate,
        omega_z_rad_s=meas_omega if beacon_has_rate else None,
    )
