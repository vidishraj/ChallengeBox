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

Stubbed (the next workstreams):

- `analyse` returns the entrypoint, the target policy, and the raw statement; it
  does NOT parse domains/invariants/edge cases yet.
- `generate` emits placeholder candidates that run without crashing (so the
  best-so-far invariant holds) but solve nothing.
- `verify` only checks "did it run" via the sandbox; `passed` means *ran*, not
  *correct*. Verification without public examples is the headline open question.
- `adjudicate` returns the first disagreeing candidate.

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
