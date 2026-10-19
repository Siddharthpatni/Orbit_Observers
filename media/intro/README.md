# Orbit Observers, 10-second intro

`../orbit_observers_intro.mp4` (1920x1080, 30 fps, mono AAC, about -18 LUFS). Source: `intro.html` (picture), `make_audio.py` (synthesised sound, no samples), `render.py` (frames + mux). Design philosophy: `design_philosophy.md`.

## Idea
The two first letters are objects, not glyphs. The **O of ORBIT** is an orbit ring that an orbit ellipse contracts into, with a satellite riding it. The **O of OBSERVERS** is a satellite (ring body, optic, two solar panels) that rocks like a tumbling client; the servicer docks to it at the end and the rocking stops (the IOS handover story in one gesture).

## Sequence
| Time | Event |
|:--|:--|
| 0.0 to 1.1 s | An orbit ellipse draws, a satellite rides it, the ellipse contracts into the O of ORBIT |
| 1.0 to 2.1 s | RBIT unfolds; the satellite O deploys its panels; BSERVERS unfolds |
| 2.1 to 3.05 s | Wordmark holds (1 s) |
| 3.05 to 3.65 s | Lockup shrinks to the corner (logo-lockup move) |
| 3.7 to 7.2 s | A servicer rides an orbit arc; each station opens its card as the servicer passes (line-carry idea). Cards 04 and 05 use real screenshots of the dashboard |
| 7.4 to 8.7 s | Cards clear, lockup returns, servicer flies to the satellite O and docks |
| 8.7 to 10 s | "terminal window met / 2.0 s hold", the three-part promise, hold (1.3 s) |

## Method (video-shotcraft, read as a reference, not installed)
Autonomous mode: product-grounded brief, one visual direction, per-shot still checks, sound pinned to picture events, final check against its rules. Ideas borrowed: orbit-ring open, lockup shrink and return, line-carry transition, real screenshots for existing pages (Q1), wordmark holds at least 1 s at start and end (R1), sound as a declarative frame-pinned table (S2). OpenMontage was reviewed but not used: it needs provider keys and a large install, and a 10 s deterministic motion graphic does not need it.

## Honest limits
Numbers in the video (41.6 / 91.8 / 100 percent at 3 deg/s) are model results from the v4.0 campaign under assumed parameters; the footer says so. The "2.0 s hold" label restates the terminal-window definition and is not a measured docking.

## Re-render
`python media/intro/render.py` from the repo root (needs `playwright`, Chromium and `ffmpeg`). Fonts: Jura and DM Mono, both SIL OFL (licence files here).
