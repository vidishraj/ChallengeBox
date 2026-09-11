# Can the hand-computed anchor be automated as a 4th independence axis?

**Question:** have a model TRACE the spec by hand on a ~3-element input, in prose, with
no code written or seen, then compare that traced result to what the implementations
produce — a fourth axis that never passes through code generation, to catch the shared
misreading the three-reading design cannot.

**Verdict up front: as literally described (trace → compare output) it is UNRELIABLE for
its stated purpose, and I would not build it as a pass/fail gate.** It is strongest
exactly where it is least needed and weakest exactly where it is most needed. But a
*reshaped* version — candidate-readings + a discriminating input — is buildable, cheaper
to adjudicate, and actually attacks the shared-misreading residue. Detail below.

## The independence it claims, and the flaw in the claim

The three existing axes (fast impl, slow reference, cross-language twin) all pass through
**code generation from an intent**. A shared misreading survives all three because the
error is born at *spec → intent*, upstream of all three; they inherit the same wrong
intent and agree. True.

But a prose hand-trace by the **same model** does **not** re-derive the intent
independently. It reads the same sentence and forms the same understanding. The error we
are hunting is a **comprehension** error ("I genuinely believe *drop* means *do
nothing*"). A comprehension error is invariant to the output medium: the hand-trace will
*also* say the level doesn't rise, agree with the buggy code, and hand us **false
confidence** — the worst outcome, because it launders a shared error into a "fourth
axis confirms it."

So the axis is genuinely independent only for **coding slips** (transcription,
off-by-one in implementation, a mis-typed `>=`) — which is the failure mode the slow
reference and twin already catch. For the **comprehension** failure mode it was built to
catch, a same-model trace is the *least* independent of all four. That inversion is the
core problem.

## What it WOULD catch that the current checks don't (the real, narrow slice)

It is not worthless. It catches comprehension errors **when three conditions all hold**:
1. the tracing context reads the clause *differently* than the codegen context did
   (different model, higher reasoning effort, or an adversarial prompt forces a re-read);
2. the ~3-element anchor input actually *exercises* the contested clause; and
3. the trace is arithmetically correct.

Concretely, on my three problems the clauses where a naive codegen + twin could agree and
both be wrong — and where a forced hand-trace has a chance:
- **P1:** "the dropping `full` still raises the level." Imperative phrasing reads as
  "drop ⇒ nothing happens"; a trace forced to write *"level is now ___"* after the
  dropping step confronts the reader with the question the code glossed.
- **P2:** header charged with the first char + strict `>` budget. A tiny budget hits the
  off-by-one immediately in a trace.
- **P3:** remove-reselection on a masked snapshot. An anchor where the selected tab *and*
  its right neighbour are both removed forces the "skip the other removed tabs" decision
  into the open.

In each, what actually caught ME was **not** a neutral trace — it was *interrogating the
clause* ("the exclusion list names spin/yield/credit and omits level — why?"). A plain
"trace this input" would likely reproduce the misreading; the catch came from adversarial
reading, not from tracing per se.

## Where it FAILS (concrete, so you can decide not to build it)

- **F1 — Correlation (the killer).** Same model, same sentence, same misreading in both
  media. Independence is near-zero precisely for shared comprehension errors. Mitigable
  only by decorrelating the reader (below), never fully.
- **F2 — The anchor usually misses the trap.** A *random* 3-element input almost never
  exercises the contested clause (most tiny P1 inputs never trigger the drop-raise
  interaction; most P2 budgets don't land on the off-by-one). To pick a **discriminating**
  anchor you must already *suspect* the ambiguity — chicken-and-egg. An undirected trace
  spends its budget on inputs that prove nothing.
- **F3 — The trace is itself error-prone.** Models slip on multi-step state/arithmetic by
  hand — the whole reason we use code. A wrong trace disagreeing with correct code is a
  **false alarm**; every disagreement then costs a human/stronger-model adjudication
  (trace-wrong vs code-wrong). If the false-alarm rate is appreciable, the signal drowns
  and the check trains people to ignore it — worse than not having it.
- **F4 — Zero help on the complexity axis.** A 3-element trace says nothing about whether
  the batched/lifted/persistent algorithm is correct at 10¹⁸ / exponential scale. Its
  unique value is confined to semantic-precision clauses, which overlap heavily with what
  the slow reference + edge-biased fuzzing already cover — *except* the shared-misreading
  residue, which is exactly where F1 bites.

## What I WOULD build instead (the reshaped version)

Don't compare a fuzzy prose trace's *output* to code output. Reshape it into a sharp,
adjudicable form that attacks the residue directly:

**Per clause the model flags as possibly-ambiguous, emit (a) the two candidate readings,
(b) a concrete input that DISCRIMINATES them, (c) the predicted output under each.** Then
run *both* readings as code on that input and ask a stronger/separate model: *which does
the spec's prose endorse?*

Why this is better than trace-and-compare:
- It converts "did my noisy trace match?" (scalar, slip-prone) into "here are two programs
  differing only on this clause, here's an input where they diverge, which is meant?" —
  a pinpointed question models answer far better than open-ended tracing.
- The discriminating-input demand **forces F2 into the open**: if the model can't
  construct an input that separates the readings, the clause is not actually ambiguous
  (or it hasn't understood it) — either way, useful signal.
- Its by-product **is the trap log** — the "reading taken vs reading rejected" list per
  clause is the artifact we already hand-write; this automates producing it.
- Decorrelation knobs that partially beat F1: run the reading-extraction at **higher
  reasoning effort / a different model** than codegen, and prompt it **adversarially**
  ("for each sentence state the reading you are NOT taking and why") — which is the thing
  that actually caught me, not neutral tracing.

**Use it as TRIAGE that surfaces candidate ambiguities for adjudication — never as an
automated pass/fail oracle.** Disagreement means "re-read this clause," not "fail this
solution." A check we cannot trust as a gate can still be valuable as an attention
director, provided we never let it auto-approve (F1's false-confidence path) or
auto-reject (F3's false alarms).

## One-line answer
The naive trace-and-compare is not reliable enough to build — it is least independent for
the very errors it targets (F1) and usually misses the trap anyway (F2). The
candidate-readings-plus-discriminating-input reshape **is** worth building, but only as an
ambiguity-triage feeding human/stronger-model adjudication, not as a fourth oracle. If we
ever "lean on it," we are leaning on F1, which fails silently on the exact case it was
built for.
