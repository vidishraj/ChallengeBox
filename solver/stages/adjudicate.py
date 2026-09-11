"""adjudicate(disagreements) -> Candidate.

STUB: when verification finds candidates that disagree on some input, something
must pick the winner. Real adjudication (majority vote, targeted re-verification,
tie-breaking by cost) is a later workstream. Here we simply return the first
disagreeing candidate, or None when there is nothing to adjudicate.
"""

from __future__ import annotations

from typing import Optional, Sequence

from ..contracts import Candidate


def adjudicate(disagreements: Sequence[Candidate]) -> Optional[Candidate]:
    return disagreements[0] if disagreements else None
