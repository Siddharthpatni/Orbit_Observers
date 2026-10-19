# Project assessment against the Phase 2 goal

**Review date:** 17 October 2026. **Assessment: 64/100 before this review; 80/100 after the changes below.**

This is a qualitative reviewer score for an early-stage Phase 2 study and proposal package. It is not an official competition score, a measured percentage of engineering completion, a novelty score or a flight-readiness rating. The increase reflects better reporting, traceability and proposal coverage; no new hardware capability or improved flight controller was delivered in this review.

## Follow-up implementation — 19 October 2026

The score below records the 17 October review. Since then, v4.1 has added propagated retreat, an all-axis position-covariance gate, tested standalone IOS logic, and source snapshots with replay checks. Read [implementation status](IMPLEMENTATION_STATUS.md) for the new-seed campaign and remaining limitations. This does not retroactively validate hardware or change the v4.0 results.

## Goal used for the assessment

The [Phase 2 reference](reference/Phase2_Serviceability.pptx), slides 1 and 11, asks for client-side serviceability features that are technically useful, economically justified and ready for a roadmap, organized into an OSIP-style proposal. The [discussion brief](reference/Phase2_ClearSpace_Call.pptx), slide 11, includes simulation results, beacon/IOS concepts, an OSAN architecture, a tier trade study and a roadmap. Assessing only the Monte Carlo simulator would miss much of that goal.

## Weighted rubric

| Criterion | Maximum | Before | After | Basis for the score and remaining gap |
|:--|--:|--:|--:|:--|
| Goal coverage and requirements traceability | 15 | 9 | 13 | New proposal maps the brief to requirements and completion gates; reviewer acceptance and sourced state of the art remain open |
| Simulation implementation and comparative evidence | 25 | 22 | 22 | Existing 35,100-run evidence, paired tiers, ablation controls and verification checks; no contact, retreat or full IOS model |
| Statistical and reporting integrity | 20 | 10 | 17 | Removed fixed success claims, corrected pooled safety bounds and made retry estimates data-derived; independent confirmation and broader fault cases remain open |
| Beacon, IOS and OSAN system definition | 15 | 8 | 11 | Added state transitions, authority guards, power-isolation needs and functional interface concept; implementation and ground tests remain open |
| Economics and development roadmap | 15 | 7 | 8 | Assumptions separated from evidence, work packages and milestone gates drafted; no validated costs, ROI, budget or schedule |
| Reproducibility and communication | 10 | 8 | 9 | Tests, replays, corrected script and updated report; existing slide exports and exact historical source snapshot remain gaps |
| **Total** | **100** | **64** | **80** | Strong study foundation; incomplete submission and hardware evidence |

## Main findings and changes made

1. **The central comparison is supported by stored data.** At 3°/s, C0 passes 208/500, C1 and C2-ID each pass 459/500, and C2 passes 500/500. All four stored study summaries agree with their raw rows.
2. **The report generator previously inserted fixed v4.0 claims into any campaign.** It could report zero violations and specific 100% results even for a different or failing campaign. Reports now use current counts, tables and calculated retry costs. Regression tests cover unsafe outcomes and partial studies.
3. **The campaign count overstated the independent safety sample.** Seeds repeat across tiers and grid cells. The `3 / 35,100` pooled bound has been removed. Zero-event bounds are calculated within each tier/grid cell: approximately 0.60% for 500 seeds or 1.49% for 200 seeds, each pointwise.
4. **The pitch overstated model maturity and some numbers were stale.** Corrected “crashes,” guaranteed rescue, 10°/s evidence, battery mass and fleet-capture claims. The true minimum sampled clearance in the stored campaign is about 2.9 mm. Physical capture and post-abort retreat remain unmodeled.
5. **The broader proposal lacked an integrated, reviewable narrative.** Added [PHASE2_PROPOSAL.md](PHASE2_PROPOSAL.md) with the proposal ask, architecture, candidate requirements, six work packages, milestone gates, risk register and economic assumptions.
6. **The retry-cost graph hid zero-pass cases by clipping probability.** Undefined costs now appear as `n/a`; unsafe and timeout outcomes invalidate the simplified model. The power/propellant figure explicitly labels its assumptions.

## Verification performed

- Existing baseline: **13 unit tests passed**, including the ten verification checks bundled in the V&V test.
- Updated suite: **16 unit tests passed**, including three new reporting/economics regression tests.
- A fresh **123-simulation smoke campaign** completed all four studies and generated its tables, figures and report. One seed per cell checks execution only; it supplies no robust probability estimate.
- Recomputed all four stored summaries from raw CSVs and checked agreement with the stored summaries.
- Replayed one representative stored row from each of the four studies; outcome, elapsed time, delta-v and minimum clearance agree within floating-point tolerance.
- Regenerated the v4.0 report and power/propellant illustration; visually checked that illustration. The recorded campaign's raw CSVs and manifest were not rewritten by this review.
- `git diff --check` passed. Existing user edits were retained.

Reproduce the tests from the project root:

```bash
.venv/bin/python -m unittest discover -s rpo_project/tests -t .
```

The system Python lacked project dependencies; the existing `.venv` was used successfully. This was not a simulator test failure.

## What would justify a 90+ score

These are prioritized completion gates, not promised points:

| Priority | Required progress | Evidence to attach |
|:--|:--|:--|
| 1 | Freeze and independently confirm the model on unseen master seeds | Exact source/config snapshot, predeclared sample sizes, per-cell intervals and explained failures |
| 2 | Close the abort-safety and sensing gaps | Propagated retreat with fuel accounting, numerical/geometry sensitivity, burst outages, combined loss/latency and larger attitude mismatch |
| 3 | Validate the beacon and IOS assumptions | Measured derated power/link budget, main-bus failure isolation, authority-handover fault tests |
| 4 | Complete the proposal business and interface evidence | Sourced comparison matrix, cost sensitivity and break-even, interface/load allocations, named owners, dates and budget |
| 5 | Finish the submission package | Reviewer feedback and corrected PPTX/PDF exports consistent with the current script |

The existing [PowerPoint](Orbit_Observers_Team_Presentation.pptx) and [PDF](Orbit_Observers_Team_Presentation.pdf) still contain the earlier wording. The [corrected Markdown pitch](PLAIN_LANGUAGE_PITCH_DECK.md) is the current source. A high-quality study should make these limitations visible rather than claim readiness it has not demonstrated.
