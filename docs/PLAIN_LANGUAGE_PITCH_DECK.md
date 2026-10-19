# Plain-language pitch and speaker guide

**Current evidence:** recorded v4.0 campaign, 35,100 simulations. This script was corrected on 17 October 2026 against the CSV results and Phase 2 reference brief.

**Export status:** the existing [PowerPoint](Orbit_Observers_Team_Presentation.pptx) and [PDF](Orbit_Observers_Team_Presentation.pdf) predate these corrections. Their wording has not been synchronized. Use this script as the current source and revise the exports before presenting them.

**19 October development update:** v4.1 adds simulated retreat and tested standalone IOS transitions. The numerical story below still describes the v4.0 campaign, which stopped at the abort decision. Cite [implementation status](IMPLEMENTATION_STATUS.md) separately when discussing the new code; do not mix versions' safety or fuel results.

## The project in 60 seconds

A robotic space tug could help a satellite that has lost fuel or stopped working. The last few metres are difficult if the satellite is spinning and the tug cannot clearly see the place it must approach.

We ask: **which small features should manufacturers add before launch to make a satellite easier to service later, including after a failure?** We compare visual markers, a radio that reports spin rate, and a cooperative slower-spin condition.

Our computer model ran 35,100 approaches under varied conditions. At 3°/s, an unprepared client reached the terminal window in **208/500 runs (41.6%)**, markers achieved **459/500 (91.8%)**, and markers plus rate telemetry achieved **500/500 (100% observed; 95% interval 99.24–100%)**. An identity-only radio gave the same pass outcomes as markers alone.

There were **zero recorded keep-out violations**. That is encouraging model evidence, not proof of zero real collisions. Physical capture and retreat after an abort are not simulated. Our next step is to validate the assumptions with independent simulation trials and ground tests, and turn the findings into a serviceability proposal.

## Slide 1 — Small client features can improve future servicing

**Say:** “We study what a satellite should carry before launch so a future servicing vehicle can approach it more reliably. Our strongest evidence so far concerns visual markers and a radio that reports how fast the satellite spins.”

## Slide 2 — The difficult last few metres

**Say:** “Imagine trying to reach the handle on a slowly rotating object while your camera is noisy. In our model, the tug starts about 12 metres away. It estimates motion, waits at a hold point, then approaches the moving handle. The challenge is to arrive close enough, slowly enough and correctly aligned.”

## Slide 3 — What we count as success

**Say:** “A terminal window means staying within 20 centimetres of the handle, below 5.5 centimetres per second relative speed, and within 15 degrees of alignment for two seconds. That makes a capture attempt possible. We do not simulate the grab or latch. Our keep-out sphere is a simplified safety boundary around the client.”

## Slide 4 — Five comparison cases

| Case | Provision | What the model changes |
|:--|:--|:--|
| C0 | Unprepared client | Noisier optical measurements and more dropouts |
| C1 | Visual markers | Better assumed optical measurements |
| C2-ID | Markers plus identity-only radio | Same navigation as C1; a comparison control |
| C2 | Markers plus rate radio | Additional noisy spin-rate measurements |
| C3 | Cooperative condition | Initial spin reduced by 95% |

**Say:** “C3 changes the motion itself. It represents a potentially useful operating condition, but the simulator does not implement the client's slowing manoeuvre or the control handover.”

## Slide 5 — Fair comparisons under varied conditions

**Say:** “We repeat approaches using numbered random seeds. Each tier faces matched starting disturbances, sensor noise draws and actuator errors. This makes the comparison fair. The campaign contains four studies: preparation versus tumble, radio loss versus rate, optical noise versus tumble, and radio latency. Seed reuse also means we must not treat every campaign row as an independent safety trial.”

Evidence: [campaign manifest](../results/v4_0/manifest.json) and [method](MONTE_CARLO_METHOD.md).

## Slide 6 — Markers deliver the largest gain at 3°/s

Use [pass-rate figure](../results/v4_0/plot1_terminal_pass_vs_tumble.png).

| Case at 3°/s | Terminal windows | Observed rate | Wilson 95% interval |
|:--|--:|--:|--:|
| C0 | 208/500 | 41.6% | 37.36–45.97% |
| C1 | 459/500 | 91.8% | 89.06–93.90% |
| C2-ID | 459/500 | 91.8% | 89.06–93.90% |
| C2 | 500/500 | 100% | 99.24–100% |

**Say:** “Markers add 50.2 percentage points here. The rate radio adds another 8.2 points. Every tested C2 run in this cell passed, but the true modeled pass probability is still uncertain. These are approach results under our assumptions.”

## Slide 7 — Safety observations and their limits

Use [outcome figure](../results/v4_0/plot6_outcome_breakdown.png).

**Say:** “We recorded no entries into the keep-out sphere across 35,100 runs. The smallest recorded clearance was about 2.9 millimetres, so geometry and numerical sensitivity deserve further checks. When the controller aborts, the run ends at that decision; we still need to simulate the retreat. Zero violations in one 500-seed cell gives a model-based upper risk bound of about 0.60% at 95% confidence. It does not establish flight safety.”

Do not apply `3 / 35,100`: seeds are reused across tiers and grid cells. The 200-seed cells have a zero-event upper bound of about 1.49%, separately for each cell.

## Slide 8 — What the rate information improves

Use [preparation trade figure](../results/v4_0/plot4_preparation_trade_curve.png).

**Say:** “At 3°/s, the beacon reduces capture-point prediction RMS error from about 7.81 centimetres with markers to 4.47 centimetres, a 42.8% reduction. Mean delta-v among successful approaches falls from 1.524 to 1.482 metres per second. The identity-only control helps establish that rate information produces this gain in our model.”

## Slide 9 — Where the evidence stops

Use [radio-loss](../results/v4_0/plot2_c2_beacon_ablation.png) and [latency](../results/v4_0/plot5_beacon_latency.png) figures.

**Say:** “We test packet loss, update rate and delay, and report the results cell by cell. Loss and latency were varied in separate studies, so their worst cases are not a jointly validated operating point. The client's rate is nearly constant, which makes delay easier to tolerate. At the tested 5 degrees per second, non-cooperative tiers abort while the slower C3 condition passes. This recorded campaign does not test 10 degrees per second.”

## Slide 10 — Hardware and business case are next-stage estimates

Use [power and propellant illustration](../results/v4_0/plot8_platform_economics_and_power.png).

**Say:** “Assuming 12 milliwatts standby plus a 1.1-watt transmit load for 15 milliseconds per second gives 28.5 milliwatts average, or 20.52 watt-hours over 30 days. A real battery design needs temperature, aging, conversion-loss and qualification allowances. We have not validated battery mass. The fuel illustration assumes repeatable independent attempts and a fixed abort cost; it excludes transfer, capture and servicing. It is a sensitivity study, not a forecast of satellites rescued or revenue.”

## Slide 11 — The broader Phase 2 proposal

**Say:** “The full concept needs three layers: passive provisions for unpowered clients, an independent beacon for degraded clients, and explicit control handover for cooperative clients. OSAN groups capture and optional service interfaces into an accessible service zone. We have drafted work packages and acceptance criteria covering simulation, beacon hardware, handover, interfaces and economics.”

Use the [Phase 2 proposal](PHASE2_PROPOSAL.md) for requirements, responsibilities and milestone gates.

## Slide 12 — Decision and next evidence

**Say:** “Our results justify validating markers and rate telemetry further. We propose agreeing a reference mission and degraded-state cases with the reviewer, freezing the model for an independent campaign, and then testing the beacon, optical measurements and handover on the ground. That is the evidence needed to move from a promising simulation to a credible serviceability platform.”

For questions on maturity and remaining work, use the [project assessment](PROJECT_ASSESSMENT.md).
