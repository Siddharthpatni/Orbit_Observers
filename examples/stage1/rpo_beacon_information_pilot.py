"""Educational Monte Carlo pilot: value of client preparation for tracking a GEO capture point.

This is NOT a closed-loop RPO or physical capture simulation. It models a 2-D
rotating interface, noisy/occluded optical attitude observations, and optional
independent angular-rate packets. It reports 2-second-ahead capture-point
PREDICTION accuracy (not physical docking success).

Usage:
    python rpo_beacon_information_pilot.py --runs 200 --out pilot_results

Requires numpy, pandas, matplotlib. Results use fixed paired seeds for C0-C2.
"""
import argparse
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

CAPTURE_RADIUS_M = 1.5
STEP_S = 0.5
DURATION_S = 20.0
PREDICTION_HORIZON_S = 2.0
REQUIRED_PREDICTION_ERROR_M = 0.20  # Study proxy ONLY
GYRO_NOISE_RAD_PER_S = np.deg2rad(0.08)  # Hypothetical, not flight data

def wrap_pi(theta):
    return (theta + np.pi) % (2*np.pi) - np.pi

def true_theta_omega(theta0, omega0, t):
    """Simple constant-rate planar tumble. omega is relative to local frame."""
    return theta0 + omega0*t, omega0

def kf_angle_update(state, cov, measurement, sigma):
    h=np.array([1.0,0.0])
    residual=wrap_pi(measurement - state[0])
    ss=float(h@cov@h+sigma*sigma)
    k=(cov@h)/ss
    state=state+k*residual
    cov=(np.eye(2)-np.outer(k,h))@cov
    return state,cov

def kf_rate_update(state,cov,rate_measurement,sigma):
    h=np.array([0.0,1.0])
    residual=rate_measurement-state[1]
    ss=float(h@cov@h+sigma*sigma)
    k=(cov@h)/ss
    state=state+k*residual
    cov=(np.eye(2)-np.outer(k,h))@cov
    return state,cov

def run_one(seed, tumble_deg_s, case, dropout=0.2):
    """Return averaged prediction error for a paired scenario."""
    rng=np.random.default_rng(int(seed))
    n=int(round(DURATION_S/STEP_S))
    theta0=rng.uniform(-np.pi,np.pi)
    omega0=np.deg2rad(float(tumble_deg_s))
    # Draw all random noise even if a case does not use it: paired trial design.
    std_normal=rng.standard_normal(n)
    gyro_noise=rng.standard_normal(n)
    optical_uniform=rng.uniform(size=n)
    beacon_uniform=rng.uniform(size=n)

    c={
        'C0_unprepared':dict(vision_sigma=np.deg2rad(12),vision_dropout=0.30,beacon=False,omega_factor=1.0),
        'C1_fiducials':dict(vision_sigma=np.deg2rad(3),vision_dropout=0.08,beacon=False,omega_factor=1.0),
        'C2_id_only':dict(vision_sigma=np.deg2rad(3),vision_dropout=0.08,beacon=False,omega_factor=1.0),
        'C2_beacon':dict(vision_sigma=np.deg2rad(3),vision_dropout=0.08,beacon=True,omega_factor=1.0),
        'C3_ios_mode':dict(vision_sigma=np.deg2rad(3),vision_dropout=0.08,beacon=True,omega_factor=0.05),
    }[case]
    omega0*=c['omega_factor']
    # Prior independent of truth; initial pose observation is noisy.
    x=np.array([theta0+std_normal[0]*c['vision_sigma'],0.0])
    cov=np.diag([c['vision_sigma']**2,np.deg2rad(3)**2])
    errs=[]
    for k in range(1,n):
        t=k*STEP_S
        th,om=true_theta_omega(theta0,omega0,t)
        F=np.array([[1.0,STEP_S],[0.0,1.0]])
        # A small rate random-walk process-noise assumption.
        qomega=np.deg2rad(0.015)**2
        Q=qomega*np.array([[STEP_S**3/3,STEP_S**2/2],
                           [STEP_S**2/2,STEP_S]])
        x=F@x
        cov=F@cov@F.T+Q
        if optical_uniform[k] >= c['vision_dropout']:
            optical=wrap_pi(th+c['vision_sigma']*std_normal[k])
            x,cov=kf_angle_update(x,cov,optical,c['vision_sigma'])
        # Transmit 1 packet per second; no latency in this minimal pilot.
        if c['beacon'] and k%2==0 and beacon_uniform[k] >= dropout:
            gyro=om+GYRO_NOISE_RAD_PER_S*gyro_noise[k]
            x,cov=kf_rate_update(x,cov,gyro,GYRO_NOISE_RAD_PER_S)
        if t>=4:  # omit filter transient
            pred_angle=x[0]+PREDICTION_HORIZON_S*x[1]
            true_future,_=true_theta_omega(theta0,omega0,t+PREDICTION_HORIZON_S)
            # 2D interface position error. No servicer trajectory is simulated.
            cp_hat=CAPTURE_RADIUS_M*np.array([np.cos(pred_angle),np.sin(pred_angle)])
            cp_true=CAPTURE_RADIUS_M*np.array([np.cos(true_future),np.sin(true_future)])
            errs.append(float(np.linalg.norm(cp_hat-cp_true)))
    return {'case':case,'tumble_deg_s':float(tumble_deg_s),'seed':int(seed),
            'mean_prediction_error_m':float(np.mean(errs)),
            'p90_prediction_error_m':float(np.percentile(errs,90)),
            'prediction_window_pass':float(np.mean(np.array(errs)<=REQUIRED_PREDICTION_ERROR_M))}

def main():
    a=argparse.ArgumentParser()
    a.add_argument('--runs',type=int,default=200)
    a.add_argument('--out',default='pilot_results')
    args=a.parse_args()
    out=Path(args.out); out.mkdir(parents=True,exist_ok=True)
    rates=[0.0,0.5,1.0,2.0,3.0,5.0]
    cases=['C0_unprepared','C1_fiducials','C2_id_only','C2_beacon','C3_ios_mode']
    rows=[]
    for omega in rates:
        for seed in range(args.runs):
            # paired seeds, including across cases
            for case in cases:
                rows.append(run_one(seed,omega,case))
    df=pd.DataFrame(rows)
    df.to_csv(out/'runs.csv',index=False)
    grp=df.groupby(['case','tumble_deg_s'],as_index=False).agg(
        mean_pred_err_m=('mean_prediction_error_m','mean'),
        prediction_window_pass=('prediction_window_pass','mean'))
    grp.to_csv(out/'summary.csv',index=False)
    fig,axs=plt.subplots(1,2,figsize=(10,4))
    for case in cases:
        q=grp[grp['case']==case]
        axs[0].plot(q.tumble_deg_s,q.mean_pred_err_m,marker='o',label=case)
        axs[1].plot(q.tumble_deg_s,q.prediction_window_pass,marker='o',label=case)
    axs[0].set(title='2-s capture-point prediction',xlabel='Initial tumble [deg/s]',ylabel='Mean error [m]')
    axs[1].set(title='Prediction-window pass proxy',xlabel='Initial tumble [deg/s]',ylabel='Fraction within 0.20 m')
    for ax in axs: ax.grid(alpha=.25)
    axs[1].set_ylim(-.02,1.02)
    fig.legend(cases,loc='lower center',ncol=3)
    fig.tight_layout(rect=(0,.19,1,1))
    fig.savefig(out/'pilot_plots.png',dpi=180)
    plt.close(fig)
    print(grp.to_string(index=False))
    print('\nLIMITATION: This is prediction-only. It does not simulate servicer guidance, collision, docking, or capture.')
if __name__=='__main__':main()
