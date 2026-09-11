from __future__ import annotations

import unittest

from solver.contracts import ExecStatus
from solver.policy import python_target_violations
from solver.sandbox import run_python_candidate, run_rust_candidate, rustc_path

RUSTC = rustc_path()


class TestPythonSandbox(unittest.TestCase):
    def test_ok_returns_value(self):
        r = run_python_candidate("def f(a, b):\n    return a + b\n", "f", [2, 3], timeout_s=5)
        self.assertEqual(r.status, ExecStatus.OK)
        self.assertEqual(r.value, 5)
        self.assertTrue(r.ran_ok)

    def test_crashed_on_raise(self):
        r = run_python_candidate("def f():\n    raise ValueError('boom')\n", "f", [], timeout_s=5)
        self.assertEqual(r.status, ExecStatus.CRASHED)
        self.assertIn("boom", r.error)

    def test_wrong_shape_missing_entrypoint(self):
        r = run_python_candidate("x = 1\n", "f", [], timeout_s=5)
        self.assertEqual(r.status, ExecStatus.WRONG_SHAPE)

    def test_compile_error_on_syntax(self):
        r = run_python_candidate("def f(:\n pass\n", "f", [], timeout_s=5)
        self.assertEqual(r.status, ExecStatus.COMPILE_ERROR)

    def test_timed_out(self):
        r = run_python_candidate("def f():\n    import time; time.sleep(3)\n", "f", [], timeout_s=0.5)
        self.assertEqual(r.status, ExecStatus.TIMED_OUT)

    def test_memory_cap_crashes_not_kills_harness(self):
        # Allocate well past a tiny cap; the child dies, the harness survives.
        src = "def f():\n    x = bytearray(500 * 1024 * 1024)\n    return len(x)\n"
        r = run_python_candidate(src, "f", [], timeout_s=5, mem_bytes=64 * 1024 * 1024)
        self.assertIn(r.status, (ExecStatus.CRASHED, ExecStatus.TIMED_OUT))


class TestPolicy(unittest.TestCase):
    def test_match_statement_flagged_under_39(self):
        # `match` is 3.10+ syntax; on the 3.9 harness it must be flagged.
        violations = python_target_violations("def f(x):\n    match x:\n        case 1:\n            return 1\n")
        self.assertTrue(violations)

    def test_plain_39_code_clean(self):
        self.assertEqual(python_target_violations("def f(x):\n    return x\n"), [])

    def test_pep604_param_annotation_flagged(self):
        # `X | Y` parses on 3.9 but raises TypeError when the annotation is
        # evaluated on the grader; compile() alone would miss it.
        violations = python_target_violations("def f(x: int | str):\n    return x\n")
        self.assertTrue(violations)
        self.assertIn("604", violations[0])

    def test_pep604_return_annotation_flagged(self):
        self.assertTrue(python_target_violations("def f() -> int | None:\n    return None\n"))

    def test_pep604_nested_annotation_flagged(self):
        # Buried inside a subscript, on a helper that is never called.
        src = "from typing import Optional\ndef helper(x: Optional[int | str]):\n    return x\n"
        self.assertTrue(python_target_violations(src))

    def test_union_import_is_clean(self):
        src = "from typing import Union\ndef f(x: Union[int, str]):\n    return x\n"
        self.assertEqual(python_target_violations(src), [])


@unittest.skipUnless(RUSTC, "rustc not available")
class TestRustSandbox(unittest.TestCase):
    def test_ok_echoes_stdin(self):
        src = (
            "use std::io::Read;\n"
            "fn main() {\n"
            "    let mut s = String::new();\n"
            "    std::io::stdin().read_to_string(&mut s).unwrap();\n"
            "    print!(\"{}\", s.trim());\n"
            "}\n"
        )
        r = run_rust_candidate(src, stdin="hello", run_timeout_s=10)
        self.assertEqual(r.status, ExecStatus.OK)
        self.assertEqual(r.value, "hello")

    def test_compile_error(self):
        r = run_rust_candidate("fn main() { let x: i32 = ; }\n", run_timeout_s=10)
        self.assertEqual(r.status, ExecStatus.COMPILE_ERROR)
        self.assertIn("error", r.stderr.lower())

    def test_integer_overflow_is_detected(self):
        # Read the operand at runtime so it is not const-folded at compile time.
        src = (
            "use std::io::Read;\n"
            "fn main() {\n"
            "    let mut s = String::new();\n"
            "    std::io::stdin().read_to_string(&mut s).unwrap();\n"
            "    let x: u8 = s.trim().parse().unwrap();\n"
            "    let y = x + 1;\n"
            "    println!(\"{}\", y);\n"
            "}\n"
        )
        r = run_rust_candidate(src, stdin="255", run_timeout_s=10)
        self.assertEqual(r.status, ExecStatus.OVERFLOWED)

    def test_crashed_on_nonzero_exit(self):
        r = run_rust_candidate("fn main() { std::process::exit(3); }\n", run_timeout_s=10)
        self.assertEqual(r.status, ExecStatus.CRASHED)


if __name__ == "__main__":
    unittest.main()
