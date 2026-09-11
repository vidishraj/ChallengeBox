"""Pipeline stages.

Every stage here is a TRIVIAL STUB that returns a valid, typed object. The
shapes are the contract two further workstreams build against; the behaviour is
intentionally not clever yet.
"""

from __future__ import annotations

from .analyse import analyse
from .generate import generate
from .verify import verify
from .adjudicate import adjudicate

__all__ = ["analyse", "generate", "verify", "adjudicate"]
