# ChallengeBox — empirical trap taxonomy (from solving 3 of the 10 samples)

Samples solved, properly, as if scored:
- `1ba0d34f…` — `simulate_writes` (python) — congestion/spin-credit state machine
- `1c182498…` — framed segmented-text delivery (rust)
- `1dea3280…` — `track_indicator` (python) — reversible tab strip

Each has a working solution + differential verification (no oracle exists, so every
solution is checked against an independent slow/brute reference over tens of
thousands of random cases, plus hand-computed edge cases). Details per problem in
`01/02/03-*.md`. This file is the taxonomy a trap-detector would need to catch.

## The single most important pattern: the input-bound / derived-bound gap

Every trap of consequence lives in the gap between **what the bounds limit** and
**what they deliberately leave huge or unbounded**. The problems bound the *inputs*
to friendly sizes (≤2–5×10⁵) while letting a *derived* quantity explode. A model
that sizes its algorithm to the input bound and simulates naively will be correct
on tiny inputs and TLE (score 0, binary) on the hidden max case.

| Problem | Input bound (small) | Derived/huge quantity (the trap) | Forced technique |
|---|---|---|---|
| simulate_writes | ≤2×10⁵ packets & runs | `max_retries`≤10¹⁸, run counts≤10¹⁸, credits≤10³⁰ → a single packet can "spin" ~10¹⁸ times | O(1) arithmetic batching of a run of retries; never iterate `cost` spins or per-retry |
| framing (rust) | N,Q ≤ 5×10⁵ | `C,H,B` ≤ 10¹⁸ **and** Σ(R−L+1) ≈ 2.5×10¹¹ across queries | per-position chunk-boundary precompute + binary lifting ⇒ O((N+Q)log N) |
| track_indicator | ops ≤ 2×10⁵, ids ≤ 3×10⁵ | "**Reversed ranges have no bound on their combined length**" (stated outright) | balanced BST / implicit treap with a **lazy reversal** flag ⇒ O(log n)/op |

The assignment's own hint ("one bounds *maximal surviving rectangles* at 150,000")
is the same move in another sample: the bound is on a **derived** quantity, and the
only way to respect it is to infer the intended algorithm from it (you can't
enumerate rectangles if only the survivors are bounded). **The detector's first job
is to diff "what is bounded" against "what the process can produce," and flag every
quantity that is large/unbounded and sits on the hot path.**

## Trap categories (what the detector must catch)

1. **Counter-not-a-loop.** A quantity described with an action verb ("performs `cost`
   spin iterations", "reverse the range") whose magnitude is huge. It must become
   arithmetic or a lazy flag, never an actual loop. (simulate_writes spins; reverse
   length.)

2. **Unbounded derived aggregate.** Σ of per-query/per-op work is unbounded even
   though each input is bounded. Forces preprocessing + sublinear queries, or a
   persistent mutable structure across ops. (framing spans; reversal combined length.)

3. **Order-of-operations within one step.** A sub-step does several things; a clause
   later *subtracts* some of them on an edge ("that final full causes no spin, yield,
   or credit deduction") **without** retracting the others (the level was still
   raised). Natural code conflates "drop" with "do nothing." (simulate_writes full-drop.)

4. **"Before" / "off-by-one" commit semantics.** "*Before* sending a character,
   include its width and, if it begins a new chunk, a header; if this exceeds B, stop
   *before* that character." The header is charged with the first char and never
   alone; equality with the budget is allowed (strictly-greater stops). Easy to charge
   the header at the wrong moment or use ≥ instead of >. (framing budget.)

5. **Reference-frame / snapshot clauses.** "Use the order **immediately before** this
   operation and **disregard every removed tab other than the selected tab**." The
   reselection is computed on a snapshot with a specific subset masked out — not on
   the post-removal array, not ignoring the selected tab. (track_indicator remove.)

6. **Implicit / infinite tails.** "After all runs are exhausted, every later attempt
   implicitly returns error" — and those implicit attempts still **count** in
   telemetry. A stream that silently ends ≠ a stream that yields a specific value
   forever. (simulate_writes outcomes.)

7. **Identity vs. position.** Selection is attached to an *identifier*, but the output
   is its *position*; reverses/inserts/removes move the position without changing the
   identity. Mixing the two is a classic bug. (track_indicator.)

8. **Numeric domain.** credits ≤10³⁰, costs ≤10¹⁸, wire totals near 2×10¹⁸. Python is
   safe (bigint); **Rust must pick u64/u128 deliberately** and prove no overflow in
   the `wire+incr > B` comparison (use u128). Exact arithmetic is demanded.

9. **Validity gates that change nothing.** "Invalid packets make no attempt and change
   no shared state" and are excluded from `attempts` but still emit a result tuple.
   Easy to either skip the tuple or leak a state change.

## Verification without an oracle — the method (honest account)

`public_examples` is empty on all ten, so I never had a provided answer. What I
actually did, and would automate:

1. **Two implementations, one slow-and-obviously-correct.** For each problem I wrote a
   literal/brute reference (per-attempt loop; per-character sim; plain list with real
   slice-reversals) whose correctness is read directly off the spec, and a fast
   solution with the trap-avoiding technique. Then I fuzzed fast-vs-slow on 2×10⁵
   (P1), 4×10⁴ (P3), 3×10³ (P2, cross-language) random cases biased toward the edges.
   Agreement is the strongest oracle available.
2. **Edge-biased generators, not uniform.** Tiny caps, zero budgets, empty inputs,
   single elements, selected-tab-removed-with/without-survivors, segment boundaries,
   4-byte codepoints, costs clamped exactly at the limit. Uniform random misses these.
3. **Hand-computed anchors.** A handful of cases where I compute the 7-tuple / index /
   telemetry by hand from the prose, to catch the case where *both* implementations
   share my misreading (fuzzing two of my own impls cannot catch that).
4. **Invariant assertions.** e.g. in P1, for every valid packet `attempts == retries+1`
   — a structural truth that, if violated, reveals a counting bug regardless of the
   oracle.
5. **Max-scale smoke + timing** to confirm the trap is actually defused (P1 200k×10¹⁸
   run: 0.23s; P3 300k tabs / 200k reverses: completes).

### What I could NOT fully convince myself of (recorded honestly)
- **P2 fast path is designed, not implemented.** My *submitted* P2 is the O(Σspan)
  literal simulator — provably correct (it's the oracle), but it will **TLE on the
  hidden max case** (Σspan ≈ 2.5×10¹¹). The binary-lifting design that defuses it is
  specified in `02-framing.md` but not yet coded/fuzzed, so I will not claim it as
  verified ground truth. For the three *sample* files this is moot (they're small);
  as a *scored* submission P2 is the weakest of the three.
- **P3 Python constant factor.** The treap is correct (40k fuzz) and O(log n)/op, but
  the pure-Python recursive split/merge takes ~33s at the 300k/200k ceiling. If the
  hidden runtime limit is a few seconds, Python alone likely fails even with the right
  asymptotics — an iterative treap / different host language would be needed. Correct,
  possibly not fast enough. Flagged, not hidden.
- **Shared-misreading residue.** Cross-impl + hand cases reduce but cannot eliminate
  the chance that a subtle clause (e.g. P1's "the level is still raised on the
  dropping full") is wrong in a way both my impls and my hand-reading share. The three
  places I consider genuinely ambiguous are called out per-problem.
