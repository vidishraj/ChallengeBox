from __future__ import annotations

import glob
import json
import unittest
from pathlib import Path

from solver.contracts import Problem
from solver.stages.analyse import analyse

SAMPLES = sorted(glob.glob(str(Path(__file__).resolve().parent.parent / "samples" / "*.json")))


def _spec(statement: str, entrypoint: str = "f", language: str = "python"):
    problem = Problem.from_dict(
        {
            "problem_id": "t",
            "language": language,
            "statement": statement,
            "entrypoint": entrypoint,
            "public_examples": [],
            "deadline_s": 300.0,
        }
    )
    return analyse(statement, problem)


class TestSignatureAndParams(unittest.TestCase):
    def test_signature_and_param_names(self):
        spec = _spec("Define `f(a, b, counts)`.\n`a` is a list of integers.")
        self.assertEqual(spec.signature, "f(a, b, counts)")
        self.assertEqual([p.name for p in spec.params], ["a", "b", "counts"])

    def test_list_type_inferred(self):
        spec = _spec("Define `f(items)`.\n`items` is a list of packet lengths.")
        self.assertEqual(spec.params[0].type, "list")

    def test_chain_inequality_bound_attached(self):
        spec = _spec("Define `f(n)`.\n`1 <= n <= 500000`.")
        self.assertIsNotNone(spec.params[0].bounds)
        self.assertIn("500000", spec.params[0].bounds)

    def test_nonempty_note_captured(self):
        spec = _spec("Define `f(xs)`.\n`xs` is a nonempty sequence.")
        self.assertIn("nonempty", spec.params[0].notes)

    def test_nearest_bracket_wins_on_multi_bracket_sentence(self):
        # Two brackets, two subjects, one sentence: each name gets the nearer one.
        stmt = (
            "Define `f(level, credits)`.\n"
            "The `level` is always in `[0, level_cap]`, and `credits` is always in `[0, credit_cap]`."
        )
        spec = _spec(stmt)
        by = {p.name: p for p in spec.params}
        self.assertIn("credit_cap", by["credits"].bounds or "")
        self.assertNotIn("level_cap", by["credits"].bounds or "")


class TestClauseMining(unittest.TestCase):
    def test_invariant_extracted(self):
        spec = _spec("Define `f(x)`.\nThe value is always in `[0, 10]`.")
        self.assertTrue(any("always" in s.lower() for s in spec.invariants))

    def test_edge_case_extracted(self):
        spec = _spec("Define `f(xs)`.\nEven if the list is empty, return `0`.")
        self.assertTrue(any("even if" in s.lower() for s in spec.edge_cases))

    def test_output_contract_prefers_return_sentence(self):
        spec = _spec("Define `f(refs)`.\nReturn one tuple per reference, in input order.")
        self.assertTrue(spec.output_contract.lower().startswith("return"))


class TestCanonicalFormProperties(unittest.TestCase):
    def test_strong_markers_captured(self):
        stmt = (
            "Return the union in canonical row-run form.\n"
            "Form the maximal inclusive intervals.\n"
            "Sort the result lexicographically."
        )
        spec = _spec(stmt)
        joined = " ".join(spec.output_properties).lower()
        self.assertIn("maximal", joined)
        self.assertIn("lexicograph", joined)

    def test_entrypoint_name_is_not_a_false_positive(self):
        # `normaliz` lives only inside the backticked function name -> not a property.
        spec = _spec("Implement `normalize_data(x)`.\nDo the thing.", entrypoint="normalize_data")
        self.assertEqual(spec.output_properties, [])

    def test_weak_marker_needs_output_context(self):
        # "in order" describing an input process is NOT an output property.
        spec = _spec("Define `f(xs)`.\nValid packets are processed in order.")
        self.assertEqual(spec.output_properties, [])


class TestRustAndTarget(unittest.TestCase):
    def test_rust_main_has_no_signature_but_carries_target(self):
        spec = _spec("Implement `fn main()`. Read N from stdin.", entrypoint="main", language="rust")
        self.assertEqual(spec.signature, "")
        self.assertIsNotNone(spec.target)
        self.assertEqual(spec.target.language, "rust")

    def test_python_target_is_pinned(self):
        spec = _spec("Define `f(x)`.\nReturn `x`.")
        self.assertEqual(spec.target.python_min, "3.9")


class TestAgainstRealSamples(unittest.TestCase):
    def test_every_sample_analyses_without_error_and_populates(self):
        self.assertTrue(SAMPLES, "expected sample problems on disk")
        for s in SAMPLES:
            problem = Problem.load(s)
            spec = analyse(problem.statement, problem)
            self.assertEqual(spec.entrypoint, problem.entrypoint)
            self.assertIsNotNone(spec.target)
            self.assertTrue(spec.raw_statement)
            # A python entrypoint states its signature; every statement yields
            # at least some mined clause (invariant / edge / output).
            if problem.language == "python":
                self.assertIn(problem.entrypoint, spec.signature)
            self.assertTrue(
                spec.invariants or spec.edge_cases or spec.output_contract,
                f"{problem.problem_id}: analyse mined nothing",
            )


if __name__ == "__main__":
    unittest.main()
