"""verify(candidates) -> VerdictReport.

STUB: the real question this project poses is "how do you verify without public
examples?" — that is the next workstream, not this one. Here, verify only does
the one thing the spine can honestly do: run each candidate through the sandbox
and record whether it executed without crashing. ``passed`` therefore means
"ran", NOT "correct". ``best`` is the first candidate that ran; ``disagreements``
is left empty (no differential testing yet).
"""

from __future__ import annotations

from typing import Any, Optional, Sequence

from ..contracts import Candidate, SpecSheet, Verdict, VerdictReport
from ..sandbox import smoke_run


def verify(
    candidates: Sequence[Candidate],
    spec: SpecSheet,
    *,
    timeout_s: float = 10.0,
    py_args: Optional[Sequence[Any]] = None,
    rust_stdin: str = "",
) -> VerdictReport:
    verdicts: list[Verdict] = []
    best: Optional[Candidate] = None

    for cand in candidates:
        result = smoke_run(
            cand,
            spec.entrypoint,
            timeout_s=timeout_s,
            py_args=py_args,
            rust_stdin=rust_stdin,
        )
        verdicts.append(
            Verdict(
                candidate_id=cand.id,
                passed=result.ran_ok,  # STUB semantics: "ran", not "correct"
                detail=result.status.value if result.ran_ok else (result.error or result.status.value),
                exec_result=result,
            )
        )
        if best is None and result.ran_ok:
            best = cand

    return VerdictReport(verdicts=verdicts, best=best, disagreements=[])
