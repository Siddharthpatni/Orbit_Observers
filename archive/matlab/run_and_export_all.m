% RUN_AND_EXPORT_ALL One-click runner for Orbit Observers Phase 2 RPO Monte Carlo
% Runs all 10 Verification & Validation checks (Handbook Section 13),
% executes the paired-seed Monte Carlo sweeps across C0, C1, C2_id_only, C2_beacon, C3_ios_mode,
% and exports all CSV tables and the 4 OSIP plots into ./results_matlab/

clear; clc; close all;
fprintf('=== ORBIT OBSERVERS PHASE 2: RPO MONTE CARLO SIMULATOR ===\n');
rpo_monte_carlo_sim('pilot', 30, 'results_matlab');
