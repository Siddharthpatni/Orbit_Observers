"""Reporting regressions: results must follow the supplied campaign, including failures."""
from pathlib import Path
import tempfile
import json
import unittest

import numpy as np
import pandas as pd

from ..analyse import expected_propellant_per_window, load_campaign, summarize_results, write_report


class ReportTests(unittest.TestCase):
    def test_report_tracks_failures_and_does_not_pool_paired_trials(self):
        for unsafe in (False, True):
            with self.subTest(unsafe=unsafe), tempfile.TemporaryDirectory() as tmp:
                rows = pd.DataFrame([
                    dict(scenario=scenario, seed=seed, tumble_deg_s=3.0,
                         status="UNSAFE_KEEPOUT_VIOLATION" if unsafe else "TERMINAL_CAPTURE_WINDOW_MET",
                         terminal_pass=not unsafe, aborted=False, unsafe=unsafe,
                         capture_point_error_m=0.1, delta_v_mps=1.0, propellant_kg=0.25,
                         elapsed_s=10.0, minimum_clearance_m=-0.01 if unsafe else 0.02)
                    for scenario in ("C1_fiducials", "C2_beacon") for seed in range(2)
                ])
                summary = summarize_results(rows, ["scenario", "tumble_deg_s"])
                manifest = {"studies": {"main": {"grid": {"tumble_deg_s": [3.0]}}}}
                write_report(Path(tmp), manifest, {"main": rows}, {"main": summary}, pd.DataFrame(), [])
                report = (Path(tmp) / "report.md").read_text()
                self.assertIn(f"Observed keep-out violations: {4 if unsafe else 0} / 4", report)
                self.assertIn("Not pooled (paired seeds)", report)
                self.assertNotIn("17,500", report)
                self.assertNotIn("29.4 clients", report)
                self.assertNotIn("+-", report)
                if unsafe:
                    self.assertIn("-10.0 mm", report)
                    self.assertNotIn("100% terminal-window pass rate", report)
                else:
                    # Each tier has two independent seeds, not four pooled independent trials.
                    self.assertIn("77.64%", report)

    def test_partial_campaign_does_not_invent_main_study_findings(self):
        rows = pd.DataFrame([dict(scenario="C2_beacon", seed=0, latency_s=0.5,
                                 unsafe=False, minimum_clearance_m=0.1)])
        manifest = {"studies": {"latency": {"grid": {"latency_s": [0.5]}}}}
        with tempfile.TemporaryDirectory() as tmp:
            write_report(Path(tmp), manifest, {"latency": rows}, {}, pd.DataFrame(), [])
            report = (Path(tmp) / "report.md").read_text()
        self.assertIn("across 1 studies", report)
        self.assertNotIn("92% vs", report)
        self.assertNotIn("100% capture pass rate", report)

    def test_missing_study_file_is_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "manifest.json").write_text(json.dumps({"studies": {"main": {}}}))
            with self.assertRaisesRegex(FileNotFoundError, "partial campaign"):
                load_campaign(root)

    def test_retreat_cost_requires_completed_retreats(self):
        summary = pd.DataFrame({"p_terminal_pass": [0.5, 0.5], "p_abort": [0.5, 0.5],
                                "mean_propellant_kg": [0.3, 0.3], "mean_abort_propellant_kg": [0.4, 0.4],
                                "n_retreat_complete": [5, 4], "n_abort": [5, 5]})
        np.testing.assert_allclose(expected_propellant_per_window(summary), [0.7, np.nan], equal_nan=True)

    def test_retry_cost_handles_undefined_and_uncosted_outcomes(self):
        summary = pd.DataFrame({"p_terminal_pass": [1.0, 0.5, 0.0, 0.5],
                                "p_abort": [0.0, 0.5, 1.0, 0.25],
                                "mean_propellant_kg": [0.3] * 4})
        np.testing.assert_allclose(expected_propellant_per_window(summary),
                                   [0.3, 0.44, np.nan, np.nan], equal_nan=True)


if __name__ == "__main__":
    unittest.main()
