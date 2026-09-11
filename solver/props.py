"""Output property checks and disagreement classification.

Two of the cheapest real signals in a no-oracle setting live here:

* PROPERTY ASSERTIONS on an output need no second candidate to be right, so
  they can catch a unanimous misreading. They must be CONSERVATIVE: only assert
  when the output shape unambiguously supports the check, else stay silent. A
  false assertion that fails a correct candidate is worse than no assertion.
* DISAGREEMENT CLASSIFICATION separates a genuine value divergence from a mere
  formatting/normalisation difference, so differential testing does not report a
  form difference as a wrong answer (two correct candidates can normalise
  differently) and adjudicate() can normalise-and-recompare without a model call.
"""

from __future__ import annotations

from typing import Any

# Output-property phrases that assert an ordering / distinctness on the ANSWER.
_SORTED_ASC = ("sorted", "increasing order", "ascending", "lexicograph")
_SORTED_DESC = ("decreasing order", "descending")
_DISTINCT = ("distinct", "unique", "cannot be combined", "maximal")


def _is_flat_scalar_list(value: Any) -> bool:
    return isinstance(value, (list, tuple)) and all(
        isinstance(x, (int, float, str)) and not isinstance(x, bool) for x in value
    )


def check_output_properties(value: Any, output_properties: list[str]) -> list[str]:
    """Return descriptions of any CONFIRMED output-property violations.

    Deliberately narrow: ordering and distinctness are only checked on a flat
    list of comparable scalars, where the check is unambiguous. Any richer shape
    is skipped (returns no violation) rather than guessed at."""
    if not output_properties or not _is_flat_scalar_list(value):
        return []

    joined = " ".join(output_properties).lower()
    violations: list[str] = []
    seq = list(value)

    if any(mk in joined for mk in _SORTED_ASC) and not _nondecreasing(seq):
        violations.append("output is not in nondecreasing order")
    if any(mk in joined for mk in _SORTED_DESC) and not _nonincreasing(seq):
        violations.append("output is not in nonincreasing order")
    if any(mk in joined for mk in _DISTINCT):
        try:
            if len(set(seq)) != len(seq):
                violations.append("output contains duplicate elements")
        except TypeError:
            pass
    return violations


def _nondecreasing(seq: list) -> bool:
    try:
        return all(seq[i] <= seq[i + 1] for i in range(len(seq) - 1))
    except TypeError:
        return True  # not order-comparable: cannot assert, so do not fail it


def _nonincreasing(seq: list) -> bool:
    try:
        return all(seq[i] >= seq[i + 1] for i in range(len(seq) - 1))
    except TypeError:
        return True


def canonicalize(value: Any) -> Any:
    """An order-insensitive, type-normalised form used only to decide whether two
    differing raw outputs are the SAME MULTISET arranged differently (a form
    difference) rather than genuinely different values."""
    if isinstance(value, (list, tuple)):
        items = [canonicalize(x) for x in value]
        try:
            return ("seq", tuple(sorted(items, key=repr)))
        except Exception:
            return ("seq", tuple(items))
    if isinstance(value, dict):
        return ("map", tuple(sorted(((canonicalize(k), canonicalize(v)) for k, v in value.items()), key=repr)))
    return value


def classify_value_disagreement(a: Any, b: Any) -> str:
    """Two OK outputs that are not raw-equal: "form" if they agree once
    normalised (same multiset, different arrangement/type), else "value"."""
    try:
        if canonicalize(a) == canonicalize(b):
            return "form"
    except Exception:
        pass
    return "value"
