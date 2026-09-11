from __future__ import annotations

import json
import tempfile
import time
import unittest
from pathlib import Path

from solver.budget import BestSoFar, TimeBudget
from solver.contracts import Candidate, Problem

_VALID = {
    "problem_id": "abc",
    "language": "python",
    "statement": "do a thing",
    "entrypoint": "f",
    "public_examples": [],
    "deadline_s": 300.0,
}


class TestProblem(unittest.TestCase):
    def test_from_dict_ok(self):
        p = Problem.from_dict(_VALID)
        self.assertEqual(p.problem_id, "abc")
        self.assertEqual(p.language, "python")
        self.assertEqual(p.ext, "py")

    def test_rust_ext(self):
        p = Problem.from_dict({**_VALID, "language": "rust", "entrypoint": "main"})
        self.assertEqual(p.ext, "rs")

    def test_missing_field(self):
        bad = {k: v for k, v in _VALID.items() if k != "entrypoint"}
        with self.assertRaises(ValueError):
            Problem.from_dict(bad)

    def test_bad_language(self):
        with self.assertRaises(ValueError):
            Problem.from_dict({**_VALID, "language": "cobol"})

    def test_bad_deadline(self):
        with self.assertRaises(ValueError):
            Problem.from_dict({**_VALID, "deadline_s": 0})

    def test_load_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "p.json"
            path.write_text(json.dumps(_VALID), encoding="utf-8")
            self.assertEqual(Problem.load(path).entrypoint, "f")


class TestTimeBudget(unittest.TestCase):
    def test_remaining_and_expired(self):
        b = TimeBudget(deadline_s=10.0, start=time.monotonic())
        self.assertGreater(b.remaining(), 9.0)
        self.assertFalse(b.expired())

    def test_expired_in_past(self):
        b = TimeBudget(deadline_s=1.0, start=time.monotonic() - 5.0)
        self.assertEqual(b.remaining(), 0.0)
        self.assertTrue(b.expired())

    def test_slice_for_capped(self):
        b = TimeBudget(deadline_s=100.0, start=time.monotonic())
        self.assertLessEqual(b.slice_for(0.5, cap=3.0), 3.0)


class TestBestSoFar(unittest.TestCase):
    def _cand(self, cid: str, src: str) -> Candidate:
        return Candidate(id=cid, language="python", source=src)

    def test_offer_then_commit(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "sol.py"
            bsf = BestSoFar(path)
            self.assertFalse(bsf.has_solution)

            # First runnable wins the slot.
            self.assertTrue(bsf.offer(self._cand("a", "# A")))
            self.assertTrue(bsf.has_solution)
            self.assertEqual(path.read_text(), "# A")

            # A second offer does NOT overwrite (only verified-better may).
            self.assertFalse(bsf.offer(self._cand("b", "# B")))
            self.assertEqual(path.read_text(), "# A")

            # commit always overwrites.
            self.assertTrue(bsf.commit(self._cand("c", "# C")))
            self.assertEqual(path.read_text(), "# C")
            self.assertEqual(bsf.current.id, "c")

    def test_write_is_atomic_no_leftover_tmp(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "nested" / "sol.py"
            BestSoFar(path).offer(self._cand("a", "x = 1"))
            self.assertTrue(path.exists())
            self.assertEqual(list(path.parent.glob("*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
