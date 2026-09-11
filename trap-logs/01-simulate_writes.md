# Trap log — `simulate_writes` (1ba0d34f…, python)

**Status:** solved; fast solution fuzzed against a literal per-attempt reference over
200,000 random cases (incl. 10¹⁸/10³⁰ scalars), all match; max-scale 200k×10¹⁸ run
returns in 0.23s. Files: `ground-truth/p1_simulate_writes/{solution,reference,fuzz}.py`.

## The solution in one paragraph
Per valid packet, consume outcomes until a terminal one. `ok`→SENT (level−1 floor 0,
credits+=len capped), `error`/implicit→ERROR (level:=0), `full`→raise level (cap), and
either schedule a retry (if `retries<max_retries` **and** `credits>=cost`, where
`cost=min(2**old_level, spin_limit)`) or DROP. The only way to be fast is to batch a
run of `full` outcomes: the level climbs ≤`level_cap`≤60 distinct steps, after which
`old_level` is constant so `cost`, the per-retry yield flag, and the credit drain are
all constant — a block of k retries is pure arithmetic.

## Traps, in the order they bite

### T1 — "performs `cost` spin iterations" is a COUNTER, not a loop *(caught me for ~0 time, but it's the headline)*
> "Scheduling it … performs `cost` spin iterations"
`cost` can be `min(2**60, 10¹⁸) ≈ 10¹⁸`. The natural reading "do a loop of `cost`
iterations" is an instant TLE/hang. It only ever contributes `spins += cost` to
telemetry. **A first-pass literal implementation absolutely gets this wrong** (it
reads like imperative instructions). Decision: `spins` is an accumulator; no loop.

### T2 — a single packet can schedule ~10¹⁸ retries ⇒ must batch *(the real algorithmic trap)*
`max_retries ≤ 10¹⁸`, run counts ≤ 10¹⁸, credits ≤ 10³⁰. One packet sitting in a long
`full` run retries until `retries==max_retries`, or `credits<cost`, or the run ends.
Per-attempt iteration is O(Σattempts) ≈ 10¹⁸ → TLE. **Reading taken:** after the level
saturates at `level_cap`, `cost` is constant, so the number of affordable retries is
`min(max_retries−retries, credits//cost, fulls_left_in_run)` computed in O(1); the
climb before saturation is ≤60 individual steps. **Reading rejected:** "counts are
small in practice" — the statement explicitly says hidden tests include max-size
inputs, so this is the intended trap, not a corner.

### T3 — the DROPPING `full` still raises the level *(caught me; recovered via close reading)*
> "`full` raises the level by one… Another attempt is scheduled only if… If either
> condition fails, the packet is dropped immediately; **that final `full` causes no
> spin, yield, or credit deduction.**"
My natural first implementation treated "dropped immediately" as "this full does
nothing." Wrong: the level raise is stated *before* the scheduling test and is **not**
in the list of things the final full doesn't cause (that list is spin/yield/credit
only). So on a drop: level is raised (capped), but no spin, no yield, no credit change.
**How I decided:** the exclusion clause enumerates three effects and omits the level —
`expressio unius`. Verified by a hand case: one packet, `[("full",5)]`, `max_retries=0`
→ `DROPPED,(0,0,0)` and `final_level==1` (raised). Confirmed by the solution.

### T4 — `old_level` is *pre-increase*; yield fires exactly when cost is clamped
`cost=min(2**old_level, spin_limit)` and a yield happens iff `2**old_level > spin_limit`
(strictly). So a yield ⇔ the spin cost was clamped by `spin_limit`. Off-by-one risk:
using the post-increase level for `cost`, or `>=` for the yield. Pinned by fuzzing
(cases with `spin_limit` set to exact powers of two around `2**old_level`).

### T5 — implicit errors after the stream ends are still ATTEMPTS
> "After all runs are exhausted, every later attempt implicitly returns error." …
> "`attempts` includes attempts receiving implicit errors."
So a packet whose first outcome is past the end is an attempt (counts), resets level to
0, and ends as ERROR. Natural bug: stop counting once `outcomes` is consumed. The
implicit tail is *infinite* `error`, not "nothing."

### T6 — invalid packets: no attempt, no state change, but still emit a tuple
`len∉[1,65535]` → `("INVALID",0,0,0)`, excluded from `attempts` and from level/credit
effects, but the `packets` list has one entry per input length including these. Two
symmetric bugs: skipping the tuple, or letting an invalid packet touch shared state.

### T7 — `ok` ordering: decrement level, THEN add length (capped)
Level −1 (floor 0) first; then `credits = min(credit_cap, credits+len)`. Independent
ops so order doesn't change the numbers here, but the cap applies to the *sum*, and
`error` resets level to 0 (not −1). Minor but pinned.

### T8 — the `attempts == retries + 1` invariant (my main self-check)
For every valid packet, the terminal/drop attempt is the "+1" over the scheduled
retries. I assert this mentally against the reference; it's a structural truth that
catches miscounting independent of any oracle.

## Complexity note — what the bounds force
Inputs bounded at 2×10⁵ (packets, runs); the process is bounded at ~10¹⁸–10³⁶ (retries,
spins). The gap is the whole game. Batching gives O(60·#packets + #(packet,run)
touches); a packet only advances to the next run when it exhausts the current one, so
touches sum to O(#packets+#runs). Python bigints make the 10³⁶ `spins` total a non-issue
numerically; a Rust port would need u128 **and** would have to reason about `spins`
overflowing even u128 (Σ could exceed 2¹²⁸) — a reason this problem is friendlier in
Python, which may be why `language=python` was chosen.

## Genuine ambiguity (hedge recorded)
Low-risk, but: "Another attempt is scheduled only if fewer than `max_retries` retries
have already been scheduled **for this packet**" — I reset the retry counter per packet
(it's explicitly per-packet). If a grader intended a global retry budget the answers
diverge; the wording ("for this packet") makes me confident, but it's the one clause I'd
re-read if a hidden test failed.
