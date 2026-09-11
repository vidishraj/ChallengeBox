"""analyse(statement, problem) -> SpecSheet.

Deterministic structured reading of a problem statement. It does NOT understand
the problem; it mines the prose for the pieces verify() can act on:

* the entrypoint signature and per-parameter domains / bounds,
* stated invariants (candidate runtime / output assertions),
* edge-case ("trap") clauses that override an earlier rule,
* the output contract and the canonical-form clauses within it (sorted /
  maximal / lexicographic / input-order / distinct), which become verify()
  property assertions so a formatting difference is not misread as a wrong answer.

Extraction is best-effort and regex/keyword driven: a missed clause degrades the
signal, it does not corrupt it. The bounds DIFF (inputs bounded vs derived
quantity huge) is a separate, heavier piece and is not done here.
"""

from __future__ import annotations

import re

from ..contracts import ParamDomain, Problem, SpecSheet
from ..policy import policy_for

# An explicit signature line:  Define `simulate_writes(a, b, c)`.
_SIG_RE = re.compile(r"`([A-Za-z_]\w*)\s*\(([^)]*)\)`")

# `[a, b]` inclusive-range bounds (numbers or symbolic names like level_cap).
_BRACKET_RANGE_RE = re.compile(r"\[\s*(-?[\w]+)\s*,\s*(-?[\w]+)\s*\]")

# Chained inequalities: `1 <= N,Q <= 500000` or `0 <= p < current_length`.
_CHAIN_INEQ_RE = re.compile(
    r"(-?[\w,]+)\s*(<=|<)\s*([A-Za-z_]\w*(?:\s*,\s*[A-Za-z_]\w*)*)\s*(<=|<)\s*([\w()\-]+)"
)

# Markers that flag a segment as each kind of clause. Kept as data so they are
# cheap to extend; none of these are load-bearing individually.
_INVARIANT_MARKERS = (
    "always",
    "never",
    "guaranteed",
    "invariant",
    "pairwise distinct",
    "distinct",
    "unique",
    "at most one",
    "exactly one",
    "is valid",
    "every input is valid",
)
_EDGE_MARKERS = (
    "even if",
    "even when",
    "unless",
    "except",
    "if none",
    "otherwise",
    "implicitly",
    "stop before",
    "never split",
    "never sent",
    "no boundary",
    "there is a boundary",
    "disregard",
    "does nothing",
    "reused",
    "before that",
    "the final",
    "the last",
    "empty",
)
_OUTPUT_MARKERS = ("return", "output:", "prints", "print ", "resolve", "answer")
# Canonical-form clauses: a non-canonical but numerically correct answer scores 0.
# STRONG markers name a canonical form outright and qualify anywhere. WEAK
# markers (ordering / distinctness words) also describe input domains, so they
# only qualify when the segment is itself output-related, else they pull
# input-domain sentences into the output properties.
_CANONICAL_STRONG = (
    "canonical",
    "maximal",
    "lexicograph",
    "cannot be combined",
    "normalis",
    "normaliz",
    "sorted",
)
_CANONICAL_WEAK = (
    "increasing order",
    "decreasing order",
    "input order",
    "in order",
    "ascending",
    "descending",
    "distinct",
)
# Type hints from prose, longest match first.
_TYPE_HINTS = (
    ("list", ("list of", "sequence of", "list ", "sequence ", "array of")),
    ("str", ("string", "text", "characters", "utf-8", "identifier")),
    ("int", ("integer", "count", "index", "number of", "nonnegative", "positive", "64-bit")),
)


def _segments(statement: str) -> list[str]:
    """Split a statement into trimmed clause-sized segments: bullet items and
    sentences. Markdown bullets and headers are stripped; backticks are kept so
    symbolic names survive."""
    out: list[str] = []
    for raw_line in statement.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        line = re.sub(r"^[#>\-\*\+]+\s*", "", line)  # bullet / header markers
        line = re.sub(r"^\d+\.\s+", "", line)  # ordered-list markers
        if not line:
            continue
        # Split into sentences on ". " while keeping decimals / abbreviations intact.
        parts = re.split(r"(?<=[.:;])\s+(?=[A-Z`\"'])", line)
        for part in parts:
            seg = part.strip()
            if seg:
                out.append(seg)
    return out


def _dedup(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for it in items:
        key = it.lower()
        if key not in seen:
            seen.add(key)
            out.append(it)
    return out


def _infer_type(context: str) -> str:
    low = context.lower()
    for typ, hints in _TYPE_HINTS:
        if any(h in low for h in hints):
            return typ
    return "unknown"


def _param_names(signature_args: str) -> list[str]:
    names: list[str] = []
    for chunk in signature_args.split(","):
        name = chunk.strip().split(":")[0].split("=")[0].strip()
        if re.fullmatch(r"[A-Za-z_]\w*", name):
            names.append(name)
    return names


def _bounds_for(name: str, segments: list[str]) -> ParamDomain:
    """Best-effort domain for one parameter by scanning segments that mention it."""
    type_ctx: list[str] = []
    bounds: list[str] = []
    notes: list[str] = []
    name_re = re.compile(rf"\b{re.escape(name)}\b")

    for seg in segments:
        # Match on a backtick-stripped copy: ranges are written `[0, cap]` and a
        # backtick between "in" and "[" would otherwise hide the bracket.
        s = seg.replace("`", " ")
        if not name_re.search(s):
            continue
        type_ctx.append(seg)
        # A chained inequality naming this param, e.g. `1 <= n <= 5e5`.
        for m in _CHAIN_INEQ_RE.finditer(s):
            named = [n.strip() for n in m.group(3).split(",")]
            if name in named:
                bounds.append(f"{m.group(1)} {m.group(2)} {name} {m.group(4)} {m.group(5)}")
        # `[a, b]` range: a sentence can carry several brackets for several
        # subjects. Grammatically the subject precedes its range ("X is in
        # [a, b]"), so attach the bracket with the smallest gap to a PRECEDING
        # mention of this name; fall back to nearest absolute if none precede.
        positions = [mm.start() for mm in name_re.finditer(s)]
        best = None
        best_gap = None
        for bm in _BRACKET_RANGE_RE.finditer(s):
            preceding = [p for p in positions if p <= bm.start()]
            if not preceding:
                continue
            gap = bm.start() - max(preceding)
            if best_gap is None or gap < best_gap:
                best_gap, best = gap, bm
        if best is None:
            for bm in _BRACKET_RANGE_RE.finditer(s):
                dist = min(abs(bm.start() - p) for p in positions)
                if best_gap is None or dist < best_gap:
                    best_gap, best = dist, bm
        if best is not None:
            bounds.append(f"in [{best.group(1)}, {best.group(2)}]")
        low = s.lower()
        for word in ("positive", "nonnegative", "non-negative", "nonempty", "non-empty", "distinct", "unique"):
            if word in low:
                notes.append(word)

    return ParamDomain(
        name=name,
        type=_infer_type(" ".join(type_ctx)) if type_ctx else "unknown",
        bounds="; ".join(_dedup(bounds)) or None,
        notes="; ".join(_dedup(notes)),
    )


def _matching(segments: list[str], markers: tuple[str, ...]) -> list[str]:
    out = [seg for seg in segments if any(mk in seg.lower() for mk in markers)]
    return _dedup(out)


def _output_properties(segments: list[str]) -> list[str]:
    """Canonical-form clauses on the ANSWER. Strong markers (canonical, maximal,
    lexicographic, sorted, ...) qualify anywhere; weak ordering/distinctness
    markers also describe input domains, so they qualify only when the segment is
    itself output-related."""
    out: list[str] = []
    for seg in segments:
        # Match against prose only: backticked code spans carry identifiers (a
        # function named normalize_* would otherwise match the "normaliz" marker).
        prose = re.sub(r"`[^`]*`", " ", seg).lower()
        if any(mk in prose for mk in _CANONICAL_STRONG):
            out.append(seg)
        elif any(mk in prose for mk in _CANONICAL_WEAK) and any(om in prose for om in _OUTPUT_MARKERS):
            out.append(seg)
    return _dedup(out)


def _output_contract(segments: list[str]) -> str:
    """First sentence that states what to return / output, plus its neighbours."""
    for seg in segments:
        low = seg.lower()
        if low.startswith("return") or low.startswith("output") or "return one" in low or "prints" in low:
            return seg
    hits = _matching(segments, _OUTPUT_MARKERS)
    return hits[0] if hits else ""


def analyse(statement: str, problem: Problem) -> SpecSheet:
    segments = _segments(statement)

    # --- signature + parameter domains ---
    signature = ""
    params: list[ParamDomain] = []
    m = _SIG_RE.search(statement)
    if m and m.group(1) == problem.entrypoint:
        signature = f"{m.group(1)}({m.group(2)})"
        params = [_bounds_for(n, segments) for n in _param_names(m.group(2))]
    elif problem.entrypoint != "main":
        signature = f"{problem.entrypoint}(...)"

    # --- clause mining ---
    invariants = _matching(segments, _INVARIANT_MARKERS)
    edge_cases = _matching(segments, _EDGE_MARKERS)
    output_contract = _output_contract(segments)
    output_properties = _output_properties(segments)

    return SpecSheet(
        entrypoint=problem.entrypoint,
        language=problem.language,
        signature=signature,
        params=params,
        invariants=invariants,
        edge_cases=edge_cases,
        output_contract=output_contract,
        output_properties=output_properties,
        bounds_diff=None,  # filled by the bounds-diff piece
        target=policy_for(problem.language),
        raw_statement=statement,
    )
