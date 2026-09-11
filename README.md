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

The three hand-solved ground-truth problems and their differential fuzzers need only
`python3` and `rustc` — **no model access, no network**:

```
( cd solutions/p1_simulate_writes && python3 fuzz.py )   # 200k cases: fast vs literal reference
( cd solutions/p3_track_indicator && python3 fuzz.py )   #  40k cases: treap vs plain-list reference
( cd solutions/p2_framing        && python3 fuzz.py )    #   3k cases: compiles main.rs, cross-checks
                                                         #   vs an independent Python twin + 5 anchors
```
(run from each solution's own directory — the framing fuzzer invokes `rustc ./main.rs`)
Each prints `OK: N cases matched`. Each directory holds the solution, a slow/independent
reference (the oracle), and the fuzzer — the verification method of `ARCHITECTURE.md §3`,
reproducible offline.

> _Note on the framing solution (`p2_framing/main.rs`): it ships as the **provably-correct
> literal simulator**, which is the right answer at sample scale but **would exceed the time
> limit on a maximum-size input**. Its fast path (binary lifting) is designed in
> `trap-logs/02` but not implemented. This is flagged, not hidden._

## What needs live model access

> _Pending the build workstreams (manifest C3/C5, B2): how to run the full system on a
> problem JSON end-to-end, and exactly what it does. Not yet written — not a claim._

### What you can run without credentials vs. what requires them (replay honesty)
> _Pending client2's replay-honesty paragraph (manifest C4), to appear here **verbatim** —
> what replay/caching lets a grader reproduce offline, and what genuinely needs live model
> access. This is the first thing a reader needs and the last thing we want discovered by
> trying it. Not yet written — not a claim._

## Map

| Path | What it is |
|------|-----------|
| `ASSIGNMENT.md` | the original brief, unchanged |
| `ARCHITECTURE.md` | architecture + evidence; answers the three required questions; **§6 = honest limits** |
| `trap-logs/00–07` | the analysis trail: 3-problem origin → held-out test → master taxonomy → rejected 4th axis → doc shape |
| `solutions/p{1,2,3}_*` | the three hand-solved problems: solution + reference + fuzzer |

## The three required questions (answered in ARCHITECTURE.md)
1. **How it finds & handles traps** — §2 (detector + 14-category catalogue + worked examples).
2. **How it verifies without public examples** — §3 (differential + fuzzing, and the two
   checks that need no second candidate; §3d names the hole this cannot close).
3. **What it does when running out of time** — §4 (staging, degradation ladder, and why the
   fallback is not simply "ship the most-verified candidate").
