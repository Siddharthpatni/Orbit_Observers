"""IOS servicing episode coupled to the RPO loop (Phase 2 deck slide 6: IOS Mode & Docked Control).

Ground authorisation -> IOS state machine -> (C3: physical client detumble) -> closed-loop RPO run ->
handover / mating / release, or ABORT from the state the episode is in. This replaces the fixed
"95 % spin cut" of ``C3_ios_mode`` with the spin actually achieved by ``simulate_ios_detumbling``.

Simplifications (stated, not hidden): latch and load-path confirmations are inputs (default nominal)
because no contact model exists; the shared credential is a simulation token, not cryptography;
detumble torque authority is the assumed client ACS capability, not a GEO design claim (Guide §15).
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .config import SCENARIOS, SimConfig
from .ios import IOSCommand, IOSState, IOSStateMachine, simulate_ios_detumbling
from .simulate import run_single_simulation

TOKEN = "CLEARSPACE-IOS-AUTH-V1"


@dataclass
class EpisodeResult:
    outcome: str                     # SERVICED_AND_RELEASED | ABORTED_SAFE | NOT_AUTHORIZED | HANDOVER_REFUSED | ...
    final_ios_state: str
    ground_approved: bool
    tier: str
    effective_omega_factor: float
    detumble: Optional[Dict[str, float]]
    rpo: Optional[Dict[str, object]]
    ios_log: List[str] = field(default_factory=list)
    authority_invariant_held: bool = True


class _Driver:
    def __init__(self, machine: IOSStateMachine, token: str):
        self.m, self.token, self.seq, self.now, self.log = machine, token, 0, 0.0, []

    def send(self, target: IOSState, dt: float = 1.0, **kw) -> bool:
        self.seq += 1
        self.now += dt
        opts = dict(servicer_ack=True, client_ack=True, client_damping_passive=True)
        opts.update(kw)
        res = self.m.step(IOSCommand(target, self.seq, self.now, self.token, **opts), self.now)
        self.log.append(f"{res.previous_state.value}->{target.value}: {'OK' if res.accepted else 'REJECT'} ({res.reason})")
        return res.accepted


def run_ios_servicing_episode(
    tier: str,
    seed: int,
    tumble_deg_s: float,
    ground_approved: bool,
    master_seed: int = 0,
    token: str = TOKEN,
    latch_confirmed: bool = True,
    load_path_verified: bool = True,
    use_physical_detumble: bool = True,
    cfg: SimConfig = SimConfig(),
    **rpo_kwargs,
) -> EpisodeResult:
    if tier not in SCENARIOS:
        raise ValueError(f"unknown tier {tier!r}")
    machine = IOSStateMachine(expected_token=TOKEN)
    d = _Driver(machine, token)
    inv = True

    def done(outcome, factor, detumble, rpo):
        return EpisodeResult(outcome, machine.state.value, ground_approved, tier, factor, detumble, rpo, d.log,
                             inv and machine.check_authority_invariant())

    # 1. Ground gate: without a human approval the IOS machine is never asked to permit an approach.
    if not ground_approved:
        d.log.append("ground approval missing: no IOS command issued")
        return done("NOT_AUTHORIZED", SCENARIOS[tier].omega_factor, None, None)
    if not (d.send(IOSState.SERVICE_STANDBY) and d.send(IOSState.APPROACH_PERMITTED)):
        return done("IOS_REFUSED_APPROACH", SCENARIOS[tier].omega_factor, None, None)

    # 2. Client spin entering the approach. Only C3 has an active client that can damp its own tumble.
    detumble, factor = None, SCENARIOS[tier].omega_factor
    if tier == "C3_ios_mode" and use_physical_detumble:
        detumble = simulate_ios_detumbling(tumble_deg_s, cfg=cfg)
        factor = detumble["final_tumble_deg_s"] / tumble_deg_s if tumble_deg_s > 0 else 0.0

    # 3. Closed-loop RPO approach with the spin the client actually has.
    rpo = run_single_simulation(tier, seed, tumble_deg_s, cfg=cfg, master_seed=master_seed,
                                omega_factor_override=factor, **rpo_kwargs)
    client_rate = tumble_deg_s * factor

    if not rpo["terminal_pass"]:
        d.send(IOSState.ABORT_SAFE)
        return done("ABORTED_SAFE" if not rpo["unsafe"] else "UNSAFE_KEEPOUT_VIOLATION", factor, detumble, rpo)

    # 4. Terminal window met -> handover (rate envelope guard), mate, verify, release.
    if not d.send(IOSState.IOS_HANDOVER, client_rate_deg_s=client_rate):
        return done("HANDOVER_REFUSED_ABORT_SAFE", factor, detumble, rpo)
    if not d.send(IOSState.MATED_SERVICING, latch_confirmed=latch_confirmed, load_path_verified=load_path_verified):
        return done("MATING_FAILED_ABORT_SAFE", factor, detumble, rpo)
    d.send(IOSState.VERIFICATION)
    d.send(IOSState.RELEASE, connectors_isolated=True)
    d.send(IOSState.NORMAL, connectors_isolated=True, separation_confirmed=True)
    ok = machine.state == IOSState.NORMAL
    return done("SERVICED_AND_RELEASED" if ok else "RELEASE_FAILED", factor, detumble, rpo)
