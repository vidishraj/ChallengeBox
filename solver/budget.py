"""Wall-clock time budget and the best-so-far-on-disk invariant.

Two small objects every stage consults:

* :class:`TimeBudget` tracks elapsed time against ``deadline_s`` measured from
  process start and exposes :meth:`remaining`.
* :class:`BestSoFar` guarantees there is ALWAYS a solution file on disk: the
  moment any candidate runs without crashing it is written out, and later stages
  overwrite it only with something verified better. A wrong answer and no answer
  both score zero, so we never fail closed.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .contracts import Candidate


class TimeBudget:
    """Hard wall-clock budget measured from a fixed start instant.

    ``start`` should be captured as early as possible (process start). The clock
    uses ``time.monotonic`` so it is immune to system-clock adjustments.
    """

    def __init__(self, deadline_s: float, start: Optional[float] = None) -> None:
        self.deadline_s = float(deadline_s)
        self._start = time.monotonic() if start is None else float(start)

    @property
    def start(self) -> float:
        return self._start

    def elapsed(self) -> float:
        return time.monotonic() - self._start

    def remaining(self) -> float:
        """Seconds left before the deadline (never negative)."""
        return max(0.0, self.deadline_s - self.elapsed())

    def expired(self) -> bool:
        return self.remaining() <= 0.0

    def fraction_used(self) -> float:
        if self.deadline_s <= 0:
            return 1.0
        return min(1.0, self.elapsed() / self.deadline_s)

    def slice_for(self, fraction: float, cap: Optional[float] = None) -> float:
        """A sub-budget (seconds) sized as ``fraction`` of what remains, so a
        single stage can bound its own work. Optionally capped."""
        budget = self.remaining() * max(0.0, min(1.0, fraction))
        if cap is not None:
            budget = min(budget, cap)
        return budget


@dataclass
class _Held:
    candidate: Candidate
    verified: bool


class BestSoFar:
    """Owns the on-disk solution file and enforces the never-fail-closed rule.

    * :meth:`offer` — accept a candidate that merely RAN. It is written only if
      nothing is on disk yet (first runnable wins the slot).
    * :meth:`commit` — accept a VERIFIED-better candidate. It always overwrites.

    Writes are atomic (temp file + ``os.replace``) so a reader never sees a
    half-written solution.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._held: Optional[_Held] = None

    @property
    def has_solution(self) -> bool:
        return self._held is not None and self.path.exists()

    @property
    def current(self) -> Optional[Candidate]:
        return self._held.candidate if self._held else None

    def offer(self, candidate: Candidate) -> bool:
        """Write ``candidate`` iff there is no solution on disk yet. Returns
        whether it was written."""
        if self.has_solution:
            return False
        self._write(candidate, verified=False)
        return True

    def commit(self, candidate: Candidate) -> bool:
        """Write ``candidate`` as a verified improvement, overwriting whatever is
        there. Returns True."""
        self._write(candidate, verified=True)
        return True

    def _write(self, candidate: Candidate, verified: bool) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(candidate.source, encoding="utf-8")
        os.replace(tmp, self.path)
        self._held = _Held(candidate=candidate, verified=verified)
