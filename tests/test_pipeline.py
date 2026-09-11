from __future__ import annotations

import glob
import json
import tempfile
import time
import unittest
from pathlib import Path

from solver.contracts import Problem
from solver.orchestrator import solve
from solver.sandbox import rustc_path

SAMPLES = sorted(glob.glob(str(Path(__file__).resolve().parent.parent / "samples" / "*.json")))


def _lang(path: str) -> str:
    return json.loads(Path(path).read_text(encoding="utf-8"))["language"]


class TestPipeline(unittest.TestCase):
    def test_python_sample_end_to_end(self):
        py = next(s for s in SAMPLES if _lang(s) == "python")
        problem = Problem.load(py)
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / f"{problem.problem_id}.py"
            result = solve(problem, out, start=time.monotonic(), n_candidates=2)
            self.assertTrue(out.exists(), "a solution file must always be on disk")
            self.assertTrue(result.delivered)
            self.assertIn(f"def {problem.entrypoint}", out.read_text())
            # Run log captured every stage.
            stages = [e.stage for e in result.runlog.entries]
            self.assertEqual(stages, ["analyse", "generate", "verify", "adjudicate"])

    @unittest.skipUnless(rustc_path(), "rustc not available")
    def test_rust_sample_end_to_end(self):
        rs = next(s for s in SAMPLES if _lang(s) == "rust")
        problem = Problem.load(rs)
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / f"{problem.problem_id}.rs"
            result = solve(problem, out, start=time.monotonic())
            self.assertTrue(out.exists())
            self.assertTrue(result.delivered)
            self.assertIn("fn main()", out.read_text())

    def test_specsheet_carries_python_target_policy(self):
        py = next(s for s in SAMPLES if _lang(s) == "python")
        problem = Problem.load(py)
        with tempfile.TemporaryDirectory() as d:
            result = solve(problem, Path(d) / "s.py", start=time.monotonic())
            self.assertIsNotNone(result.spec.target)
            self.assertEqual(result.spec.target.python_min, "3.9")

    def test_all_samples_deliver(self):
        # Every shipped sample produces a solution file within its deadline.
        for s in SAMPLES:
            problem = Problem.load(s)
            if problem.language == "rust" and not rustc_path():
                continue
            with tempfile.TemporaryDirectory() as d:
                out = Path(d) / f"{problem.problem_id}.{problem.ext}"
                result = solve(problem, out, start=time.monotonic())
                self.assertTrue(out.exists(), f"{problem.problem_id} produced no file")
                self.assertTrue(result.delivered, f"{problem.problem_id} not delivered")


if __name__ == "__main__":
    unittest.main()
