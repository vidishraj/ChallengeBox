from __future__ import annotations

import unittest

from solver.contracts import BoundsDiff, HotPathQuantity, ParamDomain, SpecSheet
from solver.generator import (
    CoverageError,
    LabeledInput,
    assert_generator_covers,
    check_generator,
    coverage_gaps,
    deterministic_battery,
    hot_path_gaps,
    structural_requirements,
)


def _spec(edge_cases=None, hot=None):
    return SpecSheet(
        entrypoint="f",
        language="python",
        params=[
            ParamDomain("xs", type="list"),
            ParamDomain("n", type="int", bounds="1 <= n <= 500000"),
        ],
        edge_cases=list(edge_cases or []),
        bounds_diff=BoundsDiff(
            hot_paths=[HotPathQuantity(quantity=q, source_sentence="s") for q in (hot or [])]
        ),
    )


class TestCoverageFires(unittest.TestCase):
    """The load-bearing control: coverage must FAIL when an edge is never hit."""

    def test_missing_edge_is_a_gap(self):
        provided = [LabeledInput(value=[[1], 1], label="singleton")]
        gaps = coverage_gaps(["empty", "singleton"], provided)
        self.assertEqual(gaps, ["empty"])

    def test_full_coverage_no_gap(self):
        provided = [LabeledInput([], "empty"), LabeledInput([[1]], "singleton")]
        self.assertEqual(coverage_gaps(["empty", "singleton"], provided), [])

    def test_extracted_clause_uncovered_by_deterministic_battery(self):
        spec = _spec(edge_cases=["Even if the list is empty, return 0."])
        report = check_generator(spec, deterministic_battery(spec), stress=[])
        self.assertIn("Even if the list is empty, return 0.", report.edge_gaps)
        self.assertFalse(report.covered)

    def test_hot_path_without_aimed_input_is_a_gap(self):
        spec = _spec(hot=["spin count"])
        gaps = hot_path_gaps(spec, stress=[])
        self.assertEqual(gaps, ["spin count"])

    def test_hot_path_with_aimed_input_is_covered(self):
        spec = _spec(hot=["spin count"])
        stress = [LabeledInput(value=[[], 500000], label="spin count", kind="stress")]
        self.assertEqual(hot_path_gaps(spec, stress), [])

    def test_assert_raises_on_gap(self):
        spec = _spec(edge_cases=["a clause never hit"], hot=["spin count"])
        with self.assertRaises(CoverageError):
            assert_generator_covers(spec, deterministic_battery(spec), stress=[])


class TestDeterministicBattery(unittest.TestCase):
    def test_hits_structural_edges(self):
        spec = _spec()  # no prose clauses, no hot paths
        battery = deterministic_battery(spec)
        report = check_generator(spec, battery, stress=[])
        self.assertTrue(report.covered)  # structural edges all hit, nothing else required
        labels = {li.label for li in battery}
        self.assertEqual(labels, set(structural_requirements(spec)))

    def test_extremes_parsed_from_bounds(self):
        spec = _spec()
        by = {li.label: li.value for li in deterministic_battery(spec)}
        # n is params[1]; min 1, max 500000
        self.assertEqual(by["n@min"][1], 1)
        self.assertEqual(by["n@max"][1], 500000)

    def test_empty_input_has_empty_list(self):
        spec = _spec()
        by = {li.label: li.value for li in deterministic_battery(spec)}
        self.assertEqual(by["empty"][0], [])
        self.assertEqual(by["singleton"][0], [1])

    def test_rust_or_no_params_yields_nothing(self):
        self.assertEqual(deterministic_battery(SpecSheet(entrypoint="main", language="rust")), [])


if __name__ == "__main__":
    unittest.main()
