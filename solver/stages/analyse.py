"""analyse(statement) -> SpecSheet.

STUB: returns a valid SpecSheet carrying the entrypoint, the language-target
policy, and the raw statement. It does NOT parse the prose — extracting input
domains, invariants, edge-case clauses and the output contract is the real
analysis workstream. The signature field is filled only if the statement states
it in the obvious ``Define `name(a, b, c)``` form, purely so downstream stubs
have a non-empty shape to look at.
"""

from __future__ import annotations

import re

from ..contracts import Problem, SpecSheet
from ..policy import policy_for

# Matches an explicit signature line like:  Define `simulate_writes(a, b, c)`.
_SIG_RE = re.compile(r"`([A-Za-z_]\w*)\s*\(([^)]*)\)`")


def analyse(statement: str, problem: Problem) -> SpecSheet:
    signature = ""
    m = _SIG_RE.search(statement)
    if m and m.group(1) == problem.entrypoint:
        signature = f"{m.group(1)}({m.group(2)})"
    elif problem.entrypoint != "main":
        signature = f"{problem.entrypoint}(...)"

    return SpecSheet(
        entrypoint=problem.entrypoint,
        language=problem.language,
        signature=signature,
        params=[],  # real analyser fills input domains + bounds
        invariants=[],
        edge_cases=[],
        output_contract="",  # real analyser fills the return/output contract
        target=policy_for(problem.language),
        raw_statement=statement,
    )
