from __future__ import annotations

import unittest

from solver.contracts import Candidate, SpecSheet
from solver.stages.verify import verify


def _spec(output_properties=None):
    return SpecSheet(entrypoint="f", language="python", output_properties=list(output_properties or []))


def _cand(cid: str, body: str) -> Candidate:
    return Candidate(id=cid, language="python", source=f"def f(x):\n{body}\n")


def _verdict(report, cid):
    return next(v for v in report.verdicts if v.candidate_id == cid)


class TestPropertyAssertionsFire(unittest.TestCase):
    """The load-bearing negative control: an assertion framework that never fails
    is indistinguishable from none. These prove it FAILS when it should."""

    def test_sorted_violation_is_caught_with_no_second_candidate(self):
        spec = _spec(["the result is sorted"])
        bad = _cand("bad", "    return [3, 1, 2]")
        report = verify([bad], spec, inputs=[[0]], timeout_s=5)
        v = _verdict(report, "bad")
        self.assertFalse(v.passed)
        self.assertIn("nondecreasing", v.detail)
        self.assertIsNone(report.best)

    def test_sorted_candidate_passes(self):
        spec = _spec(["the result is sorted"])
        good = _cand("good", "    return [1, 2, 3]")
        report = verify([good], spec, inputs=[[0]], timeout_s=5)
        self.assertTrue(_verdict(report, "good").passed)
        self.assertEqual(report.best.id, "good")

    def test_distinct_violation_is_caught(self):
        spec = _spec(["all elements are distinct"])
        dup = _cand("dup", "    return [1, 1, 2]")
        self.assertFalse(_verdict(verify([dup], spec, inputs=[[0]], timeout_s=5), "dup").passed)

    def test_no_false_positive_on_unsupported_shape(self):
        # A "sorted" property with a scalar (non-list) output must NOT fail.
        spec = _spec(["the result is sorted"])
        scalar = _cand("scalar", "    return 7")
        self.assertTrue(_verdict(verify([scalar], spec, inputs=[[0]], timeout_s=5), "scalar").passed)


class TestDifferentialClassification(unittest.TestCase):
    def test_value_disagreement(self):
        spec = _spec()
        a = _cand("a", "    return 1")
        b = _cand("b", "    return 2")
        report = verify([a, b], spec, inputs=[[0]], timeout_s=5)
        self.assertEqual(len(report.disagreements), 1)
        d = report.disagreements[0]
        self.assertEqual(d.kind, "value")
        self.assertEqual(d.failing_input, [0])
        self.assertEqual(d.outputs, {"a": 1, "b": 2})

    def test_form_disagreement_same_multiset_other_order(self):
        spec = _spec()
        a = _cand("a", "    return [1, 2]")
        b = _cand("b", "    return [2, 1]")
        report = verify([a, b], spec, inputs=[[0]], timeout_s=5)
        self.assertEqual(report.disagreements[0].kind, "form")

    def test_status_disagreement_one_crashes(self):
        spec = _spec()
        a = _cand("a", "    return 1")
        b = _cand("b", "    raise ValueError('boom')")
        report = verify([a, b], spec, inputs=[[0]], timeout_s=5)
        d = report.disagreements[0]
        self.assertEqual(d.kind, "status")
        self.assertEqual(d.outputs["b"], "<crashed>")

    def test_agreement_yields_no_disagreement(self):
        spec = _spec()
        a = _cand("a", "    return 5")
        b = _cand("b", "    return 5")
        report = verify([a, b], spec, inputs=[[0]], timeout_s=5)
        self.assertEqual(report.disagreements, [])
        self.assertIsNotNone(report.best)


if __name__ == "__main__":
    unittest.main()
