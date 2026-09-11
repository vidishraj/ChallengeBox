"""verify(candidates, spec) -> VerdictReport.

The verification checks, in the order they should run (cheapest and most
independent first):

1. PROPERTY ASSERTIONS. Run each candidate and check its output against the
   canonical-form properties analyse() extracted. A violation is a CONFIRMED
   failure with no second candidate required.
2. NAIVE-VERSUS-FAST. If a literal clause-by-clause reference candidate is
   present (origin == "literal-reference"), differential-test every other
   candidate against it on small inputs. A VALUE disagreement with the reference
   (not a mere form difference) marks that candidate wrong. This catches the
   failure binary scoring punishes hardest: right on small inputs by luck, wrong
   in a way the reference exposes.
3. DIFFERENTIAL TESTING across candidates, classifying each divergence value /
   form / status so a formatting difference is not reported as a wrong answer.
4. PERFORMANCE PROBE. If a maximum-size input is supplied, time each candidate
   on it (Rust uses the unchecked build); a candidate that does not clear it
   within the limit is rejected, because correct-but-slow scores zero exactly
   like wrong. The reference is exempt (it is the slow oracle, by design).

Inputs default to a trivial in-domain generator; the real spec-derived generator
and the max-size inputs aimed at the bounds-diff hot paths plug into ``inputs`` /
``big_inputs`` without changing this contract.
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
from ..perf import perf_probe
from ..props import canonicalize, check_output_properties, classify_value_disagreement
from ..sandbox import run_python_candidate, run_rust_candidate

REFERENCE_ORIGIN = "literal-reference"

_STATUS_TAG = {
    ExecStatus.CRASHED: "<crashed>",
    ExecStatus.TIMED_OUT: "<timed-out>",
    ExecStatus.OVERFLOWED: "<overflowed>",
    ExecStatus.COMPILE_ERROR: "<compile-error>",
    ExecStatus.WRONG_SHAPE: "<wrong-shape>",
}


def _trivial_python_inputs(spec: SpecSheet) -> list[list[Any]]:
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
    from ..contracts import ExecResult

    return ExecResult(status=ExecStatus.COMPILE_ERROR, error=f"unsupported language {candidate.language!r}")


def _safe_canon(v: Any) -> Any:
    try:
        return canonicalize(v)
    except Exception:
        return ("raw", repr(v))


def _classify(outputs: dict[str, Any], statuses: dict[str, ExecStatus]) -> Optional[str]:
    ok_ids = list(outputs)
    all_ids = list(statuses)
    if ok_ids and len(ok_ids) != len(all_ids):
        return "status"
    if len(ok_ids) < 2:
        return None
    if all(outputs[cid] == outputs[ok_ids[0]] for cid in ok_ids):
        return None
    canon = {cid: _safe_canon(outputs[cid]) for cid in ok_ids}
    first = canon[ok_ids[0]]
    if all(canon[cid] == first for cid in ok_ids):
        return "form"
    return "value"


def verify(
    candidates: Sequence[Candidate],
    spec: SpecSheet,
    *,
    timeout_s: float = 10.0,
    inputs: Optional[Sequence[Any]] = None,
    reference_id: Optional[str] = None,
    big_inputs: Optional[Sequence[Any]] = None,
    perf_limit_s: Optional[float] = None,
) -> VerdictReport:
    candidates = list(candidates)
    if not candidates:
        return VerdictReport(verdicts=[], best=None, disagreements=[])

    if inputs is None:
        inputs = _trivial_python_inputs(spec) if spec.language == PYTHON else _trivial_rust_inputs(spec)
    inputs = list(inputs)

    if reference_id is None:
        reference_id = next((c.id for c in candidates if c.origin == REFERENCE_ORIGIN), None)

    # small-input runs
    results: dict[str, list] = {c.id: [_run(c, spec, one, timeout_s) for one in inputs] for c in candidates}
    ref_runs = results.get(reference_id) if reference_id else None

    verdicts: list[Verdict] = []
    for c in candidates:
        runs = results[c.id]
        is_reference = c.id == reference_id
        ran_all = all(r.ran_ok for r in runs)

        prop_violations: list[str] = []
        for r in runs:
            if r.ran_ok:
                prop_violations.extend(check_output_properties(r.value, spec.output_properties))

        # 2. naive-vs-fast against the literal reference (skip the reference itself)
        ref_mismatch: Optional[int] = None
        if ref_runs is not None and not is_reference:
            for i, r in enumerate(runs):
                rr = ref_runs[i]
                if r.ran_ok and rr.ran_ok and classify_value_disagreement(r.value, rr.value) == "value":
                    ref_mismatch = i
                    break

        # 4. performance probe at max size (skip the reference; it is the slow oracle)
        perf_ok: Optional[bool] = None
        max_dur = 0.0
        if big_inputs and perf_limit_s and not is_reference:
            perf_ok = True
            for b in big_inputs:
                pr = perf_probe(c, spec.entrypoint, b, time_limit_s=perf_limit_s)
                max_dur = max(max_dur, pr.duration_s)
                if not pr.perf_ok:
                    perf_ok = False

        passed = ran_all and not prop_violations and ref_mismatch is None and perf_ok is not False
        verdicts.append(
            Verdict(
                candidate_id=c.id,
                passed=passed,
                detail=_detail(runs, ran_all, prop_violations, ref_mismatch, perf_ok),
                exec_result=runs[0] if runs else None,
                perf_ok=perf_ok,
                max_input_duration_s=round(max_dur, 4),
            )
        )

    passed_ids = {v.candidate_id for v in verdicts if v.passed}
    # the reference is never the shipped best (correct but slow by design)
    best = next((c for c in candidates if c.id in passed_ids and c.id != reference_id), None)

    disagreements = _differential(candidates, spec, results, inputs)
    return VerdictReport(verdicts=verdicts, best=best, disagreements=disagreements)


def _detail(runs, ran_all, prop_violations, ref_mismatch, perf_ok) -> str:
    if not ran_all:
        bad = next(r for r in runs if not r.ran_ok)
        return bad.error or bad.status.value
    if ref_mismatch is not None:
        return f"disagrees with literal reference on input #{ref_mismatch}"
    if prop_violations:
        return "property violation: " + "; ".join(sorted(set(prop_violations)))
    if perf_ok is False:
        return "too slow at max size"
    suffix = " + perf ok" if perf_ok else ""
    return "ran + properties held" + suffix


def _differential(candidates, spec, results, inputs) -> list[Disagreement]:
    disagreements: list[Disagreement] = []
    for i, one in enumerate(inputs):
        outputs: dict[str, Any] = {}
        statuses: dict[str, ExecStatus] = {}
        for c in candidates:
            r = results[c.id][i]
            statuses[c.id] = r.status
            if r.ran_ok:
                outputs[c.id] = r.value
        kind = _classify(outputs, statuses)
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
    return disagreements
