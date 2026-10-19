# Session 1 — Expert checkpoint answers and agent prompt

Written for: the Orbit Observers team and the industry expert at the Session 1 checkpoint. Everything marked **[verify]** is background knowledge not backed by this repo and must be checked against a source before it goes in a submission.

---

## Part A — Answers to the five checkpoint questions

### Q1. Who uses the solution, and what problem does it solve?

**Problem.** Satellites in geostationary orbit (GEO) that lose power, computer, attitude control or fuel are lost assets. A robotic servicer could refuel, repair or move them, but the last ~12 m of approach to a tumbling client is the hard part. The servicer's camera is noisy, the client's spin rate is unknown, and nothing on the client was designed to be grabbed. Today most clients are "non-cooperative."

**Question we answer.** Which small, cheap features can a manufacturer add *before launch* so the client stays serviceable even after it degrades? Candidates are visual markers (fiducials), an independently powered rate beacon, and a cooperative servicing mode (IOS).

**Users and who benefits**

| User | What they get |
|:--|:--|
| Satellite manufacturers and operators (the buyer of the features) | Evidence for which provisions to add to a bus, and their cost/benefit. Lower risk of stranded assets and an option to extend life. |
| Servicer operators (ClearSpace-type) | Higher terminal-approach success, less propellant and fewer aborts. A defined, testable client interface. |
| Insurers, regulators, agencies | A traceable, reproducible basis for judging servicing safety and debris-mitigation claims. |
| The Phase 2 reviewer (our immediate audience) | A proposal with requirements, evidence, limits and a roadmap. |

**Evidence we have (v4.0, 35,100 runs, tumble 3°/s).** Terminal-window pass rate: unprepared C0 208/500 (41.6%), markers C1 459/500 (91.8%), markers + rate beacon C2 500/500 (100% observed, Wilson 95% interval 99.24–100%). An identity-only beacon (C2-ID) gives the same outcomes as C1, so the gain comes from *rate information*, not from having a radio. Zero keep-out violations in every tested cell.

**What we do not claim.** "Terminal window met" is not physical capture. The v4.0 numbers are not a fleet-wide probability. v4.1 (new seeds, 6,140 runs) adds propagated abort retreat and a covariance gate, but no contact model, no hardware data, and no cost data.

---

### Q2. What are the main parts, and how do they connect?

There are three layers in the repo.

**1. The servicing concept (what we propose a client carries)**

| Provision | Role |
|:--|:--|
| Fiducials / retro-reflectors | Passive pose aid. Works with no client power. |
| Independent rate beacon | Own small power supply (assumed 28.5 mW, 20.52 Wh over 30 days at 1 Hz). Sends identity, timestamp, spin rate + uncertainty, IOS state, health flags. |
| IOS mode | Cooperative handshake and attitude-control handover. Client can slow its own tumble. |
| OSAN | Modular capture/load-transfer zone, with optional power, data, fluid and payload interfaces (functional concept only). |

**2. The simulator, `rpo_project/` (closed loop at 4 Hz, Δt = 0.25 s)**

```
 TRUTH WORLD                MEASUREMENTS                ONBOARD "BRAIN"                 ACTUATION
 dynamics.py  (CW orbit) -> sensors.py  (camera) ----> estimator.py (Kalman filters) -> guidance.py (hold point ->
 attitude.py  (tumble)   -> beacon.py   (rate pkts) -> safety.py    (abort gates)        braking-PD terminal approach)
        ^                    loss / latency / dropouts        |                                   |
        +-------------------------- thrusters (bias, noise, misalignment) <-------------------+
 simulate.py = one run   ->  scoring vs TRUTH: terminal window? keep-out violated?
 montecarlo.py = studies + paired seeds + parallel/Slurm merge -> stats.py -> analyse.py -> report.md, replay.py
 ios.py = standalone IOS state machine, detumble + derated-power estimates (not yet coupled to dynamics)
 config/ = every assumption (SimConfig) and tier definitions (C0, C1, C2-ID, C2, C3)
```

Key rule: guidance and abort logic see only *estimates*, never truth. Truth is used only for scoring.

**3. Support and presentation**
- `hpc/` — MeluXina setup and Slurm scripts (single-node and array + merge). `results/meluxina_v4_1000` is a run from there.
- `results/` — v2.1 baseline, v3.0 optimized, v4.0 (35,100 runs, historical), v4.1 validation (6,140 runs, new seeds).
- `docs/` — user guide, model reference, Monte Carlo method, architecture, Phase 2 proposal, project assessment, pitch script and slides.
- `satellite-ops-platform/` — separate React/Vite **frontend-only demo** of an AI-assisted fleet operations platform (simulated telemetry, role-based approvals, audit log, autonomous agents that pause at human-approval gates). No backend, no real AI, no real spacecraft control. It is a concept demo, not connected to the simulator.
- `examples/stage1/`, `archive/` — earlier pilot and prototypes.

---

### Q3. How does it work normally, and when something goes wrong?

**Normal sequence (five flight modes)**
1. **Ingress** from ~12 m toward a 4 m hold point.
2. **Hold point.** Measure, settle, synchronise with the rotation of the hold point.
3. **Terminal approach**, only if hold error < 1.25 m, speed error ≤ 0.055 m/s, angle uncertainty < 8° and t ≥ 8 s. Follows a square-root braking curve inside a 55° alignment corridor.
4. **Terminal window**: within 20 cm of the capture point, < 5.5 cm/s relative speed, within 15°, held for 2 s. This ends the simulation as a "pass." The grab itself is not modeled.
5. **Abort / retreat** (v4.1: propagated, with a separate fuel reserve).

**Outcomes are kept separate:** terminal-window met, abort (the safety system working), timeout, unsafe (keep-out violation, sphere radius 1.35 m).

**What goes wrong, and what the system does**

| Fault | Modeled handling | Honest limit |
|:--|:--|:--|
| Camera noise, dropouts, occlusion | Kalman filter coasts; position-covariance gate blocks entering terminal approach; covariance-aware standoff and barrier inflation | Noise distributions are assumptions, not measured |
| Beacon packet loss / latency | Time-stamped rate packets; at 1 Hz C2 holds 200/200 up to 50% loss, 199/200 at 75%, and through 2 s latency | Loss and latency tested separately, not jointly; no burst outages |
| Tumble too fast | Rate-gate abort. At 5°/s C0–C2 abort | C3 passes only because spin is cut by an assumed 95% |
| Thruster bias, misalignment, noise | Dispersed every run (2% gain, 0.5° misalignment) | No thruster failure model |
| Estimate degrades in terminal phase | Abort and active retreat | Retreat is simplified; no contact or plume model |
| IOS command stale, replayed, contradictory, or abort while docked | Standalone state machine has handshake, freshness, heartbeat, docked-abort and separation guards | Not coupled to RPO dynamics; auth is a flag, not cryptography |
| Beacon unavailable | Falls back to the optical baseline (C1) | Power independence is arithmetic only, untested on hardware |

**Reproducibility.** Five independent seed streams, paired across tiers, any CSV row re-flown with `python -m rpo_project.replay`. `manifest.json` records config hash, git commit, source SHA-256. Serial = parallel = chunked-merge results.

**Known inconsistency to fix before the meeting:** the README and proposal link to `docs/IMPLEMENTATION_STATUS.md`, but that file was missing and has now been added. The PPTX/PDF exports predate the corrected pitch script.

---

### Q4. Which rules and standards may apply? **[verify all against current editions]**

Nothing in the repo cites a standard, so this is a starting map, not a compliance claim.

| Area | Candidates |
|:--|:--|
| RPO / on-orbit servicing practice | ISO 24330 (RPO and OOS programmatic principles); CONFERS recommended design and operational practices for OOS; the interface names in the brief (MICE, MASI, ASSIST) — check what each actually specifies and who governs it |
| European engineering standards | ECSS series: GNC/AOCS requirements (E-ST-60-30), verification (E-ST-10-02), system engineering (E-ST-10), product assurance (Q-ST-80 software, Q-ST-30 dependability), TRL definitions (ISO 16290 / ECSS-E-AS-11) |
| Debris and end-of-life | ISO 24113; IADC guidelines; ESA Zero Debris approach; GEO graveyard disposal practice (IADC / ITU-R) |
| Modeling and simulation credibility | NASA-STD-7009 (models and simulations credibility) — directly relevant to our "early-stage, low-to-medium fidelity" labeling |
| Licensing and authorization | National space law of the launching/operating state (e.g. Luxembourg 2020 space law, French LOS); the proposed EU Space Act; US FCC rules if US-licensed. Proximity operations on another operator's asset need the client owner's consent and likely regulator notification |
| Radio | ITU Radio Regulations and national frequency licensing for the beacon (band, power, interference to GEO neighbors) |
| Security | Authenticated servicing commands: no crypto is implemented today. Look at CCSDS Space Data Link Security (SDLS) and ECSS cybersecurity guidance |
| Space traffic and insurance | Conjunction and proximity-ops coordination, third-party liability and insurer requirements for approach to a live GEO asset |
| Our own requirements | REQ-RPO-001..006 and RPO-01..04, BEACON-01, IOS-01, OSAN-01, ECON-01 in `PHASE2_PROPOSAL.md` — proposed, not approved by ClearSpace |

---

### Q5. Which existing offers address a similar need, and who buys them? **[verify; none of this is in the repo]**

The proposal itself says a sourced state-of-the-art comparison is still missing. Use this as the list to research.

| Offer | Type | Buyer / customer | Relevance |
|:--|:--|:--|:--|
| Northrop Grumman MEV (Mission Extension Vehicle) and MRV/MEP | Commercial life extension of *non-prepared* GEO satellites (docked to existing features) | GEO operators (Intelsat and others) | Shows operators already pay for servicing without client provisions. The benchmark we must beat on cost and risk |
| Astroscale (ELSA-d, ELSA-M, ADRAS-J, LEXI-GEO) | Debris removal, inspection, life extension; ELSA-M uses a magnetic docking plate on client | Operators (OneWeb), JAXA, UK/ESA agencies | Closest analogue to "client carries a docking aid" |
| ClearSpace (ClearSpace-1 / ESA debris removal, plus servicing roadmap) | Capture of defunct objects | ESA and agencies, operators | The Phase 2 partner; they define the use case |
| Starfish Space (Otter) | Docking, inspection, life extension of GEO/LEO satellites | US Space Force, NASA, commercial operators | Autonomous RPO and capture of non-cooperative clients |
| Airbus, Thales Alenia, OHB, MDA (Canadarm / Gateway, Skyworks) | Servicing hardware, robotic arms, refuel/servicing interfaces | Agencies, prime contractors | Interface and arm suppliers |
| Orbit Fab (RAFTI refuel port), Katalyst, Impulse and similar | Standardised refueling interface and servicing vehicles | Operators, DoD / DARPA | Direct "client-side provision" comparison (a port you add before launch) |
| DARPA RSGS, NASA OSAM-1 (cancelled) and ESA/EU servicing programs | Government demonstrators | Agencies | Maturity and cost reference points |
| Satellite vendors adding grapple fixtures, docking plates or fiducials | Client-side provisioning | Satellite operators | Competing "preparedness" feature sets that OSAN would be compared against |

**Gaps relative to ours:** most listed offers fix the servicer. Few address a degraded client that has lost power or computer (independent beacon plus IOS handover). That is the distinguishing idea in the brief, but its economic value is **not yet quantified**. ECON-01 needs costed integration, full-mission fuel and break-even sensitivities.

---

## Part B — Ready-to-paste prompt for the expert's AI agent

Copy everything inside the block. Fill nothing in. It is self-contained so it works in a fresh session.

````text
You are acting as an independent reviewer for a space-systems study. I am a student team member
presenting at an expert checkpoint. Answer the five questions below using the project summary
I give you. Where you rely on knowledge outside my summary, label it "[external - verify]".
Where my summary does not support a claim, say so. Do not invent numbers, standards clause
numbers, prices, or company facts. If unsure, say "unknown". Challenge weak points.

=== PROJECT SUMMARY ===
Name: Orbit Observers / ClearSpace Phase 2 - client-side serviceability for degraded GEO satellites.
Question: Which cheap provisions added to a satellite before launch keep it serviceable by a
robotic servicer after it degrades (power, computer, comms, attitude control)?

Candidate provisions (client tiers):
 C0 unprepared; C1 visual fiducials/retro-reflectors; C2-ID fiducials + identity-only beacon
 (ablation control); C2 fiducials + independently powered beacon sending identity, timestamp,
 spin rate + uncertainty, IOS state, health flags; C3 C2 + cooperative IOS mode where the client
 slows its tumble (modeled only as a 95% cut in initial spin, not a controller).
 Also a concept OSAN: modular capture/load-transfer zone with optional power/data/fluid/payload
 interfaces (functional concept only, no loads/structure model).

What I built (Python, rpo_project/):
 - Closed-loop RPO simulator at 4 Hz: Clohessy-Wiltshire relative orbit (RK4 + analytic STM),
   quaternion rigid-body tumble, camera/fiducial sensor with noise/dropouts/occlusion, beacon
   packets with loss and latency, Kalman filters (position/velocity and angle/rate), hold-point
   then braking-PD terminal approach guidance, abort gates, 1.35 m keep-out sphere.
 - Guidance/abort see only estimates, never truth; truth is used only for scoring.
 - Flight modes: ingress (~12 m) -> 4 m hold point -> terminal approach (gates: hold error <1.25 m,
   speed error <=0.055 m/s, angle uncertainty <8 deg, t>=8 s, 55 deg corridor) -> terminal window
   (<20 cm, <5.5 cm/s, <15 deg for 2 s) -> or abort/retreat.
 - Monte Carlo: five independent seed streams, paired seeds across tiers, dispersions of initial
   state, client orientation, spin-axis tilt (2 deg), inertia (5%), camera noise, beacon loss,
   thruster gain bias (2%) and misalignment (0.5 deg). Four studies: tier vs tumble, beacon
   loss x rate ablation, tumble x camera-noise envelope, beacon latency. Wilson 95% intervals,
   exact McNemar paired tests, zero-event upper bounds, convergence. Runs serial, parallel, and on
   the MeluXina HPC via Slurm with validated chunk merge. Manifest records config hash, git
   commit, source SHA-256. Any run can be replayed.
 - ios.py: standalone IOS state machine (Normal -> Service standby -> Approach permitted -> IOS
   handover -> Mated/servicing -> Verification -> Release -> Normal) with handshake, freshness,
   heartbeat, docked-abort and separation guards, plus detumble and derated-power estimates. NOT
   coupled to the RPO dynamics. Authentication is a flag, not cryptography.
 - Separate React/TypeScript frontend-only demo (satellite-ops-platform/): simulated fleet
   monitoring, role-based approvals, audit log, autonomous agents that stop at human-approval
   gates. All data is fabricated; no backend, no real AI, no real control. Not linked to the sim.
 - Docs: user guide, model reference, Monte Carlo method, architecture, Phase 2 proposal with
   candidate requirements (RPO-01..04, BEACON-01, IOS-01, OSAN-01, ECON-01) and 6 work packages.

Evidence (model, not hardware):
 - v4.0: 35,100 runs, 500 paired seeds per main cell. At 3 deg/s terminal-window pass: C0 208/500
   (41.6%, 37.36-45.97%), C1 459/500 (91.8%, 89.06-93.90%), C2-ID same as C1, C2 500/500
   (99.24-100%). Mean successful delta-v C1 1.524 -> C2 1.482 m/s; prediction RMS 0.0781 -> 0.0447 m.
 - 0 keep-out violations; minimum sampled clearance +2.9 mm. Seeds are reused across cells so no
   pooled safety bound is claimed; per-cell one-sided 95% bound ~0.60% (500 seeds), ~1.49% (200).
 - Beacon at 1 Hz: C2 200/200 through 50% packet loss, 199/200 at 75%; latency up to 2 s 200/200;
   joint worst cases untested.
 - At 5 deg/s C0-C2 abort; C3 passes only via the assumed 95% spin reduction. No 10 deg/s cell.
 - v4.1 (new master seed, 6,140 runs): propagated abort retreat with separate fuel reserve,
   position-covariance gate, 0/6,140 keep-out violations (descriptive only).
 - Beacon power arithmetic only: assumed 28.5 mW average, 20.52 Wh over 30 days; unvalidated.
 - Self-assessed 80/100 against the Phase 2 brief (qualitative, not an official score).
Known limits: low-to-medium fidelity; "terminal window met" is not physical capture; no contact,
 plume, or structural model; no hardware data; ClearSpace has not endorsed the requirements; no
 costed economics; no sourced state-of-the-art comparison; docs/IMPLEMENTATION_STATUS.md was
 missing (now added); slide exports are out of date.

=== QUESTIONS ===
Q1. Who uses the solution, and what problem does it solve?
Q2. What are the main parts, and how do they connect?
Q3. How does it work normally and when something goes wrong?
Q4. Which rules and standards may apply?
Q5. Which existing offers address a similar need, and who buys them?

=== HOW TO ANSWER ===
For each question give: (a) a direct answer in 5-10 lines, (b) what in my summary supports it,
(c) what is missing or weak, (d) one concrete next step. For Q4 and Q5 use tables, name specific
standards/products with the exact title or scope you are confident about, and flag every item
[external - verify]. For Q3 include a fault table: fault, expected system response, what evidence
I have, what test is missing. Finish with: the three biggest risks to my proposal and the three
questions an expert reviewer would most likely ask me, with a suggested honest answer to each.
````

---

## Part B2 — Fit with the NeoSpace / SPAIDER playbook

Source: `NeoSpace Hackathon - SPAIDER Student Playbook.pptx`. The five Q1–Q5 above are the **Session 1** checkpoint questions (Concept V1 + system sketch + evidence). The playbook's prompt shape is *context + question → constraints + assumptions → requested output*, which Part B follows. Later sessions reuse the same repo material:

| Playbook session | Checkpoint asks | Where the answer already is |
|:--|:--|:--|
| 1 Concept definition | users/problem, parts, normal/failure, standards, existing offers | Part A above; [SCOPE_ARCHITECTURE.md](SCOPE_ARCHITECTURE.md) |
| 2 Integrated solution | feedback effects, requirements, uncertainty, buyer/business, costs and feasibility tests | requirements in [PHASE2_PROPOSAL.md](PHASE2_PROPOSAL.md) §5; [ECONOMICS_MODEL.md](ECONOMICS_MODEL.md); [BEACON_BENCH_PLAN.md](BEACON_BENCH_PLAN.md) |
| 3 Proposal + plan (10–15 pages: technology 5, business 3, implementation 4) | what changed, customers/revenue, R&D milestones, funds, evidence/risks | proposal §6 work packages, roadmap in SCOPE_ARCHITECTURE §10, economics assumptions (to be replaced with real quotes) |

Playbook-specific gaps: patent search (Espacenet / IPIL) is not done, and the Q4/Q5 tables are unsourced until the SPAIDER libraries (code in the playbook) or web sources are checked. Record expert feedback in a table of comment / response / owner.

## Part C — Fix list before the meeting
1. ~~Add `docs/IMPLEMENTATION_STATUS.md`~~ (done).
2. Re-export the PPTX/PDF from the corrected pitch script.
3. Build the sourced state-of-the-art table (Q5) and standards map (Q4), including a patent check.
4. Decide whether the ops-platform demo is in scope for this checkpoint; if yes, state clearly it is a simulated concept.
5. Cost the integration of each tier (ECON-01) or say plainly it is not yet done.
