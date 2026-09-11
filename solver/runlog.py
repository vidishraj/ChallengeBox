"""Structured run log: every stage's timing and decisions.

Kept deliberately simple (a list of entries + a JSON dump) so it is useful both
for the write-up and for debugging the pipeline. Timings are wall-clock seconds
relative to the run's start.
"""

from __future__ import annotations

import json
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterator


@dataclass
class StageEntry:
    stage: str
    start_s: float  # relative to run start
    end_s: float
    duration_s: float
    decision: str = ""
    data: dict[str, Any] = field(default_factory=dict)


class RunLog:
    def __init__(self, problem_id: str, start: float | None = None) -> None:
        self.problem_id = problem_id
        self._start = time.monotonic() if start is None else start
        self.entries: list[StageEntry] = []
        self.events: list[dict[str, Any]] = []

    def _rel(self) -> float:
        return time.monotonic() - self._start

    def event(self, message: str, **data: Any) -> None:
        """Record a point-in-time note (not tied to a stage span)."""
        self.events.append({"at_s": round(self._rel(), 4), "message": message, **data})

    @contextmanager
    def stage(self, name: str) -> Iterator["StageRecord"]:
        """Time a stage; the yielded record collects its decision + data."""
        start = self._rel()
        rec = StageRecord()
        try:
            yield rec
        finally:
            end = self._rel()
            self.entries.append(
                StageEntry(
                    stage=name,
                    start_s=round(start, 4),
                    end_s=round(end, 4),
                    duration_s=round(end - start, 4),
                    decision=rec.decision,
                    data=rec.data,
                )
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "problem_id": self.problem_id,
            "total_s": round(self._rel(), 4),
            "stages": [asdict(e) for e in self.entries],
            "events": self.events,
        }

    def write(self, path: str | Path) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")

    def summary(self) -> str:
        lines = [f"run {self.problem_id}  total={self.to_dict()['total_s']}s"]
        for e in self.entries:
            tail = f"  -> {e.decision}" if e.decision else ""
            lines.append(f"  [{e.duration_s:7.3f}s] {e.stage}{tail}")
        return "\n".join(lines)


@dataclass
class StageRecord:
    """Handle a stage uses to attach its decision and structured data."""

    decision: str = ""
    data: dict[str, Any] = field(default_factory=dict)

    def note(self, decision: str, **data: Any) -> None:
        self.decision = decision
        self.data.update(data)
