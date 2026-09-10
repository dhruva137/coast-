"""Exporter must replay the frozen mapfilter junctions set, not max-turn."""

from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

import numpy as np

_REPO = Path(__file__).resolve().parents[1]
_STRESS = _REPO / "lab" / "stress"
if str(_STRESS) not in sys.path:
    sys.path.insert(0, str(_STRESS))

import export_filter_trace as exp  # noqa: E402


class ExportFilterTraceContractTest(unittest.TestCase):
    def test_particles_match_eval_default(self) -> None:
        self.assertEqual(exp.DEFAULT_PARTICLES, 600)
        self.assertEqual(exp.DEFAULT_YAW_SIGMA, 0.30)
        self.assertEqual(exp.DENY_S, 60.0)

    def test_select_demo_outages_two_help_one_hurt(self) -> None:
        rows = exp.load_benchmark_junctions(exp.DEFAULT_REPORT)
        self.assertGreaterEqual(len(rows), 43)
        picks = exp.select_demo_outages(rows, n_help=2, n_hurt=1)
        self.assertEqual(len(picks), 3)
        helped = [p for p in picks if p["pf_error_m"] < p["free_error_m"]]
        hurt = [p for p in picks if p["pf_error_m"] > p["free_error_m"]]
        self.assertEqual(len(helped), 2, picks)
        self.assertEqual(len(hurt), 1, picks)
        self.assertTrue(all(exp.demo_usable(p) for p in picks))
        # Distinct drives when the report allows it.
        self.assertEqual(len({p["name"] for p in picks}), 3)
        self.assertGreater(picks[-1]["free_error_m"], picks[-1]["pf_error_m"])
        self.assertLess(picks[0]["free_error_m"], picks[0]["pf_error_m"])

    def test_free_dr_trajectory_matches_eval_endpoint(self) -> None:
        t = np.linspace(0.0, 6.0, 61)
        v = np.full(61, 10.0)
        gz = np.zeros(61)
        yaw0 = 0.1
        end = exp._free_dr(t, v, gz, 52.4, -1.5, yaw0)
        lats, lons = exp._free_dr_trajectory(t, v, gz, 52.4, -1.5, yaw0)
        self.assertTrue(np.isfinite(lats[-1]))
        self.assertAlmostEqual(float(lats[-1]), end[0], places=9)
        self.assertAlmostEqual(float(lons[-1]), end[1], places=9)

    def test_eval_seed_yaw_requires_ten_metres(self) -> None:
        cla = np.full(80, 52.4)
        clo = np.zeros(80)
        yaw, _ = exp._eval_seed_yaw(cla, clo, 60)
        self.assertFalse(math.isfinite(yaw))
        clo[59] = 0.00025  # ~17 m east of sample 10 at lat 52.4
        yaw, heading = exp._eval_seed_yaw(cla, clo, 60)
        self.assertTrue(math.isfinite(yaw))
        self.assertTrue(0.0 <= heading < 360.0)

    def test_synthetic_still_labelled(self) -> None:
        trace = exp.run_synthetic_trace(
            n_particles=16, show=8, yaw_sigma=0.30, seed=26168
        )
        self.assertEqual(trace["meta"]["honesty"], "SYNTHETIC")
        self.assertGreater(len(trace["steps"]), 10)
        self.assertNotIn("matched_benchmark", trace["meta"])


if __name__ == "__main__":
    unittest.main()
