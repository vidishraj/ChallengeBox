"""Performance probe: a correct-but-slow candidate scores zero exactly like a
wrong one, so speed at maximum size is a verification signal, not polish.

Two facts shape this:

* We measure REAL wall-clock at max size rather than reasoning about complexity.
  A correct O(log n) pure-Python treap ran a stated ceiling in ~33 seconds in
  this corpus; correct asymptotics were not sufficient, CPython constant factors
  and recursion cost were. So the probe runs the candidate and times it.
* Rust timing uses the UNCHECKED build (overflow_checks=False). The overflow
  checks are a correctness instrument, not something the grader pays for, so
  timing against the checked build would be pessimistic and could discard a
  candidate that is actually fast enough. Correctness is judged on the checked
  build elsewhere; speed is judged here on the unchecked one.

The probe measures; it does not itself decide policy. verify() turns
(ran-in-time?) into a Verdict, aimed by the bounds-diff hot paths at the specific
quantity that can explode.
"""

from __future__ import annotations

from dataclasses import dataclass

from .contracts import PYTHON, RUST, Candidate, ExecStatus
from .sandbox import run_python_candidate, run_rust_candidate


@dataclass
class PerfResult:
    perf_ok: bool  # ran to completion within the time limit at max size
    duration_s: float
    status: ExecStatus
    detail: str = ""


def perf_probe(candidate: Candidate, entrypoint: str, big_input, *, time_limit_s: float) -> PerfResult:
    """Run one candidate on a maximum-size input and time it. ``perf_ok`` is True
    only when it RAN TO COMPLETION within ``time_limit_s`` (a timeout is a
    performance failure, not an error to be excused)."""
    if candidate.language == PYTHON:
        r = run_python_candidate(candidate.source, entrypoint, big_input, timeout_s=time_limit_s)
    elif candidate.language == RUST:
        # Unchecked build for timing (see module docstring).
        r = run_rust_candidate(candidate.source, big_input, run_timeout_s=time_limit_s, overflow_checks=False)
    else:
        return PerfResult(perf_ok=False, duration_s=0.0, status=ExecStatus.COMPILE_ERROR, detail="unsupported language")

    perf_ok = r.status == ExecStatus.OK
    if r.status == ExecStatus.TIMED_OUT:
        detail = f"too slow: exceeded {time_limit_s:.2f}s at max size"
    elif not perf_ok:
        detail = r.error or r.status.value
    else:
        detail = f"cleared max size in {r.duration_s:.3f}s"
    return PerfResult(perf_ok=perf_ok, duration_s=r.duration_s, status=r.status, detail=detail)
