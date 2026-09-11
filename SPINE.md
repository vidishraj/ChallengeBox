# Solver spine

An end-to-end skeleton that runs today: `solve <problem.json> -> <solution file>`.
It is deliberately the SPINE, not the clever parts. The pipeline stages are
trivial stubs that return valid, typed objects; the two invariants that must be
real from day one (a hard wall-clock budget and a best-so-far solution always on
disk) are real; and the one hard mechanism (sandboxed execution) is real.

## Run it

```
./solve samples/<id>.json            # writes ./solutions/<id>.<py|rs> + a runlog
./solve samples/<id>.json -o out/    # choose an output dir or file
python3 -m solver samples/<id>.json  # equivalent
python3 -m unittest discover -s tests -t .   # tests (run from repo root)
```

Exit code is 0 when a solution file is on disk within the deadline, else 1.

## Pipeline

```
problem.json
   -> Problem            (parse + validate the input schema)
   -> analyse  -> SpecSheet      (entrypoint, input domains, invariants, edge cases,
                                  output contract, language-target policy)
   -> generate -> [Candidate]    (source + provenance)
   -> verify   -> VerdictReport  (per-candidate verdicts, a best, disagreements)
   -> adjudicate -> Candidate    (resolve disagreements)
   -> solution file on disk
```

Every stage has a typed contract in `solver/contracts.py` and a stub in
`solver/stages/`. The stubs are marked `SPINE STUB`; replace the body, keep the
signature.

## What is real vs stubbed

Real (do not treat as placeholder):

- **Sandboxed execution** (`solver/sandbox/`): runs a candidate under a
  wall-clock timeout and an address-space (RLIMIT_AS) memory cap in a
  subprocess, returning a structured `ExecResult`
  (`ok` / `wrong-shape` / `crashed` / `timed-out` / `compile-error` /
  `overflowed`). The harness cannot be taken down by a candidate.
- **Time budget** (`solver/budget.py:TimeBudget`): hard wall-clock budget
  measured from process start (captured in `cli.py` as `PROCESS_START`);
  `remaining()` sizes each stage's sub-budget.
- **Best-so-far on disk** (`solver/budget.py:BestSoFar`): the first candidate
  that runs is written out immediately (atomic temp + replace); only a
  verified-better candidate overwrites it. We never fail closed — a wrong answer
  and no answer both score zero.
- **Run log** (`solver/runlog.py`): per-stage timings + decisions, written to
  `<solution>.runlog.json`.

Real (landed since the spine):

- `analyse` mines the statement into a structured `SpecSheet`: entrypoint
  signature, per-parameter domains/bounds, invariants, edge-case clauses, the
  output contract, and the canonical-form output properties (sorted / maximal /
  lexicographic / distinct) that a numerically-correct-but-mis-formatted answer
  would violate. Best-effort and regex/keyword driven; a missed clause degrades
  the signal, it does not corrupt it.
- `bounds_diff` (in `solver/bounds.py`) is the trap thesis made structural:
  it separates what the INPUTS bound from what the PROCESS can produce. Primary
  output is ENUMERATION HINTS (an explicit derived bound, "at most 150000
  maximal rectangles", read as what to enumerate); secondary is HOT PATHS (a
  derived quantity large or unbounded and unaccounted for, which the perf probe
  will aim at). It is OPEN-WORLD: a category registry (extensible data) PLUS a
  residue channel for trap-shaped structure that matches nothing, since the
  catalogue is not converged. Its `status` earns a `clear-verified` verdict only
  on positive evidence and keeps it distinct from `inconclusive` / `not-run`;
  `residue_fired` is logged per problem as a held-out coverage metric.
- `generator` (`solver/generator.py`) derives inputs from the SPEC (a call kept
  distinct from candidate generation, so a misreading cannot propagate into both
  the solution and the inputs that test it). Its load-bearing part is the
  COVERAGE CONTROL: it fails loudly unless every extracted edge clause (and every
  structural edge: empty, singleton, each bound at its extreme) is exercised, and
  unless every flagged hot path has a max-size input aimed at it. A max-size
  input that does not explode the flagged quantity would make the perf probe pass
  while testing nothing. A deterministic battery covers the structural edges
  offline; the model-written generator (through the LLM seam) covers the prose
  clauses and hot paths and is gated on the live-call confirmation.
- `model_generator` (`solver/model_generator.py`) is the model-written generator,
  prepared against the seam so activation is a config flip. It makes TWO distinct
  calls, not conflated: a valid-input battery across the stated domains, and (per
  flagged hot path, with the hot path passed IN as the target) one maximum-size
  input built to explode that quantity while staying in bounds. Output is a
  compact plan (literal / repeat / range) materialised into concrete inputs, so a
  huge input is a rule not a huge literal. It is decoupled from the concrete seam
  via an injected client; `solve(input_client=..., to_request=...)` is the flip
  that feeds the coverage-checked battery and the max-size inputs to the perf
  probe. Until the credential lands, the deterministic battery is used.
- `triage` (`solver/triage.py`) is clause-ambiguity triage - the semantic
  complement to the bounds diff, aimed at the traps a scaling detector cannot see
  (a clause read two ways). Per flagged clause it emits two candidate READINGS as
  programs and a discriminating input, runs both, and keeps the clause ONLY if
  the readings actually diverge (value-level) on that input; otherwise it is
  dropped (self-validating: no discriminating input, no finding). Outputs are a
  routed adjudication (a Disagreement with kind == "clause") and a structured
  trap-log entry (reading-taken-versus-rejected). It is TRIAGE, NEVER A GATE:
  there is no code path from a clause finding to a Verdict (a unit test asserts
  verdicts are unchanged when triage runs), because the flagging and codegen
  models share a comprehension bias. Prompted adversarially at a higher-tier
  model for partial decorrelation; the model call is gated like the generator and
  wired via `solve(triage_client=..., triage_to_request=...)`.
- `verify` runs four checks (cheapest, most independent first): PROPERTY
  ASSERTIONS on each output against the extracted canonical-form properties (a
  confirmed failure, no second candidate required); NAIVE-VERSUS-FAST against a
  literal clause-by-clause reference candidate (a value disagreement with the
  reference marks the fast candidate wrong); DIFFERENTIAL TESTING across
  candidates, classifying each divergence value / form / status; and a
  PERFORMANCE PROBE (`solver/perf.py`) that times a candidate on a maximum-size
  input (Rust unchecked build) and rejects correct-but-slow, since that scores
  zero exactly like wrong. `passed` means *ran, properties held, agreed with the
  reference, and cleared max size in time*.

Stubbed (the next workstreams):

- `generate` emits placeholder candidates that run without crashing (so the
  best-so-far invariant holds) but solve nothing.
- `verify`'s naive-versus-fast and performance probe are BUILT and unit-tested,
  but inert in the live pipeline until their inputs exist: naive-versus-fast
  needs a literal reference candidate (generation side), and the performance
  probe needs a real maximum-size input aimed at the bounds-diff hot paths (the
  spec-derived generator). Small inputs still come from a trivial in-domain
  generator. Wiring these to real inputs is what activates them end to end.
- `adjudicate` returns the first disagreeing candidate (the real resolver, which
  normalises form disagreements and re-verifies, lands with generation).

## The README's exam questions, at spine level

- **How traps are handled** — analyse extracts them into `SpecSheet.edge_cases`
  / `invariants`; not implemented, contract in place.
- **How a solution is verified without examples** — the verify + adjudicate
  contracts and the sandbox exist; the strategy (input generators, differential
  testing, self-consistency) is the next workstream.
- **What happens when out of time** — the best-so-far-on-disk rule: there is
  always a runnable solution written, so a timeout still delivers *something*
  rather than nothing.

## Targeting decisions baked in

- **Python 3.9 target.** The grader's Python is unknown; 3.9 code runs on 3.12
  but not vice-versa. `SpecSheet.target` (a `TargetPolicy`) carries this so
  generation is constrained structurally, and because the harness itself runs on
  3.9 a candidate using 3.10+ syntax fails at OUR compile step
  (`policy.python_target_violations`) rather than silently on the grader.
- **Rust integer overflow is detectable.** `10^18` overflows i64 under
  multiplication and `10^30` needs u128/i128. The Rust sandbox compiles with
  `rustc -O -C overflow-checks=on`, so a candidate that reaches for a too-narrow
  integer type surfaces as an `overflowed` outcome instead of a silent wrap that
  would only be wrong on the grader. Optimization is kept for max-size-input
  speed; the availability check degrades cleanly to `compile-error` if `rustc`
  disappears.
