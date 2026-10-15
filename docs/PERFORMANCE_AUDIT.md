# Detailed Performance & Failure Mode Audit: RPO Simulation vs. Monte Carlo

**Document ID:** AUD-RPO-2026-V3  
**Status:** Approved & Verified  
**Model Versions Audited:** `Phase2-RPO-MC-v2.1` (Baseline) vs. `Phase2-RPO-MC-v3.0` (Optimized)  
**Target Architecture:** ClearSpace Phase 2 Rendezvous & Proximity Operations (RPO) in GEO  

---

## Executive Summary

When transitioning from simplified Stage-I estimation models or deterministic single-run verification scripts to stochastic Monte Carlo campaigns, mission pass rates frequently drop. 

This audit provides a complete, forensic investigation into:
1. **Why closed-loop Monte Carlo performance is lower than single-run verification.**
2. **The exact failure modes across 1,050 baseline simulations** (identifying why runs failed and why specific random seeds triggered aborts or collisions).
3. **The architectural enhancements introduced in `v3.0` (`braking_pd`)**, which eliminated 100% of keep-out zone violations, reduced fuel consumption by 45–55%, and leveled up $3.0^\circ/\text{s}$ tumble pass rates from **63.3% to 100%** on beacon-assisted targets.

---

## 1. Root-Cause Analysis: Why Simulation Performance Drops in Monte Carlo

### A. Stage-I Kinematic Pilot vs. Full Closed-Loop RPO Simulation
The original Stage-I pilot (`examples/stage1/rpo_beacon_information_pilot.py`) was strictly an **information-value feasibility check**:
- It computed the geometric Kalman filter prediction error: $\|\hat{\mathbf{r}}_{\text{cap}} - \mathbf{r}_{\text{cap}}\| < \text{threshold}$.
- It assumed the chaser had zero physical mass, infinite acceleration authority, instantaneous response, zero thruster noise, and no physical collision barriers.
- **The full closed-loop simulation (`rpo_project/`)**, by contrast, models physical spacecraft flight in 3D relative orbit:
  - Finite thrust limits ($a_{\max} = 0.040\text{ m/s}^2$).
  - A strict keep-out sphere boundary ($R_{\text{keepout}} = 1.35\text{ m}$).
  - A fuel limit ($\Delta V \le 2.50\text{ m/s}$).
  - A 2.0-second continuous dwell requirement across position, velocity, and angular alignment.

### B. Deterministic Single-Run vs. Stochastic Monte Carlo Dispersions
In single-run deterministic verification (e.g. V&V Test 2), noise is zeroed and the chaser starts perfectly aligned. In Monte Carlo, multiple uncertainties compound simultaneously:

| Stochastic Parameter | Nominal / Deterministic | Monte Carlo Distribution | Physical Impact on Performance |
|:---|:---:|:---|:---|
| Initial Position Dispersion | $0.0\text{ m}$ | $\mathbf{r}_0 \sim \mathcal{N}(\mathbf{0}, 0.50^2\mathbf{I}_3)\text{ m}$ | Requires initial trajectory correction burns. |
| Initial Velocity Dispersion | $0.0\text{ m/s}$ | $\mathbf{v}_0 \sim \mathcal{N}(\mathbf{0}, 0.015^2\mathbf{I}_3)\text{ m/s}$ | Increases initial relative drift. |
| Initial Attitude Phase $\theta_0$ | $0.0\text{ rad}$ | $\theta_0 \sim \mathcal{U}(-\pi, +\pi)$ | If docking port faces away, chaser must fly around the keep-out zone. |
| Optical Position Noise | $0.0\text{ m}$ | $\sigma_{\text{pos}} = 0.05\text{ m}$ ($0.125\text{ m}$ for $C_0$) | Jitter in relative position estimates. |
| Optical Angle Noise | $0.0^\circ$ | $\sigma_\theta = 3.0^\circ$ ($12.0^\circ$ for $C_0$) | Jitter in attitude angle estimate. |
| Optical Dropout Probability | $0\%$ | $8\%$ ($30\%$ for $C_0$) | Forces estimator to dead-reckon; covariance grows. |
| Line-of-Sight Occlusion | Off | Lost when $\cos \theta < -0.35$ | Periodic blindness as client satellite tumbles. |
| Thruster Execution Noise | $0\%$ | $\pm 2.0\%$ Gaussian jitter | Imperfect control execution during braking. |
| RF Beacon Loss & Latency | $0\%, 0\text{ ms}$ | $20\%$ packet loss, $100\text{ ms}$ latency | Stale/missed angular velocity telemetry. |

---

## 2. Forensic Audit of Baseline v2.1 (1,050 Monte Carlo Runs)

An audit of the baseline dataset (`results/baseline_v2_1/runs_main.csv`) revealed four distinct outcomes across 1,050 runs:

```
Total Simulations: 1,050
├── TERMINAL_CAPTURE_WINDOW_MET:  837 (79.71%)
├── ABORT_EXCESS_TUMBLE_RATE:     153 (14.57%)
├── ABORT_DELTA_V_BUDGET:          48 ( 4.57%)
└── UNSAFE_KEEPOUT_VIOLATION:      12 ( 1.14%)
```

### Breakdown by Scenario & Tumble Rate

```
Scenario        ABORT_DELTA_V   ABORT_TUMBLE   TERMINAL_PASS   UNSAFE_KEEPOUT   Total
C0_unprepared         11             51             147              1           210
C1_fiducials          13             36             160              1           210
C2_id_only            13             36             160              1           210
C2_beacon             11             30             167              2           210
C3_ios_mode            0              0             203              7           210
Total                 48            153             837             12          1050
```

```
Tumble Rate     ABORT_DELTA_V   ABORT_TUMBLE   TERMINAL_PASS   UNSAFE_KEEPOUT   Total
0.00 deg/s             4              0             141              5           150
0.25 deg/s             7              0             141              2           150
0.50 deg/s             4              0             145              1           150
1.00 deg/s             2              0             147              1           150
2.00 deg/s             1              0             148              1           150
3.00 deg/s            30             33              86              1           150
5.00 deg/s             0            120              29              1           150
Total                 48            153             837             12          1050
```

---

## 3. Forensic Investigation of the Three Failure Modes

### Failure Mode 1: The "Seed 13" Anomaly (All 12 Keep-Out Violations)
- **Observation:** In the baseline dataset, exactly 12 runs resulted in `UNSAFE_KEEPOUT_VIOLATION`. **Every single one occurred on Seed 13** across different scenarios.
- **Root Cause Analysis:**
  1. In Seed 13, initial position dispersion placed the chaser at an offset requiring an approach vector where the rotating hold-point was decelerating toward the keep-out barrier.
  2. Under `legacy_pd`, the control law applied unconstrained position and velocity errors:
     $$\mathbf{a}_{\text{cmd}} = -K_p (\hat{\mathbf{r}} - \mathbf{r}_{\text{ref}}) - K_d (\hat{\mathbf{v}} - \mathbf{v}_{\text{ref}})$$
  3. Because the chaser approached at maximum speed ($0.30\text{ m/s}$), the commanded deceleration when reaching the capture point saturated the thrusters ($a > a_{\max} = 0.040\text{ m/s}^2$).
  4. Saturated thrusters meant the proportional feedback dominated while derivative damping was clipped. The chaser overshot the capture point by **8.3 millimeters**, breaching $R_{\text{keepout}} = 1.35\text{ m}$ (`min_clearance = -0.0083 m`).
- **Validation:**
  - `legacy_pd` on Seed 13: `UNSAFE_KEEPOUT_VIOLATION` (Clearance: $-0.0083\text{ m}$).
  - `braking_pd` on Seed 13: `TERMINAL_CAPTURE_WINDOW_MET` (Clearance: $+0.1072\text{ m}$).

### Failure Mode 2: Delta-V Budget Exhaustion (Seeds 3, 13, 27)
- **Observation:** 48 runs aborted because cumulative $\Delta V$ reached the $2.50\text{ m/s}$ ceiling around $t \approx 68\text{ seconds}$. 30 of these occurred at $3.0^\circ/\text{s}$ tumble.
- **Root Cause Analysis:**
  1. At $3.0^\circ/\text{s}$, the hold point ($4.0\text{ m}$ radius) travels at $v = \omega \cdot R = (0.0524\text{ rad/s}) \times 4.0\text{ m} = 0.209\text{ m/s}$.
  2. In `legacy_pd`, the controller did not include rotating reference feed-forward acceleration ($\mathbf{a}_{\text{ref}} = \mathbf{\omega} \times \mathbf{v}_{\text{ref}}$).
  3. The controller constantly lagged behind the rotating hold point, burning maximum thrust ($0.040\text{ m/s}^2$) to catch up.
  4. Because velocity error relative to the hold point remained above the entry gate threshold ($0.055\text{ m/s}$), the chaser remained trapped at the hold point, burning propellant until the fuel budget aborted the mission.

### Failure Mode 3: High Tumble Rate Aborts ($\omega \ge 3.0^\circ/\text{s}$)
- **Observation:** 153 runs aborted due to `ABORT_EXCESS_TUMBLE_RATE`.
  - At $5.0^\circ/\text{s}$, 120/120 runs aborted for $C_0, C_1, C_2$.
  - At $3.0^\circ/\text{s}$, 33 runs aborted (21 in $C_0$, 6 in $C_1$, 6 in $C_2\_id$, and **0 in $C_2\_beacon$**).
- **Root Cause Analysis:**
  1. The safety abort threshold is hard-coded at $\omega_{\max} = 3.2^\circ/\text{s}$ ($0.0558\text{ rad/s}$).
  2. At $5.0^\circ/\text{s}$, client tumble exceeds the safety envelope. Aborting is **mandatory and correct behavior**—no servicer should attempt docking with a tumbling target beyond its physical capture capability. Only $C_3$ (which features cooperative active detumbling to $0.05 \times \omega = 0.25^\circ/\text{s}$) can dock.
  3. At $3.0^\circ/\text{s}$, the true rate is $3.0^\circ/\text{s}$, but in $C_0$, angle noise is $\sigma = 12.0^\circ$ with $30\%$ dropouts. Noisy differentiation in the Kalman filter caused the instantaneous estimate $\hat{\omega}$ to spike above $3.2^\circ/\text{s}$, triggering an abort.
  4. In $C_2\_beacon$, active RF telemetry provided direct rate data $\omega_z$. The estimate was stable, resulting in **0 false aborts**.

---

## 4. The `v3.0` Architecture: How `braking_pd` Levels Up Performance

To resolve thruster saturation, overshoot collisions, and propellant exhaustion without altering physical mission constraints, `v3.0` introduced the **Braking PD Controller with Reserved Control Authority**:

### Mathematical Formulation
Instead of commanding raw linear error to the target, `braking_pd` limits the closing velocity reference based on the kinematic stopping distance:

$$v_{\text{closing}} = \min \left( v_{\text{max\_close}}, \; \frac{K_p}{K_d} d, \; \sqrt{2 \cdot \eta \cdot a_{\max} \cdot d} \right)$$

where:
- $d = \|\mathbf{r}_{\text{ref}} - \hat{\mathbf{r}}\|$ is the distance to the reference.
- $\eta = 0.50$ is the **braking acceleration fraction** (reserves 50% of thruster capacity for trajectory tracking and disturbance rejection).
- $v_{\text{max\_close}} = 0.30\text{ m/s}$ is the maximum allowed approach speed.

The total acceleration command incorporates feed-forward centrifugal compensation and orbital CW cancellation:
$$\mathbf{a}_{\text{cmd}} = K_d \left( \mathbf{v}_{\text{ref}} + v_{\text{closing}} \hat{\mathbf{e}}_{\text{close}} - \hat{\mathbf{v}} \right) + \mathbf{\omega}_{\text{est}} \times \mathbf{v}_{\text{ref}} - \mathbf{a}_{\text{CW}}(\hat{\mathbf{s}})$$

Additionally, an active repulsive artificial potential field activates if the chaser penetrates within $1.48\text{ m}$ ($13\text{ cm}$ buffer above keep-out):
$$\mathbf{a}_{\text{barrier}} = 0.06 \left( \frac{1.48 - \|\hat{\mathbf{r}}\|}{0.15} \right) \hat{\mathbf{r}}_{\text{radial}}$$

---

## 5. Quantitative Verification: Baseline vs. Optimized Results

A full 1,050 Monte Carlo campaign was executed under `v3.0` (`results/optimized_v3_0/`) using the exact same paired seeds:

### Overall Campaign Comparison

| Metric | Baseline v2.1 (`legacy_pd`) | Optimized v3.0 (`braking_pd`) | Improvement |
|:---|:---:|:---:|:---|
| **Keep-Out Sphere Violations** | 12 runs (1.14%) | **0 runs (0.00%)** | **100% elimination of collisions** |
| **Delta-V Budget Aborts** | 48 runs (4.57%) | **0 runs (0.00%)** | **100% elimination of fuel aborts** |
| **Overall Pass Rate ($\le 2^\circ/\text{s}$)** | 96.0% | **100.0%** | **+4.0% absolute gain** |
| **$C_2\_beacon$ Pass Rate at $3.0^\circ/\text{s}$** | 63.3% | **100.0%** | **+36.7% absolute gain** |
| **$C_1\_fiducials$ Pass Rate at $3.0^\circ/\text{s}$** | 50.0% | **80.0%** | **+30.0% absolute gain** |
| **Mean Delta-V Expended** | $2.10 - 2.40\text{ m/s}$ | **$1.00 - 1.53\text{ m/s}$** | **45% to 55% fuel reduction** |
| **Mean Mission Duration** | $62.6 - 67.9\text{ s}$ | **$51.4 - 58.4\text{ s}$** | **~10 to 15 seconds faster** |

### Scenario-by-Scenario Pass Rate Matrix

| Scenario | Tumble Rate | Baseline v2.1 Pass Rate | Optimized v3.0 Pass Rate | Status in v3.0 |
|:---|:---:|:---:|:---:|:---|
| **$C_0\_unprepared$** | $0.0^\circ - 2.0^\circ/\text{s}$ | $90.0\% - 96.7\%$ | **$100.0\%$** | Clean capture |
| **$C_0\_unprepared$** | $3.0^\circ/\text{s}$ | $26.7\%$ | **$30.0\%$** | Limited by $\sigma_\theta=12^\circ$ false aborts |
| **$C_0\_unprepared$** | $5.0^\circ/\text{s}$ | $0.0\%$ | **$0.0\%$** | Safe abort gate ($\omega > 3.2^\circ/\text{s}$) |
| **$C_1\_fiducials$** | $0.0^\circ - 2.0^\circ/\text{s}$ | $93.3\% - 100.0\%$ | **$100.0\%$** | Clean capture |
| **$C_1\_fiducials$** | $3.0^\circ/\text{s}$ | $50.0\%$ | **$80.0\%$** | $+30\%$ boost (fuel aborts removed) |
| **$C_1\_fiducials$** | $5.0^\circ/\text{s}$ | $0.0\%$ | **$0.0\%$** | Safe abort gate ($\omega > 3.2^\circ/\text{s}$) |
| **$C_2\_beacon$** | $0.0^\circ - 2.0^\circ/\text{s}$ | $96.7\% - 100.0\%$ | **$100.0\%$** | Clean capture |
| **$C_2\_beacon$** | $3.0^\circ/\text{s}$ | $63.3\%$ | **$100.0\%$** | **$+36.7\%$ boost (perfect capture)** |
| **$C_2\_beacon$** | $5.0^\circ/\text{s}$ | $0.0\%$ | **$0.0\%$** | Safe abort gate ($\omega > 3.2^\circ/\text{s}$) |
| **$C_3\_ios\_mode$** | $0.0^\circ - 5.0^\circ/\text{s}$ | $96.7\%$ | **$100.0\%$** | Clean capture across all tumble rates |

---

## 6. Audit Conclusion & Key Takeaways

1. **Safety gates are functioning as intended:** The 0% pass rate at $5.0^\circ/\text{s}$ for unassisted targets is an intentional safety feature, not a software bug. A non-cooperative GEO satellite tumbling at $5^\circ/\text{s}$ cannot be safely captured within nominal thruster and safety constraints without active detumbling ($C_3$).
2. **The RF Service Beacon ($C_2$) provides critical robustness at high tumble:** At $3.0^\circ/\text{s}$, $C_2\_beacon$ achieves **100% pass rate** compared to only $30\%$ for $C_0$ and $80\%$ for $C_1$. Direct rate telemetry prevents filter lag and eliminates false angular rate aborts.
3. **`braking_pd` eliminates thruster saturation induced collisions:** By reserving 50% acceleration for braking and capping approach velocity to physical stopping distance, keep-out zone penetrations were reduced to absolute zero while halving fuel consumption.
