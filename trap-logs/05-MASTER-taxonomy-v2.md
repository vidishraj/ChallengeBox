# ChallengeBox trap taxonomy — v2 (master, for USE)

**Supersedes `00-SUMMARY` for use; does NOT replace it.** Provenance is deliberate:
- `00-SUMMARY` (v1) = the catalogue derived from **3** solved problems. Unchanged.
- `04-classification` = the **held-out test**: v1 applied, blind-ish, to the other 7.
- This file (v2) = the merged catalogue to build against, **with its derivation cited**.

Why keep all three: "here are N trap categories" is an assertion; "we derived K from 3,
tested against 7 held-out, the meta-pattern held 6/7, the technique categories covered
only 3/7, and we added 5" is *evidence of method* — the same test-against-held-out-cases
discipline the assignment asks us to apply to solutions, applied to our own taxonomy.

**Convergence status, stated plainly: NOT proven converged.** 14 categories from 10
problems; the last 7 problems added 5; the discovery curve has **not** flattened (the
10th problem still introduced a new category). Treat this catalogue as the best current
map, not a closed set. Count correction vs. earlier messaging: v1 enumerates **9**
categories (validity-gate is #9), so the total is **9 + 5 = 14**, not 13.

---

## PRIMARY detector rule — the bounds-diff, in its strong form

Generalised in **6 of 7** held-out problems (all but S7). Build this first; it is
mechanical.

> **Read every explicit bound on a DERIVED quantity as an INSTRUCTION about what to
> enumerate — not merely as a constraint. Then diff "what the inputs are bounded to"
> against "what the process can produce"; anything large/unbounded on the hot path is
> the trap, and anything the statement bounds by an odd specific number is the intended
> representation.**

- **Strong form (primary):** "the number of ⟨derived thing⟩ is at most Y" tells you the
  solution. S9 "≤150,000 maximal surviving rectangles" → track rectangles, not cells.
  S4 "≤1,000,000 induced candidate names" → index by candidate key. S7's aggregate
  bounds (ΣM, Σpath-len, total printed) → near-linear is intended.
- **Secondary form:** flag quantities left huge/unbounded on the hot path (max_retries
  10¹⁸; Σ query spans 2.5×10¹¹; "reversed ranges have no bound on their combined
  length"; "flattened layouts may be enormous"; a DAG whose unfolding is exponential).

### REQUIREMENT, not a footnote: the detector must be able to return "NO complexity trap."
S7/Patchboard has genuinely generous bounds and zero scaling trap; its difficulty is
semantic precision. A detector that *always* finds a complexity trap will over-engineer
such problems, burn budget, and may ship a needlessly complex (more bug-prone) solution.
This is the same failure direction as a guard that flags legitimate input — "no trap
here, the risk is correctness" must be a first-class verdict.

---

## The 14 categories

Grouped by what they force. ★ = singleton (seen in exactly one of the 10 problems) —
these drive the convergence estimate below.

### A. Scaling / complexity mechanisms (what algorithm the bounds force)
1. **Counter-not-a-loop** — a huge quantity described with an action verb becomes
   arithmetic or a lazy flag, never a loop. *(P1 "performs cost spin iterations"; S6
   "repeat t r times", `default k`, r,k≤10¹⁸; S9 "do not enumerate cells", dims≤10⁹.)*
2. **Unbounded derived aggregate** — Σ per-query/op work is unbounded though each input
   is bounded ⇒ preprocess + sublinear queries. *(P2 Σspans; S4 refs×snapshots; S5
   grapheme-LCE; S10.)*
3. **N3 · Persistent / branching-version state** ★ — "version `i` from an *earlier*
   version `b`; versions may **branch**" ⇒ confluent persistence; in-place mutation is
   wrong. *(S8.)* Looks like #2 but the forced technique (persistence, not
   preprocess-then-query) is distinct.
4. **N5 · Exponential unfolding of a shared structure** ★ — a DAG whose *meaning* is its
   exponential tree unfolding ⇒ DP over the folded form, never materialise. *(S10.)*

### B. Within-step / ordering precision (semantic traps; no scaling)
5. **Order-of-operations within one step** — an edge clause subtracts *some* effects but
   not others. *(P1: the dropping "full" still raises the level; S7 restore order; S9
   edit order.)*
6. **Masked-snapshot / reference-frame** — compute on a snapshot with a specific subset
   masked / remembered values, not live state. *(P3 remove-reselection "order
   immediately before … disregard every removed tab other than the selected"; S7 "writes
   the remembered value even if another activation later changed that cell".)*
7. **N1 · Ordered rule-priority over OVERLAPPING conditions** ★ — "apply the first
   matching rule", "rule order is authoritative", classes overlap. *(S5.)* Distinct from
   OR-ed conditions (P2 chunk reasons) — here priority resolves overlap.
8. **N2 · Context-sensitive look-back** ★ — a decision depends on a *variable-length*
   backward scan (Regional-Indicator parity; ZWJ skip-Attachments). *(S5.)* Not a
   fixed-window off-by-one.

### C. Boundary / commit / counting edges
9. **Before / off-by-one commit semantics** — strict `>` vs `≥`; charge-with-first-item;
   stop-before vs after. *(P2 budget "exceed"; S5 negative-index resolve+clamp; S6
   three-way return; S8 4-way status.)*
10. **Implicit / infinite tails** ★ — a stream that ends yields a specific value forever,
    and those implicit events still *count*. *(P1 implicit errors in `attempts`.)*
11. **Validity gates that change nothing** — invalid input emits a shaped result, touches
    no state, is excluded from counters. *(P1 INVALID packets; S4 invalid references; S6
    atomic "entire operation invalid if any position is".)* Sub-wrinkle: **adversarial
    canonical-grammar validation** (S4 `@N` only on function/value, "no leading zeroes",
    terminal-case picks namespace) — an input-side cousin of #13.

### D. Representation / domain
12. **Identity-vs-position → coordinate-system translation** — the answer is a *position*
    but state is keyed by *identity*, and/or one point lives in several coordinate spaces.
    *(P3 selection-by-id → index; S5 grapheme/UTF-8/UTF-16; S9 row/col remap under edits
    "protection moves with surviving cells".)*
13. **Numeric domain / overflow** — bigint (Python) vs deliberate u64/u128 (Rust); exact
    arithmetic; modular rollups. *(P1 credits≤10³⁰; P2 wire≈2×10¹⁸ compare in u128; S8
    hash mod 1e9+7; demand≤10¹⁸.)*

### E. Output side (the new axis)
14. **N4 · Canonical-form output** ★ — the answer must match a *uniquely-defined
    normalised shape* or score 0: "maximal intervals … cannot be combined in any other
    way … sort lexicographically". *(S9 strong; S4/S6 return-shape rules are mild
    cousins.)* This is the **only output-side category**, and it has a verification
    consequence below.

---

## Verification consequences (for the build workstreams)

- **N4 is a HOLE in the differential oracle, not just a trap.** Our correctness check is
  agreement between independently-derived candidates. Under a canonical-output demand,
  **two correct candidates can disagree** (different normalisation → reported as a false
  correctness failure), **and two wrong candidates can agree** on a non-canonical shape
  (false pass, both score 0). So for N4 problems, differential agreement is neither
  necessary nor sufficient. **Close it with PROPERTY ASSERTIONS on the output** — is it
  sorted, are intervals maximal, is the merge rule respected, is it the unique canonical
  form — which are directly checkable and do not depend on a second candidate. This is a
  general reason property-checks outrank differential testing whenever the output shape
  is constrained.
- **Differential testing remains primary where the output is a scalar/tuple with a unique
  value** (P1 telemetry, P2 7-tuple, P3 index) — there, agreement is strong evidence.
- **Pure-semantic-precision problems (S7) need neither a scaling check nor a second
  candidate** so much as a *spec-clause checklist* verifier: enumerate the ordering /
  snapshot clauses and assert each holds.

## Honest limits carried from v1 (still true)
- Cross-impl agreement + hand anchors reduce but cannot eliminate a **shared misreading**.
- **Correct asymptotics ≠ fast enough in CPython** (P3 treap ~33s at ceiling) — a
  generation constraint: for Python targets prefer iterative over recursive, arrays over
  per-node objects; treat right-O() as necessary, not sufficient.
- **P2's fast path is designed, not verified** — the literal simulator is the oracle and
  would TLE at max size.

---

## Convergence estimate (answering "what are we still missing?")

**There is a cheap, principled estimate** — and it says we are *not* converged.

**Method (species-richness / Good-Turing on held-out discovery):** treat categories as
species, problems as samples, and count how many categories were seen in exactly one
problem (singletons, f₁) vs exactly two (doubletons, f₂). A high singleton count means
much unseen richness remains.

Tally across the 10 problems: **f₁ = 6** singletons (★: #3/N3, #4/N5, #7/N1, #8/N2,
#10 implicit-tail, #14/N4), **f₂ = 1** doubleton (#6 masked-snapshot), S_obs = 14.

- Chao1 = S_obs + f₁²/(2f₂) = 14 + 36/2 = **32** (unstable: f₂=1 inflates it).
- Bias-corrected Chao1 = S_obs + f₁(f₁−1)/(2(f₂+1)) = 14 + 30/4 ≈ **22**.

**Reading:** a point estimate around **~22 categories** (we've seen perhaps ~60–65%),
with wide error bars because n=10 and f₂=1. The robust qualitative signal is not the
number but that **6 of 14 categories appear only once and the 10th problem still added
one** — the discovery curve is still climbing. If the curve had flattened we'd expect the
last few problems to add nothing and f₁ to be small; neither holds.

**The honest ceiling:** 10 problems is the entire sample corpus we were given, so this is
an extrapolation to the *generator* behind ChallengeBox, not a measurement we can refine
by sampling more of the same set. We should **state the uncertainty, not imply coverage**:
"we mapped 14 trap categories from all 10 samples; singleton analysis suggests meaningfully
more exist in the generator (rough Chao1 ≈ 22, wide bars); the detector must therefore be
open-world — score a problem's traps against the catalogue **and** flag residue that fits
none, treating misses as expected, not anomalous." The cheapest ongoing estimate is to
**keep the held-out test running**: every new problem the system meets, record whether it
introduced a category; when a run of K new problems adds zero, the curve has flattened and
only then can we claim coverage.
