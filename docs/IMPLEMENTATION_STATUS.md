# Implementation status — model `Phase2-RPO-MC-v4.1`

**Updated:** 19 October 2026. Companion to [PHASE2_PROPOSAL.md](PHASE2_PROPOSAL.md) and [PROJECT_ASSESSMENT.md](PROJECT_ASSESSMENT.md). All statements describe simulation code and results, not hardware.

## What v4.1 adds over v4.0

| Item | Status | Where |
|:--|:--|:--|
| Propagated abort retreat with separate fuel reserve | Implemented, tested | `rpo_project/safety.py`, `simulate.py`, `tests/test_retreat.py` |
| Position-covariance gate (all axes) before terminal approach | Implemented | `rpo_project/safety.py`, `config/` |
| Standalone IOS state machine (handshake, freshness, heartbeat, docked-abort, separation guards), detumble and derated-power estimates | Implemented, tested; **not coupled to RPO dynamics** | `rpo_project/ios.py`, `tests/test_ios.py` |
| Source snapshot (`source.zip`, SHA-256) in each campaign, replay checks | Implemented | `montecarlo.py`, `replay.py` |
| New-seed validation campaign (master seed 20261019) | Run, 6,140 simulations | [results/v4_1_validation/report.md](../results/v4_1_validation/report.md) |

## Verification

`python -m unittest discover -s rpo_project/tests -t .` → **30 tests, all pass** (run in the project `.venv`, 19 Oct 2026). Includes the 10 Handbook §13 V&V checks, statistics against hand-computed values, chunk/merge integrity, parallel = serial, retreat and IOS tests.

## v4.1 validation results (descriptive)

- 0 keep-out violations in 6,140 runs. Seeds are reused across tiers and cells, so this is a count, not a pooled confidence bound.
- Main study (100 paired seeds per cell): C3 passes 100% at 5°/s only because initial spin is cut by an assumed 95%.
- Retreat outcomes after aborts (main study): 421 complete, **61 end in `ESTIMATE_MISMATCH`** (the controller believed it had arrived but truth disagreed). These are not successes and need analysis before any retreat-safety claim.
- v4.0 numbers (35,100 runs) remain historical evidence and are not relabelled as v4.1.

## Not implemented / open

| Gap | Consequence |
|:--|:--|
| Contact, capture, latch, plume and structural models | "Terminal window met" ≠ physical capture |
| IOS coupled to vehicle dynamics (handover, authority) | C3 is only a 95% initial-spin reduction |
| Cryptographic authentication | `authenticated_id` is a flag |
| Joint loss × latency, burst outages, thruster failures | Link robustness only tested one factor at a time |
| 10°/s and degraded-client fault cases | Envelope ends at 5°/s |
| Hardware data (optics, beacon power, RF) | All noise and power numbers are assumptions |
| Costed economics (ECON-01) and sourced state-of-the-art comparison | Proposal cannot yet claim economic justification |
| Presentation exports | `Orbit_Observers_Team_Presentation.pptx/.pdf` predate corrections; use [PLAIN_LANGUAGE_PITCH_DECK.md](PLAIN_LANGUAGE_PITCH_DECK.md) |
| Independent replication / safety review | Required by RPO-04 |

## Related components

- `hpc/` and `results/meluxina_v4_1000/`: MeluXina Slurm workflow and a run from it.
- `satellite-ops-platform/`: frontend-only demo with fabricated data; not connected to the simulator.
