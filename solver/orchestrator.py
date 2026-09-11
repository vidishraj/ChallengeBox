"""The staged pipeline: analyse -> generate -> verify -> adjudicate.

Wires the (stubbed) stages together around the two invariants that must be real
from day one: a hard wall-clock budget measured from process start, and a
best-so-far solution ALWAYS present on disk (written the moment any candidate
runs, overwritten only by a verified-better one). We never fail closed — a wrong
answer and no answer both score zero.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .budget import BestSoFar, TimeBudget
from .contracts import Candidate, Problem, SpecSheet, VerdictReport
from .runlog import RunLog
from .stages import adjudicate, analyse, generate, verify

# Fraction of the remaining budget any single smoke-run may consume, and a hard
# cap so a generous deadline doesn't mean minute-long stub runs.
_SMOKE_FRACTION = 0.5
_SMOKE_CAP_S = 10.0


@dataclass
class SolveResult:
    problem_id: str
    language: str
    path: Path
    best: Optional[Candidate]
    verified: bool
    spec: SpecSheet
    report: VerdictReport
    budget: TimeBudget
    runlog: RunLog

    @property
    def delivered(self) -> bool:
        """A solution file exists on disk within the deadline."""
        return self.path.exists() and not self.budget.expired()


def solve(
    problem: Problem,
    out_path: str | Path,
    *,
    start: Optional[float] = None,
    n_candidates: int = 1,
    runlog: Optional[RunLog] = None,
) -> SolveResult:
    out_path = Path(out_path)
    budget = TimeBudget(problem.deadline_s, start=start)
    log = runlog or RunLog(problem.problem_id, start=budget.start)
    best = BestSoFar(out_path)

    log.event(
        "start",
        language=problem.language,
        entrypoint=problem.entrypoint,
        deadline_s=problem.deadline_s,
    )

    # 1. analyse
    with log.stage("analyse") as rec:
        spec = analyse(problem.statement, problem)
        rec.note(
            "specsheet ready",
            signature=spec.signature,
            target=(spec.target.python_min if spec.target else None),
        )

    # 2. generate
    with log.stage("generate") as rec:
        candidates = generate(spec, n_candidates)
        rec.note(f"{len(candidates)} candidate(s)", ids=[c.id for c in candidates])

    # 3. verify (property assertions + differential) + establish best-so-far ASAP
    with log.stage("verify") as rec:
        smoke_s = budget.slice_for(_SMOKE_FRACTION, cap=_SMOKE_CAP_S)
        report = verify(candidates, spec, timeout_s=max(1.0, smoke_s))
        # Best-so-far on disk = the first candidate that RAN (never fail closed),
        # even if it later fails a property; a verified-better one overwrites it.
        for verdict in report.verdicts:
            if verdict.exec_result and verdict.exec_result.ran_ok:
                cand = next(c for c in candidates if c.id == verdict.candidate_id)
                if best.offer(cand):
                    log.event("best-so-far written (ran ok)", candidate=cand.id, verified=False)
                break
        passed = sum(1 for v in report.verdicts if v.passed)
        rec.note(
            f"{passed}/{len(report.verdicts)} passed; "
            f"best={report.best.id if report.best else None}; "
            f"disagreements={len(report.disagreements)}",
            statuses={v.candidate_id: (v.exec_result.status.value if v.exec_result else "?") for v in report.verdicts},
            disagreement_kinds=[d.kind for d in report.disagreements],
            smoke_timeout_s=round(smoke_s, 3),
        )

    # 4. adjudicate disagreements -> the chosen candidate. Defensive: use the
    # adjudicated result only when it is a Candidate, else fall back to the
    # verified best. (The real two-arg adjudicate lands with the generation
    # workstream; this stays correct with the stub until then.)
    with log.stage("adjudicate") as rec:
        resolved = adjudicate(report.disagreements)
        chosen = resolved if isinstance(resolved, Candidate) else report.best
        rec.note("chosen=" + (chosen.id if chosen else "none"))

    # 5. commit the verified-better choice over the best-so-far
    verified = False
    if chosen is not None:
        best.commit(chosen)
        verified = True
        log.event("committed verified best", candidate=chosen.id)

    # 6. never fail closed: guarantee a file on disk even if nothing ran
    if not best.has_solution and candidates:
        best.offer(candidates[0])
        log.event("fallback: wrote unverified candidate", candidate=candidates[0].id)

    log.event(
        "done",
        delivered=best.has_solution,
        expired=budget.expired(),
        remaining_s=round(budget.remaining(), 3),
    )

    return SolveResult(
        problem_id=problem.problem_id,
        language=problem.language,
        path=out_path,
        best=best.current,
        verified=verified,
        spec=spec,
        report=report,
        budget=budget,
        runlog=log,
    )
