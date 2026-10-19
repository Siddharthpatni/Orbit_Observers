"""Campaign runner checks: option validation, pairing, chunk/merge integrity, parallel determinism."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import hashlib
import zipfile
import unittest
from unittest.mock import patch

import pandas as pd

from ..montecarlo import STUDIES, Study, build_task_groups, merge_chunks, run_campaign, run_task_group
from ..config import SimConfig

TINY = Study("tiny", "tiny test study", ("C1_fiducials", "C2_beacon"), (("tumble_deg_s", (0.0, 3.0)),), seed_offset=0)


def fake_simulation(scenario, seed, tumble, vision, loss, rate, latency, cfg, master_seed=0):
    return {"scenario": scenario, "seed": seed, "tumble_deg_s": tumble, "vision_sigma_m": vision,
            "beacon_packet_loss": loss, "beacon_rate_hz": rate, "latency_s": latency,
            "status": "TERMINAL_CAPTURE_WINDOW_MET", "terminal_pass": True, "aborted": False, "unsafe": False,
            "master_seed": master_seed}


@contextlib.contextmanager
def quiet():
    with contextlib.redirect_stdout(io.StringIO()):
        yield


class OptionTests(unittest.TestCase):
    def test_invalid_options_do_not_create_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "results"
            for options in (
                {"runs_per_cell": 0}, {"runs_per_cell": -1}, {"num_chunks": 0}, {"chunk_id": -1},
                {"chunk_id": 1, "num_chunks": 1}, {"sweep_runs": 0}, {"master_seed": -1},
                {"studies": ["nope"]}, {"runs_per_cell": 1_000_000},
                {"chunk_id": 999, "num_chunks": 1000, "studies": ["main"]},
            ):
                with self.subTest(options=options), self.assertRaises(ValueError):
                    run_campaign(**({"runs_per_cell": 1, "out_dir": out} | options))
                self.assertFalse(out.exists())


class TaskTests(unittest.TestCase):
    def test_counts_and_seed_blocks(self):
        groups = build_task_groups(list(STUDIES.values()), runs=3, sweep_runs=2)
        sims = sum(len(g[0].scenarios) for g in groups)
        self.assertEqual(sims, 7 * 3 * 5 + 15 * 2 * 2 + 24 * 2 * 2 + 5 * 2 * 2)
        seeds = {name: {g[0].seed_offset + g[2] for g in groups if g[0].name == name} for name in STUDIES}
        for a in STUDIES:
            for b in STUDIES:
                if a != b:
                    self.assertFalse(seeds[a] & seeds[b], f"studies {a} and {b} share seeds")

    def test_group_runs_every_tier_on_one_seed(self):
        with patch("rpo_project.montecarlo.run_single_simulation", side_effect=fake_simulation):
            rows = run_task_group((TINY, 1, 4), SimConfig(), master_seed=7)
        self.assertEqual([r["scenario"] for r in rows], ["C1_fiducials", "C2_beacon"])
        self.assertEqual({(r["seed"], r["tumble_deg_s"], r["master_seed"], r["cell"]) for r in rows}, {(4, 3.0, 7, 1)})


class CampaignTests(unittest.TestCase):
    def test_chunks_partition_paired_groups_and_merge(self):
        with tempfile.TemporaryDirectory() as tmp, quiet(), \
                patch("rpo_project.montecarlo.run_single_simulation", side_effect=fake_simulation), \
                patch.dict("rpo_project.montecarlo.STUDIES", {"main": STUDIES["main"]}, clear=True):
            out = Path(tmp)
            for chunk in range(3):
                run_campaign(2, out, chunk_id=chunk, num_chunks=3, studies=["main"])
                part = pd.read_csv(out / "chunks" / f"runs_chunk_{chunk:03d}.csv")
                self.assertTrue((part.groupby(["cell", "seed"]).size() == 5).all(), "a tier pair was split")
            merge_chunks(out, analyse=False)
            merged = pd.read_csv(out / "runs_main.csv")
            self.assertEqual(len(merged), 7 * 2 * 5)
            self.assertFalse(merged.duplicated(["cell", "seed", "scenario"]).any())
            self.assertEqual(json.loads((out / "manifest.json").read_text())["merged_chunks"], 3)

    def test_merge_rejects_missing_or_mismatched_chunks(self):
        with tempfile.TemporaryDirectory() as tmp, quiet(), \
                patch("rpo_project.montecarlo.run_single_simulation", side_effect=fake_simulation):
            out = Path(tmp)
            run_campaign(1, out, chunk_id=0, num_chunks=2, studies=["main"])
            with self.assertRaisesRegex(ValueError, "missing chunks"):
                merge_chunks(out, analyse=False)
            run_campaign(1, out, chunk_id=1, num_chunks=2, studies=["main"], master_seed=5)
            with self.assertRaisesRegex(ValueError, "different campaigns"):
                merge_chunks(out, analyse=False)

    def test_source_snapshot_and_mismatched_source_merge(self):
        with tempfile.TemporaryDirectory() as tmp, quiet(), \
                patch("rpo_project.montecarlo.run_single_simulation", side_effect=fake_simulation):
            out = Path(tmp)
            for chunk in range(2):
                run_campaign(1, out, chunk_id=chunk, num_chunks=2, studies=["main"])
            path = out / "chunks" / "manifest_chunk_001.json"
            manifest = json.loads(path.read_text())
            with zipfile.ZipFile(out / manifest["source_archive"]) as archive:
                for name, digest in manifest["source_files_sha256"].items():
                    self.assertEqual(hashlib.sha256(archive.read(name)).hexdigest(), digest)
            manifest["source_sha256"] = "different-source"
            path.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, "source_sha256"):
                merge_chunks(out, analyse=False)
            self.assertFalse((out / "runs_main.csv").exists())

    def test_parallel_equals_serial_with_real_simulations(self):
        with tempfile.TemporaryDirectory() as tmp, quiet(), \
                patch.dict("rpo_project.montecarlo.STUDIES", {"tiny": TINY}, clear=True), \
                patch("rpo_project.analyse.analyse_campaign"):
            serial, parallel = Path(tmp) / "serial", Path(tmp) / "parallel"
            run_campaign(2, serial, studies=["tiny"], workers=1)
            run_campaign(2, parallel, studies=["tiny"], workers=2)
            self.assertEqual((serial / "runs_tiny.csv").read_bytes(), (parallel / "runs_tiny.csv").read_bytes())


if __name__ == "__main__":
    unittest.main()
