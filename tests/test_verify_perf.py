from __future__ import annotations

import unittest

from solver.contracts import Candidate, SpecSheet
from solver.stages.verify import verify


def _spec():
    return SpecSheet(entrypoint="f", language="python")


def _cand(cid: str, body: str, origin: str = "stub") -> Candidate:
    return Candidate(id=cid, language="python", source=f"def f(x):\n{body}\n", origin=origin)


def _v(report, cid):
    return next(v for v in report.verdicts if v.candidate_id == cid)


class TestPerformanceProbe(unittest.TestCase):
    """Correct-but-slow scores zero exactly like wrong: the probe must reject it."""

    def test_slow_candidate_rejected_on_perf(self):
        slow = _cand("slow", "    import time\n    if x:\n        time.sleep(2)\n    return 1")
        report = verify([slow], _spec(), inputs=[[0]], big_inputs=[[1]], perf_limit_s=0.5)
        v = _v(report, "slow")
        self.assertFalse(v.perf_ok)
        self.assertFalse(v.passed)
        self.assertIn("slow", v.detail)

    def test_fast_candidate_passes_perf(self):
        fast = _cand("fast", "    return 1")
        report = verify([fast], _spec(), inputs=[[0]], big_inputs=[[1]], perf_limit_s=5)
        v = _v(report, "fast")
        self.assertTrue(v.perf_ok)
        self.assertTrue(v.passed)


class TestNaiveVersusFast(unittest.TestCase):
    """A literal reference is the oracle on small inputs; a value disagreement
    with it marks the fast candidate wrong."""

    def _ref(self):
        return _cand("ref", "    return x * 2", origin="literal-reference")

    def test_wrong_candidate_caught_by_reference(self):
        wrong = _cand("wrong", "    return x * 3")
        report = verify([self._ref(), wrong], _spec(), inputs=[[2]])
        self.assertFalse(_v(report, "wrong").passed)
        self.assertIn("reference", _v(report, "wrong").detail)

    def test_agreeing_candidate_passes(self):
        good = _cand("good", "    return x + x")  # == x*2 for ints
        report = verify([self._ref(), good], _spec(), inputs=[[2]])
        self.assertTrue(_v(report, "good").passed)

    def test_reference_not_selected_as_best(self):
        good = _cand("good", "    return x * 2")
        report = verify([self._ref(), good], _spec(), inputs=[[2]])
        self.assertIsNotNone(report.best)
        self.assertNotEqual(report.best.id, "ref")
        self.assertEqual(report.best.id, "good")

    def test_reference_exempt_from_perf_probe(self):
        good = _cand("good", "    return x * 2")
        report = verify(
            [self._ref(), good], _spec(), inputs=[[2]], big_inputs=[[2]], perf_limit_s=5
        )
        self.assertIsNone(_v(report, "ref").perf_ok)  # not probed
        self.assertTrue(_v(report, "good").perf_ok)


if __name__ == "__main__":
    unittest.main()
