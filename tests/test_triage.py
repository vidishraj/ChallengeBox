from __future__ import annotations

import json
import types
import unittest

from solver.contracts import ClauseFinding, Disagreement, SpecSheet
from solver.triage import parse_clauses, run_triage, triage_prompt


def _spec():
    return SpecSheet(entrypoint="f", language="python", raw_statement="If the list is empty, return zero.")


class _Client:
    """Duck-typed seam stand-in returning a canned triage response."""

    def __init__(self, payload: dict):
        self.payload = payload
        self.calls = 0

    def complete(self, prompt):
        self.calls += 1
        return types.SimpleNamespace(text=json.dumps(self.payload))


def _clause(code_a, code_b, params, clause="C", extra=None):
    item = {
        "clause": clause,
        "reading_a": {"prose": "A", "code": code_a},
        "reading_b": {"prose": "B", "code": code_b},
        "discriminating_input": {"params": params},
    }
    if extra:
        item.update(extra)
    return {"clauses": [item]}


def _run(payload):
    return run_triage(_spec(), _Client(payload), to_request=lambda p: p, timeout_s=5)


class TestTriagePrompt(unittest.TestCase):
    def test_prompt_is_adversarial_and_decorrelated(self):
        p = triage_prompt(_spec())
        self.assertIn("NOT taking", p.system)
        self.assertEqual(p.model, "strong")  # higher-tier / different model knob
        self.assertEqual(p.kind, "triage")

    def test_parse_clauses_tolerates_prose(self):
        text = "here:\n```json\n{\"clauses\": [{\"clause\": \"x\"}]}\n```"
        self.assertEqual(parse_clauses(text), [{"clause": "x"}])


class TestDivergenceEmitsFinding(unittest.TestCase):
    def test_diverging_readings_emit_clause_disagreement_and_finding(self):
        payload = _clause("def f(x):\n    return 1\n", "def f(x):\n    return 2\n", [{"literal": 0}])
        dis, findings = _run(payload)
        self.assertEqual(len(dis), 1)
        self.assertEqual(len(findings), 1)
        d = dis[0]
        self.assertEqual(d.kind, "clause")
        self.assertEqual(d.clause_hint, "C")  # REQUIRED for kind == "clause"
        self.assertEqual(d.failing_input, [0])
        self.assertEqual(set(d.outputs.values()), {1, 2})
        self.assertIsInstance(findings[0], ClauseFinding)
        self.assertEqual((findings[0].output_a, findings[0].output_b), (1, 2))


class TestSelfValidatingDrop(unittest.TestCase):
    def test_agreeing_readings_dropped(self):
        # same output on the discriminating input -> the input did not discriminate.
        dis, findings = _run(_clause("def f(x):\n    return 1\n", "def f(x):\n    return 1\n", [{"literal": 0}]))
        self.assertEqual(dis, [])
        self.assertEqual(findings, [])

    def test_form_only_difference_is_not_a_semantic_ambiguity(self):
        # same multiset, different order -> form, not value -> dropped.
        dis, _ = _run(_clause("def f(x):\n    return [1, 2]\n", "def f(x):\n    return [2, 1]\n", [{"literal": 0}]))
        self.assertEqual(dis, [])

    def test_missing_discriminating_input_dropped(self):
        item = {"clause": "C", "reading_a": {"code": "def f(x):\n return 1\n"}, "reading_b": {"code": "def f(x):\n return 2\n"}}
        dis, _ = run_triage(_spec(), _Client({"clauses": [item]}), to_request=lambda p: p, timeout_s=5)
        self.assertEqual(dis, [])

    def test_missing_reading_code_dropped(self):
        item = {"clause": "C", "reading_a": {"prose": "A"}, "reading_b": {"prose": "B"}, "discriminating_input": {"params": [{"literal": 0}]}}
        dis, _ = run_triage(_spec(), _Client({"clauses": [item]}), to_request=lambda p: p, timeout_s=5)
        self.assertEqual(dis, [])

    def test_a_reading_that_crashes_is_dropped(self):
        dis, _ = _run(_clause("def f(x):\n    return 1\n", "def f(x):\n    raise ValueError('x')\n", [{"literal": 0}]))
        self.assertEqual(dis, [])


class TestNeverGates(unittest.TestCase):
    def test_returns_only_disagreements_and_findings_no_verdict(self):
        # Structural guarantee: triage produces routing + trap-log, never a Verdict.
        dis, findings = _run(_clause("def f(x):\n    return 1\n", "def f(x):\n    return 2\n", [{"literal": 0}]))
        self.assertTrue(all(isinstance(d, Disagreement) for d in dis))
        self.assertTrue(all(isinstance(f, ClauseFinding) for f in findings))

    def test_triage_does_not_change_any_verdict_through_solve(self):
        # Wiring triage into solve() must leave every candidate's pass/fail
        # exactly as it was without triage: triage is not a gate.
        import tempfile
        import time
        from pathlib import Path

        from solver.contracts import Problem
        from solver.orchestrator import solve

        problem = Problem.from_dict({
            "problem_id": "t", "language": "python",
            "statement": "Define `f(xs)`.\nReturn `0`.", "entrypoint": "f",
            "public_examples": [], "deadline_s": 300.0,
        })
        payload = _clause("def f(xs):\n    return 1\n", "def f(xs):\n    return 2\n", [{"literal": []}])

        def _passed_map(**kw):
            with tempfile.TemporaryDirectory() as d:
                r = solve(problem, Path(d) / "f.py", start=time.monotonic(), n_candidates=2, **kw)
                return {v.candidate_id: v.passed for v in r.report.verdicts}, r

        base, _ = _passed_map()
        withtri, r = _passed_map(triage_client=_Client(payload), triage_to_request=lambda p: p)
        self.assertEqual(base, withtri)  # verdicts identical
        self.assertTrue(r.clause_findings)  # but triage still produced its trap-log


if __name__ == "__main__":
    unittest.main()
