"""Sandboxed execution of candidate solutions.

The one piece of the spine that is real, not stubbed: run a candidate under a
wall-clock timeout and a memory cap and return a structured
:class:`~solver.contracts.ExecResult`.
"""

from __future__ import annotations

from typing import Any, Optional, Sequence

from ..contracts import Candidate, ExecResult, ExecStatus, PYTHON, RUST
from .python_exec import run_python_candidate
from .rust_exec import run_rust_candidate, rustc_path

__all__ = [
    "run_python_candidate",
    "run_rust_candidate",
    "rustc_path",
    "smoke_run",
]


def smoke_run(
    candidate: Candidate,
    entrypoint: str,
    *,
    timeout_s: float,
    py_args: Optional[Sequence[Any]] = None,
    rust_stdin: str = "",
) -> ExecResult:
    """Language-agnostic 'does it run without crashing' check used to establish
    a best-so-far. Real verification (with generated inputs) plugs in later."""
    if candidate.language == PYTHON:
        return run_python_candidate(candidate.source, entrypoint, py_args, timeout_s=timeout_s)
    if candidate.language == RUST:
        return run_rust_candidate(candidate.source, rust_stdin, run_timeout_s=timeout_s)
    return ExecResult(status=ExecStatus.COMPILE_ERROR, error=f"unsupported language {candidate.language!r}")
