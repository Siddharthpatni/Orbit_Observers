"""Service Beacon engineering budget, main-bus isolation model, and IOS Mode state machine (Phase 2 Proposal §§3-5).

This module provides executable system-definition models and fault-injection
verification targets for the three non-RPO pillars of the Phase 2 study:

1. **IOS Mode & Docked Control State Machine** (`IOSStateMachine`):
   Implements the 8-state sequence (`NORMAL -> SERVICE_STANDBY -> APPROACH_PERMITTED
   -> IOS_HANDOVER -> MATED_SERVICING -> VERIFICATION -> RELEASE -> NORMAL`, plus
   `ABORT_SAFE`) with explicit authority guards, replay/stale-command rejection,
   acknowledgment timeout monitoring, and a strict single-authority invariant so
   client and servicer attitude controllers never fight each other.
2. **Active Client Detumbling Model** (`simulate_ios_detumbling`):
   Propagates 3-D Euler rigid-body attitude dynamics under bounded client rate-damping
   torques from 3-10 deg/s down to the 5% residual rate assumed by `C3_ios_mode`,
   quantifying angular momentum removed, detumbling duration, and client ACS propellant.
3. **Derated Service Beacon Power, Fault Isolation & Link Budget** (`evaluate_beacon_engineering_budget`):
   Extends the ideal 28.5 mW / 20.52 Wh load calculation with regulator efficiency,
   cold-temperature (-20 C), 15-year GEO aging/radiation, and depth-of-discharge
   derating, main-bus short/overvoltage fault isolation leakage, and a 401.5 MHz
   RF link budget. All figures are engineering model estimates pending bench testing (Milestone M3).
"""
from dataclasses import dataclass
from enum import Enum
import math
import hmac
from typing import Dict, List, Optional, Tuple
import numpy as np
from .attitude import propagate_attitude_rk4
from .config import G0_MPS2, SimConfig


class IOSState(str, Enum):
    NORMAL = "NORMAL"
    SERVICE_STANDBY = "SERVICE_STANDBY"
    APPROACH_PERMITTED = "APPROACH_PERMITTED"
    IOS_HANDOVER = "IOS_HANDOVER"
    MATED_SERVICING = "MATED_SERVICING"
    VERIFICATION = "VERIFICATION"
    RELEASE = "RELEASE"
    ABORT_SAFE = "ABORT_SAFE"


@dataclass(frozen=True)
class IOSCommand:
    target_state: IOSState
    sequence_id: int
    timestamp_s: float
    auth_token: str
    client_rate_deg_s: float = 0.0
    servicer_ack: bool = False
    client_ack: bool = False
    client_damping_passive: bool = False
    latch_confirmed: bool = False
    load_path_verified: bool = False
    connectors_isolated: bool = False
    separation_confirmed: bool = False


@dataclass(frozen=True)
class TransitionResult:
    accepted: bool
    previous_state: IOSState
    new_state: IOSState
    reason: str
    client_attitude_authority: bool
    servicer_stack_authority: bool


class IOSStateMachine:
    """Command-level model with fault guards, not cryptographic or physical handover validation.

    The fixed token is a simulation credential. Flight use requires a separate authenticated channel.
    """

    def __init__(
        self,
        expected_token: str = "CLEARSPACE-IOS-AUTH-V1",
        max_command_age_s: float = 5.0,
        ack_timeout_s: float = 10.0,
        max_handover_rate_deg_s: float = 3.25,
    ) -> None:
        if not isinstance(expected_token, str) or not expected_token:
            raise ValueError("expected_token must be a nonempty simulation credential")
        for name, value in (("max_command_age_s", max_command_age_s), ("ack_timeout_s", ack_timeout_s),
                            ("max_handover_rate_deg_s", max_handover_rate_deg_s)):
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be finite and positive")
        self.mated = False
        self._last_time_s = 0.0
        self.expected_token = expected_token
        self.max_command_age_s = max_command_age_s
        self.ack_timeout_s = ack_timeout_s
        self.max_handover_rate_deg_s = max_handover_rate_deg_s
        self.state: IOSState = IOSState.NORMAL
        self.last_sequence_id: int = 0
        self.last_valid_ack_time_s: float = 0.0
        self.history: List[TransitionResult] = []

    @property
    def client_attitude_authority(self) -> bool:
        """True when the client bus actively controls its own attitude."""
        if self.mated:
            return False
        return self.state in {
            IOSState.NORMAL,
            IOSState.SERVICE_STANDBY,
            IOSState.APPROACH_PERMITTED,
            IOSState.RELEASE,
            IOSState.ABORT_SAFE,
        }

    @property
    def servicer_stack_authority(self) -> bool:
        """True when the servicer has exclusive attitude authority or handover lock."""
        return self.mated or self.state in {
            IOSState.IOS_HANDOVER,
            IOSState.MATED_SERVICING,
            IOSState.VERIFICATION,
        }

    def check_authority_invariant(self) -> bool:
        """Single-authority invariant: client and servicer never fight each other."""
        return not (self.client_attitude_authority and self.servicer_stack_authority)

    def _record(self, accepted: bool, prev: IOSState, reason: str) -> TransitionResult:
        assert self.check_authority_invariant(), "authority conflict violated invariant"
        res = TransitionResult(
            accepted=accepted,
            previous_state=prev,
            new_state=self.state,
            reason=reason,
            client_attitude_authority=self.client_attitude_authority,
            servicer_stack_authority=self.servicer_stack_authority,
        )
        self.history.append(res)
        return res

    def _check_time(self, current_time_s: float) -> None:
        if not math.isfinite(current_time_s) or current_time_s < self._last_time_s:
            raise ValueError("current_time_s must be finite, nonnegative and monotonic")
        self._last_time_s = current_time_s

    def check_heartbeat(self, current_time_s: float) -> TransitionResult:
        """Check timeouts even when no command arrives; docked abort retains stack authority."""
        self._check_time(current_time_s)
        prev = self.state
        if self.state in {IOSState.APPROACH_PERMITTED, IOSState.IOS_HANDOVER,
                          IOSState.MATED_SERVICING, IOSState.VERIFICATION, IOSState.RELEASE}:
            if current_time_s - self.last_valid_ack_time_s > self.ack_timeout_s:
                self.state = IOSState.ABORT_SAFE
                return self._record(False, prev, "ACK_TIMEOUT_ABORT")
        return self._record(True, prev, "HEARTBEAT_OK")

    def step(self, cmd: IOSCommand, current_time_s: float) -> TransitionResult:
        prev = self.state
        heartbeat = self.check_heartbeat(current_time_s)
        if not heartbeat.accepted:
            return heartbeat
        if not isinstance(cmd.target_state, IOSState):
            return self._record(False, prev, "INVALID_TARGET_STATE")
        if not isinstance(cmd.auth_token, str) or not hmac.compare_digest(
                cmd.auth_token.encode(), self.expected_token.encode()):
            return self._record(False, prev, "UNAUTHORIZED_TOKEN_REJECTED")
        if (isinstance(cmd.sequence_id, bool) or not isinstance(cmd.sequence_id, int)
                or cmd.sequence_id <= self.last_sequence_id or not math.isfinite(cmd.timestamp_s)
                or not math.isfinite(cmd.client_rate_deg_s)):
            return self._record(False, prev, "INVALID_OR_REPLAYED_COMMAND")
        age_s = current_time_s - cmd.timestamp_s
        if age_s < 0 or age_s > self.max_command_age_s:
            return self._record(False, prev, "STALE_OR_REPLAYED_COMMAND")
        if any(not isinstance(getattr(cmd, name), bool) for name in (
                "servicer_ack", "client_ack", "client_damping_passive", "latch_confirmed",
                "load_path_verified", "connectors_isolated", "separation_confirmed")):
            return self._record(False, prev, "INVALID_COMMAND_FLAGS")
        # Consume every authenticated fresh command, even if its requested transition fails.
        self.last_sequence_id = cmd.sequence_id
        if cmd.target_state == IOSState.ABORT_SAFE:
            self.state = IOSState.ABORT_SAFE
            return self._record(True, prev, "EXPLICIT_ABORT_TO_SAFE_STATE")
        if cmd.target_state == self.state:
            if not (cmd.servicer_ack and cmd.client_ack):
                return self._record(False, prev, "MISSING_HEARTBEAT_ACK")
            self.last_valid_ack_time_s = current_time_s
            return self._record(True, prev, "HEARTBEAT_ACK")

        # 4. State-specific transition guards.
        allowed_next = {
            IOSState.NORMAL: {IOSState.SERVICE_STANDBY},
            IOSState.SERVICE_STANDBY: {IOSState.APPROACH_PERMITTED, IOSState.NORMAL},
            IOSState.APPROACH_PERMITTED: {IOSState.IOS_HANDOVER},
            IOSState.IOS_HANDOVER: {IOSState.MATED_SERVICING},
            IOSState.MATED_SERVICING: {IOSState.VERIFICATION},
            IOSState.VERIFICATION: {IOSState.RELEASE},
            IOSState.RELEASE: {IOSState.NORMAL},
            IOSState.ABORT_SAFE: {IOSState.SERVICE_STANDBY, IOSState.NORMAL},
        }
        if cmd.target_state not in allowed_next.get(self.state, set()):
            return self._record(False, prev, f"INVALID_TRANSITION_{self.state.value}_TO_{cmd.target_state.value}")

        if cmd.target_state == IOSState.APPROACH_PERMITTED:
            if not (cmd.servicer_ack and cmd.client_ack):
                return self._record(False, prev, "MISSING_INITIAL_HANDSHAKE_ACK")

        elif cmd.target_state == IOSState.IOS_HANDOVER:
            if not (cmd.servicer_ack and cmd.client_ack):
                self.state = IOSState.ABORT_SAFE
                return self._record(False, prev, "LOST_HANDSHAKE_ACK_ABORT")
            if not cmd.client_damping_passive:
                self.state = IOSState.ABORT_SAFE
                return self._record(False, prev, "AUTHORITY_CONFLICT_ABORT")
            if abs(cmd.client_rate_deg_s) > self.max_handover_rate_deg_s:
                self.state = IOSState.ABORT_SAFE
                return self._record(False, prev, "RATE_OUTSIDE_HANDOVER_ENVELOPE")

        elif cmd.target_state == IOSState.MATED_SERVICING:
            # A confirmed latch must retain stack authority even if load verification fails.
            self.mated = cmd.latch_confirmed
            if not (cmd.latch_confirmed and cmd.load_path_verified):
                self.state = IOSState.ABORT_SAFE
                return self._record(False, prev, "UNVERIFIED_LATCH_OR_LOAD_PATH_ABORT")

        elif cmd.target_state == IOSState.RELEASE:
            if not cmd.connectors_isolated:
                return self._record(False, prev, "CONNECTORS_NOT_ISOLATED")

        if self.mated and cmd.target_state in {IOSState.NORMAL, IOSState.SERVICE_STANDBY}:
            if not (cmd.connectors_isolated and cmd.separation_confirmed):
                return self._record(False, prev, "SEPARATION_NOT_CONFIRMED")
            self.mated = False
        self.last_sequence_id = cmd.sequence_id
        self.last_valid_ack_time_s = current_time_s
        self.state = cmd.target_state
        return self._record(True, prev, "TRANSITION_OK")


def simulate_ios_detumbling(
    initial_tumble_deg_s: float,
    residual_fraction: float = 0.05,
    max_torque_nm: float = 2.5,
    kd_nm_per_rad_s: float = 45.0,
    thruster_moment_arm_m: float = 1.2,
    client_isp_s: float = 220.0,
    tilt_deg: float = 2.0,
    dt_s: float = 0.25,
    max_time_s: float = 600.0,
    cfg: SimConfig = SimConfig(),
) -> Dict[str, float]:
    """Propagate 3-D Euler dynamics with active client rate damping for C3 IOS preparation."""
    for name, value in (("max_torque_nm", max_torque_nm), ("kd_nm_per_rad_s", kd_nm_per_rad_s),
                        ("thruster_moment_arm_m", thruster_moment_arm_m), ("client_isp_s", client_isp_s),
                        ("dt_s", dt_s), ("max_time_s", max_time_s)):
        if not math.isfinite(value) or value <= 0:
            raise ValueError(f"{name} must be finite and positive")
    if not math.isfinite(initial_tumble_deg_s) or initial_tumble_deg_s < 0:
        raise ValueError("initial_tumble_deg_s must be finite and nonnegative")
    if not math.isfinite(tilt_deg) or not 0 < residual_fraction <= 1:
        raise ValueError("tilt must be finite and residual_fraction must be in (0, 1]")
    if dt_s > max_time_s:
        raise ValueError("dt_s must not exceed max_time_s")
    inertia = np.array(cfg.inertia_diag_kgm2, dtype=float)
    tilt_rad = math.radians(tilt_deg)
    axis = np.array([math.sin(tilt_rad), 0.0, math.cos(tilt_rad)], dtype=float)
    omega = math.radians(initial_tumble_deg_s) * axis
    target_norm = math.radians(initial_tumble_deg_s * residual_fraction)
    q = np.array([1.0, 0.0, 0.0, 0.0], dtype=float)

    h_init = float(np.linalg.norm(inertia * omega))
    impulse_nms = 0.0
    t_s = 0.0
    n_steps = math.ceil(max_time_s / dt_s)
    for _ in range(n_steps):
        if float(np.linalg.norm(omega)) <= max(target_norm, 1e-6):
            break
        step_s = min(dt_s, max_time_s - t_s)
        tau = np.clip(-kd_nm_per_rad_s * omega, -max_torque_nm, max_torque_nm)
        # Half-step torque impulse around RK4 torque-free attitude propagation
        alpha = tau / inertia
        omega_mid = omega + 0.5 * alpha * step_s
        q, omega_free = propagate_attitude_rk4(q, omega_mid, step_s, inertia)
        omega = omega_free + 0.5 * alpha * step_s
        impulse_nms += float(np.linalg.norm(tau)) * step_s
        t_s += step_s

    h_final = float(np.linalg.norm(inertia * omega))
    # Equivalent thruster propellant if damped via coupled RCS thrusters of arm L:
    total_force_impulse_ns = impulse_nms / thruster_moment_arm_m
    client_propellant_kg = total_force_impulse_ns / (client_isp_s * G0_MPS2)
    return {
        "initial_tumble_deg_s": float(initial_tumble_deg_s),
        "final_tumble_deg_s": math.degrees(float(np.linalg.norm(omega))),
        "detumble_time_s": float(t_s),
        "angular_momentum_removed_nms": float(h_init - h_final),
        "control_torque_impulse_nms": float(impulse_nms),
        "client_rcs_propellant_kg": float(client_propellant_kg),
        "residual_target_met": float(np.linalg.norm(omega)) <= max(target_norm, 1e-6),
        "handover_ready": float(np.linalg.norm(omega)) <= cfg.max_safe_target_omega_rad_s,
    }


def evaluate_beacon_engineering_budget(
    rate_hz: float = 1.0,
    duration_days: float = 30.0,
    range_m: float = 1000.0,
    freq_mhz: float = 401.5,
) -> Dict[str, float]:
    """Compute ideal and derated 30-day beacon reserve energy, fault isolation loss, and RF link margin."""
    for name, value in (("duration_days", duration_days), ("range_m", range_m), ("freq_mhz", freq_mhz)):
        if not math.isfinite(value) or value <= 0:
            raise ValueError(f"{name} must be finite and positive")
    if not math.isfinite(rate_hz) or not 0 <= rate_hz <= 1 / 0.015:
        raise ValueError("rate_hz must be finite and keep the assumed transmit duty cycle <= 100%")
    tx_duration_s = 0.015
    p_sleep_mw = 12.0
    p_tx_mw = 1100.0
    duty_cycle = rate_hz * tx_duration_s
    p_load_avg_mw = p_sleep_mw + duty_cycle * p_tx_mw
    net_energy_wh = (p_load_avg_mw * 1e-3) * 24.0 * duration_days

    # Illustrative derating assumptions; not a claim of compliance with a hardware standard.
    eta_dcdc = 0.82          # low-quiescent buck/boost regulator efficiency
    eta_isolation = 0.96     # series eFuse + reverse-blocking barrier efficiency
    f_temp_m20c = 0.85       # usable capacity factor at -20 C passive eclipse
    f_aging_15yr = 0.88      # 15-year GEO storage + radiation degradation factor
    f_dod_limit = 0.85       # maximum allowable depth of discharge
    combined_derating = eta_dcdc * eta_isolation * f_temp_m20c * f_aging_15yr * f_dod_limit

    # Main-bus 0-Ohm short-circuit isolation leakage (2 uA @ 3.6 V over 30 days)
    fault_leakage_wh = (2.0e-6 * 3.6) * 24.0 * duration_days
    required_nameplate_wh = (net_energy_wh + fault_leakage_wh) / combined_derating
    recommended_nameplate_wh = 1.20 * required_nameplate_wh  # +20% system design margin

    # Mass breakdown: primary LiSOCl2 cells (~450 Wh/kg) + packaging/shielding/PCB/antenna (2.3x packaging factor)
    bare_cell_mass_g = 1000.0 * (recommended_nameplate_wh / 450.0)
    packaged_unit_mass_g = bare_cell_mass_g * 2.35 + 45.0

    # UHF 401.5 MHz link budget at `range_m` (19.2 kbps GMSK/FSK)
    tx_power_dbm = 10.0 * math.log10(500.0)  # 0.5 W RF = +27.0 dBm
    tx_ant_gain_dbi = -3.0                   # worst-case tumbling hemispheric patch
    pol_and_line_loss_db = -4.0
    wavelength_m = 299_792_458.0 / (freq_mhz * 1e6)
    fspl_db = 20.0 * math.log10(4.0 * math.pi * range_m / wavelength_m)
    rx_ant_gain_dbi = 3.0
    rx_power_dbm = tx_power_dbm + tx_ant_gain_dbi + pol_and_line_loss_db - fspl_db + rx_ant_gain_dbi
    noise_density_dbm_hz = -174.0 + 4.0      # 290 K + 4.0 dB receiver noise figure
    bit_rate_db_hz = 10.0 * math.log10(19_200.0)
    eb_n0_db = rx_power_dbm - noise_density_dbm_hz - bit_rate_db_hz
    eb_n0_req_db = 10.6                      # BER <= 1e-5 non-coherent FSK + 2 dB implementation loss
    link_margin_db = eb_n0_db - eb_n0_req_db

    return {
        "rate_hz": float(rate_hz),
        "duty_cycle_pct": 100.0 * duty_cycle,
        "net_avg_power_mw": float(p_load_avg_mw),
        "duration_days": float(duration_days),
        "net_energy_wh": float(net_energy_wh),
        "net_energy_30d_wh": float(net_energy_wh),
        "combined_derating_factor": float(combined_derating),
        "short_circuit_leakage_wh": float(fault_leakage_wh),
        "short_circuit_leakage_30d_wh": float(fault_leakage_wh),
        "required_nameplate_wh": float(required_nameplate_wh),
        "recommended_nameplate_wh": float(recommended_nameplate_wh),
        "bare_cell_mass_g": float(bare_cell_mass_g),
        "packaged_unit_mass_g": float(packaged_unit_mass_g),
        "range_m": float(range_m),
        "fspl_db": float(fspl_db),
        "eb_n0_db": float(eb_n0_db),
        "link_margin_db": float(link_margin_db),
    }


if __name__ == "__main__":
    import json
    print(json.dumps({
        "status": "Illustrative standalone system models; not coupled to RPO or hardware validated",
        "beacon": evaluate_beacon_engineering_budget(),
        "detumbling": [simulate_ios_detumbling(rate) for rate in (3.0, 5.0, 10.0)],
    }, indent=2))
