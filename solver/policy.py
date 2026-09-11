"""Language-target policy: what candidate code is allowed to use.

The grader's Python and Rust versions are unstated. Code valid on an older
toolchain runs on a newer one, not the reverse, so we target the lowest common
denominator the box gives us and make that a structural constraint rather than a
thing to remember:

* Python: target 3.9. The harness itself runs on 3.9, so a candidate that uses
  3.10+ syntax (``match``, some ``X | Y`` forms) fails at OUR compile step
  (:func:`python_target_violations`) instead of silently on the grader.
* Rust: integer width. ``10**18`` fits i64 but products/sums of such values do
  not; ``10**30`` needs u128/i128. The Rust sandbox compiles with overflow
  checks so a candidate reaching for a too-narrow type is a DETECTABLE overflow
  rather than a silent wrap (see ``sandbox.rust_exec``).
"""

from __future__ import annotations

import ast

from .contracts import PYTHON, RUST, TargetPolicy

PYTHON_MIN = "3.9"

PYTHON_FORBIDDEN = [
    "match statements (3.10+)",
    "PEP 604 X | Y type annotations (3.10+)",
    "PEP 695 type-parameter syntax (3.12+)",
    "any stdlib API newer than 3.9",
]

RUST_NOTES = [
    "integers: 10^18 exceeds i32 and products of such values exceed i64/u64; "
    "use i128/u128 (u128 tops out ~3.4e38, covering the 10^30 bounds)",
    "stdlib only; no unsafe; no nondeterminism",
    "the sandbox compiles with overflow checks on, so a too-narrow integer type "
    "surfaces as an OVERFLOWED outcome instead of a silent wrap",
]


def policy_for(language: str) -> TargetPolicy:
    if language == PYTHON:
        return TargetPolicy(
            language=PYTHON,
            python_min=PYTHON_MIN,
            forbidden_features=list(PYTHON_FORBIDDEN),
            notes=[f"generate + verify against Python {PYTHON_MIN}"],
        )
    if language == RUST:
        return TargetPolicy(language=RUST, notes=list(RUST_NOTES))
    return TargetPolicy(language=language)


def python_target_violations(source: str) -> list[str]:
    """Best-effort structural check that ``source`` is valid under the harness's
    Python (3.9). A non-empty result means the candidate uses syntax newer than
    the target and would risk failing only on the grader.

    Note: this catches syntax-level regressions (e.g. ``match``); it cannot catch
    every newer-API misuse. It relies on the harness running on the target
    version, so it stays correct as the floor moves.
    """
    try:
        tree = compile(source, "<candidate>", "exec", flags=ast.PyCF_ONLY_AST)
    except SyntaxError as exc:  # 3.10+ syntax on a 3.9 interpreter lands here
        return [f"not valid under Python {PYTHON_MIN}: {exc.msg} (line {exc.lineno})"]

    # PEP 604 (`X | Y`) annotations parse and — under `from __future__ import
    # annotations`, or on an uncalled helper — never evaluate, so the compile
    # gate above cannot see them; on a 3.9 grader they raise TypeError the moment
    # the annotation is evaluated. Flag them explicitly from the AST.
    return _pep604_annotation_violations(tree)


def _pep604_annotation_violations(tree: ast.AST) -> list[str]:
    violations: list[str] = []

    def uses_bitor(node: ast.AST) -> bool:
        return any(
            isinstance(n, ast.BinOp) and isinstance(n.op, ast.BitOr)
            for n in ast.walk(node)
        )

    for node in ast.walk(tree):
        anns: list = []
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            a = node.args
            for arg in [*a.posonlyargs, *a.args, *a.kwonlyargs, a.vararg, a.kwarg]:
                if arg is not None and arg.annotation is not None:
                    anns.append(arg.annotation)
            if node.returns is not None:
                anns.append(node.returns)
        elif isinstance(node, ast.AnnAssign):
            anns.append(node.annotation)
        for ann in anns:
            if uses_bitor(ann):
                line = getattr(ann, "lineno", "?")
                violations.append(
                    f"PEP 604 `X | Y` type annotation is 3.10+ (line {line}); "
                    f"use typing.Union / Optional under Python {PYTHON_MIN}"
                )
    return violations
