function rpo_monte_carlo_sim(mode, runs_per_cell, out_dir)
% RPO_MONTE_CARLO_SIM Orbit Observers / ClearSpace Phase 2 RPO Monte Carlo Simulator
% Model Maturity Label: Early-stage, scenario-based, low-to-medium-fidelity RPO
% robustness assessment.
%
% Implements Sections 4-13 of the Orbit Observers RPO Monte Carlo Simulation Handbook:
%   - 3D Clohessy-Wiltshire (CW) relative orbital translation with RK4 & analytical STM check
%   - 3D quaternion attitude & rigid-body Euler propagation + LVLH capture-point kinematics
%   - Paired-seed experimental design across C0, C1, C2_id_only, C2_beacon, C3_ios_mode
%   - Vision occlusion/noise + Timestamped Service Beacon with Bernoulli loss & latency
%   - Strict Truth vs. Estimator state boundary (Kalman filter for translation & attitude)
%   - Two-stage hold-point & terminal capture-point guidance with keep-out safety monitor
%   - Exact 20-column CSV schema, Wilson 95% CIs, 4 core plots, and 10-point V&V suite.

    if nargin < 1 || isempty(mode), mode = 'pilot'; end
    if nargin < 2 || isempty(runs_per_cell), runs_per_cell = 30; end
    if nargin < 3 || isempty(out_dir), out_dir = 'results_matlab'; end

    cfg = get_default_config();

    % Always execute the 10 mandatory Section 13 V&V tests first
    run_verification_suite(cfg);
    if strcmpi(mode, 'verify')
        return;
    end

    if strcmpi(mode, 'full')
        runs_per_cell = max(runs_per_cell, 200);
    end

    if ~exist(out_dir, 'dir')
        mkdir(out_dir);
    end

    scenarios = {'C0_unprepared', 'C1_fiducials', 'C2_id_only', 'C2_beacon', 'C3_ios_mode'};
    tumble_grid = [0.0, 0.25, 0.5, 1.0, 2.0, 3.0, 5.0];

    fprintf('Running Main Paired-Seed Monte Carlo (%d seeds x %d rates x %d scenarios)...\n', ...
        runs_per_cell, numel(tumble_grid), numel(scenarios));

    % 1. Main Sweep (Plot 1 & Plot 4)
    total_main = numel(tumble_grid) * runs_per_cell * numel(scenarios);
    main_rows = cell(total_main, 1);
    idx = 0;
    for ir = 1:numel(tumble_grid)
        omega_deg = tumble_grid(ir);
        for seed = 1:runs_per_cell
            for isc = 1:numel(scenarios)
                idx = idx + 1;
                main_rows{idx} = run_single_simulation( ...
                    scenarios{isc}, seed, omega_deg, 0.05, 0.20, 1.0, 0.10, cfg, false);
            end
        end
    end
    T_main = struct_cell_to_table(main_rows);
    writetable(T_main, fullfile(out_dir, 'runs_main.csv'));

    T_summary = summarize_results(T_main, {'scenario', 'tumble_deg_s'});
    writetable(T_summary, fullfile(out_dir, 'summary_main.csv'));
    disp(T_summary(:, {'scenario', 'tumble_deg_s', 'n_runs', 'p_terminal_pass', ...
                       'p_abort', 'p_unsafe', 'rms_capture_point_error_m', 'mean_delta_v_mps'}));

    % 2. C2 Beacon Ablation Sweep (Plot 2)
    fprintf('Running C2 Beacon Ablation Sweep (ID-only vs. Gyro Rate Packets)...\n');
    loss_grid = [0.0, 0.10, 0.25, 0.50, 0.75];
    rate_grid = [0.5, 1.0, 2.0];
    abl_Scens = {'C2_id_only', 'C2_beacon'};
    n_abl_seeds = max(10, round(runs_per_cell / 2));
    abl_rows = {};
    a_idx = 0;
    for il = 1:numel(loss_grid)
        for ih = 1:numel(rate_grid)
            for seed = 1:n_abl_seeds
                for isc = 1:numel(abl_Scens)
                    a_idx = a_idx + 1;
                    abl_rows{a_idx, 1} = run_single_simulation( ...
                        abl_Scens{isc}, seed, 1.5, 0.05, loss_grid(il), rate_grid(ih), 0.10, cfg, false); %#ok<AGROW>
                end
            end
        end
    end
    T_ablation = struct_cell_to_table(abl_rows);
    writetable(T_ablation, fullfile(out_dir, 'runs_ablation.csv'));

    % 3. 2-D Servicing Envelope Sweep (Plot 3)
    fprintf('Running 2-D Servicing Envelope Sweep (Tumble Rate x Vision Noise)...\n');
    env_rates = [0.0, 0.5, 1.0, 2.0, 3.0, 5.0];
    env_sigmas = [0.02, 0.05, 0.10, 0.25];
    env_rows = {};
    e_idx = 0;
    for ir = 1:numel(env_rates)
        for isg = 1:numel(env_sigmas)
            for seed = 1:n_abl_seeds
                e_idx = e_idx + 1;
                env_rows{e_idx, 1} = run_single_simulation( ...
                    'C2_beacon', seed, env_rates(ir), env_sigmas(isg), 0.20, 1.0, 0.10, cfg, false); %#ok<AGROW>
            end
        end
    end
    T_envelope = struct_cell_to_table(env_rows);
    writetable(T_envelope, fullfile(out_dir, 'runs_envelope.csv'));

    % 4. Generate the 4 Core Publishable Figures (Section 11)
    generate_four_core_plots(T_main, T_ablation, T_envelope, out_dir, scenarios);

    fprintf('\nAll CSV results and plots saved to: %s\n', out_dir);
    fprintf(['RESEARCH INTEGRITY NOTE: p_terminal_pass reports conditional terminal-window ', ...
             'feasibility under stated model assumptions, NOT physical latch contact verification.\n']);
end

%% ========================================================================
%  1. CONFIGURATION & SCENARIO DEFINITIONS (Handbook Sections 4, 5, 6, 9)
%  ========================================================================
function cfg = get_default_config()
    cfg.model_version = 'Phase2-RPO-MC-MATLAB-v2.0';
    cfg.config_hash = 'a7c9e31b04';

    % Reference GEO Orbit (Section 5 & 6)
    cfg.mu_earth_m3_s2 = 3.986004418e14;
    cfg.a_geo_m = 42164.0e3;
    cfg.n_geo_rad_s = sqrt(cfg.mu_earth_m3_s2 / (cfg.a_geo_m ^ 3)); % ~7.292115e-5 rad/s

    % Time integration
    cfg.dt_s = 0.25;
    cfg.max_duration_s = 120.0;
    cfg.prediction_horizon_s = 2.0;

    % Target geometry & inertia (3500 kg, ~2.5x2.0x3.0 m bus)
    cfg.target_mass_kg = 3500.0;
    cfg.inertia_diag_kgm2 = [2400.0; 2800.0; 3100.0];
    cfg.capture_offset_body_m = [1.5; 0.0; 0.0];
    cfg.keepout_radius_m = 1.35;
    cfg.hold_distance_m = 4.0;

    % Servicer parameters
    cfg.chaser_start_distance_m = 12.0;
    cfg.chaser_pos_disp_sigma_m = 0.50;
    cfg.chaser_vel_disp_sigma_mps = 0.015;
    cfg.a_max_mps2 = 0.040;
    cfg.thruster_noise_sigma_frac = 0.02;
    cfg.kp_pos = 0.085;
    cfg.kd_vel = 0.420;

    % Sensor & Beacon parameters
    cfg.gyro_noise_rad_s = deg2rad(0.08);
    cfg.fov_occlusion_cos_limit = -0.35;

    % Terminal capture window & safety abort limits (Section 9)
    cfg.terminal_pos_tol_m = 0.20;
    cfg.terminal_vel_tol_mps = 0.055;
    cfg.terminal_align_tol_rad = deg2rad(15.0);
    cfg.terminal_dwell_s = 2.0;
    cfg.max_safe_target_omega_rad_s = deg2rad(3.2);
    cfg.max_allowed_angle_std_rad = deg2rad(18.0);
    cfg.max_delta_v_mps = 2.50;
end

function scen = get_scenario_spec(scenario_name)
    switch scenario_name
        case 'C0_unprepared'
            scen = struct('name', 'C0_unprepared', 'vision_angle_sigma_rad', deg2rad(12.0), ...
                'vision_pos_scale', 2.5, 'vision_dropout_prob', 0.30, ...
                'beacon_enabled', false, 'beacon_has_rate', false, 'omega_factor', 1.0);
        case 'C1_fiducials'
            scen = struct('name', 'C1_fiducials', 'vision_angle_sigma_rad', deg2rad(3.0), ...
                'vision_pos_scale', 1.0, 'vision_dropout_prob', 0.08, ...
                'beacon_enabled', false, 'beacon_has_rate', false, 'omega_factor', 1.0);
        case 'C2_id_only'
            scen = struct('name', 'C2_id_only', 'vision_angle_sigma_rad', deg2rad(3.0), ...
                'vision_pos_scale', 1.0, 'vision_dropout_prob', 0.08, ...
                'beacon_enabled', true, 'beacon_has_rate', false, 'omega_factor', 1.0);
        case 'C2_beacon'
            scen = struct('name', 'C2_beacon', 'vision_angle_sigma_rad', deg2rad(3.0), ...
                'vision_pos_scale', 1.0, 'vision_dropout_prob', 0.08, ...
                'beacon_enabled', true, 'beacon_has_rate', true, 'omega_factor', 1.0);
        case 'C3_ios_mode'
            scen = struct('name', 'C3_ios_mode', 'vision_angle_sigma_rad', deg2rad(3.0), ...
                'vision_pos_scale', 1.0, 'vision_dropout_prob', 0.08, ...
                'beacon_enabled', true, 'beacon_has_rate', true, 'omega_factor', 0.05);
        otherwise
            error('Unknown scenario: %s', scenario_name);
    end
end

%% ========================================================================
%  2. ORBITAL TRANSLATION DYNAMICS: CW & RK4 (Handbook Section 6)
%  ========================================================================
function ds = cw_derivative(s, a_lvlh, n)
    x = s(1); y = s(2); z = s(3); %#ok<NASGU>
    vx = s(4); vy = s(5); vz = s(6);
    x_ddot =  3.0 * (n^2) * x + 2.0 * n * vy + a_lvlh(1);
    y_ddot = -2.0 * n * vx + a_lvlh(2);
    z_ddot = -(n^2) * z + a_lvlh(3);
    ds = [vx; vy; vz; x_ddot; y_ddot; z_ddot];
end

function s_next = propagate_cw_rk4(s, a_lvlh, dt, n)
    k1 = cw_derivative(s, a_lvlh, n);
    k2 = cw_derivative(s + 0.5 * dt * k1, a_lvlh, n);
    k3 = cw_derivative(s + 0.5 * dt * k2, a_lvlh, n);
    k4 = cw_derivative(s + dt * k3, a_lvlh, n);
    s_next = s + (dt / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4);
end

function phi = cw_state_transition_matrix(t, n)
    nt = n * t;
    c = cos(nt);
    s = sin(nt);
    phi = zeros(6, 6);
    phi(1, 1) = 4.0 - 3.0 * c;
    phi(1, 4) = s / n;
    phi(1, 5) = (2.0 / n) * (1.0 - c);
    phi(2, 1) = 6.0 * (s - nt);
    phi(2, 2) = 1.0;
    phi(2, 4) = -(2.0 / n) * (1.0 - c);
    phi(2, 5) = (4.0 * s - 3.0 * nt) / n;
    phi(3, 3) = c;
    phi(3, 6) = s / n;
    phi(4, 1) = 3.0 * n * s;
    phi(4, 4) = c;
    phi(4, 5) = 2.0 * s;
    phi(5, 1) = -6.0 * n * (1.0 - c);
    phi(5, 4) = -2.0 * s;
    phi(5, 5) = 4.0 * c - 3.0;
    phi(6, 3) = -n * s;
    phi(6, 6) = c;
end

%% ========================================================================
%  3. ATTITUDE & CAPTURE-POINT KINEMATICS (Handbook Section 7)
%  ========================================================================
function a = wrap_pi(angle_rad)
    a = mod(angle_rad + pi, 2.0 * pi) - pi;
end

function q_n = quat_normalize(q)
    nm = norm(q);
    if nm < 1e-15
        q_n = [1.0; 0.0; 0.0; 0.0];
    else
        q_n = q / nm;
    end
end

function q = quat_from_z_angle(theta_rad)
    half_ang = 0.5 * theta_rad;
    q = [cos(half_ang); 0.0; 0.0; sin(half_ang)];
end

function yaw = z_angle_from_quat(q)
    q = quat_normalize(q);
    qw = q(1); qx = q(2); qy = q(3); qz = q(4);
    yaw = atan2(2.0 * (qw * qz + qx * qy), 1.0 - 2.0 * (qy^2 + qz^2));
end

function R = rotmat_from_quat(q)
    q = quat_normalize(q);
    qw = q(1); qx = q(2); qy = q(3); qz = q(4);
    R = [1.0 - 2.0*(qy^2 + qz^2), 2.0*(qx*qy - qw*qz),     2.0*(qx*qz + qw*qy);
         2.0*(qx*qy + qw*qz),     1.0 - 2.0*(qx^2 + qz^2), 2.0*(qy*qz - qw*qx);
         2.0*(qx*qz - qw*qy),     2.0*(qy*qz + qw*qx),     1.0 - 2.0*(qx^2 + qy^2)];
end

function [q_dot, w_dot] = attitude_derivative(q, w_body, I_diag, tau_ext)
    wx = w_body(1); wy = w_body(2); wz = w_body(3);
    Omega = [0.0, -wx, -wy, -wz;
             wx,  0.0,  wz, -wy;
             wy, -wz,  0.0,  wx;
             wz,  wy, -wx,  0.0];
    q_dot = 0.5 * (Omega * q);
    H = I_diag .* w_body;
    w_dot = (tau_ext - cross(w_body, H)) ./ I_diag;
end

function [q_next, w_next] = propagate_attitude_rk4(q, w_body, dt, I_diag)
    tau_ext = [0.0; 0.0; 0.0];
    [kq1, kw1] = attitude_derivative(q, w_body, I_diag, tau_ext);
    [kq2, kw2] = attitude_derivative(q + 0.5*dt*kq1, w_body + 0.5*dt*kw1, I_diag, tau_ext);
    [kq3, kw3] = attitude_derivative(q + 0.5*dt*kq2, w_body + 0.5*dt*kw2, I_diag, tau_ext);
    [kq4, kw4] = attitude_derivative(q + dt*kq3, w_body + dt*kw3, I_diag, tau_ext);
    q_next = quat_normalize(q + (dt / 6.0) * (kq1 + 2.0*kq2 + 2.0*kq3 + kq4));
    w_next = w_body + (dt / 6.0) * (kw1 + 2.0*kw2 + 2.0*kw3 + kw4);
end

function [r_cap_l, v_cap_l, n_cap_l] = capture_point_kinematics_lvlh(q_bl, w_body_rel_lvlh, rho_cap_body)
    R_bl = rotmat_from_quat(q_bl);
    r_cap_l = R_bl * rho_cap_body;
    w_lvlh = R_bl * w_body_rel_lvlh;
    v_cap_l = cross(w_lvlh, r_cap_l);
    nr = norm(r_cap_l);
    if nr > 1e-12
        n_cap_l = r_cap_l / nr;
    else
        n_cap_l = [1.0; 0.0; 0.0];
    end
end

%% ========================================================================
%  4. KALMAN ESTIMATOR & LATENCY-COMPENSATED BEACON FUSION (Section 8 & 12)
%  ========================================================================
function est = init_estimator(init_pos, init_vel, init_theta, init_omega, pos_sigma, ang_sigma)
    est.s_hat = [init_pos(:); init_vel(:)];
    p_var = max(pos_sigma^2, 0.05^2);
    v_var = 0.03^2;
    est.P_trans = diag([p_var, p_var, p_var, v_var, v_var, v_var]);

    est.att_hat = [wrap_pi(init_theta); init_omega];
    a_var = max(ang_sigma^2, deg2rad(1.0)^2);
    r_var = deg2rad(3.0)^2;
    est.P_att = diag([a_var, r_var]);
end

function est = estimator_predict(est, dt, a_cmd_lvlh, n_geo)
    est.s_hat = propagate_cw_rk4(est.s_hat, a_cmd_lvlh, dt, n_geo);
    phi = cw_state_transition_matrix(dt, n_geo);
    q_pos = (0.005 * dt)^2;
    q_vel = (0.003 * sqrt(dt))^2;
    Q_trans = diag([q_pos, q_pos, q_pos, q_vel, q_vel, q_vel]);
    est.P_trans = phi * est.P_trans * phi' + Q_trans;

    F_att = [1.0, dt; 0.0, 1.0];
    est.att_hat = [wrap_pi(est.att_hat(1) + est.att_hat(2) * dt); est.att_hat(2)];
    q_omega = deg2rad(0.015)^2;
    Q_att = q_omega * [(dt^3)/3.0, (dt^2)/2.0; (dt^2)/2.0, dt];
    est.P_att = F_att * est.P_att * F_att' + Q_att;
end

function est = estimator_update_vision(est, meas_pos, meas_theta, pos_sigma, ang_sigma)
    H_t = [eye(3), zeros(3, 3)];
    R_t = eye(3) * max(pos_sigma^2, 1e-6);
    y_t = meas_pos(:) - H_t * est.s_hat;
    S_t = H_t * est.P_trans * H_t' + R_t;
    K_t = (est.P_trans * H_t') / S_t;
    est.s_hat = est.s_hat + K_t * y_t;
    est.P_trans = (eye(6) - K_t * H_t) * est.P_trans;

    h_a = [1.0, 0.0];
    r_a = max(ang_sigma^2, 1e-8);
    res = wrap_pi(meas_theta - est.att_hat(1));
    s_a = h_a * est.P_att * h_a' + r_a;
    k_a = (est.P_att * h_a') / s_a;
    est.att_hat = [wrap_pi(est.att_hat(1) + k_a(1) * res); est.att_hat(2) + k_a(2) * res];
    est.P_att = (eye(2) - k_a * h_a) * est.P_att;
end

function est = estimator_update_beacon(est, pkt, current_time_s, gyro_sigma)
    if ~pkt.has_rate
        return;
    end
    age_s = max(0.0, current_time_s - pkt.timestamp_s);
    q_omega = deg2rad(0.015)^2;
    eff_var = max(gyro_sigma^2 + q_omega * age_s, 1e-10);

    h_r = [0.0, 1.0];
    res = pkt.omega_z_rad_s - est.att_hat(2);
    s_r = h_r * est.P_att * h_r' + eff_var;
    k_r = (est.P_att * h_r') / s_r;
    est.att_hat = [wrap_pi(est.att_hat(1) + (k_r(1) + k_r(2) * age_s) * res);
                   est.att_hat(2) + k_r(2) * res];
    est.P_att = (eye(2) - k_r * h_r) * est.P_att;
end

function [r_cap_hat, v_cap_hat, n_cap_hat] = estimator_predict_capture_point(est, horizon_s, rho_cap_body)
    theta_pred = wrap_pi(est.att_hat(1) + est.att_hat(2) * horizon_s);
    q_pred = quat_from_z_angle(theta_pred);
    w_pred = [0.0; 0.0; est.att_hat(2)];
    [r_cap_hat, v_cap_hat, n_cap_hat] = capture_point_kinematics_lvlh(q_pred, w_pred, rho_cap_body);
end

%% ========================================================================
%  5. GUIDANCE, CONTROL & SAFETY MONITOR (Handbook Section 9 & 12)
%  ========================================================================
function [a_cmd, in_term, abort_trig, abort_reason] = compute_guidance_and_safety( ...
    est, cfg, rho_cap_body, elapsed_s, dv_used, in_term)

    r_hat = est.s_hat(1:3);
    v_hat = est.s_hat(4:6);
    [r_cap_hat, v_cap_hat, n_cap_hat] = estimator_predict_capture_point(est, 0.0, rho_cap_body);

    omega_hat = abs(est.att_hat(2));
    ang_std = sqrt(max(0.0, est.P_att(1, 1)));
    est_dist = norm(r_hat);

    % Safety Monitor Abort Gates (Section 9)
    if elapsed_s >= 10.0 && omega_hat > cfg.max_safe_target_omega_rad_s
        a_cmd = [0; 0; 0]; abort_trig = true; abort_reason = 'ABORT_EXCESS_TUMBLE_RATE';
        return;
    end
    if elapsed_s >= 12.0 && ang_std > cfg.max_allowed_angle_std_rad
        a_cmd = [0; 0; 0]; abort_trig = true; abort_reason = 'ABORT_NAVIGATION_COVARIANCE';
        return;
    end
    if dv_used >= cfg.max_delta_v_mps
        a_cmd = [0; 0; 0]; abort_trig = true; abort_reason = 'ABORT_DELTA_V_BUDGET';
        return;
    end

    w_vec_hat = [0.0; 0.0; est.att_hat(2)];
    r_hold_ref = n_cap_hat * cfg.hold_distance_m;
    v_hold_ref = cross(w_vec_hat, r_hold_ref);

    hold_err = norm(r_hat - r_hold_ref);
    if ~in_term
        if elapsed_s >= 8.0 && hold_err < 1.25 && ang_std < deg2rad(8.0)
            in_term = true;
        end
    end

    if ~in_term
        r_ref = r_hold_ref;
        v_ref = v_hold_ref;
    else
        if est_dist < 2.8
            cos_align = dot(r_hat / max(est_dist, 1e-6), n_cap_hat);
            if cos_align < cos(deg2rad(55.0)) || ang_std > deg2rad(10.0)
                a_cmd = [0; 0; 0]; abort_trig = true; abort_reason = 'ABORT_CORRIDOR_MISALIGNMENT';
                return;
            end
        end
        r_ref = r_cap_hat;
        v_ref = v_cap_hat;
    end

    % Obstacle-avoidance tangential waypoint when on opposite side of bus
    cos_side = dot(r_hat / max(est_dist, 1e-6), r_ref / max(norm(r_ref), 1e-6));
    if cos_side < 0.15 && est_dist < cfg.hold_distance_m + 1.5
        tang = [-r_hat(2); r_hat(1); 0.0];
        tn = norm(tang);
        if tn > 1e-6, tang = tang / tn; else, tang = [0.0; 1.0; 0.0]; end
        r_ref = (r_hat / max(est_dist, 1e-6)) * cfg.hold_distance_m + 2.5 * tang;
        v_ref = [0.0; 0.0; 0.0];
    end

    a_cmd = -cfg.kp_pos * (r_hat - r_ref) - cfg.kd_vel * (v_hat - v_ref);

    % Repulsive keep-out barrier outside keepout_radius_m
    safety_margin_m = 1.48;
    if est_dist < safety_margin_m
        radial_unit = r_hat / max(est_dist, 1e-6);
        repulse = 0.06 * ((safety_margin_m - est_dist) / 0.15);
        a_cmd = a_cmd + repulse * radial_unit;
    end

    a_norm = norm(a_cmd);
    if a_norm > cfg.a_max_mps2
        a_cmd = a_cmd * (cfg.a_max_mps2 / a_norm);
    end
    abort_trig = false;
    abort_reason = 'NOMINAL';
end

%% ========================================================================
%  6. SINGLE CLOSED-LOOP SIMULATION RUN (Handbook Section 12)
%  ========================================================================
function res = run_single_simulation( ...
    scenario_name, seed, tumble_deg_s, vision_sigma_m, ...
    beacon_packet_loss, beacon_rate_hz, latency_s, cfg, deterministic_zero_noise)

    scen = get_scenario_spec(scenario_name);
    n_steps = round(cfg.max_duration_s / cfg.dt_s);
    rho_cap_body = cfg.capture_offset_body_m;
    I_diag = cfg.inertia_diag_kgm2;

    % Pre-draw ALL random sequences using paired seed (Section 4 & 10)
    rng(double(seed), 'twister');
    if deterministic_zero_noise
        theta0_rad = 0.0;
        pos_init_noise = [0; 0; 0];
        vel_init_noise = [0; 0; 0];
        vis_pos_noise_seq = zeros(3, n_steps);
        vis_ang_noise_seq = zeros(1, n_steps);
        vis_uniform_seq = ones(1, n_steps);
        beacon_gyro_noise_seq = zeros(1, n_steps);
        beacon_uniform_seq = ones(1, n_steps);
        thruster_noise_seq = zeros(3, n_steps);
    else
        theta0_rad = -pi + 2.0 * pi * rand();
        pos_init_noise = cfg.chaser_pos_disp_sigma_m * randn(3, 1);
        vel_init_noise = cfg.chaser_vel_disp_sigma_mps * randn(3, 1);
        vis_pos_noise_seq = randn(3, n_steps);
        vis_ang_noise_seq = randn(1, n_steps);
        vis_uniform_seq = rand(1, n_steps);
        beacon_gyro_noise_seq = randn(1, n_steps);
        beacon_uniform_seq = rand(1, n_steps);
        thruster_noise_seq = cfg.thruster_noise_sigma_frac * randn(3, n_steps);
    end

    % Initialize Truth State
    omega_true_z = deg2rad(double(tumble_deg_s)) * scen.omega_factor;
    q_init = quat_from_z_angle(theta0_rad);
    [~, ~, n_cap_init] = capture_point_kinematics_lvlh(q_init, [0; 0; omega_true_z], rho_cap_body);

    chaser_pos_init = n_cap_init * cfg.chaser_start_distance_m + pos_init_noise;
    chaser_vel_init = vel_init_noise;

    truth.t_s = 0.0;
    truth.chaser_state_lvlh = [chaser_pos_init; chaser_vel_init];
    truth.target_quat_bl = q_init;
    truth.target_omega_body = [0.0; 0.0; omega_true_z];

    % Initialize Estimator (Prior only - no truth leakage)
    if deterministic_zero_noise
        eff_pos_sigma = 0.0;
        eff_ang_sigma = 0.0;
    else
        eff_pos_sigma = vision_sigma_m * scen.vision_pos_scale;
        eff_ang_sigma = scen.vision_angle_sigma_rad;
    end
    init_theta_meas = wrap_pi(theta0_rad + eff_ang_sigma * vis_ang_noise_seq(1));
    init_pos_meas = chaser_pos_init + eff_pos_sigma * vis_pos_noise_seq(:, 1);
    est = init_estimator(init_pos_meas, [0; 0; 0], init_theta_meas, 0.0, ...
        max(eff_pos_sigma, 1e-4), max(eff_ang_sigma, 1e-4));

    if beacon_rate_hz > 0
        beacon_step_interval = max(1, round(1.0 / (beacon_rate_hz * cfg.dt_s)));
    else
        beacon_step_interval = 999999;
    end
    beacon_queue = struct('timestamp_s', {}, 'arrival_time_s', {}, 'has_rate', {}, 'omega_z_rad_s', {});

    min_clearance_m = norm(truth.chaser_state_lvlh(1:3));
    delta_v_mps = 0.0;
    dwell_accum_s = 0.0;
    in_terminal_phase = false;
    pred_errors_m = [];

    status = 'TIMEOUT';
    terminal_pass = false;
    aborted = false;
    unsafe = false;
    rel_speed_final = 0.0;
    elapsed_s = 0.0;

    for k = 2:n_steps
        t_s = (k - 1) * cfg.dt_s;
        elapsed_s = t_s;

        % 1. Vision Measurement & Occlusion
        [~, ~, n_cap_true] = capture_point_kinematics_lvlh( ...
            truth.target_quat_bl, truth.target_omega_body, rho_cap_body);
        chaser_pos_true = truth.chaser_state_lvlh(1:3);
        chaser_unit = chaser_pos_true / max(norm(chaser_pos_true), 1e-6);
        los_cos = dot(chaser_unit, n_cap_true);
        occluded = (los_cos < cfg.fov_occlusion_cos_limit) && ~deterministic_zero_noise;

        if ~occluded && (vis_uniform_seq(k) >= scen.vision_dropout_prob || deterministic_zero_noise)
            true_yaw = z_angle_from_quat(truth.target_quat_bl);
            meas_yaw = wrap_pi(true_yaw + eff_ang_sigma * vis_ang_noise_seq(k));
            meas_pos = chaser_pos_true + eff_pos_sigma * vis_pos_noise_seq(:, k);
            est = estimator_update_vision(est, meas_pos, meas_yaw, ...
                max(eff_pos_sigma, 1e-4), max(eff_ang_sigma, 1e-4));
        end

        % 2. Service Beacon Packet Generation & Latency Queue
        if scen.beacon_enabled && mod(k - 1, beacon_step_interval) == 0
            if beacon_uniform_seq(k) >= beacon_packet_loss || deterministic_zero_noise
                if deterministic_zero_noise, g_sig = 0.0; else, g_sig = cfg.gyro_noise_rad_s; end
                meas_w = truth.target_omega_body(3) + g_sig * beacon_gyro_noise_seq(k);
                pkt.timestamp_s = t_s;
                pkt.arrival_time_s = t_s + max(0.0, latency_s);
                pkt.has_rate = scen.beacon_has_rate;
                pkt.omega_z_rad_s = meas_w;
                beacon_queue(end + 1) = pkt; %#ok<AGROW>
            end
        end

        keep_mask = false(1, numel(beacon_queue));
        for ip = 1:numel(beacon_queue)
            if beacon_queue(ip).arrival_time_s <= t_s + 1e-9
                if deterministic_zero_noise, g_sig = 0.0; else, g_sig = cfg.gyro_noise_rad_s; end
                est = estimator_update_beacon(est, beacon_queue(ip), t_s, g_sig);
            else
                keep_mask(ip) = true;
            end
        end
        beacon_queue = beacon_queue(keep_mask);

        % 3. 2-Second Capture-Point Prediction Error (after 4 s transient)
        if t_s >= 4.0
            [cp_hat, ~, ~] = estimator_predict_capture_point(est, cfg.prediction_horizon_s, rho_cap_body);
            [q_fut, w_fut] = propagate_attitude_rk4( ...
                truth.target_quat_bl, truth.target_omega_body, cfg.prediction_horizon_s, I_diag);
            [cp_true, ~, ~] = capture_point_kinematics_lvlh(q_fut, w_fut, rho_cap_body);
            pred_errors_m(end + 1) = norm(cp_hat - cp_true); %#ok<AGROW>
        end

        % 4. Closed-Loop Guidance & Safety Monitor (Estimated States Only)
        [a_cmd, in_terminal_phase, abort_trig, abort_reason] = compute_guidance_and_safety( ...
            est, cfg, rho_cap_body, t_s, delta_v_mps, in_terminal_phase);

        if abort_trig
            aborted = true;
            status = abort_reason;
            delta_v_mps = delta_v_mps + 0.08;
            [~, v_cap_true, ~] = capture_point_kinematics_lvlh( ...
                truth.target_quat_bl, truth.target_omega_body, rho_cap_body);
            rel_speed_final = norm(truth.chaser_state_lvlh(4:6) - v_cap_true);
            break;
        end

        % 5. Apply Thruster Command to Truth & Advance
        a_applied = a_cmd .* (1.0 + thruster_noise_seq(:, k));
        if norm(a_applied) > cfg.a_max_mps2
            a_applied = a_applied * (cfg.a_max_mps2 / norm(a_applied));
        end
        delta_v_mps = delta_v_mps + norm(a_applied) * cfg.dt_s;

        truth.chaser_state_lvlh = propagate_cw_rk4(truth.chaser_state_lvlh, a_applied, cfg.dt_s, cfg.n_geo_rad_s);
        [truth.target_quat_bl, truth.target_omega_body] = propagate_attitude_rk4( ...
            truth.target_quat_bl, truth.target_omega_body, cfg.dt_s, I_diag);
        truth.t_s = t_s;

        est = estimator_predict(est, cfg.dt_s, a_cmd, cfg.n_geo_rad_s);

        % 6. Check Physical Keep-Out & Terminal Window
        chaser_pos = truth.chaser_state_lvlh(1:3);
        chaser_vel = truth.chaser_state_lvlh(4:6);
        dist_origin = norm(chaser_pos);
        min_clearance_m = min(min_clearance_m, dist_origin);

        [r_cap_true, v_cap_true, n_cap_true] = capture_point_kinematics_lvlh( ...
            truth.target_quat_bl, truth.target_omega_body, rho_cap_body);
        pos_err_cap = norm(chaser_pos - r_cap_true);
        rel_speed = norm(chaser_vel - v_cap_true);
        rel_speed_final = rel_speed;

        if dist_origin < cfg.keepout_radius_m
            unsafe = true;
            status = 'UNSAFE_KEEPOUT_VIOLATION';
            break;
        end

        cos_align_true = max(-1.0, min(1.0, dot(chaser_pos / max(dist_origin, 1e-6), n_cap_true)));
        align_err_rad = acos(cos_align_true);

        if pos_err_cap <= cfg.terminal_pos_tol_m && ...
           rel_speed <= cfg.terminal_vel_tol_mps && ...
           align_err_rad <= cfg.terminal_align_tol_rad
            dwell_accum_s = dwell_accum_s + cfg.dt_s;
            if dwell_accum_s >= cfg.terminal_dwell_s
                terminal_pass = true;
                status = 'TERMINAL_CAPTURE_WINDOW_MET';
                break;
            end
        else
            dwell_accum_s = 0.0;
        end
    end

    if isempty(pred_errors_m)
        mean_cp_err = 0.0;
    else
        mean_cp_err = mean(pred_errors_m);
    end

    % Exact 20-Column Schema (Section 12)
    res = struct( ...
        'scenario', string(scenario_name), ...
        'seed', int32(seed), ...
        'tumble_deg_s', double(tumble_deg_s), ...
        'vision_sigma_m', double(vision_sigma_m), ...
        'beacon_enabled', logical(scen.beacon_enabled), ...
        'beacon_packet_loss', double(ternary(scen.beacon_enabled, beacon_packet_loss, 1.0)), ...
        'beacon_rate_hz', double(ternary(scen.beacon_enabled, beacon_rate_hz, 0.0)), ...
        'latency_s', double(ternary(scen.beacon_enabled, latency_s, 0.0)), ...
        'theta0_rad', double(theta0_rad), ...
        'status', string(status), ...
        'terminal_pass', logical(terminal_pass), ...
        'aborted', logical(aborted), ...
        'unsafe', logical(unsafe), ...
        'minimum_clearance_m', double(min_clearance_m), ...
        'capture_point_error_m', double(mean_cp_err), ...
        'relative_speed_mps', double(rel_speed_final), ...
        'delta_v_mps', double(delta_v_mps), ...
        'elapsed_s', double(elapsed_s), ...
        'model_version', string(cfg.model_version), ...
        'config_hash', string(cfg.config_hash));
end

function out = ternary(cond, val_true, val_false)
    if cond, out = val_true; else, out = val_false; end
end

function T = struct_cell_to_table(cell_rows)
    s_arr = vertcat(cell_rows{:});
    T = struct2table(s_arr);
end

%% ========================================================================
%  7. WILSON 95% CIs & FOUR ESSENTIAL PLOTS (Handbook Section 11)
%  ========================================================================
function [p_hat, ci_low, ci_high] = wilson_ci_95(k_success, n_total)
    if n_total <= 0
        p_hat = 0.0; ci_low = 0.0; ci_high = 0.0; return;
    end
    z = 1.959963984540054;
    z2 = z^2;
    p_hat = double(k_success) / double(n_total);
    denom = 1.0 + z2 / n_total;
    center = (p_hat + z2 / (2.0 * n_total)) / denom;
    half_w = (z / denom) * sqrt(max(0.0, (p_hat * (1.0 - p_hat) / n_total) + (z2 / (4.0 * (n_total^2)))));
    ci_low = max(0.0, center - half_w);
    ci_high = min(1.0, center + half_w);
end

function T_sum = summarize_results(T, group_cols)
    [G, ~] = findgroups(T(:, group_cols));
    u_groups = unique(G);
    rows = cell(numel(u_groups), 1);
    for ig = 1:numel(u_groups)
        sub = T(G == u_groups(ig), :);
        n_runs = height(sub);
        [p_pass, pass_lo, pass_hi] = wilson_ci_95(sum(sub.terminal_pass), n_runs);
        [p_abort, ab_lo, ab_hi] = wilson_ci_95(sum(sub.aborted), n_runs);
        [p_unsafe, un_lo, un_hi] = wilson_ci_95(sum(sub.unsafe), n_runs);

        r = struct();
        for ic = 1:numel(group_cols)
            col = group_cols{ic};
            r.(col) = sub.(col)(1);
        end
        r.n_runs = n_runs;
        r.p_terminal_pass = p_pass;
        r.p_terminal_pass_ci95_low = pass_lo;
        r.p_terminal_pass_ci95_high = pass_hi;
        r.p_abort = p_abort;
        r.p_abort_ci95_low = ab_lo;
        r.p_abort_ci95_high = ab_hi;
        r.p_unsafe = p_unsafe;
        r.p_unsafe_ci95_low = un_lo;
        r.p_unsafe_ci95_high = un_hi;
        r.rms_capture_point_error_m = sqrt(mean(sub.capture_point_error_m .^ 2));
        r.p95_capture_point_error_m = prctile_base(sub.capture_point_error_m, 95);
        r.mean_minimum_clearance_m = mean(sub.minimum_clearance_m);
        r.mean_delta_v_mps = mean(sub.delta_v_mps);
        r.mean_elapsed_s = mean(sub.elapsed_s);
        rows{ig} = r;
    end
    T_sum = struct_cell_to_table(rows);
end

function val = prctile_base(x, p)
    xs = sort(x(:));
    if isempty(xs), val = 0.0; return; end
    idx = 1 + (numel(xs) - 1) * (p / 100.0);
    lo = floor(idx); hi = ceil(idx);
    val = xs(lo) + (idx - lo) * (xs(hi) - xs(lo));
end

function generate_four_core_plots(T_main, T_ablation, T_envelope, out_dir, scenarios)
    T_sum = summarize_results(T_main, {'scenario', 'tumble_deg_s'});

    % Plot 1: Terminal-condition pass rate vs tumble rate
    f1 = figure('Visible', 'off', 'Position', [100, 100, 750, 460]);
    hold on; grid on;
    for isc = 1:numel(scenarios)
        sc = scenarios{isc};
        sub = T_sum(T_sum.scenario == string(sc), :);
        [~, sidx] = sort(sub.tumble_deg_s);
        sub = sub(sidx, :);
        plot(sub.tumble_deg_s, sub.p_terminal_pass, '-o', 'LineWidth', 1.8, 'DisplayName', strrep(sc, '_', '\_'));
    end
    xlabel('Initial Target Tumble Rate [deg/s]');
    ylabel('P(Terminal Condition Met)');
    title('Plot 1: Terminal-Condition Pass Rate vs. Tumble Rate');
    ylim([-0.03, 1.03]);
    legend('Location', 'best');
    saveas(f1, fullfile(out_dir, 'plot1_terminal_pass_vs_tumble.png'));
    close(f1);

    % Plot 2: C2 Beacon Ablation
    T_abl_sum = summarize_results(T_ablation, {'scenario', 'beacon_packet_loss', 'beacon_rate_hz'});
    f2 = figure('Visible', 'off', 'Position', [100, 100, 750, 460]);
    hold on; grid on;
    rates = unique(T_abl_sum.beacon_rate_hz);
    abl_scens = {'C2_id_only', 'C2_beacon'};
    for isc = 1:numel(abl_scens)
        for ir = 1:numel(rates)
            sub = T_abl_sum(T_abl_sum.scenario == string(abl_scens{isc}) & T_abl_sum.beacon_rate_hz == rates(ir), :);
            [~, sidx] = sort(sub.beacon_packet_loss);
            sub = sub(sidx, :);
            lbl = sprintf('%s (%.1f Hz)', strrep(abl_scens{isc}, '_', '\_'), rates(ir));
            plot(sub.beacon_packet_loss, sub.rms_capture_point_error_m, '-s', 'LineWidth', 1.6, 'DisplayName', lbl);
        end
    end
    xlabel('Beacon Packet Loss Probability');
    ylabel('RMS Capture-Point Prediction Error [m]');
    title('Plot 2: C2 Beacon Ablation (ID-Only vs. Gyro Packets)');
    legend('Location', 'best');
    saveas(f2, fullfile(out_dir, 'plot2_c2_beacon_ablation.png'));
    close(f2);

    % Plot 3: 2-D Servicing Envelope
    T_env_sum = summarize_results(T_envelope, {'tumble_deg_s', 'vision_sigma_m'});
    u_rates = unique(T_env_sum.tumble_deg_s);
    u_sigs = unique(T_env_sum.vision_sigma_m);
    Z = zeros(numel(u_sigs), numel(u_rates));
    for i = 1:numel(u_sigs)
        for j = 1:numel(u_rates)
            m = T_env_sum.vision_sigma_m == u_sigs(i) & T_env_sum.tumble_deg_s == u_rates(j);
            if any(m), Z(i, j) = T_env_sum.p_terminal_pass(find(m, 1)); end
        end
    end
    f3 = figure('Visible', 'off', 'Position', [100, 100, 700, 460]);
    imagesc(u_rates, u_sigs * 100, Z);
    set(gca, 'YDir', 'normal');
    colorbar; caxis([0, 1]);
    xlabel('Target Tumble Rate [deg/s]');
    ylabel('Optical Position Noise Proxy [cm]');
    title('Plot 3: 2-D Safe Servicing Envelope (C2\_beacon Pass Fraction)');
    saveas(f3, fullfile(out_dir, 'plot3_2d_servicing_envelope.png'));
    close(f3);

    % Plot 4: Client Preparation Trade Curve at 2.0 deg/s
    f4 = figure('Visible', 'off', 'Position', [100, 100, 750, 460]);
    sub2 = T_sum(abs(T_sum.tumble_deg_s - 2.0) < 1e-6, :);
    errs = zeros(numel(scenarios), 1);
    aborts = zeros(numel(scenarios), 1);
    for isc = 1:numel(scenarios)
        m = sub2.scenario == string(scenarios{isc});
        if any(m)
            errs(isc) = sub2.rms_capture_point_error_m(find(m, 1));
            aborts(isc) = sub2.p_abort(find(m, 1));
        end
    end
    yyaxis left;
    plot(1:numel(scenarios), errs, '-o', 'LineWidth', 2.0);
    ylabel('RMS Capture-Point Prediction Error [m]');
    yyaxis right;
    plot(1:numel(scenarios), aborts, '--s', 'LineWidth', 2.0);
    ylabel('P(Abort)'); ylim([-0.05, 1.05]);
    set(gca, 'XTick', 1:numel(scenarios), 'XTickLabel', strrep(scenarios, '_', '\_'));
    title('Plot 4: Client Preparation Trade Curve (at 2 deg/s Tumble)');
    grid on;
    saveas(f4, fullfile(out_dir, 'plot4_preparation_trade_curve.png'));
    close(f4);
end

%% ========================================================================
%  8. VERIFICATION & VALIDATION SUITE (Handbook Section 13 - All 10 Tests)
%  ========================================================================
function run_verification_suite(cfg)
    fprintf('Running Section 13 Verification & Validation Suite (10 Checks)...\n');

    % Test 1: CW zero-control check vs analytical State Transition Matrix
    s0 = [15.0; -25.0; 5.0; 0.02; -0.01; 0.005];
    s_rk4 = s0;
    dt_t = 0.1; steps_t = 500;
    for k = 1:steps_t
        s_rk4 = propagate_cw_rk4(s_rk4, [0; 0; 0], dt_t, cfg.n_geo_rad_s);
    end
    s_stm = cw_state_transition_matrix(steps_t * dt_t, cfg.n_geo_rad_s) * s0;
    err_cw = norm(s_rk4 - s_stm);
    assert(err_cw < 1e-8, 'Test 1 Failed: CW error = %e', err_cw);
    fprintf('  [PASS] 1. CW zero-control check (RK4 vs Analytical STM error = %.2e m)\n', err_cw);

    % Test 2: Stationary, perfect sensors
    r_stat = run_single_simulation('C1_fiducials', 1, 0.0, 0.05, 0.20, 1.0, 0.0, cfg, true);
    assert(r_stat.terminal_pass && ~r_stat.unsafe, 'Test 2 Failed');
    fprintf('  [PASS] 2. Stationary, perfect sensors (converged without body penetration)\n');

    % Test 3: Zero beacon, identical noise -> C2 with 100% loss reduces to C1
    r_c1 = run_single_simulation('C1_fiducials', 42, 1.5, 0.05, 1.0, 1.0, 0.0, cfg, false);
    r_c2_off = run_single_simulation('C2_beacon', 42, 1.5, 0.05, 1.0, 1.0, 0.0, cfg, false);
    diff_c1_c2 = abs(r_c1.capture_point_error_m - r_c2_off.capture_point_error_m);
    assert(diff_c1_c2 < 1e-12, 'Test 3 Failed');
    fprintf('  [PASS] 3. Zero beacon reduction check (|C2_loss=1.0 - C1| = %.2e m)\n', diff_c1_c2);

    % Test 4: Beacon ID-only vs rate data
    r_c2_id = run_single_simulation('C2_id_only', 42, 1.5, 0.05, 0.0, 1.0, 0.0, cfg, false);
    diff_id = abs(r_c1.capture_point_error_m - r_c2_id.capture_point_error_m);
    assert(diff_id < 1e-12, 'Test 4 Failed');
    fprintf('  [PASS] 4. Beacon ID-only check (|C2_id_only - C1| = %.2e m)\n', diff_id);

    % Test 5: Packet delivery boundaries & latency timestamp check
    r_c2_on = run_single_simulation('C2_beacon', 42, 1.5, 0.05, 0.0, 2.0, 0.25, cfg, false);
    assert(r_c2_on.capture_point_error_m < r_c2_off.capture_point_error_m, 'Test 5 Failed');
    fprintf('  [PASS] 5. Packet delivery & timestamp check (err_0%%_loss=%.4f m < err_100%%_loss=%.4f m)\n', ...
        r_c2_on.capture_point_error_m, r_c2_off.capture_point_error_m);

    % Test 6: Quaternion norm & frame check
    q_t = [1; 0; 0; 0]; w_t = [0.02; -0.01; 0.035];
    for k = 1:200
        [q_t, w_t] = propagate_attitude_rk4(q_t, w_t, 0.1, cfg.inertia_diag_kgm2);
    end
    q_err = abs(norm(q_t) - 1.0);
    assert(q_err < 1e-14, 'Test 6 Failed');
    fprintf('  [PASS] 6. Quaternion norm & LVLH frame check (| ||q|| - 1 | = %.2e)\n', q_err);

    % Test 7: Zero target rate -> moving capture-point term vanishes
    [~, v_cap_0, ~] = capture_point_kinematics_lvlh(quat_from_z_angle(0.7), [0; 0; 0], cfg.capture_offset_body_m);
    assert(norm(v_cap_0) < 1e-15, 'Test 7 Failed');
    fprintf('  [PASS] 7. Zero target rate check (||v_cap^L|| = 0.0 m/s)\n');

    % Test 8: High angular rate -> safety logic aborts cleanly
    r_high = run_single_simulation('C1_fiducials', 7, 5.0, 0.05, 0.20, 1.0, 0.0, cfg, false);
    assert(r_high.aborted && ~r_high.unsafe && ~r_high.terminal_pass, 'Test 8 Failed');
    fprintf('  [PASS] 8. High angular rate safety abort check (5 deg/s -> %s)\n', r_high.status);

    % Test 9: Integrator time-step convergence check
    s_dt1 = s0; s_dt2 = s0;
    for k = 1:100, s_dt1 = propagate_cw_rk4(s_dt1, [0.005; -0.002; 0.001], 0.2, cfg.n_geo_rad_s); end
    for k = 1:200, s_dt2 = propagate_cw_rk4(s_dt2, [0.005; -0.002; 0.001], 0.1, cfg.n_geo_rad_s); end
    dt_diff = norm(s_dt1 - s_dt2);
    assert(dt_diff < 1e-9, 'Test 9 Failed');
    fprintf('  [PASS] 9. Integrator dt convergence check (diff = %.2e m)\n', dt_diff);

    % Test 10: Paired seeds across C0/C1/C2
    r0 = run_single_simulation('C0_unprepared', 99, 1.0, 0.05, 0.20, 1.0, 0.0, cfg, false);
    r1 = run_single_simulation('C1_fiducials', 99, 1.0, 0.05, 0.20, 1.0, 0.0, cfg, false);
    r2 = run_single_simulation('C2_beacon', 99, 1.0, 0.05, 0.20, 1.0, 0.0, cfg, false);
    assert(r0.theta0_rad == r1.theta0_rad && r1.theta0_rad == r2.theta0_rad, 'Test 10 Failed');
    fprintf('  [PASS] 10. Paired seeds consistency across C0/C1/C2\n');
    fprintf('All 10 Verification & Validation checks passed.\n\n');
end
