"""Clause-ambiguity triage (prepared against the LLM seam).

The bounds diff catches SCALING traps; the traps it cannot see are SEMANTIC - a
clause read two ways, where the fast candidate and a cross-check can share the
same misreading and agree confidently on the wrong answer. This attacks that
residue, in the one shape that is reliable (per trap-log 06):

Per clause the model flags as possibly ambiguous, emit (a) two candidate
READINGS as runnable programs, (b) a concrete input that DISCRIMINATES them.
Run both readings on that input. If they diverge, the clause is genuinely
ambiguous: route it to adjudication and record the reading-taken-versus-rejected
trap-log entry. If a discriminating input cannot be constructed, or the two
readings do NOT actually diverge on it, the clause is not a finding and is
DROPPED, not escalated (self-validating).

TWO hard constraints, structural not incidental:

* TRIAGE, NEVER A GATE. Nothing here marks a Verdict. The only outputs are routed
  Disagreements (kind == "clause") for adjudication and ClauseFinding trap-log
  entries. There is deliberately no path from a clause finding to pass/fail,
  because the flagging model and the codegen model share a comprehension bias and
  gating on it would lean on exactly the correlation it cannot escape.
* DECORRELATION. The reading extraction is prompted ADVERSARIALLY ("state the
  reading you are NOT taking and why") and is meant to run at higher effort or on
  a different model than candidate generation - partial decorrelation, since a
  same-model neutral re-read reproduces the misreading.

Model calls are gated on the live-call credential; this is prepared against the
seam so activation is a config flip (an injected client + adapter), exactly like
the input generator.
"""

from __future__ import annotations

import json
import re
from typing import Any, Callable, Optional

from .contracts import PYTHON, RUST, Candidate, ClauseFinding, Disagreement, SpecSheet
from .model_generator import GenPrompt, expand_params
from .props import classify_value_disagreement
from .sandbox import run_python_candidate, run_rust_candidate

_TRIAGE_SYSTEM = (
    "You are an adversarial specification reader. For each sentence that could be read more "
    "than one way, you state the reading you are NOT taking and why, then give two runnable "
    "programs that differ ONLY on that clause and one input on which they produce different "
    "results. You never decide which reading is correct - you only surface the ambiguity."
)

_TRIAGE_SCHEMA = (
    '{"clauses": [{"clause": str, "reading_a": {"prose": str, "code": str}, '
    '"reading_b": {"prose": str, "code": str}, '
    '"discriminating_input": {"params": [ {"literal": any} | {"repeat": {...}} | {"range": {...}} ]}}]}'
)

_JSON_OBJ_RE = re.compile(r"\{.*\}", re.DOTALL)


def triage_prompt(spec: SpecSheet) -> GenPrompt:
    user = (
        f"Entrypoint: {spec.signature or spec.entrypoint}\n\n"
        f"Statement:\n{spec.raw_statement}\n\n"
        "Find clauses that admit two genuinely different readings. For each, give two "
        "programs implementing the entrypoint that agree everywhere EXCEPT that clause, and "
        "one input on which they diverge. If you cannot construct an input that separates the "
        "two readings, DO NOT include the clause - it is not actually ambiguous.\n"
        f"Return only JSON matching:\n{_TRIAGE_SCHEMA}"
    )
    # higher effort / different model is a decorrelation knob; carried on the prompt.
    return GenPrompt(kind="triage", system=_TRIAGE_SYSTEM, user=user, schema=_TRIAGE_SCHEMA, model="strong")


def parse_clauses(text: str) -> list[dict]:
    m = _JSON_OBJ_RE.search(text)
    if not m:
        return []
    try:
        obj = json.loads(m.group(0))
    except json.JSONDecodeError:
        return []
    clauses = obj.get("clauses")
    return clauses if isinstance(clauses, list) else []


def _run(code: str, spec: SpecSheet, one_input: Any, timeout_s: float):
    if spec.language == PYTHON:
        return run_python_candidate(code, spec.entrypoint, one_input, timeout_s=timeout_s)
    if spec.language == RUST:
        return run_rust_candidate(code, one_input, run_timeout_s=timeout_s)
    from .contracts import ExecResult, ExecStatus

    return ExecResult(status=ExecStatus.COMPILE_ERROR, error="unsupported language")


def run_triage(
    spec: SpecSheet,
    client: Any,
    to_request: Callable[[GenPrompt], Any],
    *,
    timeout_s: float = 10.0,
) -> tuple[list[Disagreement], list[ClauseFinding]]:
    """Return (disagreements, findings). NEVER returns or mutates a Verdict.

    A clause is kept only if a discriminating input exists AND the two readings
    actually diverge (value-level) on it; otherwise it is dropped."""
    resp = client.complete(to_request(triage_prompt(spec)))
    disagreements: list[Disagreement] = []
    findings: list[ClauseFinding] = []

    for i, item in enumerate(parse_clauses(resp.text)):
        if not isinstance(item, dict):
            continue
        clause = str(item.get("clause", "")).strip()
        ra, rb = item.get("reading_a") or {}, item.get("reading_b") or {}
        code_a, code_b = ra.get("code"), rb.get("code")
        disc = item.get("discriminating_input") or {}
        # SELF-VALIDATING DROP: no clause, no code for a reading, or no
        # discriminating input -> not a finding.
        if not clause or not code_a or not code_b or "params" not in disc:
            continue
        disc_input = expand_params(disc.get("params", []))

        res_a = _run(code_a, spec, disc_input, timeout_s)
        res_b = _run(code_b, spec, disc_input, timeout_s)
        # Both readings must RUN, and must diverge at VALUE level (a mere form
        # difference is not a semantic ambiguity). Otherwise the input did not
        # discriminate -> drop.
        if not (res_a.ran_ok and res_b.ran_ok):
            continue
        if classify_value_disagreement(res_a.value, res_b.value) != "value":
            continue

        cand_a = Candidate(id=f"reading-a-{i}", language=spec.language, source=code_a,
                           origin="reading-a", meta={"clause": clause, "reading": ra.get("prose", "")})
        cand_b = Candidate(id=f"reading-b-{i}", language=spec.language, source=code_b,
                           origin="reading-b", meta={"clause": clause, "reading": rb.get("prose", "")})
        disagreements.append(
            Disagreement(
                failing_input=disc_input,
                outputs={cand_a.id: res_a.value, cand_b.id: res_b.value},
                candidates=[cand_a, cand_b],
                clause_hint=clause,  # REQUIRED for kind == "clause"
                seed=i,
                kind="clause",
            )
        )
        findings.append(
            ClauseFinding(
                clause=clause,
                reading_a=str(ra.get("prose", "")),
                reading_b=str(rb.get("prose", "")),
                discriminating_input=disc_input,
                output_a=res_a.value,
                output_b=res_b.value,
                seed=i,
            )
        )
    return disagreements, findings
