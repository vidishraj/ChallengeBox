# ChallengeBox solver — our submission

A system that reads an algorithmic problem JSON (dense prose spec, target language,
entrypoint, empty `public_examples`, 300 s deadline), **finds the trap the bounds hide**,
produces a solution, **verifies it without any public examples**, and returns it before the
deadline. The original assignment brief is preserved verbatim in **[`ASSIGNMENT.md`](ASSIGNMENT.md)**.

> **What we claim:** the system *raises* P(correct); it does not *prove* it. Scoring is
> binary (1 = passes every hidden test, else 0) and the tests are hidden, so no self-check
> can establish a score. The honest boundary of every claim — including how many problems we
> have actually solved and verified — is in **[`ARCHITECTURE.md`](ARCHITECTURE.md) §6**, which
> is the section to read first if you are grading.

## The one idea

Traps live in the gap between **bounded inputs** and a **huge/unbounded derived quantity**:
size your algorithm to the input bound, simulate naively, and you are correct on every small
case and score 0 on the hidden maximum. The detector's primary rule: **"the number of
⟨derived thing⟩ is at most Y" is an instruction about what to enumerate, not just a
constraint.** Full taxonomy and its derivation: `trap-logs/`, master at
`trap-logs/05-MASTER-taxonomy-v2.md`.

## What a grader can run RIGHT NOW, without credentials

**(1) The ground-truth problems + their differential fuzzers** — need only `python3` and
`rustc`, **no model access, no network**. These are the three hand-solved problems and the
verification method of `ARCHITECTURE.md §3`, reproducible offline:

```
( cd ground-truth/p1_simulate_writes && python3 fuzz.py )   # 200k cases: fast vs literal reference
( cd ground-truth/p3_track_indicator && python3 fuzz.py )   #  40k cases: treap vs plain-list reference
( cd ground-truth/p2_framing        && python3 fuzz.py )    #   3k cases: compiles main.rs, cross-checks
                                                            #   vs an independent Python twin + 5 anchors
```
(run from each problem's own directory — the framing fuzzer invokes `rustc ./main.rs`).
Each prints `OK: N cases matched`. Each directory holds the solution, a slow/independent
reference (the oracle), and the fuzzer.

> _Note on the framing solution (`ground-truth/p2_framing/main.rs`): it ships as the
> **provably-correct literal simulator**, the right answer at sample scale but it **would
> exceed the time limit on a maximum-size input**. Its fast path (binary lifting) is designed
> in `trap-logs/02` but not implemented. Flagged, not hidden._

**(2) The solver spine** — the end-to-end pipeline (`SPINE.md`). It runs today and always
delivers a file within the deadline, but **`generate`/`verify` are spine stubs** — it does
not yet *solve* (see `ARCHITECTURE.md §6.1`, coverage = 0). The sandboxed execution, hard
time budget, and best-so-far-on-disk rule are real:

```
./solve samples/<id>.json                      # writes ./solutions/<id>.<py|rs> + a runlog
python3 -m unittest discover -s tests -t .     # the solver's unit tests
```

## What needs live model access

The live generator is what turns the spine from "delivers a file" into "attempts a real
solution." `./solve` runs offline **today** only because `generate` is a stub; once the live
generator lands, `./solve` will call the model.

> _Pending the build workstreams: the exact end-to-end run once the live path is wired
> (manifest C3/C5, B2), and — **verbatim** — client2's replay-honesty paragraph (C4): what
> replay/caching lets a grader reproduce offline vs. what genuinely needs live model access.
> The first thing a reader needs and the last thing we want discovered by trying it. Not yet
> written — not a claim._

## Map

| Path | What it is |
|------|-----------|
| `ASSIGNMENT.md` | the original brief, unchanged |
| `ARCHITECTURE.md` | architecture + evidence; answers the three required questions; **§6 = honest limits** |
| `SPINE.md` | the solver spine: what runs today vs. what is stubbed |
| `solve`, `solver/` | the pipeline — `./solve problem.json` → solution file; stages in `solver/stages/` |
| `tests/` | the solver's unit tests |
| `trap-logs/00–07` | the analysis trail: 3-problem origin → held-out test → master taxonomy → rejected 4th axis → doc shape |
| `ground-truth/p{1,2,3}_*` | the three hand-solved problems: solution + independent reference + fuzzer (tracked source) |
| `solutions/`, `out/` | **solver output** — regenerated per run, git-ignored; not source (ground truth lives in `ground-truth/`) |

## The three required questions (answered in ARCHITECTURE.md)
1. **How it finds & handles traps** — §2 (detector + 14-category catalogue + worked examples).
2. **How it verifies without public examples** — §3 (differential + fuzzing, and the two
   checks that need no second candidate; §3d names the hole this cannot close).
3. **What it does when running out of time** — §4 (staging, degradation ladder, and why the
   fallback is not simply "ship the most-verified candidate").
