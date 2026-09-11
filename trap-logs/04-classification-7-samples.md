# Does the taxonomy generalise? — classifying the other 7 samples (read, not solved)

Tested: do 8 categories + the meta-pattern drawn from 3 problems cover the other 7?
**Honest headline: the META-PATTERN generalises; the technique-categories do NOT.**

Reference categories (from the 3 solved, as reported):
C1 counter-not-a-loop · C2 unbounded derived aggregate · C3 order-of-ops-within-a-step ·
C4 before/off-by-one commit · C5 masked-snapshot/reference-frame · C6 implicit/infinite
tail · C7 identity-vs-position · C8 numeric domain/overflow · (C9 validity-gate-that-
changes-nothing — was the 9th in the summary file).

## Fit rate

- **Meta-pattern (bounded input vs huge/unbounded derived quantity): 6 of 7.** Present
  in S4, S5, S6, S8, S9, S10. The lone exception is **S7 (Patchboard)**, whose bounds
  are generous *aggregates* (total M, Σpath-len, total printed) and whose traps are
  purely semantic ordering. **That itself is a finding: the meta-pattern is dominant
  but NOT universal — some problems are pure semantic-precision, no complexity trap.**

- **Existing categories cover the problem with no new category needed: 3 of 7**
  (S6, S7, S4 — S4 with minor strain). **4 of 7 surface at least one genuinely new
  category** (S5, S8, S9, S10).

**Conclusion: the taxonomy is NOT converged. Three problems was too small.** The
detector's *first job* (diff bounded-inputs vs derivable-quantities) is sound and worth
building. The *catalogue of forced techniques* needs ~5 additions before it's a spec.

## The 5 new categories the other 7 force (the valuable part)

- **N1 — Ordered rule-priority over overlapping conditions.** "Apply the first matching
  rule"; "Classes may overlap; **rule order is authoritative**." (S5 grapheme rules.)
  Distinct from P2's "three OR-ed reasons to open a chunk": here the predicates overlap
  and **priority** decides. Mechanically detectable ("first matching", "in order").

- **N2 — Context-sensitive look-back.** A local decision depends on a *variable-length*
  scan backwards: "count the consecutive Regional Indicators ending at the left scalar …
  no boundary exactly when that count is **odd**"; "the nearest scalar before that U+200D
  **after skipping Attachments**." (S5.) Not a fixed-window off-by-one (C4) — the window
  is data-dependent.

- **N3 — Persistent / branching-version state (confluent persistence).** "Operation `i`
  creates version `i` from an **earlier version `b`**; **versions may branch.**" (S8.)
  In-place mutation is simply wrong; you need persistent/path-copied structures. The
  quadratic naive (copy-per-version) looks like C2 but the *forced technique* —
  persistence, not preprocess-then-query — is different enough to stand alone.

- **N4 — Canonical-form output.** The answer must match a **uniquely-defined normalised
  decomposition**; an equivalent-but-differently-shaped answer scores 0. "form the
  **maximal** inclusive intervals … **Rectangles cannot be combined in any other way.**
  **Sort lexicographically.**" (S9, strong; S4/S6 return-shape rules are mild cousins.)
  This is an *output-side* trap; C1–C9 are all input/process-side.

- **N5 — Exponential unfolding of a shared structure.** "The expression-rooted term is …
  an acyclic directed graph … **its meaning is its complete unfolding into a tree** …
  the same `var` node may represent occurrences under **different lexical paths**." (S10.)
  The DAG is ≤250k nodes but its unfolding is exponential; you must DP over the folded
  form. Related to C2 but the mechanism (memoise over shared structure) is distinct.

## Two refinements to existing findings
- **The meta-check has a stronger form: read EXPLICIT bounds on derived quantities as
  algorithm hints.** Several statements hand you the intended representation by bounding
  a derived count: S9 "maximal surviving rectangles ≤ 150,000", S4 "≤ 1,000,000 induced
  candidate names", S7 aggregate bounds. The detector shouldn't only flag *unbounded*
  derived quantities — it should treat "the number of ⟨derived thing⟩ is at most Y" as a
  direct instruction about what to enumerate.
- **C7 generalises to "coordinate-system translation."** S5 juggles grapheme index /
  UTF-8 bytes / UTF-16 code units for one position; S9 remaps row/col under insert/delete.
  "Identity-vs-position" is the 1-D case of "the same point in multiple coordinate spaces."

---
## Per-problem detail

### S4 — `refresh_references` (python) · FITS (minor strain)
- **Gap:** ≤200k snapshots & references, but "processed at `start` and **every later
  snapshot**" ⇒ naive is O(refs × snapshots) ≈ 4×10¹⁰ (**C2**). Explicit derived bound
  "≤1,000,000 induced candidate names" is the algorithm hint (index by candidate key).
- **C9:** "An invalid reference returns (…) and **is never processed**" — validity gate
  emitting original fields, no state touch.
- **C3 (mild):** "if its exact key exists, its hash becomes the entry's current hash;
  **otherwise its retained hash is unchanged**" — do-nothing-on-edge across snapshots.
- **Strain:** dense canonical-grammar validation (`@N` suffix only on function/value,
  "**without leading zeroes**", terminal case decides namespace). Covered by C9 but the
  *grammar strictness* is a wrinkle; a mild N4 cousin on the input side.
- **Intended complexity:** ~O((entries+candidates+refs)·log) incremental key-existence
  index advanced over snapshots.

### S5 — Unicode Matchday Repeats (rust) · MISFIT → N1, N2 (+ C7 extension)
- **Gap:** query 2 is a grapheme-level longest-common-extension; naive O(G) per query ⇒
  Q×G ≈ 1.8×10¹¹ (**C2**) ⇒ suffix-automaton / hashing / Z over the grapheme sequence.
- **C4:** negative-index resolution "`x`→`G+x` then clamp to `[0,G]`"; "if `j>=i` … else
  output boundary `i` twice." Edge-dense.
- **N1:** six-rule grapheme boundary table, "apply the first matching rule", "rule order
  is authoritative".
- **N2:** Regional-Indicator parity and ZWJ look-back-skipping-Attachments.
- **C7→coordinate translation:** grapheme / UTF-8 / UTF-16 triple indexing.
- **Intended complexity:** O(|S|) boundary + prefix-UTF-16 precompute + O(1)/O(log) LCE.

### S6 — `validate_build` (python) · FITS cleanly (reinforces C1)
- **C1 (textbook):** "`repeat t r times`", `r`,`k` up to 10¹⁸, "**Flattened layouts may
  be enormous**" ⇒ never materialise; navigate a virtual flattened layout; `default k`
  skips k positions by arithmetic. This is the cleanest C1 after "spin iterations".
- **C2/meta:** enormous derived layout from ≤300k terms.
- **C4:** three-way return (0 / earliest-invalid / `len+1`); "entire operation invalid
  if **any** requested position is invalid" (atomic).
- **C9 + recursive descriptor equality** (incl. capacities).
- **Intended complexity:** cursor stack over virtual layout + per-schema flattened field
  counts as bigints; ~O(ops · nesting≤60).

### S7 — Patchboard (rust) · FITS (C3+C5) — and breaks the meta-pattern
- **No complexity trap:** bounds are generous aggregates (ΣM≤200k, Σpath≤400k,
  Σprinted≤400k) ⇒ near-linear is intended; no 10¹⁸ explosion.
- **C5 (strong):** "remember the identified cell and its **current value** … Each
  restoration writes the remembered value **even if another activation later changed that
  cell**. Remembered paths are never resolved again." Snapshot-value semantics.
- **C3 (strong):** "restore … in **reverse** replacement order"; "STOPALL … **newest to
  oldest**"; "resolve its path **after all preceding replacements in that same
  activation**". LIFO/undo ordering.
- **Intended complexity:** O(K+ΣM+Σpath+Σprinted); cells hold current value, activations
  hold (cell, old-value) lists, ordered set for STACK.

### S8 — persistent fan-in trace evaluator (rust) · MISFIT → N3
- **N3 (core):** "creates version `i` from an earlier version `b`; **versions may
  branch**" ⇒ confluent persistence; in-place state is wrong. Naive copy-per-version is
  O(N·Q) (a C2 symptom) but the fix is *persistent structures*, not preprocessing.
- **C4:** 4-way status (COMPLETE/WAITING/BLOCKED/BACKPRESSURE) by exact (p,c,d, slot-c)
  conditions.
- **C8:** rolling hash mod 1e9+7 with signed-value residue; demand ≤10¹⁸.
- **Intended complexity:** persistent per-version (p,c,d + published slots + queue
  cursor); drains amortised over shared ancestry.

### S9 — `normalize_protection` (python) · MISFIT → N4 (+ strong C1/meta)
- **C1 + meta (explicit derived bound):** dimensions ≤10⁹, "**Do not enumerate
  individual worksheet cells or rows**"; "≤150,000 maximal surviving rectangles",
  "≤200,000 maximal column intervals" are the representation hints.
- **C3:** edits applied in order; insert/delete shift + discard-past-boundary.
- **C7→coordinate:** "Protection belongs to cells and **moves with surviving cells**"
  under row/col remapping.
- **N4 (core):** strict canonical output — maximal intervals, merge consecutive equal
  rows, "cannot be combined in any other way", sort lexicographically.
- **Intended complexity:** coordinate-compressed interval structures; O((rect+edit)·log),
  output size bounded by the stated derived counts.

### S10 — `capture_binders` (python) · MISFIT → N5 (+ dense scope semantics)
- **N5 (core):** expression is a **DAG whose meaning is its exponential tree unfolding**;
  "same `var` node … under different lexical paths" ⇒ DP over the folded graph, never
  materialise unfolding.
- **C2/meta:** ≤250k nodes, paths "may be linear in node count", unfolding exponential.
- **Scope-semantics precision (C3/C4 flavour):** let-vs-bind-vs-match scoping ("scrutinee
  outside arm scopes", "shared scopes over body but not auxiliaries") — a capture
  condition defined over path-crosses-scoped-edge ∧ name-free-in-replacement.
- **Intended complexity:** memoised pass over nodes tracking shadowing/free-name state;
  ~O(nodes + refs), set-merge care for names.

## What I'd tell the detector team
1. Ship the meta-check (bounded-input vs derivable-quantity diff) — it catches 6/7 and is
   mechanical. Extend it to *read explicit derived-count bounds as hints*.
2. Add N1–N5 to the technique catalogue; do **not** assume the 8 are complete.
3. Keep a "no-complexity-trap, pure-semantic-precision" bucket (S7) — the detector must
   not hallucinate a scaling trap where the bounds are genuinely generous; the risk there
   is ordering/snapshot correctness, not TLE.
