from __future__ import annotations

import unittest

from solver.bounds import classify, detect_bounds
from solver.contracts import SCAN_CLEAR_VERIFIED, SCAN_INCONCLUSIVE, SCAN_TRAPS_FOUND


class TestEnumerationHints(unittest.TestCase):
    """The PRIMARY output: an explicit derived bound read as what to enumerate."""

    def test_number_of_X_is_at_most_Y(self):
        bd = detect_bounds("The number of maximal surviving rectangles is at most 150000.")
        self.assertEqual(bd.status, SCAN_TRAPS_FOUND)
        self.assertEqual(len(bd.enumeration_hints), 1)
        h = bd.enumeration_hints[0]
        self.assertIn("rectangles", h.quantity)
        self.assertEqual(h.bound, "150000")

    def test_at_most_N_derived_subject(self):
        bd = detect_bounds("There are at most 1,000,000 candidate names to consider.")
        self.assertTrue(bd.enumeration_hints)
        self.assertEqual(bd.enumeration_hints[0].bound, "1,000,000")

    def test_at_most_N_input_subject_is_not_an_enumeration_hint(self):
        # "at most 200000 packets" is an input size, not a derived quantity.
        bd = detect_bounds("There are at most 200000 packets.")
        self.assertEqual(bd.enumeration_hints, [])


class TestHotPaths(unittest.TestCase):
    def test_large_magnitude_is_a_hot_path(self):
        bd = detect_bounds("Along every ancestry, demand never exceeds 10^18.")
        self.assertEqual(bd.status, SCAN_TRAPS_FOUND)
        self.assertTrue(bd.hot_paths)
        self.assertEqual(bd.hot_paths[0].magnitude, "10^18")

    def test_unbounded_derived_quantity(self):
        bd = detect_bounds("Reversed ranges have no bound on their combined length.")
        self.assertTrue(any(h.magnitude == "unbounded" for h in bd.hot_paths))

    def test_no_boundary_is_not_read_as_unbounded(self):
        # Regression: "no boundary" must NOT match "no bound".
        bd = detect_bounds("Between U+000D and U+000A, there is no boundary.")
        self.assertFalse(any(h.magnitude == "unbounded" for h in bd.hot_paths))


class TestResidueChannel(unittest.TestCase):
    def test_unclassified_hot_path_becomes_residue(self):
        # A large magnitude with no category cue (comma form, no 10^/1e token):
        # flagged AND surfaced as residue.
        bd = detect_bounds("The frobnicator tally reaches 2,500,000,000 during processing.")
        self.assertTrue(bd.hot_paths)
        self.assertEqual(bd.hot_paths[0].category, "")
        self.assertTrue(bd.residue_fired)

    def test_classified_hot_path_does_not_fire_residue(self):
        bd = detect_bounds("The worker performs that many spin iterations, up to 10^18 of them.")
        self.assertTrue(bd.hot_paths)
        self.assertTrue(bd.hot_paths[0].category)  # counter-not-a-loop
        self.assertFalse(bd.residue_fired)


class TestStatusDistinctness(unittest.TestCase):
    """The core requirement: verified-clear and not-verified must be DIFFERENT
    values, and clear must rest on positive evidence."""

    def test_clear_verified_needs_positive_evidence(self):
        bd = detect_bounds("Here 1 <= N <= 5000. Return the resulting sorted list.")
        self.assertEqual(bd.status, SCAN_CLEAR_VERIFIED)
        self.assertTrue(bd.input_bounds)
        self.assertTrue(bd.derived_quantities)

    def test_inconclusive_when_nothing_established(self):
        bd = detect_bounds("Do the thing described above.")
        self.assertEqual(bd.status, SCAN_INCONCLUSIVE)

    def test_clear_and_inconclusive_are_distinct(self):
        clear = detect_bounds("With 1 <= N <= 100, return the computed answer.").status
        incon = detect_bounds("An opaque instruction.").status
        self.assertNotEqual(clear, incon)


class TestValueDomainVersusScaling(unittest.TestCase):
    """A magnitude bounding a stored VALUE is a width concern, not a scaling trap
    (calibrated against patchboard, the one genuinely generous sample)."""

    def test_value_domain_magnitude_is_not_a_scaling_hot_path(self):
        bd = detect_bounds("Attributes are in 1..=10^9.")
        self.assertEqual(bd.hot_paths, [])

    def test_count_magnitude_is_a_scaling_hot_path(self):
        bd = detect_bounds("The demand reaches 10^9 units.")
        self.assertTrue(bd.hot_paths)


class TestClassify(unittest.TestCase):
    def test_known_cue_maps_to_category(self):
        self.assertEqual(classify("it performs cost spin iterations"), "counter-not-a-loop")
        self.assertEqual(classify("return the maximal intervals, canonical form"), "canonical-form-output")

    def test_new_categories_classify(self):
        self.assertEqual(classify("apply the first matching rule"), "ordered-rule-priority")
        self.assertEqual(classify("count the consecutive indicators ending at the left"), "context-sensitive-look-back")
        self.assertEqual(classify("creates version i from an earlier version b"), "persistent-or-branching-version-state")
        self.assertEqual(classify("its complete unfolding into a tree"), "exponential-unfolding-of-shared-dag")

    def test_unknown_returns_empty(self):
        self.assertEqual(classify("the sky is a pleasant shade of blue"), "")


if __name__ == "__main__":
    unittest.main()
