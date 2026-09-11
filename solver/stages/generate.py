"""generate(SpecSheet, n) -> [Candidate].

STUB: emits ``n`` placeholder candidates that are guaranteed to run without
crashing, so the best-so-far-on-disk invariant holds from the very first stage.
They are NOT real solutions. Real candidate generation (prompting, strategy
selection, trap handling) is a separate workstream that plugs into this exact
signature and returns the same Candidate shape.
"""

from __future__ import annotations

from ..contracts import PYTHON, RUST, Candidate, SpecSheet

_PY_STUB = '''\
def {entrypoint}(*args, **kwargs):
    # SPINE STUB - not a real solution. It runs without crashing so a best-so-far
    # solution always exists on disk. The generation workstream replaces this.
    return None
'''

_RUST_STUB = '''\
use std::io::Read;

fn main() {
    // SPINE STUB - not a real solution. Consumes stdin and exits cleanly so a
    // best-so-far solution always exists on disk. Replaced by the generation
    // workstream.
    let mut input = String::new();
    let _ = std::io::stdin().read_to_string(&mut input);
}
'''


def generate(spec: SpecSheet, n: int = 1) -> list[Candidate]:
    n = max(1, int(n))
    if spec.language == PYTHON:
        source = _PY_STUB.format(entrypoint=spec.entrypoint)
    elif spec.language == RUST:
        source = _RUST_STUB
    else:  # pragma: no cover - Problem.from_dict already rejects other languages
        source = ""

    return [
        Candidate(
            id=f"stub-{i}",
            language=spec.language,
            source=source,
            origin="stub",
            meta={"note": "spine placeholder", "index": i},
        )
        for i in range(n)
    ]
