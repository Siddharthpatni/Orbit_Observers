# Model Reference — equations, parameters and assumptions

**Audience:** engineers and reviewers who need to know exactly what is simulated.
**Model version:** `Phase2-RPO-MC-v4.0` · **Maturity:** early-stage, scenario-based, low-to-medium-fidelity RPO robustness assessment.

For a gentler introduction read [GUIDE_FOR_EVERYONE.md](GUIDE_FOR_EVERYONE.md) first; for how the runs are combined statistically see [MONTE_CARLO_METHOD.md](MONTE_CARLO_METHOD.md).

---

## 1. Frames and units

| Frame | Definition | Used for |
|:--|:--|:--|
| **LVLH (L)** | Origin at the client's centre of mass; *x* radial outward, *y* along-track, *z* orbit normal (right-handed). | Servicer relative position/velocity, capture point, measurements. |
| **Client body (B)** | Fixed to the client structure, principal inertia axes. | Capture-fixture location `ρ_cap^B = (1.5, 0, 0) m`, inertia, angular rate. |
| `R_BL(q)` | Rotation body → LVLH from the scalar-first unit quaternion `q = (q_w, q_x, q_y, q_z)`. | Placing the capture point in LVLH. |

All code uses SI units (m, s, kg, rad). Degrees appear only in names ending in `_deg`. Every numerical assumption lives in [`rpo_project/config/__init__.py`](../rpo_project/config/__init__.py) and is fingerprinted by `SimConfig.config_hash()` (which also covers the scenario definitions and model version).

## 2. One time step (Δt = 0.25 s)

```
truth ──► sense (camera, beacon) ──► estimate (Kalman filters) ──► guidance + abort gates ──► thrusters ──► truth
  ▲                                                                                                          │
  └──────────────────────────────── scoring (truth only: keep-out, terminal window) ◄────────────────────────┘
```

Order inside `simulate.run_single_simulation` for step *k*:

1. **Sense** the true state → noisy camera pose (may drop out / be occluded).
2. **Beacon** packet generated if due (may be lost); queued until `t + latency`.
3. **Estimate**: vision update; assimilate every queued packet whose arrival time has passed.
4. **Score prediction** (metric only): predicted vs true capture point 2 s ahead.
5. **Guide**: abort gates, then the acceleration command — from estimates only.
6. **Actuate**: gain bias, misalignment, execution noise, saturation at `a_max`.
7. **Propagate** truth (RK4) and the estimator's prediction (using the *commanded*, not applied, acceleration).
8. **Score** truth: keep-out violation, terminal-window dwell.

A run ends at the first of: terminal window held for 2 s · abort · keep-out violation · 120 s timeout.

## 3. Translational dynamics — Clohessy–Wiltshire (Handbook §6)

```
ẍ = 3n²x + 2nẏ + a_x
ÿ = −2nẋ + a_y            n = √(μ/a³) = 7.292×10⁻⁵ rad/s   (a = 42 164 km, GEO)
z̈ = −n²z + a_z
```

Integrated with fixed-step RK4 (`dynamics.propagate_cw_rk4`). The closed-form 6×6 state-transition matrix (`cw_state_transition_matrix`) is used by the estimator and to verify the integrator to < 10⁻⁸ m (V&V check 1). Over 120 s at GEO the orbital rate turns LVLH by only 0.5°, so these terms are small but retained.

## 4. Client attitude and the moving capture point (Handbook §7)

Torque-free rigid body with diagonal inertia **I**:

```
I ω̇ + ω × (I ω) = 0            q̇ = ½ Ω(ω) q      (RK4, quaternion renormalised each step)
r_cap^L = R_BL(q) ρ_cap^B       v_cap^L = (R_BL ω) × r_cap^L       n_cap = r_cap^L / |r_cap^L|
```

* Nominal spin is about body *z* (the major axis, 3 100 kg·m²) at the study's tumble rate.
* **Monte Carlo dispersion (v4.0):** the spin axis is tilted from body *z* by a random 2-D Gaussian (σ = 2° per axis), and each principal inertia is scaled by `1 + 0.05·N(0,1)`. A tilted spin on an asymmetric body nutates, so the true capture point leaves the orbit plane slightly — the planar estimator does not model this, which is deliberate model mismatch.
* Simplification: the inertial body rate is used as the rate relative to LVLH (difference ≤ n = 0.004°/s).
* **C3 IOS mode** multiplies the tumble rate by 0.05: the client actively slows itself. This is the only tier that changes true dynamics.

## 5. Sensors (Handbook §8)

### Camera / fiducials (`sensors.py`)

| Effect | Model |
|:--|:--|
| Occlusion | No measurement if `cos(∠(servicer direction, n_cap)) < −0.35` (fixture faces away). |
| Dropout | No measurement with probability `p_drop` (independent per frame). |
| Position | `z_r = r_servicer + σ_pos · N(0, I₃)`, with `σ_pos = vision_sigma_m × vision_pos_scale`. |
| Attitude | `z_θ = wrap(yaw_true + σ_θ · N(0,1))` — yaw extracted from the true quaternion. |

### Service Beacon (`beacon.py`)

Packets due every `1/(rate · Δt)` steps; each lost with probability `p_loss` (Bernoulli). Content: an ID field labeled authenticated (no cryptographic authentication is implemented), timestamp and — only for `C2_beacon` / `C3` — the body-*z* rate `ω_z + σ_g·N(0,1)`, σ_g = 0.08°/s. A packet is assimilated only once `t ≥ timestamp + latency` (the estimator raises an error if asked earlier).

### Tier definitions

| Tier | σ_θ | Position-noise scale | Dropout | Beacon | Rate in packets | Tumble factor |
|:--|--:|--:|--:|:--:|:--:|--:|
| `C0_unprepared` | 12° | 2.5× | 30% | – | – | 1.0 |
| `C1_fiducials` | 3° | 1.0× | 8% | – | – | 1.0 |
| `C2_id_only` | 3° | 1.0× | 8% | ✓ | – | 1.0 |
| `C2_beacon` | 3° | 1.0× | 8% | ✓ | ✓ | 1.0 |
| `C3_ios_mode` | 3° | 1.0× | 8% | ✓ | ✓ | 0.05 |

## 6. Estimator (`estimator.py`)

Two decoupled linear Kalman filters, both in Joseph form.

**Translation** — state `[r, v]` (6), prediction with the CW STM and the commanded acceleration, position-only measurement `H = [I₃ 0]`, `R = σ_pos² I₃`. Process noise `diag((0.005Δt)²·I₃, (0.003√Δt)²·I₃)`. Initial σ: max(σ_pos, 5 cm) and 3 cm/s.

**Attitude/rate** — state `[θ, ω]` (yaw angle and rate), constant-rate model `F = [[1, Δt],[0, 1]]`, white-noise-acceleration process noise with intensity (0.015°/s)². Vision updates θ; beacon packets update ω with variance `σ_g² + q·age` (inflated for staleness — an approximation, not a full out-of-sequence filter). Initial σ: max(σ_θ, 1°) and 3°/s.

The capture point is predicted by rotating ρ_cap by `θ̂ + ω̂·t_h`.

## 7. Guidance (`guidance.py`)

Two phases, both driven only by the estimate:

1. **Hold** at 4 m along the estimated capture normal, co-rotating (`v_ref = s_corot · (ω̂ × r_ref)` where `s_corot` smoothly scales tangential speed with rate confidence and distance outside the hold sphere).
2. **Terminal** tracking of the estimated capture point (`r_ref = r_cap_hat + standoff · n_cap_hat`), entered once *t* ≥ 8 s, hold error < 1.25 m, speed error ≤ 0.055 m/s and attitude σ < 8°.

Extra logic: inside 2.8 m the approach must stay within a 55° cone around the capture normal and attitude σ < 10° (else `ABORT_CORRIDOR_MISALIGNMENT`); if the target point is on the far side of the client the reference is moved tangentially to fly around it; when estimated position uncertainty `σ_r = √λ_max(P_trans[:3,:3])` exceeds 2.0 cm, a radial capture standoff `min(0.065, 1.65·(σ_r − 0.02))` m is added and the repulsive barrier radius `1.48 + 2.5·max(0, σ_r − 0.02)` m (gain 0.06 m/s² per 0.15 m) is inflated to prevent keep-out violations under degraded optical navigation.

**`braking_pd` control law (default):**

```
v_close = min( v_max, (K_p/K_d)·d, √(2 η a_max d) )          d = |r_ref − r̂|, η = 0.5, v_max = 0.30 m/s
a_cmd   = K_d (v_ref + v_close·ê − v̂) + ω̂ × v_ref − a_CW(ŝ)     K_p = 0.085, K_d = 0.42
|a_cmd| ≤ a_max = 0.040 m/s²
```

`legacy_pd` (`a = −K_p(r̂−r_ref) − K_d(v̂−v_ref)`) is kept for comparison with v2.1 results.

**Actuation errors (per run, v4.0):** per-axis gain bias σ = 2%, thrust-vector misalignment σ = 0.5° per axis; **per step:** execution noise σ = 2% per axis. The applied (not commanded) acceleration integrates Δv and moves the truth.

## 8. Safety gates and outcomes (`safety.py`, Handbook §9)

| Gate (on estimates) | Active from | Threshold | Status |
|:--|:--|:--|:--|
| Position uncertainty (largest covariance eigenvalue) | immediately | σ_r > 0.30 m | `ABORT_POSITION_COVARIANCE` |
| Estimated tumble rate | 10 s | > 3.25°/s | `ABORT_EXCESS_TUMBLE_RATE` |
| Attitude uncertainty | 12 s | σ_θ > 18° | `ABORT_NAVIGATION_COVARIANCE` |
| Fuel | always | Δv ≥ 2.5 m/s | `ABORT_DELTA_V_BUDGET` |
| Corridor | inside 2.8 m | > 55° off-axis or σ_θ > 10° | `ABORT_CORRIDOR_MISALIGNMENT` |

| Outcome (on truth) | Definition |
|:--|:--|
| `TERMINAL_CAPTURE_WINDOW_MET` | Within 0.20 m of the capture point, relative speed ≤ 0.055 m/s, within 15° of the capture normal, continuously for 2.0 s. **Not** physical capture. |
| `UNSAFE_KEEPOUT_VIOLATION` | True servicer centre inside the 1.35 m keep-out sphere. |
| `TIMEOUT` | None of the above within 120 s. |

In v4.1, an abort records its reason/time and switches to active retreat toward a fixed reference 12 m from the origin in the estimated departure direction. The bounded braking controller uses estimates only. Truth and noisy sensing continue for up to 120 additional seconds, with a separate 1.50 m/s retreat reserve. Exhaustion cuts thrust and propagation continues to the retreat time limit so later sampled keep-out violations remain visible. Estimated arrival requires position error ≤0.25 m and speed ≤0.055 m/s; truth scoring independently confirms these conditions. A false arrival estimate is `ESTIMATE_MISMATCH`, not completion. This is an active point-mass retreat, not a passively safe orbit proof.

`abort_triggered` records the decision even when the later outcome is unsafe. `aborted` excludes unsafe outcomes so the outcome counts remain disjoint. `delta_v_mps` and `propellant_kg` include executed retreat thrust; separate approach/retreat diagnostics are also saved. Historical v4.0 runs still stop at the abort decision.

## 9. Truth/estimate separation (Handbook §12 hard boundary)

Guidance, control and abort gates receive only the `RPOEstimator` object. Truth is used by the sensor models (to *generate* measurements), by the dynamics, and by scoring. The estimator predicts with the commanded acceleration, never the applied one.

## 10. Every parameter

| Group | Parameter | Value | Note |
|:--|:--|--:|:--|
| Time | `dt_s` / `max_duration_s` | 0.25 / 120 s | |
| | `prediction_horizon_s` / `prediction_metric_start_s` | 2.0 / 1.0 s | capture-point error scored over `[1.0, 10.0]` s |
| Client | `target_mass_kg` | 3 500 | not used dynamically |
| | `inertia_diag_kgm2` | 2 400, 2 800, 3 100 | |
| | `capture_offset_body_m` | (1.5, 0, 0) | |
| | `keepout_radius_m` / `hold_distance_m` | 1.35 / 4.0 m | |
| Servicer | `chaser_start_distance_m` | 12 m | along initial capture normal |
| | `a_max_mps2` | 0.040 | |
| | `servicer_mass_kg` / `servicer_isp_s` | 500 kg / 220 s | illustrative; Δv → propellant only |
| Dispersions | `chaser_pos_disp_sigma_m` / `chaser_vel_disp_sigma_mps` | 0.50 m / 0.015 m/s | per axis |
| | `thruster_noise_sigma_frac` | 0.02 | per step, per axis |
| | `thruster_scale_sigma_frac` | 0.02 | per run, per axis |
| | `thruster_misalign_sigma_rad` | 0.5° | per run, per axis |
| | `tumble_axis_tilt_sigma_rad` | 2.0° | per run, per axis |
| | `inertia_sigma_frac` | 0.05 | per run, per axis |
| | initial client yaw | U(−π, π) | |
| Sensors | `gyro_noise_rad_s` | 0.08°/s | beacon rate sensor |
| | `fov_occlusion_cos_limit` | −0.35 | |
| Estimator | `est_*` | see §6 | |
| Guidance | `kp_pos`, `kd_vel`, `max_closing_speed_mps`, `braking_accel_fraction` | 0.085, 0.42, 0.30, 0.5 | |
| | `terminal_entry_*` | 8 s, 1.25 m, 8° | |
| | `corridor_*` | 2.8 m, 55°, 10° | |
| | `flyaround_*` | cos 0.15, +1.5 m, 2.5 m | |
| | `barrier_*` | 1.48 m, 0.06 m/s², 0.15 m | inflated by `2.5·max(0, σ_r − 0.02)` |
| | `terminal_standoff_*` | thresh 2 cm, gain 1.65, max 6.5 cm | covariance-aware radial margin |
| | `corot_*` | σ_ω 0.05°/s, gain 0.55, span 5 m | proximity co-rotation shaping |
| Safety | rate gate / covariance gate / Δv budget | 3.25°/s @10 s / 18° @12 s / 2.5 m/s | |
| Terminal window | pos / speed / alignment / dwell | 0.20 m / 0.055 m/s / 15° / 2.0 s | |

Campaign-level inputs (tumble rate, optical noise, beacon loss/rate/latency) are set per study — see [MONTE_CARLO_METHOD.md](MONTE_CARLO_METHOD.md#3-the-four-studies).

## 11. Known limitations

* Linearised CW relative motion about a circular orbit; no J2, solar radiation pressure, third-body or plume effects.
* Planar (yaw + yaw-rate) estimator; full 3-D attitude estimation is future work. Out-of-plane nutation is present in the truth only.
* Point-mass servicer with ideal attitude; no thruster delay or minimum impulse bit.
* Camera dropouts and packet losses are independent per frame/packet; burst (correlated) outages are future work.
* No contact, latch, compliance, flexible appendage or detailed client shape model — "terminal window met" is not capture.
* Covariance-aware radial standoff (`≤ 6.5 cm`) and barrier inflation were used in the campaign with zero observed keep-out violations across the studied optical-noise grid (`σ_pos ≤ 25 cm`), and v4.1 now aborts when the largest principal position standard deviation exceeds 0.30 m. This threshold is an illustrative allocation, not a hardware-qualified safety limit.
* The true tumble rate is almost constant (torque-free, small nutation), so a stale beacon rate is still nearly correct; latency results do not apply to clients whose rate changes (e.g. active detumbling, flat-spin transitions).
* All numbers are illustrative assumptions, not measured ClearSpace or hardware data.

## v4.1 additions

New `SimConfig` parameters: `max_allowed_position_std_m=0.30`, `retreat_duration_s=120`, `retreat_delta_v_reserve_mps=1.50`, `retreat_position_tol_m=0.25`, `retreat_speed_tol_mps=0.055`. Position uncertainty uses the largest eigenvalue of the symmetrized 3×3 position covariance, including correlations. Approach random draws retain their original length; retreat extension draws use a separate deterministic seed stream.

`ios.py` implements a standalone command-state model, bounded per-axis detumbling torques and an assumed-load RF/energy calculation. The detumbling model reports both reaching its requested residual rate and meeting the handover-rate threshold; those are distinct outcomes. These models are not coupled into the RPO C3 dynamics. Token checks are a simulation stand-in, not cryptographic authentication. Derating factors, specific energy and packaging mass remain assumptions.

## 12. Evidence boundaries for the Phase 2 proposal

The current stored campaign sweeps tumble only through 5°/s. C3 initializes a slower client; it does not implement detumbling, IOS transitions or docked control. All tiers share capture geometry, so the mechanical-interface benefit is not separately identified. The beacon power and retry-cost illustrations are assumption-based calculations, not measured hardware or lifecycle economics. See [PHASE2_PROPOSAL.md](PHASE2_PROPOSAL.md) for candidate requirements and validation gates.
