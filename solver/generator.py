"""Spec-derived input generation and its coverage controls.

The input generator is derived from the SPEC via a call distinct from any
candidate generation. Independence is the whole point: if the same reading that
writes the solution also writes the generator, one misreading of the input
domain propagates into both and the generator produces inputs the buggy
candidate handles perfectly. So the generator is a separate artifact keyed to a
distinct prompt.

The load-bearing part here is not the generation, it is the COVERAGE CONTROL. A
generator that never emits an empty input, never hits a bound exactly, never
produces an invalid element will certify everything, and now that the
performance probe consumes the generator's max-size input, a weak generator
would make the probe pass by feeding it inputs that never stress the flagged hot
path. So two coverage checks, both of which must be able to FAIL loudly:

* EDGE COVERAGE: every extracted edge clause (and every structural edge: empty,
  singleton, each bound at its extreme) is exercised by at least one input.
* HOT-PATH COVERAGE: every flagged hot path has a max-size input aimed at it. A
  max-size input that does not explode the flagged derived quantity tests
  nothing while looking like a passing performance check.

A model-written generator plugs in through the LLM seam and labels its own
inputs; the deterministic battery below is the offline fallback and the vehicle
that proves the controls fire.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Optional, Sequence

from .contracts import SpecSheet


class CoverageError(AssertionError):
    """Raised when a generator fails to exercise a required edge or hot path.
    Fail-loud by design: a silently under-covering generator is indistinguishable
    from a strong one until it costs us a problem."""


@dataclass
class LabeledInput:
    """One generated input plus WHAT it is meant to exercise, so coverage is
    checkable rather than assumed."""

    value: Any  # python: positional-args list; rust: stdin string
    label: str  # the edge/clause/hot-path this input targets
    kind: str = "edge"  # "edge" | "stress" | "random"


@dataclass
class GeneratorReport:
    battery: list[LabeledInput] = field(default_factory=list)
    stress: list[LabeledInput] = field(default_factory=list)
    edge_gaps: list[str] = field(default_factory=list)  # required edges never exercised
    hot_path_gaps: list[str] = field(default_factory=list)  # hot paths with no aimed input

    @property
    def covered(self) -> bool:
        return not self.edge_gaps and not self.hot_path_gaps


# --- coverage core -------------------------------------------------------


def coverage_gaps(required: Sequence[str], provided: Sequence[LabeledInput]) -> list[str]:
    """Required labels that no provided input claims to exercise."""
    have = {li.label for li in provided}
    return [r for r in required if r not in have]


def structural_requirements(spec: SpecSheet) -> list[str]:
    """Edges any generator must hit regardless of the prose: empty and singleton
    collections, and each bounded parameter at both extremes."""
    reqs: list[str] = []
    if any(p.type == "list" for p in spec.params):
        reqs += ["empty", "singleton"]
    for p in spec.params:
        if p.bounds:
            reqs += [f"{p.name}@min", f"{p.name}@max"]
    return reqs


def clause_requirements(spec: SpecSheet) -> list[str]:
    """Every extracted edge clause must be exercised. The deterministic battery
    cannot construct inputs for arbitrary prose clauses, so these surface as gaps
    until the model-written generator (which labels its inputs) covers them."""
    return list(spec.edge_cases)


def hot_path_gaps(spec: SpecSheet, stress: Sequence[LabeledInput]) -> list[str]:
    """Flagged hot paths with no max-size input aimed at them."""
    if not spec.bounds_diff:
        return []
    aimed = {s.label for s in stress}
    return [h.quantity for h in spec.bounds_diff.hot_paths if h.quantity not in aimed]


def check_generator(spec: SpecSheet, battery: Sequence[LabeledInput], stress: Sequence[LabeledInput]) -> GeneratorReport:
    required = structural_requirements(spec) + clause_requirements(spec)
    return GeneratorReport(
        battery=list(battery),
        stress=list(stress),
        edge_gaps=coverage_gaps(required, battery),
        hot_path_gaps=hot_path_gaps(spec, stress),
    )


def assert_generator_covers(spec: SpecSheet, battery: Sequence[LabeledInput], stress: Sequence[LabeledInput]) -> None:
    """Fail-loud gate: raise unless every required edge and every hot path is
    exercised. Use to VALIDATE a model-written generator before trusting its
    inputs (and therefore the perf probe's verdict)."""
    report = check_generator(spec, battery, stress)
    if not report.covered:
        raise CoverageError(
            f"generator under-covers: edges {report.edge_gaps}; hot paths {report.hot_path_gaps}"
        )


# --- deterministic fallback generator ------------------------------------

_NUM_RE = re.compile(r"-?\d[\d,]*")


def _bound_extremes(bounds: str) -> tuple[Optional[int], Optional[int]]:
    """Best-effort (min, max) integers parsed from a bounds string."""
    nums = [int(m.group(0).replace(",", "")) for m in _NUM_RE.finditer(bounds)]
    if not nums:
        return None, None
    return min(nums), max(nums)


def _default_for(kind: str) -> Any:
    return {"list": [], "str": "", "int": 0}.get(kind, None)


def deterministic_battery(spec: SpecSheet) -> list[LabeledInput]:
    """Offline spec-driven battery for python entrypoints: empties, singletons,
    and each bounded int parameter at its extremes. Every input is a full
    positional-args list, labelled with the edge it exercises. This is the
    fallback until the model generator lands; it covers structural edges, not
    arbitrary prose clauses."""
    if spec.language != "python" or not spec.params:
        return []

    base = [_default_for(p.type) for p in spec.params]
    out: list[LabeledInput] = []

    if any(p.type == "list" for p in spec.params):
        empty = list(base)  # lists already default to []
        out.append(LabeledInput(value=empty, label="empty"))
        singleton = list(base)
        for i, p in enumerate(spec.params):
            if p.type == "list":
                singleton[i] = [1]
        out.append(LabeledInput(value=singleton, label="singleton"))

    for i, p in enumerate(spec.params):
        if not p.bounds:
            continue
        lo, hi = _bound_extremes(p.bounds)
        if lo is not None:
            args = list(base)
            args[i] = lo
            out.append(LabeledInput(value=args, label=f"{p.name}@min"))
        if hi is not None:
            args = list(base)
            args[i] = hi
            out.append(LabeledInput(value=args, label=f"{p.name}@max"))
    return out


def battery_values(battery: Sequence[LabeledInput]) -> list[Any]:
    """The raw inputs, for feeding verify()'s ``inputs``."""
    return [li.value for li in battery]
