"""Typed data contracts shared across every pipeline stage.

These shapes are the interface two further workstreams (real analysis /
generation / verification) will build against, so they are deliberately explicit
even while the stage behaviour is stubbed. Nothing here contains logic beyond
parsing and validation of the problem input.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional

# --- languages -----------------------------------------------------------

PYTHON = "python"
RUST = "rust"
SUPPORTED_LANGUAGES = (PYTHON, RUST)

#: File extension per language, used when writing a solution to disk.
LANG_EXT = {PYTHON: "py", RUST: "rs"}


# --- problem input -------------------------------------------------------


@dataclass(frozen=True)
class Problem:
    """A parsed problem JSON.

    Mirrors the input schema exactly:
    ``{problem_id, language, statement, entrypoint, public_examples, deadline_s}``.
    """

    problem_id: str
    language: str
    statement: str
    entrypoint: str
    public_examples: list[Any]
    deadline_s: float

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "Problem":
        missing = [
            k
            for k in ("problem_id", "language", "statement", "entrypoint", "deadline_s")
            if k not in data
        ]
        if missing:
            raise ValueError(f"problem JSON missing required fields: {missing}")

        language = str(data["language"]).strip().lower()
        if language not in SUPPORTED_LANGUAGES:
            raise ValueError(f"unsupported language {language!r}; expected one of {SUPPORTED_LANGUAGES}")

        deadline_s = float(data["deadline_s"])
        if deadline_s <= 0:
            raise ValueError(f"deadline_s must be positive, got {deadline_s}")

        examples = data.get("public_examples") or []
        if not isinstance(examples, list):
            raise ValueError("public_examples must be a list")

        return Problem(
            problem_id=str(data["problem_id"]),
            language=language,
            statement=str(data["statement"]),
            entrypoint=str(data["entrypoint"]),
            public_examples=list(examples),
            deadline_s=deadline_s,
        )

    @staticmethod
    def load(path: str | Path) -> "Problem":
        raw = Path(path).read_text(encoding="utf-8")
        return Problem.from_dict(json.loads(raw))

    @property
    def ext(self) -> str:
        return LANG_EXT[self.language]


# --- spec sheet (analyse output) -----------------------------------------


@dataclass
class ParamDomain:
    """One entrypoint parameter with its (best-effort) domain and bounds."""

    name: str
    type: str = "unknown"  # e.g. "int" | "list" | "str"; best-effort
    bounds: Optional[str] = None  # e.g. "1..65535" or prose; None if unknown
    notes: str = ""


@dataclass
class TargetPolicy:
    """Language-target constraints candidate generation must honour.

    The grader's toolchain version is unknown, so we deliberately target the
    lowest common denominator: code valid on the older toolchain runs on newer,
    not vice-versa. Carried on the SpecSheet so the constraint is structural, not
    remembered.
    """

    language: str
    python_min: Optional[str] = None  # e.g. "3.9" — generate/verify pin to this
    forbidden_features: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


@dataclass
class HotPathQuantity:
    """A derived quantity that is large or unbounded while its inputs stay small.

    The core trap pattern: inputs are bounded to friendly sizes but a quantity
    the described PROCESS produces (an iteration count, an accumulation, a span, a
    repetition) is huge or unbounded and is NOT itself an input bound. Sizing an
    algorithm to the input bound then passes every small input and scores zero on
    the hidden maximum. Each flag carries the sentence that creates it and a
    taxonomy tag, and feeds verify()'s performance probe as a specific target.
    """

    quantity: str  # short name, e.g. "spin cost per packet", "combined reversed length"
    source_sentence: str  # the statement sentence that creates it
    magnitude: str = ""  # bound hint, e.g. "~1e18", "unbounded"
    category: str = ""  # taxonomy tag, e.g. "counter-not-a-loop" (see policy registry)
    why: str = ""  # short reason it can explode


@dataclass
class EnumerationHint:
    """An EXPLICIT bound on a derived quantity, read as an instruction for WHAT
    TO ENUMERATE. "The number of maximal surviving rectangles is at most 150000"
    is not merely a flag; it tells you the intended object and its scale, i.e.
    the algorithm. This is the PRIMARY output of the bounds diff."""

    quantity: str  # the object to enumerate, e.g. "maximal surviving rectangles"
    bound: str  # the explicit bound, e.g. "150000"
    source_sentence: str
    note: str = ""


@dataclass
class Residue:
    """Trap-shaped structure that matches NOTHING in the known catalogue.

    The catalogue is not converged (the richness curve is still climbing), so a
    closed classifier would return a confident "no trap" on the category it has
    never seen — a check that cannot fire on the case it most needs to catch.
    The residue channel makes a miss EXPECTED: unexplained bounds, derived
    quantities no category accounts for, override clauses fitting no known
    pattern. A residue entry is a lead for a human / downstream, not a verdict."""

    description: str  # what looks trap-shaped
    source_sentence: str
    why: str = ""


# BoundsDiff.status values. "clear" and "unmatched"/"not-run" are DELIBERATELY
# distinct: an empty result and a verified-empty result look identical unless
# made different, and a negative "no trap" verdict must rest on positive
# evidence, not on the mere absence of a catalogue match.
SCAN_NOT_RUN = "not-run"  # detector did not run
SCAN_TRAPS_FOUND = "traps-found"  # at least one enumeration hint or hot path
SCAN_CLEAR_VERIFIED = "clear-verified"  # ran, derived quantities enumerated, each accounted for by a bound
SCAN_INCONCLUSIVE = "inconclusive"  # ran, but could not establish either (NOT the same as clear)


@dataclass
class BoundsDiff:
    """analyse()'s bounds subtraction: what the inputs bound vs what the process
    can produce. Open-world by design — a classifier over the known catalogue
    PLUS a residue channel for the unmatched.

    Primary output is ``enumeration_hints`` (explicit derived bounds = algorithm
    hints); ``hot_paths`` is the secondary flag (large/unbounded & unaccounted);
    ``residue`` is the anomaly channel; ``status`` distinguishes verified-clear
    from not-run / inconclusive."""

    input_bounds: list[str] = field(default_factory=list)  # bounded input quantities + bounds
    derived_quantities: list[str] = field(default_factory=list)  # quantities the process produces
    enumeration_hints: list[EnumerationHint] = field(default_factory=list)  # PRIMARY: explicit derived bounds
    hot_paths: list[HotPathQuantity] = field(default_factory=list)  # SECONDARY: large/unbounded & unaccounted
    residue: list[Residue] = field(default_factory=list)  # open-world: trap-shaped but unmatched
    status: str = SCAN_NOT_RUN  # one of SCAN_* above

    @property
    def residue_fired(self) -> bool:
        """Runlog metric: did the anomaly channel surface anything on this
        problem. Feeds the held-out coverage claim (K consecutive problems with
        no residue before coverage is asserted)."""
        return bool(self.residue)


@dataclass
class SpecSheet:
    """Structured reading of a statement — the analyse() output.

    Populated trivially by the stub; the real analyser fills every field.
    """

    entrypoint: str
    language: str
    signature: str = ""  # reconstructed call signature, best-effort
    params: list[ParamDomain] = field(default_factory=list)  # input domains + bounds
    invariants: list[str] = field(default_factory=list)  # stated invariants
    edge_cases: list[str] = field(default_factory=list)  # trap / edge-case clauses
    output_contract: str = ""  # what the return value / stdout must be (prose)
    output_properties: list[str] = field(default_factory=list)  # checkable canonical-form
    # clauses (sorted / maximal / lexicographic / input-order / distinct ...). A
    # non-canonical but numerically correct answer scores zero, and two correct
    # candidates can differ only in form; these become verify() property
    # assertions so a form difference is not misread as a value disagreement.
    bounds_diff: Optional[BoundsDiff] = None  # input-vs-derived bounds; hot paths for the perf probe
    target: Optional[TargetPolicy] = None  # language-target constraints
    raw_statement: str = ""


# --- candidates (generate output) ----------------------------------------


@dataclass
class Candidate:
    """A proposed solution's source, plus provenance."""

    id: str
    language: str
    source: str
    origin: str = "stub"  # which strategy produced it
    meta: dict[str, Any] = field(default_factory=dict)


# --- sandbox execution results -------------------------------------------


class ExecStatus(str, Enum):
    """Structured outcome of running a candidate in the sandbox."""

    OK = "ok"
    WRONG_SHAPE = "wrong-shape"  # ran, but didn't define/return the required shape
    CRASHED = "crashed"  # raised / non-zero exit
    TIMED_OUT = "timed-out"
    COMPILE_ERROR = "compile-error"  # syntax error / rustc failure / rustc absent
    OVERFLOWED = "overflowed"  # rust integer overflow (checked build) — silent wrap otherwise


@dataclass
class ExecResult:
    status: ExecStatus
    value: Any = None  # entrypoint return (python) or stdout (rust) when OK
    stdout: str = ""
    stderr: str = ""
    error: str = ""  # human-readable failure detail
    duration_s: float = 0.0

    @property
    def ran_ok(self) -> bool:
        """True when the candidate executed without crashing — the bar for
        becoming the best-so-far on disk."""
        return self.status == ExecStatus.OK


# --- verdicts (verify / adjudicate) --------------------------------------


@dataclass
class Verdict:
    candidate_id: str
    passed: bool
    detail: str = ""
    exec_result: Optional[ExecResult] = None
    # Performance probe result (set by verify()'s perf probe; consumed by the
    # generation side for cheap-path vs escalation decisions). Agreement says
    # nothing about speed, and a correct-but-slow candidate scores zero.
    perf_ok: Optional[bool] = None  # None = not probed; True/False = cleared max-size within limits
    max_input_duration_s: float = 0.0  # measured wall-clock at max size (logging / thresholds)


@dataclass
class Disagreement:
    """A concrete divergence between candidates on one input, everything
    adjudicate() needs to resolve it: the failing input, each candidate's output
    on it, the divergent candidates, and (if verify localised it) the contended
    spec clause."""

    failing_input: Any  # the concrete input the candidates diverged on
    outputs: dict[str, Any]  # candidate_id -> output on that input (see below)
    candidates: list[Candidate]  # the divergent candidates (>= 2)
    clause_hint: str = ""  # relevant spec sentence(s) if verify localised; else ""
    seed: Optional[int] = None  # RNG seed that produced failing_input (repro; input may be huge)
    kind: str = "value"  # see below: "value" | "status" | "form" | "clause"
    canonical_hint: str = ""  # for kind == "form": the canonical-form clause(s) to normalise by
    # kind semantics:
    #   "value"  differing returns that stay different after canonical-form
    #            normalisation — a genuine correctness divergence.
    #   "status" one candidate ran, another crashed/timed-out/overflowed;
    #            outputs[cid] is the string tag "<crashed>"/"<timed-out>"/"<overflowed>".
    #   "form"   returns differ RAW but agree once normalised by the extracted
    #            canonical form (two correct candidates, different normalisation).
    #            canonical_hint carries the clause so adjudicate() can
    #            normalise-and-recompare instead of spending a model call.
    #   "clause" ambiguity triage: two explicit READINGS of a contended clause,
    #            emitted as candidates and run on a discriminating input; can fire
    #            even when the shipped candidates all agree. REQUIRES both
    #            failing_input (the discriminating input) and clause_hint (the
    #            contended sentence) — a clause flag with no discriminating input
    #            is not a finding and MUST be dropped upstream, never emitted.
    # outputs[cid] is the return value (python) / stdout (rust) when the candidate
    # ran OK, else the status tag above.


@dataclass
class VerdictReport:
    """Result of verify(): per-candidate verdicts, a chosen best, and any
    disagreements for adjudicate() to resolve."""

    verdicts: list[Verdict] = field(default_factory=list)
    best: Optional[Candidate] = None
    disagreements: list[Disagreement] = field(default_factory=list)
