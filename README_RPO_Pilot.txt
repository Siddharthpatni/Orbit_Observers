ORBIT OBSERVERS - RPO SIMULATION STARTER
=======================================

Main reference: Orbit_Observers_RPO_Monte_Carlo_Project_Guide.pdf
Companion executable: rpo_beacon_information_pilot.py

This starter is deliberately ONLY a Stage-I information-value Monte Carlo.
It estimates the prediction error of a rotating capture point when using
optical attitude measurements and (optionally) independent target angular-rate
packets. It does NOT model relative orbital translation, real camera geometry,
servicer dynamics, thrust, collision, physical capture, or closed-loop docking.
Do not claim its prediction-window pass rate is a capture-success rate.

REQUIREMENTS
Python 3.10+ and: numpy, pandas, matplotlib

QUICK START
1. python -m pip install numpy pandas matplotlib
2. python rpo_beacon_information_pilot.py --runs 100 --out results_pilot
3. Open results_pilot/pilot_plots.png and results_pilot/summary.csv

EXPERIMENT CONFIGURATIONS
C0_unprepared  : noisier optical measurements, higher dropout
C1_fiducials  : better optical measurements; no rate packets
C2_id_only    : identity-only beacon; identical navigation to C1
C2_beacon     : fiducials + independent low-rate angular-rate packets
C3_ios_mode   : fiducials + packets + reduced target tumble (different dynamics)

All sensor noise, rates, interface radius, and fault probabilities are
explicit study assumptions. They are not measured ClearSpace hardware data.

UPGRADE TO FULL RPO MODEL (READ GUIDE SECTIONS 5-13)
1. Propagate chaser-relative 3D CW dynamics.
2. Propagate target attitude and body-frame capture point correctly.
3. Add realistic camera/lidar measurements and a 6+ DOF estimator.
4. Add hold points, collision geometry, thrust bounds, abort logic.
5. Only then measure terminal approach conditions and Δv in Monte Carlo.
6. Scale independent batches on MeluXina after local verification.
