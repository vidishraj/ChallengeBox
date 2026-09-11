"""Bounds-diff detector: the trap thesis, made structural.

The consequential trap in this corpus is one shape: the statement bounds the
INPUTS to friendly sizes while leaving a DERIVED quantity (an iteration count, an
accumulation, a span, a repetition) huge or unbounded. Size an algorithm to the
input bound, simulate naively, and you are correct on every small input and score
zero on the hidden maximum.

Two first-class outputs, in priority order:

1. ENUMERATION HINTS (primary). An EXPLICIT bound on a derived quantity ("at most
   150000 maximal surviving rectangles") is an algorithm instruction: it names
   the object to enumerate and its scale. This turns the detector from a warning
   system into a solution hint.
2. HOT PATHS (secondary). A derived quantity that is large or unbounded and is
   NOT accounted for by any stated input bound. This is what verify()'s
   performance probe must aim at.

OPEN-WORLD by construction. The category catalogue is not converged (the richness
curve is still climbing across the corpus), so this is a classifier over the
known categories PLUS a residue channel for structure that looks trap-shaped and
matches nothing. A miss is EXPECTED, not a failure; a closed classifier would
return a confident "no trap" on the one category it has never seen.

And the negative verdict is EARNED: "clear-verified" requires positive evidence
(derived quantities were enumerated and each is accounted for by a stated bound),
and is a DIFFERENT status value from "not-run" / "inconclusive".
"""

from __future__ import annotations

import re

from .contracts import (
    SCAN_CLEAR_VERIFIED,
    SCAN_INCONCLUSIVE,
    SCAN_TRAPS_FOUND,
    BoundsDiff,
    EnumerationHint,
    HotPathQuantity,
    Residue,
)

# --- category registry (DATA, extensible) --------------------------------
#
# (name, one-line description, cue substrings). Cues CLASSIFY an already-detected
# quantity; they do not detect it — detection is generic so an unknown category
# still surfaces via the residue channel. The catalogue is expected to grow; add
# rows here, do not thread category names through the logic.
TRAP_CATEGORIES: list[tuple[str, str, tuple[str, ...]]] = [
    ("counter-not-a-loop", "a stated count is a value to compute in O(1), not a loop to run",
     ("iteration", "iterations", "spin", "spins", "repeats", "performs", "times", "steps",
      "retries", "retry", "demand", "run count", "run counts", "k units")),
    ("unbounded-derived-aggregate", "a sum/accumulation the process builds has no input-sized bound",
     ("sum of", "total number", "accumulat", "combined", "aggregate", "grand total")),
    ("order-of-operations-within-a-step", "sub-steps inside one operation have a mandated order",
     ("in this order", "resolve", "after all preceding", "before this", "then write", "first to last")),
    ("before-after-off-by-one-on-commit", "a value is read/remembered before a commit boundary",
     ("remember", "remembered", "before", "after", "commit", "append the")),
    ("masked-snapshot-clauses", "a remembered value survives later mutation of the same cell",
     ("snapshot", "masked", "even if another", "later changed", "remembered value")),
    ("implicit-or-infinite-tails", "an implicit tail extends behaviour past the enumerated input",
     ("implicitly", "every later", "after all", "exhausted", "no bound", "unbounded", "no limit", "infinite")),
    ("identity-versus-position", "identity (id) and position (index) must not be conflated",
     ("identifier", "identifiers", "position", "index", "attached to the same", "same identifier")),
    ("numeric-domain-and-overflow", "a value's magnitude exceeds a narrow integer type",
     ("64-bit", "signed", "exceeds", "overflow", "10^", "1e1", "1e2", "1e3", "u128", "i128")),
    ("canonical-form-output", "the answer must be a uniquely-normalised shape",
     ("canonical", "maximal", "lexicograph", "cannot be combined", "normalis", "normaliz")),
    ("ordered-rule-priority", "overlapping predicates resolved by rule order, not OR",
     ("first matching rule", "rule order", "apply the first", "first matching", "authoritative")),
    ("context-sensitive-look-back", "a decision depends on a variable-length backward scan",
     ("consecutive", "parity", "nearest", "skipping", "preceding", "ending at", "look back", "look-back")),
    ("persistent-or-branching-version-state", "versions branch from earlier ones; needs confluent persistence",
     ("earlier version", "versions may", "may branch", "persistent", "from an earlier", "ancestry", "version i")),
    ("exponential-unfolding-of-shared-dag", "a shared DAG unfolds exponentially; DP over the folded form",
     ("complete unfolding", "unfolding into a tree", "unfolding", "multiple incoming", "folded", "directed acyclic")),
]

# A large magnitude that bounds a stored VALUE (an integer a cell holds, an
# identifier) is a numeric-WIDTH concern (use i128), NOT a scaling trap. Only a
# magnitude on a COUNT / demand / aggregate / span drives complexity. Keeping
# these apart stops a generous problem (patchboard: attributes in 1..=10^9) from
# reading as a scaling trap and telling the generator to over-engineer.
_VALUE_DOMAIN_CUES = (
    "attribute", "attributes", "identifier", "identifiers", "value", "values",
    "stored", "cell", "64-bit", "signed", "the integer",
)
_SCALING_CUES = (
    "count", "counts", "number of", "iteration", "iterations", "times", "retries",
    "retry", "demand", "spin", "spins", "operations", "length", "sum", "total",
    "repeat", "repetition", "span", "spans", "reach", "reaches", "exceeds",
)

# Subjects that mark an "at most N X" as a DERIVED quantity (what to enumerate)
# rather than an input size.
_DERIVED_SUBJECT_CUES = (
    "maximal", "surviving", "candidate", "distinct", "resulting", "produced",
    "generated", "reachable", "combined", "intermediate", "total", "possible",
)

# --- number magnitudes ---------------------------------------------------

_MAG_PATTERNS = [
    (re.compile(r"10\s*\^\s*(\d+)"), lambda m: 10 ** int(m.group(1))),
    (re.compile(r"10\*\*(\d+)"), lambda m: 10 ** int(m.group(1))),
    (re.compile(r"(\d+(?:\.\d+)?)\s*[eE]\s*(\d+)"), lambda m: float(m.group(1)) * 10 ** int(m.group(2))),
    (re.compile(r"\b(\d{1,3}(?:,\d{3})+)\b"), lambda m: int(m.group(1).replace(",", ""))),
    (re.compile(r"\b(\d{7,})\b"), lambda m: int(m.group(1))),
]

# A magnitude at or above this is "large": it comfortably clears typical input
# sizes (<= a few 1e5-1e6) so it flags values/demands/counts, not input bounds.
_LARGE = 1_000_000_000  # 1e9


def _max_magnitude(text: str) -> tuple[float, str]:
    best = 0.0
    best_str = ""
    for pat, conv in _MAG_PATTERNS:
        for m in pat.finditer(text):
            try:
                val = float(conv(m))
            except (ValueError, OverflowError):
                continue
            if val > best:
                best, best_str = val, m.group(0)
    return best, best_str


def classify(sentence: str) -> str:
    """Best-matching known category for a sentence, or "" if none match."""
    low = sentence.lower()
    for name, _desc, cues in TRAP_CATEGORIES:
        if any(cue in low for cue in cues):
            return name
    return ""


def _sentences(statement: str) -> list[str]:
    out: list[str] = []
    for raw in statement.splitlines():
        line = re.sub(r"^[#>\-\*\+\s]+", "", raw).strip()
        if not line:
            continue
        for part in re.split(r"(?<=[.;:])\s+(?=[A-Z`\"'\d])", line):
            part = part.strip()
            if part:
                out.append(part)
    return out


# --- extraction ----------------------------------------------------------

_AT_MOST_RE = re.compile(
    r"(?:at most|no more than|up to)\s+([0-9][0-9,]*(?:\s*\^\s*\d+)?|\d+(?:\.\d+)?[eE]\d+)\s+([a-z][\w \-]{2,45})",
    re.IGNORECASE,
)
_NUMBER_OF_RE = re.compile(
    r"(?:the\s+)?number of ([a-z][\w \-]{2,45}?) is at most ([0-9][0-9,]*|\d+(?:\.\d+)?[eE]\d+|10\s*\^\s*\d+)",
    re.IGNORECASE,
)
# A chained inequality bounding one or more symbols: `1 <= N,Q <= 500000`.
# Captures modest bounds that the magnitude patterns (>= 7 digits / 10^k) miss,
# so a generously-bounded problem registers its input bounds and can earn a
# clear verdict.
_INEQ_RE = re.compile(
    r"(-?\d[\d,]*|[A-Za-z_]\w*)\s*(?:<=|<)\s*([A-Za-z_]\w*(?:\s*,\s*[A-Za-z_]\w*)*)\s*(?:<=|<)\s*([\w(),\^*]+)"
)
_BENIGN_DERIVED_RE = re.compile(
    r"\b(return|returns|the result|produce|produces|for each|compute|computes|output is)\b",
    re.IGNORECASE,
)
_UNBOUNDED_RE = re.compile(
    # word-boundaried so "no boundary" (a common grapheme-rule phrase) does NOT
    # match "no bound".
    r"(\bno bound\b|\bunbounded\b|\bno limit\b|arbitrarily large|may be enormous|\bno upper bound\b)",
    re.IGNORECASE,
)


def _is_derived_subject(subject: str) -> bool:
    low = subject.lower()
    return any(cue in low for cue in _DERIVED_SUBJECT_CUES)


def detect_bounds(statement: str) -> BoundsDiff:
    sentences = _sentences(statement)
    input_bounds: list[str] = []
    derived: list[str] = []
    enumeration_hints: list[EnumerationHint] = []
    hot_paths: list[HotPathQuantity] = []
    residue: list[Residue] = []

    def add_hot(quantity: str, sentence: str, magnitude: str, why: str) -> None:
        cat = classify(sentence)
        hot_paths.append(
            HotPathQuantity(quantity=quantity, source_sentence=sentence, magnitude=magnitude, category=cat, why=why)
        )
        if not cat:
            residue.append(Residue(description=f"unclassified hot path: {quantity}", source_sentence=sentence, why=why))

    for s in sentences:
        # 0. any chained inequality registers an input bound (does not consume the
        # sentence: it may ALSO carry a large magnitude that flags a hot path).
        for im in _INEQ_RE.finditer(s):
            input_bounds.append(f"{im.group(1)} <= {im.group(2)} <= {im.group(3)}")

        # 1. explicit "number of X is at most Y" -> the strongest enumeration hint.
        m = _NUMBER_OF_RE.search(s)
        if m:
            subject, bound = m.group(1).strip(), m.group(2).strip()
            enumeration_hints.append(EnumerationHint(quantity=subject, bound=bound, source_sentence=s))
            derived.append(subject)
            continue

        # 2. "at most N <subject>": derived subject -> enumeration hint; a LARGE
        # bound (>= 1e9) on any subject -> hot path (a count that can explode);
        # else a modest input bound.
        m = _AT_MOST_RE.search(s)
        if m:
            bound, subject = m.group(1).strip(), m.group(2).strip()
            bmag, _ = _max_magnitude(bound)
            if _is_derived_subject(subject):
                enumeration_hints.append(EnumerationHint(quantity=subject, bound=bound, source_sentence=s))
                derived.append(subject)
            elif bmag >= _LARGE:
                add_hot(quantity=subject, sentence=s, magnitude=bound, why="large 'at most' bound on a process quantity")
                derived.append(subject)
            else:
                input_bounds.append(f"at most {bound} {subject}")
            continue

        # 3. explicit unbounded derived quantity -> hot path (unbounded).
        if _UNBOUNDED_RE.search(s):
            add_hot(quantity=_subject_near_unbounded(s), sentence=s, magnitude="unbounded", why="stated to have no bound")
            derived.append(_subject_near_unbounded(s))
            continue

        # 4. large magnitude (>= 1e9). Whether it bounds an input symbol
        # (max_retries <= 10^18) or a process value (demand never exceeds 10^18),
        # a magnitude this size clears every plausible input SIZE, so it marks a
        # count / value / demand that the process can drive to explosion. This is
        # the flagship trap (a 10^18 bound on an iterated parameter is a counter,
        # not a loop), so flag it. classify() routes it to a category or residue.
        val, val_str = _max_magnitude(s)
        if val >= _LARGE:
            low = s.lower()
            is_value_domain = any(c in low for c in _VALUE_DOMAIN_CUES) and not any(c in low for c in _SCALING_CUES)
            if is_value_domain:
                # numeric WIDTH concern (use i128), not a complexity trap.
                input_bounds.append(f"numeric domain (width) {val_str}: {s[:70]}")
            else:
                add_hot(
                    quantity=_subject_of_magnitude(s),
                    sentence=s,
                    magnitude=val_str,
                    why="a bound/value at this magnitude drives a derived quantity past input scale",
                )
                derived.append(_subject_of_magnitude(s))
            continue
        if val > 0:
            # a modest explicit number: an input-side bound for the diff.
            input_bounds.append(s if len(s) < 90 else val_str)

        # 5. benign derived quantity: the process produces something, but nothing
        # above flagged it as exploding. Recording it is the POSITIVE EVIDENCE a
        # "clear-verified" verdict needs (we saw the process output and it did not
        # blow up), distinct from having scanned nothing.
        if _BENIGN_DERIVED_RE.search(s):
            derived.append(s if len(s) < 70 else s[:70])

    status = _verdict(input_bounds, derived, enumeration_hints, hot_paths, residue)
    return BoundsDiff(
        input_bounds=_dedup(input_bounds),
        derived_quantities=_dedup(derived),
        enumeration_hints=enumeration_hints,
        hot_paths=hot_paths,
        residue=residue,
        status=status,
    )


def _verdict(input_bounds, derived, enumeration_hints, hot_paths, residue) -> str:
    if hot_paths or enumeration_hints:
        return SCAN_TRAPS_FOUND
    # No trap signal. Earn a clear verdict with positive evidence: we DID find
    # input bounds and DID enumerate derived quantities, and nothing was
    # unbounded / unexplained. Otherwise it is inconclusive, NOT clear.
    if input_bounds and derived and not residue:
        return SCAN_CLEAR_VERIFIED
    return SCAN_INCONCLUSIVE


# --- subject heuristics (best-effort) ------------------------------------

def _subject_near_unbounded(sentence: str) -> str:
    m = re.search(r"(?:no bound on|unbounded)\s+(?:their\s+|the\s+)?([a-z][\w \-]{2,40})", sentence, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return sentence[:48].strip()


def _subject_of_magnitude(sentence: str) -> str:
    # The noun phrase before "never exceeds/reaches/up to <magnitude>".
    m = re.search(r"([a-z][\w \-]{2,40})\s+(?:never exceeds|exceeds|reaches|reach|up to|can reach)", sentence, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return sentence[:48].strip()


def _dedup(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for it in items:
        k = it.lower()
        if k not in seen:
            seen.add(k)
            out.append(it)
    return out
