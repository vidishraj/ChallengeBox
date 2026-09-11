"""verify(candidates, spec) -> VerdictReport.

Thin vertical slice: the two checks that need NO oracle beyond the statement and
each other, so they can catch even a unanimous misreading.

1. PROPERTY ASSERTIONS. Run each candidate and check its output against the
   canonical-form properties analyse() extracted (ordering, distinctness). A
   violation is a CONFIRMED failure with no second candidate required. Run first
   and conservatively (see solver.props).
2. DIFFERENTIAL TESTING. Run every candidate on the same inputs; where OK outputs
   differ, emit a Disagreement carrying the failing input and each output, and
   classify it value / form / status so a formatting difference is not reported
   as a wrong answer.

Not in this slice (later pieces): the max-size performance probe, the bounds-diff
hot-path targeting, and naive-versus-fast. Inputs here come from a TRIVIAL
in-domain generator derived from the spec; the real spec-derived generator (a
distinct model call) replaces it without changing this contract.
"""

from __future__ import annotations

from typing import Any, Optional, Sequence

from ..contracts import (
    PYTHON,
    RUST,
    Candidate,
    Disagreement,
    ExecStatus,
    SpecSheet,
    Verdict,
    VerdictReport,
)
from ..props import canonicalize, check_output_properties, classify_value_disagreement
from ..sandbox import run_python_candidate, run_rust_candidate

_STATUS_TAG = {
    ExecStatus.CRASHED: "<crashed>",
    ExecStatus.TIMED_OUT: "<timed-out>",
    ExecStatus.OVERFLOWED: "<overflowed>",
    ExecStatus.COMPILE_ERROR: "<compile-error>",
    ExecStatus.WRONG_SHAPE: "<wrong-shape>",
}


def _trivial_python_inputs(spec: SpecSheet) -> list[list[Any]]:
    """A tiny in-domain argument battery, one value per parameter by inferred
    type. Placeholder for the spec-derived generator; enough to run the engine
    and to exercise differential + property checks on real candidates."""
    default = {"list": [], "str": "", "int": 0}
    small = {"list": [1], "str": "a", "int": 1}

    def build(table):
        return [table.get(p.type, None) for p in spec.params]

    if not spec.params:
        return [[]]
    return [build(default), build(small)]


def _trivial_rust_inputs(_spec: SpecSheet) -> list[str]:
    return ["", "0\n"]


def _run(candidate: Candidate, spec: SpecSheet, one_input: Any, timeout_s: float):
    if candidate.language == PYTHON:
        return run_python_candidate(candidate.source, spec.entrypoint, one_input, timeout_s=timeout_s)
    if candidate.language == RUST:
        return run_rust_candidate(candidate.source, one_input, run_timeout_s=timeout_s)
    from ..contracts import ExecResult  # local import to avoid cycle at top

    return ExecResult(status=ExecStatus.COMPILE_ERROR, error=f"unsupported language {candidate.language!r}")


def _classify(outputs: dict[str, Any], statuses: dict[str, ExecStatus], spec: SpecSheet) -> Optional[str]:
    """Given every candidate's result on one input, decide the disagreement kind
    (or None if they agree). ``outputs`` holds OK return values only."""
    ok_ids = list(outputs)
    all_ids = list(statuses)

    # Status divergence: at least one ran OK and at least one did not.
    if ok_ids and len(ok_ids) != len(all_ids):
        return "status"

    if len(ok_ids) < 2:
        return None

    # All ran OK: do the OK outputs agree raw?
    canon = {cid: _safe_canon(outputs[cid]) for cid in ok_ids}
    raw_equal = all(outputs[cid] == outputs[ok_ids[0]] for cid in ok_ids)
    if raw_equal:
        return None
    # Differ raw: form if they agree once normalised, else value.
    first = canon[ok_ids[0]]
    if all(canon[cid] == first for cid in ok_ids):
        return "form"
    return "value"


def _safe_canon(v: Any) -> Any:
    try:
        return canonicalize(v)
    except Exception:
        return ("raw", repr(v))


def verify(
    candidates: Sequence[Candidate],
    spec: SpecSheet,
    *,
    timeout_s: float = 10.0,
    inputs: Optional[Sequence[Any]] = None,
) -> VerdictReport:
    candidates = list(candidates)
    if not candidates:
        return VerdictReport(verdicts=[], best=None, disagreements=[])

    if inputs is None:
        inputs = _trivial_python_inputs(spec) if spec.language == PYTHON else _trivial_rust_inputs(spec)
    inputs = list(inputs)

    # results[cid][i] = ExecResult for candidate cid on input i
    results: dict[str, list] = {c.id: [] for c in candidates}
    for c in candidates:
        for one in inputs:
            results[c.id].append(_run(c, spec, one, timeout_s))

    # --- per-candidate verdicts: ran on every input + no property violation ---
    verdicts: list[Verdict] = []
    for c in candidates:
        runs = results[c.id]
        ran_all = all(r.ran_ok for r in runs)
        prop_violations: list[str] = []
        for r in runs:
            if r.ran_ok:
                prop_violations.extend(check_output_properties(r.value, spec.output_properties))
        passed = ran_all and not prop_violations
        if not ran_all:
            first_bad = next(r for r in runs if not r.ran_ok)
            detail = first_bad.error or first_bad.status.value
        elif prop_violations:
            detail = "property violation: " + "; ".join(sorted(set(prop_violations)))
        else:
            detail = "ran + properties held"
        verdicts.append(
            Verdict(candidate_id=c.id, passed=passed, detail=detail, exec_result=runs[0] if runs else None)
        )

    best = next((c for c in candidates if _passed(verdicts, c.id)), None)

    # --- differential testing across candidates, per input ---
    disagreements: list[Disagreement] = []
    for i, one in enumerate(inputs):
        outputs: dict[str, Any] = {}
        statuses: dict[str, ExecStatus] = {}
        for c in candidates:
            r = results[c.id][i]
            statuses[c.id] = r.status
            if r.ran_ok:
                outputs[c.id] = r.value
        kind = _classify(outputs, statuses, spec)
        if kind is None:
            continue
        divergent = [c for c in candidates if c.id in statuses]
        recorded = {
            c.id: outputs[c.id] if c.id in outputs else _STATUS_TAG.get(statuses[c.id], "<unknown>")
            for c in divergent
        }
        disagreements.append(
            Disagreement(
                failing_input=one,
                outputs=recorded,
                candidates=divergent,
                seed=i,
                kind=kind,
                canonical_hint="; ".join(spec.output_properties) if kind == "form" else "",
            )
        )

    return VerdictReport(verdicts=verdicts, best=best, disagreements=disagreements)


def _passed(verdicts: list[Verdict], cid: str) -> bool:
    return any(v.candidate_id == cid and v.passed for v in verdicts)
