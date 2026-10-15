"""Educational Monte Carlo pilot: value of client preparation for tracking a GEO capture point.
Companion Stage-I starter script included for reference.
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
REQUIRED_PREDICTION_ERROR_M = 0.20
GYRO_NOISE_RAD_PER_S = np.deg2rad(0.08)

def wrap_pi(theta):
    return (theta + np.pi) % (2*np.pi) - np.pi

def true_theta_omega(theta0, omega0, t):
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
