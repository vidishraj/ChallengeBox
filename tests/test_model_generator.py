from __future__ import annotations

import json
import tempfile
import time
import types
import unittest
from pathlib import Path

from solver.contracts import BoundsDiff, HotPathQuantity, ParamDomain, Problem, SpecSheet
from solver.generator import check_generator
from solver.model_generator import (
    hotpath_prompt,
    input_generator_prompt,
    materialize,
    parse_plan,
    request_generators,
)
from solver.orchestrator import solve


def _spec():
    return SpecSheet(
        entrypoint="f",
        language="python",
        signature="f(xs, n)",
        params=[ParamDomain("xs", type="list"), ParamDomain("n", type="int", bounds="1 <= n <= 500000")],
        edge_cases=["Even if the list is empty, return 0."],
        bounds_diff=BoundsDiff(
            input_bounds=["1 <= n <= 500000"],
            hot_paths=[HotPathQuantity(quantity="spin count", source_sentence="performs n spins")],
        ),
    )


class TestPrompts(unittest.TestCase):
    def test_two_artifacts_have_distinct_systems(self):
        spec = _spec()
        inp = input_generator_prompt(spec)
        st = hotpath_prompt(spec, spec.bounds_diff.hot_paths[0])
        self.assertNotEqual(inp.system, st.system)
        self.assertEqual(inp.kind, "input")
        self.assertEqual(st.kind, "stress")

    def test_input_prompt_lists_edge_clauses(self):
        p = input_generator_prompt(_spec())
        self.assertIn("Even if the list is empty, return 0.", p.user)

    def test_hotpath_prompt_names_target_and_bounds(self):
        spec = _spec()
        p = hotpath_prompt(spec, spec.bounds_diff.hot_paths[0])
        self.assertEqual(p.target, "spin count")
        self.assertIn("spin count", p.user)
        self.assertIn("1 <= n <= 500000", p.user)  # bound must be preserved


class TestParseAndMaterialize(unittest.TestCase):
    def test_parse_plan_tolerates_prose_and_fence(self):
        text = "Sure!\n```json\n{\"inputs\": [{\"label\": \"empty\", \"params\": []}]}\n```\n"
        self.assertEqual(parse_plan(text), [{"label": "empty", "params": []}])

    def test_parse_plan_garbage_is_empty(self):
        self.assertEqual(parse_plan("no json here"), [])

    def test_materialize_expands_rules(self):
        items = [
            {"label": "a", "params": [{"literal": 5}, {"repeat": {"item": 1, "times": 3}}, {"range": {"start": 0, "stop": 3}}]}
        ]
        li = materialize(items)[0]
        self.assertEqual(li.value, [5, [1, 1, 1], [0, 1, 2]])
        self.assertEqual(li.label, "a")


class _StubClient:
    """Duck-typed stand-in for solver.llm's client: .complete(req).text."""

    def __init__(self):
        self.calls = []

    def complete(self, prompt):  # to_request is identity, so prompt is a GenPrompt
        self.calls.append(prompt)
        if prompt.kind == "input":
            plan = {
                "inputs": [
                    {"label": "empty", "params": [{"literal": []}, {"literal": 1}]},
                    {"label": "singleton", "params": [{"literal": [1]}, {"literal": 1}]},
                    {"label": "n@min", "params": [{"literal": []}, {"literal": 1}]},
                    {"label": "n@max", "params": [{"literal": []}, {"literal": 500000}]},
                    {"label": "Even if the list is empty, return 0.", "params": [{"literal": []}, {"literal": 1}]},
                ]
            }
        else:  # stress, targeting prompt.target
            plan = {"inputs": [{"label": prompt.target, "kind": "stress", "params": [{"repeat": {"item": 1, "times": 10}}, {"literal": 500000}]}]}
        return types.SimpleNamespace(text=json.dumps(plan))


class TestRequestGeneratorsEndToEnd(unittest.TestCase):
    def test_wiring_produces_fully_covered_battery(self):
        spec = _spec()
        client = _StubClient()
        battery, stress = request_generators(spec, client, to_request=lambda p: p)

        # one input call + one call per hot path
        self.assertEqual(sum(1 for c in client.calls if c.kind == "input"), 1)
        self.assertEqual(sum(1 for c in client.calls if c.kind == "stress"), 1)

        # the coverage control adjudicates: this generator covers everything
        report = check_generator(spec, battery, stress)
        self.assertEqual(report.edge_gaps, [])
        self.assertEqual(report.hot_path_gaps, [])
        self.assertTrue(report.covered)

    def test_stress_label_forced_to_hot_path(self):
        spec = _spec()
        _, stress = request_generators(spec, _StubClient(), to_request=lambda p: p)
        self.assertEqual([s.label for s in stress], ["spin count"])
        self.assertEqual(stress[0].kind, "stress")


class _HookStub:
    def complete(self, prompt):
        if prompt.kind == "input":
            plan = {"inputs": [
                {"label": "empty", "params": [{"literal": []}, {"literal": 1}]},
                {"label": "singleton", "params": [{"literal": [1]}, {"literal": 1}]},
            ]}
        else:
            plan = {"inputs": [{"label": prompt.target, "kind": "stress", "params": [{"literal": []}, {"literal": 500000}]}]}
        return types.SimpleNamespace(text=json.dumps(plan))


class TestSolveModelHook(unittest.TestCase):
    def test_model_client_activates_perf_probe(self):
        # A statement with a flagged hot path, so a stress input is requested and
        # the performance probe actually runs on it.
        problem = Problem.from_dict({
            "problem_id": "hook",
            "language": "python",
            "statement": "Define `f(xs, n)`.\n`1 <= n <= 500000`.\nThe demand reaches 10^18.",
            "entrypoint": "f",
            "public_examples": [],
            "deadline_s": 300.0,
        })
        with tempfile.TemporaryDirectory() as d:
            r = solve(
                problem, Path(d) / "f.py", start=time.monotonic(),
                input_client=_HookStub(), to_request=lambda p: p,
            )
            self.assertTrue(r.delivered)
            # the perf probe ran on the candidate (perf_ok set, not None)
            self.assertTrue(any(v.perf_ok is not None for v in r.report.verdicts))


if __name__ == "__main__":
    unittest.main()
