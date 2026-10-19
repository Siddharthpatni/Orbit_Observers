# Presentation pack: Business, Technical, Serviceability

Source for the format: `NeoSpace Hackathon - SPAIDER Student Playbook.pptx` (three sessions, 10–15 page proposal split Technology 5 / Business 3 / Implementation 4, then a **5-minute pitch + 5-minute Q&A**). Companion deck: [presentation/Orbit_Observers_Pitch.pptx](presentation/Orbit_Observers_Pitch.pptx). Every number below names the file it comes from. Anything marked **ASSUMPTION** or **[verify]** is not evidence.

---

## 1. How our idea compares with the playbook

### 1.1 Process and deliverables

| Playbook asks for | Where we are | Status | Action before presenting |
|:--|:--|:--|:--|
| S1: users and problem | [EXPERT_CHECKPOINT_SESSION1.md](EXPERT_CHECKPOINT_SESSION1.md) Q1, [SCOPE_ARCHITECTURE.md](SCOPE_ARCHITECTURE.md) §1–2 | Done | Ask ClearSpace to confirm the gap (deck B questions) |
| S1: ConOps, normal and disrupted use | Flight modes, fault table, three client states ([SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md), checkpoint Q3) | Done | None |
| S1: patents and market search | Competitor list is from memory, unsourced | **Gap** | Search Espacenet/IPIL and company sources; mark every row sourced or dropped |
| S1: architecture, data flow, deployment, human authority | [PLATFORM_ARCHITECTURE.md](PLATFORM_ARCHITECTURE.md), [SCOPE_ARCHITECTURE.md](SCOPE_ARCHITECTURE.md) | Done | None |
| S2: feedback turned into changes | No expert feedback recorded yet | **Gap** | Use the feedback table in §7 after the checkpoint |
| S2: requirements and IP positioning | Requirements RPO-01..04, BEACON-01, IOS-01, OSAN-01, ECON-01 ([PHASE2_PROPOSAL.md](PHASE2_PROPOSAL.md) §5); no IP view | Partial | State what is new vs prior art after the patent search |
| S2: regulatory approach | Standards map exists, unsourced ([checkpoint](EXPERT_CHECKPOINT_SESSION1.md) Q4) | Partial | Verify each standard and name the authorisation steps |
| S2: business model and key-assumption test | [ECONOMICS_MODEL.md](ECONOMICS_MODEL.md): all prices assumed | Partial | Test the one assumption that drives value (P(needs rescue), §3.3) with ClearSpace/operators |
| S3: R&D plan, TRL, milestones | Roadmap in SCOPE_ARCHITECTURE §10; TRL statement below | Partial | Agree gates with the reviewer |
| S3: budget and use of funds | Draft in §5, **ASSUMPTION** | Draft | Replace with quotes |
| S3: 10–15 page proposal | Proposal draft + this pack | Draft | Assemble from §2–§4 |
| Pitch 5 min + Q&A 5 min | Script in §6, deck built | Done | Rehearse to time |

### 1.2 Your three areas vs the playbook's three workstreams

| Playbook workstream | Your area | Note |
|:--|:--|:--|
| Technology (5 pages) | **Technical** + **Serviceability** | Serviceability is the product concept; Technical is how it is built and proven |
| Business (3 pages) | **Business** | Includes market, offer, revenue, costs |
| Regulation (own thread in S2) | folded into Business and Technical | Playbook treats it as a separate thread. Show at least one slide row so it is not read as a gap |
| Implementation (4 pages) | closing section of each area | Roadmap, work packages, budget, risks |

### 1.3 Where we are stronger or weaker than a typical entry

* **Stronger:** reproducible quantitative evidence (74 tests, paired Monte Carlo, intervals, manifest/source hash), an integrated demo (dashboard, downlink, fuel), explicit limits on every claim.
* **Weaker:** no customer evidence, no patent search, costs assumed, nothing built in hardware. Judges asking "who pays and how do you know" will hit the weakest point, so lead with the mechanism and be open that value is an assumption.

---

## 2. SERVICEABILITY: what the product is

**One sentence.** The minimum client-side preparation that keeps a satellite serviceable in every state: nominal, degraded, and non-cooperative or tumbling. Not another docking port.

### 2.1 Three states, five layered elements

| Client state | What still works | Element that carries serviceability | Case |
|:--|:--|:--|:--|
| Nominal / cooperative | Bus, comms, attitude control | IOS mode (control handover), authenticated beacon | C3 |
| Degraded / partially cooperative | Independent beacon power and RF | Independent Service Beacon (rate, ID, interface, health, IOS state, authentication) | C2 |
| Non-cooperative / tumbling | Nothing powered | Fiducials plus MICE-like capture provision | C1 (C0 = none) |
| High-value platforms, all states | | OSAN service zone: capture and load transfer, power/data, optional fluid, POD attachment | functional concept |

### 2.2 The serviceability envelope (our headline evidence)

Terminal window met in the model, 100 paired seeds per cell, new seed ([results/v4_1_validation/report.md](../results/v4_1_validation/report.md)):

| Tumble | C0 unprepared | C1 markers | C2 marker + rate beacon | C3 IOS mode |
|--:|--:|--:|--:|--:|
| 1°/s | 100% | 100% | 100% | 100% |
| 2°/s | 93% | 100% | 100% | 100% |
| 3°/s | 41% [32–51] | 92% [85–96] | 100% [96–100] | 100% |
| 5°/s | 0% | 0% | 0% | 100% (assumes the client damps its own spin) |

v4.0 (35,100 runs, 500 seeds per main cell) at 3°/s: 41.6% → 91.8% → 100% ([results/v4_0/report.md](../results/v4_0/report.md)).

**What it means.** Below about 1°/s preparation does not matter; the value sits in the band around 2–3°/s where an unprepared client starts to fail; above the rate gate nothing passive helps and only client cooperation does. An identity-only radio changes nothing (C2-ID = C1); the gain comes from **rate information** (+8 pp, p = 0.008, exact McNemar).

### 2.3 Minimum beacon content and size

Six items from the deck (ID, interface location/type, IOS state, health flags, angular rate, authentication) fit a 27-byte packet: 11.3 ms at 19.2 kbit/s, consistent with the 15 ms slot in the power budget ([SCOPE_ARCHITECTURE.md](SCOPE_ARCHITECTURE.md) §5). Interface location/type and health flags are specified but not yet modelled.

### 2.4 Serviceability tiers (product family from the ClearSpace deck)

| Tier | Provisions | Servicing option it enables |
|:--|:--|:--|
| 1 EOL-ready | MICE-like capture + fiducials | Removal |
| 2 Service-ready | + IOS mode + beacon | MEV-style attached propulsion |
| 3 Life-extension-ready | + refuelling / propulsion augmentation | Refuel-and-release, propulsion POD |
| 4 Augmentation-ready | + power/data + upgrade POD (OSAN) | Upgrade POD |

### 2.5 What "serviceable" does not mean here

Not physical capture (no contact model), not safe retreat proven (passive safety not established), not interoperable with MICE/MASI/ASSIST (references, not certified choices). The GEO chemical → hybrid → electric transition is a question for ClearSpace; our model uses one fixed capture point.

---

## 3. BUSINESS

### 3.1 Problem and buyers

* **Problem:** legacy GEO clients are non-cooperative; the servicer carries all the risk and cost; future all-electric platforms remove accidental capture features (deck B, slide 7).
* **Likely early stakeholders** (Guide §17): commercial GEO telecom operators, high-value institutional and weather owners, spacecraft OEMs, servicing providers. LEO fleet operators for low-mass design-for-removal. **These are hypotheses, not validated customers.**

### 3.2 Offer and revenue logic (hypotheses)

| Offer | Buyer | How it earns | Evidence |
|:--|:--|:--|:--|
| Tiered serviceability kit (tiers 1–4) | OEM or operator at build time | Unit price per satellite; royalty or licence for the interface set | Cost per tier modelled, price not tested |
| Servicing at lower risk | Servicer operator | More successful visits per vehicle, lower price per success | Break-even price per success €32.0 M (C0) vs €19.5–20.0 M (C1–C3) at 3°/s |
| Evidence and assessment service | Insurers, regulators, agencies | Reproducible serviceability envelopes per client class | Method exists (manifest, replay) |

### 3.3 Economics (all inputs ASSUMPTION; outcomes from the simulator)

Source: [ECONOMICS_MODEL.md](ECONOMICS_MODEL.md), regenerated by `tools/generate_model_docs.py`.

* One successful rescue is worth **€20.8 M** net of price, discounted (assumed: €40 M/yr revenue, 60% margin, 5-year extension at year 10, 8% discount, €75 M price).
* Cost of preparation per client (cumulative): fiducials €45 k; + beacon €404 k; + IOS mode €1.15 M. Product tiers 1–4: **€0.36 M, €1.46 M, €2.18 M, €6.68 M** (assumed unit, mass, launch, NRE).
* **Break-even P(client ever needs rescue):** fiducials vs none **0.6%** at 3°/s. Beacon vs fiducials 75% at 3°/s (rate beacon is not repaid by RPO benefit alone). IOS mode vs none 14.5% at 3°/s and 5.3% at 5°/s.
* Reading: fiducials are an easy decision; the beacon needs value outside the simulator (identity, interface data, health, state before committing a servicer) to justify itself; IOS mode is justified where tumble can exceed the passive limit.
* Servicer throughput: about 21–22 visits per vehicle (fuel limited); expected successes 13.4 (C0) vs 21.5–22.0 (C1–C3).

**The one assumption to test first:** the probability that a client degrades enough to need rescue. It dominates every break-even. Ask operators and ClearSpace for failure statistics.

### 3.4 Competition and positioning **[verify all]**

Servicers with non-prepared clients (Northrop Grumman MEV/MRV, Astroscale, Starfish Space, ClearSpace) and interface or refuel providers (Orbit Fab, MDA, Airbus, Thales Alenia, OHB) are the reference set ([checkpoint Q5](EXPERT_CHECKPOINT_SESSION1.md)). Positioning: most fix the servicer; we specify the **client's minimum preparation for the degraded state**. Needs a sourced comparison and a patent check before it is claimed as novelty.

### 3.5 Regulation and standards as business enablers **[verify all]**

ISO 24330 (RPO/OOS programmatic principles), ISO 24113 and IADC (debris), ECSS series (GNC, verification, interface management ECSS-E-ST-10-24C), NASA-STD-7009 (model credibility), ITU/national licensing for the beacon, owner consent and national authorisation for proximity operations, EU Space Act (evolving). Security: authenticated, replay-protected commands (CCSDS SDLS-style). Implication: authentication in the beacon and IOS is a requirement, not an option.

### 3.6 Business risks

Value rests on assumed failure probability and price; buyers may prefer servicer-side solutions; added mass and cost at the OEM; standards fragmentation (MICE/MASI/ASSIST); regulatory timing.

---

## 4. TECHNICAL

### 4.1 System in one view

Ground (dashboard, agents, policy, human approval, audit) ↔ servicer ↔ client (fiducials, beacon, IOS, capture). Simulator layers: truth physics (Clohessy-Wiltshire, quaternion tumble) → noisy sensors and beacon packets → Kalman estimators → guidance and abort gates → thrusters, scored against truth. Flight logic never sees truth. Full diagrams: [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md), [PLATFORM_ARCHITECTURE.md](PLATFORM_ARCHITECTURE.md).

### 4.2 What is built and verified

| Component | What it does | Evidence |
|:--|:--|:--|
| RPO Monte Carlo (`rpo_project`) | Closed-loop approach, 5 independent seed streams, paired tiers, Wilson intervals, McNemar tests | 74 tests; serial = parallel = chunked merge; manifest with config hash and source SHA-256; any run replayable |
| IOS state machine + coupling | Ground approval gates IOS; handover refused above 3.25°/s; abort from any state; C3 spin from a physical detumble | 8 coupling tests; physical detumble reaches the assumed 5% residual in about 206 s, about 0.06 kg client propellant at 3°/s |
| Abort and retreat (v4.1) | Propagated retreat with reserve fuel, covariance gate | 0 keep-out violations in 6,140 runs (a count, not a pooled bound); 61 of 482 aborted main-study runs ended with an estimate mismatch |
| Beacon engineering | 28.5 mW average, 20.5 Wh per 30 days ideal, 49.2 Wh derated nameplate, about 302 g | Bench plan B1–B7, virtual bench of 20,000 builds ([BEACON_BENCH_PLAN.md](BEACON_BENCH_PLAN.md)); no hardware |
| Fuel gauging | Book-keeping + PVT fused by a 3-state filter, leak and sensor flag | About 1.2 kg RMS from an 800 kg start; ±2σ band covers truth about 99%; leak flagged in 100/100 runs |
| On-board recorder and downlink | Hash-chained logs, priority downlink, gaps visible | 6 tests; dashboard page |
| Platform | Dashboard, server-side approval and mission rules, hash-chained audit, feasibility from campaign data | 10 API tests |

### 4.3 Maturity statement (use verbatim)

"Early-stage, scenario-based, low-to-medium-fidelity RPO robustness assessment." Current maturity is simulation and concept (our judgement: about TRL 2–3). The proposed target for the next stage is a ground demonstration (about TRL 4–5). **TRL values are our judgement, not an assessed rating.**

### 4.4 Known limits (say them before you are asked)

No contact, latch, plume or structural model; "terminal window met" is not capture. Passive safety of the retreat is not established. IOS is coupled by outcome, not by joint attitude-control dynamics. Authentication is a simulation token. Link tests vary one factor at a time. Envelope ends at 5°/s. All noise, power and gauging figures are assumptions; Basilisk cross-check (V4) not done.

---

## 5. Implementation plan and draft budget (ASSUMPTION)

### 5.1 Roadmap

| Stage | Content | Exit evidence |
|:--|:--|:--|
| Study (now) | Envelopes, beacon/IOS concept, OSAN layout, tier trade | Reviewer agrees scope and targets; hold-out campaign meets per-cell targets |
| Ground demo | Software-in-loop, comms and controller demo, beacon bench B1–B7, HIL/contact tests | All bench tests pass; contact model validated against a rig |
| IOD | Prepared client plus servicer rendezvous | Ground-demo gates, owner consent, national authorisation |
| Product family | Tiers 1–4 as catalogue items | IOD result; positive cost-benefit per tier for target clients |

### 5.2 Draft budget for the ground-demo stage (ASSUMPTION; replace with quotes)

Loaded rate €8,000 per person-month (assumed).

| Work package | Person-months | Hardware / services € | Notes |
|:--|--:|--:|:--|
| 1 Systems and proposal | 6 | 0 | |
| 2 RPO/GNC: contact model, 3-D, Basilisk cross-check | 12 | 0 | |
| 3 HPC and analysis | 4 | 0 | assumes an allocation grant covers compute |
| 4 Beacon bench | 6 | 160,000 | EM units 120 k, chamber 15 k, RF 25 k |
| 5 IOS/OSAN: HIL rig, layout, loads | 8 | 150,000 | rig cost assumed |
| 6 Business, regulatory, standards | 4 | 40,000 | external advice assumed |
| **Subtotal** | **40** | **350,000** | 40 × 8,000 = 320,000 effort |
| Contingency 15% | | | (320,000 + 350,000) × 0.15 = 100,500 |
| **Total** | | | **€770,500** |

Use of funds in one line: about 42% people, 45% bench and rig hardware, 13% contingency.

### 5.3 Delivery risks

Contact-model fidelity; hardware lead time; reviewer and ClearSpace not aligned on the reference client; assumed costs wrong by a large factor; single-team dependence.

---

## 6. The 5-minute pitch (customer view, money first)

Deck: [presentation/Orbit_Observers_Pitch.pptx](presentation/Orbit_Observers_Pitch.pptx), 12 main slides plus 4 backup. Notes are in each slide's speaker notes. Numbers are generated by `tools/deck_numbers.py`. Playbook Session 3 questions: Q1 what changed, Q2 customers and revenue, Q3 R&D steps, Q4 funds, Q5 evidence and risks.

| Time | Slide | Message |
|:--|:--|:--|
| 0:00 | 1 Title and video | Turn a stranded satellite into a recoverable asset |
| 0:15 | 2 The money problem | A failed GEO satellite strands about EUR 120 M of value (assumed); a rescue costs EUR 75 M; the owner keeps EUR 45 M, if the servicer can reach it |
| 0:40 | 3 Three customers | Operator or maker: does the kit pay (16.5x on markers). Servicer: more clients per vehicle (break-even price -37%). Insurer or regulator: can I trust the number (0 violations in 6,140 runs, replayable) |
| 1:05 | 4 The offer | Four priced tiers, EUR 0.36 M to 6.68 M per satellite (assumed) |
| 1:30 | 5 Return on spend | Markers return 16.5x; EUR 7.4 M expected benefit on a 10-satellite fleet for EUR 0.45 M; beacon and IOS pay for the right risk |
| 2:00 | 6 When it pays | Break-even chance of ever needing rescue: 0.6% (markers), 5.3% (IOS at 5 deg/s); test this first |
| 2:25 | 7 Why it works | Success within 3 attempts 64% to 98%; missions lost 30% to 2%; three client states covered |
| 2:50 | 8 Servicers | 13.4 to 21.5 rescues per vehicle; break-even price EUR 32.0 M to 20.0 M |
| 3:05 | 9 What is new | Paired preparation measurement, degraded-state handover layer, money chain; builds on Naasz, Madonna, Opromolla, CONFERS, Sullivan |
| 3:25 | 10 Trust | 74 tests, 41,240 runs, what we do not claim |
| 3:45 | 11 How we earn, competition, rules | Kit, servicer partnerships, evidence service |
| 4:10 | 12 Plan, funds, asks | Each stage proves one money assumption; EUR 770 k draft; three asks |
| 4:45 | Close | A small preparation now. A recoverable asset later |

Backup: reference architecture, money inputs, evidence vs assumed, plus the Q&A in section 7.

---

## 7. Q&A preparation (10 likely questions, honest answers)

| Question | Answer | Evidence / next step |
|:--|:--|:--|
| Is 100% real? | It is an observed rate in the model: 100/100 in v4.1 (interval 96–100%) and 500/500 in v4.0 (99.24–100%). Not a physical probability. | Reports; pooled safety bounds withdrawn on purpose |
| Does the simulator capture the grab? | No. The terminal window (within 20 cm, under 5.5 cm/s, within 15°, held 2 s) makes capture possible. | Contact model is WP2 |
| Why not just a better servicer? | Servicer-side improvements cannot recover information a silent client does not provide; rate data adds 8 pp at 3°/s. Both are needed. | Paired result, p = 0.008 |
| Who pays for the kit? | Hypothesis: OEM or operator at build time. Break-even depends on the probability of needing rescue (0.6% for fiducials). | Test with operator failure data |
| Beacon is not repaid in your model; why include it? | RPO value alone is small at 3°/s; identity, interface data, health and pre-approach state are not valued in the simulator. We flag it as undervalued, not proven. | Add a value model for non-RPO benefits |
| How do you prevent spoofing? | Today a shared simulation token plus sequence and freshness checks. Flight use needs authenticated signing. | Requirement BEACON-01 and IOS-01 |
| What is novel vs MICE/MASI/ASSIST/MEV? | Degraded-state serviceability as a system: independent state data plus handover, not another port. | Patent and state-of-the-art check outstanding |
| What if the client is fully dead? | Fall back to passive markers and known capture geometry (C1). Envelope shows C1 holds up to about 2°/s and fails near 5°/s without cooperation. | C0/C1 results |
| How big and heavy is the beacon? | Model: about 302 g packaged, 49 Wh nameplate for 30 days at 1 Hz. Assumed derating. | Bench plan B1–B7 |
| What do you need from us? | Reference client, failure statistics, agreed success criteria for the ground demo. | §6 slide 9 |

Feedback log (playbook format; fill after each expert session):

| Expert comment | Team response | Owner and next action |
|:--|:--|:--|
| | | |

---

## 8. Number sheet (single source)

| Claim | Value | Source |
|:--|:--|:--|
| v4.0 runs | 35,100 | [results/v4_0/report.md](../results/v4_0/report.md) |
| v4.1 runs, seed | 6,140, 20261019 | [results/v4_1_validation/manifest.json](../results/v4_1_validation/manifest.json) |
| Pass at 3°/s v4.1 (C0/C1/C2/C3) | 41% / 92% / 100% / 100% | v4.1 report |
| Pass at 3°/s v4.0 | 41.6% / 91.8% / 100% | v4.0 report |
| Fiducials effect | +51 pp (p = 8.9e-16) | v4.1 paired table |
| Rate data effect | +8 pp (p = 0.0078) | v4.1 paired table |
| Keep-out violations | 0 / 6,140 (count only) | v4.1 report |
| Tests | 74 | `python -m unittest discover -s rpo_project/tests -t .` |
| Beacon power | 28.5 mW, 20.52 Wh/30 d | `ios.evaluate_beacon_engineering_budget` |
| Rescue value | €20.84 M | ECONOMICS_MODEL §3 |
| Tier costs | €0.36 / 1.46 / 2.18 / 6.68 M | ECONOMICS_MODEL §7 |
| Break-even P(needs rescue), fiducials | 0.60% | ECONOMICS_MODEL §4 |
| Draft ground-demo budget | €770,500 | §5.2 here, ASSUMPTION |

---

## 9. Gaps to close, in priority order

1. Patent and state-of-the-art search (playbook step 1C), then fix Q4/Q5 tables to sourced rows.
2. Get operator or ClearSpace failure data to test P(needs rescue).
3. Value model for the beacon's non-RPO benefits.
4. Replace assumed costs and budget with quotes.
5. Contact model and joint IOS attitude dynamics.
6. Re-export the old PPTX/PDF exports from the corrected pitch script, or retire them in favour of the new deck.

---

## 10. Reference architecture check

Reference diagram supplied by the team: [reference/Reference_System_Architecture.jpg](reference/Reference_System_Architecture.jpg) (client satellite with health monitoring and OSAN interface; OSAN service interface; servicing spacecraft; ground segment and service management). It agrees with our three layers and **adds four blocks we had not treated as first-class**: a client Health Monitoring System, a Power Management Unit that isolates service interfaces, a modular Utility Interface Panel, and an Expansion/Upgrade Port. Coverage of every block:

| Reference block | What it contains | Our status | Where / gap |
|:--|:--|:--|:--|
| Client: Health Monitoring System | Data acquisition, FDIR, remaining-life estimate, health storage | **Partial** | Fuel gauge with leak and sensor flag and remaining delta-v (`onboard/fuel.py`), hash-chained on-board log (`onboard/recorder.py`). No general FDIR or remaining-life model for other subsystems |
| Client: Power Management Unit | Regulated power, isolate service interfaces | **Partial** | Beacon main-bus fault isolation and leakage in the power budget; bench test B2. No PMU model |
| Client: OBC with servicing mode and encryption | IOS mode control, security | **Partial** | `ios.py` state machine, coupled to approach outcome. Encryption is a token flag |
| Client: communication system | Main comms, proximity comms (RF/optical) | **Partial** | Beacon packets with loss and latency, downlink passes. No optical link |
| OSAN: Independent Service Beacon | ID, health summary, interface type and location, RF/optical broadcast, authentication | **Partial** | C2 beacon carries identity and rate. Interface type/location and health summary specified (27-byte packet) but not modelled |
| OSAN: navigation aids | Fiducials, retroreflectors, known geometry, visible with no power | **Covered** | C1 tier, fiducial vision model |
| OSAN: structural capture interface | Standard docking or grapple, load transfer | **Partial** | Capture point geometry only; no loads, no contact |
| OSAN: utility interface panel | Power, data (Ethernet/SpaceWire), optional fluid, optional thermal | **Concept only** | Cost in product tiers 3 and 4; no model |
| OSAN: expansion / upgrade port | Mechanical, power, data for propulsion or payload PODs | **Concept only** | Tier 4 cost only |
| Servicer: communication and authentication | RF/optical transceiver, proximity data link | **Partial** | Beacon reception; authentication simulated |
| Servicer: GNC and navigation | Cameras, lidar, rendezvous guidance | **Covered** | Vision model, Kalman estimators, guidance, abort gates |
| Servicer: robotic servicing system | Capture mechanism, inspection, refuel and repair, POD handling | **Not modelled** | Terminal window only |
| Servicer: utility transfer system | Power conditioning, data, fluid transfer, thermal | **Not modelled** | |
| Servicer: avionics | Mission management, service control, safety and abort logic | **Covered** | `safety.py`, IOS coupling, retreat |
| Ground: operator / customer | Receives health reports, reviews and approves service | **Covered (demo)** | Customer role, approvals, cases in the dashboard |
| Ground: service provider platform | Health processing, need assessment, mission planning, fleet management | **Covered (demo)** | Health agent, maintenance cases, 11-stage missions, feasibility card, downlink and fuel pages |
| Ground: servicing mission control | RPO and docking control, execution, post-service verification | **Partial (demo)** | Mission stages and approval gates; no real command path |
| Connection types | Power, data, fluid, thermal, RF beacon, RF/optical proximity, mechanical, modular attachment | **Partial** | We model RF beacon, proximity navigation, simplified mechanical capture and data. Power, fluid and thermal lines are not modelled |

**What to say:** the reference shows the full target system; our study quantifies the part that decides whether a degraded client can be approached (beacon, navigation aids, capture geometry, IOS handover) and demonstrates the ground and health-monitoring layers. Power, fluid, thermal and robotic transfer are the next stages, not claimed.

**New action items from this check:** (1) add a client Health Monitoring System scope (FDIR, remaining-life) to the technical plan and work package 5; (2) model interface type/location and health summary in the beacon; (3) decide whether utility and upgrade ports are in the study or explicitly out of scope, and say so on the architecture slide.

---

## 11. Research and novelty

See [RESEARCH_AND_NOVELTY.md](RESEARCH_AND_NOVELTY.md): what existing papers already do, what we could not find (paired preparation measurement, degraded-state information and handover layer, tier-level money chain), what we must not claim as new (servicer GNC, marker pose estimation, interface standards, expected-value economics, PVT and book-keeping gauging), and the checks still needed (full texts, patent search).
