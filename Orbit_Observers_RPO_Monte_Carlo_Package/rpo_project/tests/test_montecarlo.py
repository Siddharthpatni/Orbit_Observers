"""Fast runner checks without executing the spacecraft model."""
import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

from ..montecarlo import run_campaign


class CampaignTests(unittest.TestCase):
    def test_invalid_options_do_not_create_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "results"
            for options in (
                {"runs_per_cell": 0}, {"runs_per_cell": -1},
                {"num_chunks": 0}, {"chunk_id": -1},
                {"chunk_id": 1, "num_chunks": 1},
                {"chunk_id": 7, "num_chunks": 8}, {"sweep_runs": 0},
            ):
                with self.subTest(options=options), self.assertRaises(ValueError):
                    run_campaign(**({"runs_per_cell": 1, "out_dir": out} | options))
                self.assertFalse(out.exists())

    def test_small_campaign_exports_all_sweeps(self):
        with tempfile.TemporaryDirectory() as tmp, \
                patch("rpo_project.montecarlo.run_single_simulation", return_value={"seed": 0}) as simulate, \
                patch("rpo_project.montecarlo.summarize_results", return_value=pd.DataFrame({"n_runs": [1]})), \
                patch("rpo_project.montecarlo.generate_four_core_plots") as plots, \
                contextlib.redirect_stdout(io.StringIO()):
            out = Path(tmp)
            run_campaign(1, out, sweep_runs=1)
            self.assertEqual(simulate.call_count, 89)
            for name, count in (("main", 35), ("ablation", 30), ("envelope", 24)):
                self.assertEqual(len(pd.read_csv(out / f"runs_{name}.csv")), count)
            self.assertTrue((out / "summary_main.csv").exists())
            plots.assert_called_once()

    def test_chunks_partition_paired_scenarios(self):
        with tempfile.TemporaryDirectory() as tmp, \
                patch("rpo_project.montecarlo.run_single_simulation", return_value={"seed": 0}) as simulate, \
                contextlib.redirect_stdout(io.StringIO()):
            groups = []
            for chunk in range(2):
                simulate.reset_mock()
                run_campaign(1, Path(tmp), chunk_id=chunk, num_chunks=2)
                groups.append({call.args[:3] for call in simulate.call_args_list})
                for omega in {args[2] for args in groups[-1]}:
                    self.assertEqual(sum(args[2] == omega for args in groups[-1]), 5)
            self.assertFalse(groups[0] & groups[1])
            self.assertEqual(len(groups[0] | groups[1]), 35)


if __name__ == "__main__":
    unittest.main()
