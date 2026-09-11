"""ChallengeBox solver harness.

An end-to-end SPINE: load a problem JSON, run a staged pipeline
(analyse -> generate -> verify -> adjudicate), sandbox-execute candidates, and
always keep a best-so-far solution on disk within a hard wall-clock deadline.

The "clever" parts (spec parsing, candidate generation strategy, verification
without examples, input generators) are intentionally stubbed here so the
contracts exist and other workstreams can plug into them.
"""

from __future__ import annotations

__all__ = ["__version__"]

__version__ = "0.1.0"
