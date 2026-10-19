# Phase 2 proposal: serviceability when the client is degraded

**Status:** internal proposal draft, 17 October 2026. Requirements and work-package assignments below are proposed, not approved by ClearSpace. No funding, partner endorsement or hardware qualification is claimed.

## Implementation update — 19 October 2026

v4.1 now propagates active abort retreats and includes a position-covariance gate. The standalone `ios.py` has tested handshake, freshness, heartbeat, docked-abort and separation guards, plus detumbling and derated-power estimates. See [implementation status](IMPLEMENTATION_STATUS.md) and [v4.1 validation](../results/v4_1_validation/report.md). The original v4.0 evidence and proposed hardware gates below remain historical/proposed; IOS logic is now driven by the approach outcome (`ios_coupling.py`) but not by joint attitude-control dynamics.

## 1. Executive summary and decision requested

We propose a layered client-side serviceability concept: passive navigation aids and known capture geometry for unpowered clients; an independently powered rate beacon for degraded clients; and a defined control-handover mode for cooperative clients. A modular service zone, OSAN, would combine capture/load transfer and navigation references with optional power, data, fluid and payload interfaces.

The evidence available today is a 35,100-run RPO simulation campaign. At 3°/s, terminal-window passes increase from 208/500 for an unprepared client to 459/500 with fiducials and 500/500 with rate telemetry. This supports further validation of navigation aids and rate information. It does not establish physical capture, safe retreat, hardware feasibility or profitability.

**Requested next decision:** agree the reference client, degraded failure cases and interface constraints with the industry reviewer; then authorize a ground-validation study with agreed success criteria. Budget and schedule require team estimates and reviewer agreement before submission.

## 2. Need, innovation and comparison baseline

The reference brief asks which minimum client-side features are technically useful, economically justified and ready for a product roadmap. Its distinguishing idea is retention of serviceability after main power, computer or communications degrade. The simulator addresses one part: relative approach near an assumed capture fixture.

The baseline comparison is C0 versus C1 versus C2 under paired disturbances. C2-ID isolates the value of rate information. C3 currently assumes a 95% reduction in initial tumble; it is a sensitivity case, not an implemented IOS handover controller. All tiers share capture geometry, so this campaign does not isolate the benefit of adding a mechanical capture interface.

Before external submission, add a sourced state-of-the-art comparison for the interfaces named in the brief (MICE, MASI and ASSIST), including compatibility and integration gaps. Their names in the brief do not establish interoperability or permission to claim endorsement.

## 3. Proposed architecture and failure boundaries

| Client state | Available provisions | Intended operation | Evidence and open gap |
|:--|:--|:--|:--|
| Nominal/cooperative | Fiducials, beacon, functioning attitude control | Authenticate servicing permission; coordinate control authority | C3 initializes slower tumble; command transitions and authority guards now exist as a separate tested model |
| Degraded computer/comms | Independent beacon power, rate sensing and RF; passive markers | Retain rate and interface data when main bus services fail | Packet loss and latency modeled; power independence and hardware untested |
| Unpowered/non-cooperative | Passive fiducials and known capture geometry | Estimate motion optically; refuse approaches outside the validated envelope | C1 modeled; geometry, illumination and occlusion need physical validation |
| Mated/servicing | OSAN load path and selected service interfaces | Transfer loads and agreed power/data/fluids/POD services | Functional concept only; no structural or contact model |

Proposed beacon fields: version, client identity, timestamp/sequence, rate and uncertainty, interface identifier, health flags, IOS state and authentication data. The current code models identity and noisy rate delivery; an `authenticated_id` field is not a cryptographic implementation. Reject stale/replayed or unauthorized commands in a future implementation. A failed beacon leaves the optical baseline available.

The independent beacon requires explicit fault isolation from main-bus shorts and resets, a reserve-energy allocation, antenna coverage, and measured behavior after main power loss. These requirements need a bench demonstration.

## 4. IOS mode and OSAN functional concept

Proposed state sequence: **Normal → Service standby → Approach permitted → IOS handover → Mated/servicing → Verification → Release → Normal**.

| Transition | Proposed guard / action | Verification needed |
|:--|:--|:--|
| Standby to permitted | Valid identity, fresh state data and explicit mission authorization | Unauthorized, replayed and stale-command injection |
| Permitted to handover | Agreed rate envelope; both vehicles acknowledge who controls attitude | Lost acknowledgment, contradictory authority and timeout tests |
| Handover to mated | Confirm contact/latch and load-path state before service transfer | Contact/load test and false latch indication |
| Mated to release | Isolate service connections and confirm separation readiness | Failed valve/connector, residual load and separation tests |
| Any servicing state to abort | Stop approach/service; agree predictable client behavior; execute verified retreat or mated safe state | v4.1 simulates active retreat and fuel; standalone IOS preserves mated authority. Coupled fault tests remain |

OSAN layout concept: a mechanically verified capture/load-transfer location with fiducials referenced to the same coordinate frame; a nearby data/power connection zone; separately isolated optional fluid and POD connections. Keep servicing access and antenna visibility outside appendage and thruster exclusion zones. Dimensions, loads, connector choices and interface compatibility remain design inputs.

## 5. Candidate requirements and acceptance evidence

These are proposed tests and allocations. Numerical simulator settings are assumptions pending validation.

| ID | Candidate requirement | Current evidence | Exit criterion / missing evidence |
|:--|:--|:--|:--|
| RPO-01 | Retain a clear benefit from passive markers under matched disturbances | C0 41.6%, C1 91.8% at 3°/s | Repeat on a held-out master seed and measured optical error distributions |
| RPO-02 | Demonstrate added value of angular-rate telemetry | C2-ID = C1 pass outcomes; C2 500/500 at 3°/s | Predeclare acceptance target; lower 95% pass bound ≥99% at the agreed nominal cell; validate rate noise on hardware |
| RPO-03 | Characterize link degradation at 1 Hz | Separate packet-loss and latency studies | Joint loss/latency tests, burst outages and changing rates; no extrapolation from separate sweeps |
| RPO-04 | Report safety per tested tier/grid cell and preserve truth/estimate separation | Zero recorded keep-out violations; estimate-driven control | v4.1 implements position-covariance faults and propagated retreat; independent safety review and physical geometry checks remain |
| BEACON-01 | Operate after loss of main computer/comms and power | Power arithmetic only: assumed 28.5 mW, 20.52 Wh/30 days | Bench test isolated reserve supply, RF link, sensing and derated usable energy |
| IOS-01 | Maintain unambiguous attitude-control authority | C3 slower initial condition only | State-machine fault tests and coupled vehicle dynamics during handover |
| OSAN-01 | Provide a defined, accessible capture load path and optional service interfaces | Shared simplified capture point | Interface drawing, tolerances, loads, appendage clearances and ground demonstration |
| ECON-01 | Quantify lifecycle value against added client cost | Approach propellant and assumed retries only | Costed integration/qualification, full mission fuel, failure consequences and sensitivity break-even |

A 500/500 cell has a Wilson 95% pass interval of about 99.24–100%. Zero unsafe events in 500 independent seeds gives a one-sided 95% upper bound of about 0.60%; with 200 seeds it is about 1.49%. These are pointwise model bounds, not flight guarantees or simultaneous grid certification.

## 6. Work packages, outputs and milestone gates

Owners are team roles from the reference brief; named assignments and durations remain to be agreed.

| WP / proposed owner | Output | Completion gate |
|:--|:--|:--|
| 1 Systems / proposal lead | Reference mission, requirements, state-of-the-art matrix, interface and assumption register | Reviewer agrees scope and measurable targets |
| 2 RPO / GNC | Fault cases, position-covariance handling, retreat, 3-D estimation and contact-model plan | Hold-out campaign meets agreed per-cell targets; failures replayed and explained |
| 3 HPC / analysis | Versioned campaign inputs, source provenance, paired comparisons and uncertainty | Serial/parallel agreement, validated chunk merge, archived independent replication |
| 4 Beacon / communications | Packet definition, isolation design, link and derated energy budget | Power-off and loss/latency bench tests with recorded measurements |
| 5 IOS / OSAN | Control authority state machine, functional layout and load/interface allocation | Fault-injection review and ground handover/interface demonstration |
| 6 Business / roadmap | Cost ranges, mission-value sensitivities, operational/regulatory issues for expert review | Quantified break-even and a feasible next-stage budget/schedule |

Milestones: **M1 agreed study baseline → M2 independent simulation replication → M3 beacon/optical/handover ground demonstrations → M4 integrated demonstration proposal → M5 in-orbit demonstration decision**. Progress to the next milestone depends on its evidence gate; none of M3–M5 is complete.

## 7. Economic case and risk register

For a simplified repeatable approach, expected propellant per terminal window is `m_pass + (p_abort / p_pass) × m_abort`. This assumes independently repeated attempts, no unsafe or timeout outcomes, and an illustrative 0.14 kg abort/retreat cost. Real failed clients may remain unserviceable on every retry. The generated report derives this sensitivity from the current campaign; it must not be marketed as satellites rescued per tank.

An economic decision requires: expected avoided loss or service value, minus installation, integration, qualification, operations and additional mission costs. Carry ranges for each term and report where net value changes sign. No euro ROI or battery mass has been validated here.

| Risk | Why it matters | Mitigation / next evidence |
|:--|:--|:--|
| Optimistic sensing and planar estimation | Real faults may invalidate the apparent envelope | Measured sensor errors, larger tilt and burst-outage trials |
| Controller tuning on the reported seeds | Results may overstate generalization | Freeze configuration, then run unseen master seeds |
| Unmodeled abort/contact | Active retreat is now simulated but does not prove passive safety or capture | Validate reserve sizing, geometry, sample spacing and contact |
| Beacon common-cause failure | Main-bus failure could disable the supposedly independent beacon | Isolation and power-loss testing |
| IOS authority conflict | Both vehicles may command incompatible motion | Handshake, timeout and coupled-control fault tests |
| Unsupported economics | Approach savings may be small relative to total service costs | Full mission/integration costs and sensitivity ranges |
| Missing source snapshot | Existing manifest records a dirty working tree | v4.1 archives source/config hashes; retain snapshots and reproduce the recorded environment |

## 8. Basis and submission checklist

Local goal sources: [Phase 2 Serviceability slides](reference/Phase2_Serviceability.pptx), especially slides 1, 3–11, and [ClearSpace discussion brief](reference/Phase2_ClearSpace_Call.pptx), slides 4–11. Evidence: [v4.0 report](../results/v4_0/report.md), [model reference](MODEL_REFERENCE.md), [Monte Carlo method](MONTE_CARLO_METHOD.md).

Before submission: obtain reference-mission feedback; complete sourced state-of-the-art and cost comparisons; assign owners, dates and budget; independently replicate results; regenerate the presentation exports from the corrected script. This draft has not been submitted externally.
