# Trap log — `track_indicator` (1dea3280…, python)

**Status:** solved; implicit-treap solution fuzzed against a plain-list brute force over
40,000 random op-sequences (empty→insert, reverse in/out of selection, remove of the
selected tab with survivors right-only / left-only / none), all match; 300k-tab /
200k-reverse max run completes (timing caveat below). Files:
`ground-truth/p3_track_indicator/{solution,brute,fuzz}.py`.

## The solution in one paragraph
An ordered sequence with `insert`-before-position, batch `remove`-by-id, and
range-`reverse`, reporting the selected tab's **index** after each op. The unbounded
reversal forbids materialising reversals, so I use an implicit treap with a **lazy
reversal** flag; the selection is a stable node reference and its index is `rank(node)`
recomputed on demand (O(log n)). Reselection on removing the selected tab is a bounded
outward scan that skips the other tabs being removed.

## Traps, in the order they bite

### TT1 — "Reversed ranges have no bound on their combined length" *(the trap, stated in plain sight)*
The statement hands you the trap explicitly. Every other quantity is bounded (ops
≤2×10⁵, ids ≤3×10⁵), but Σ(reverse length) is unbounded ⇒ real slice-reversal is
O(ops·len) ≈ 6×10¹⁰ → TLE. **Forced technique:** balanced BST / implicit treap with a
lazy `rev` flag that swaps children and toggles on push-down; a reverse is two splits,
a flag toggle, and two merges — O(log n). A model that reverses a Python list passes
the small samples and dies on the max case.

### TT2 — selection is an IDENTITY, the output is a POSITION *(the conceptual trap)*
"An existing selection remains attached to the same identifier." Insert/reverse/remove
move the selected tab's *position* without changing *which* tab is selected. I track
the selected **node**, never an index, and compute the index at report time. Bug I
avoided by construction: storing the selected index and trying to patch it through
reverses (doable for reverse in O(1), but remove's reselection needs the real order
anyway, so identity-tracking is the clean model).

### TT3 — remove reselection is computed on a masked SNAPSHOT *(caught me; subtle wording)*
> "use the order **immediately before** this operation and **disregard every removed
> tab other than the selected tab**: select the first surviving tab to its right; if
> none, the last surviving tab to its left; if none survives, leave it unselected."
Three traps in one clause:
- **Snapshot:** positions are the ones *before* the batch removal, not after.
- **Mask:** you look rightward/leftward from the selected tab's slot, **skipping the
  other tabs being removed** (they're gone), to the first *surviving* (not-removed) tab.
  My first instinct was "nearest neighbor in the current array" — wrong when several
  adjacent tabs are removed together; you must skip all of them in one direction.
- **Right-first, then left, then none**, and "last surviving to its **left**" means the
  nearest survivor on the left (largest position < selected). Getting the
  right/left priority or the left-direction "last" backwards flips answers.
I implement it as: from `pos_sel`, scan increasing index skipping ids in the remove
set until a survivor (→ right pick); else scan decreasing index similarly (→ left
pick); else unselected. The scan is bounded by the remove-set size, so total scan work
across the whole run is O(Σ removed ids). Pinned hard by the fuzzer (it deliberately
removes contiguous blocks around the selection).

### TT4 — `insert` only re-selects when the strip was EMPTY
"If the strip was empty, the first inserted identifier becomes selected." Otherwise the
selection is untouched (same identity), and its index shifts by `+len(ids)` iff the
insertion point `p ≤ selected_index`. The node-reference model makes the shift
automatic; the empty-strip case is the one explicit special case.

### TT5 — ids are "never appeared before, even as removed"; 64-bit signed
Inserted ids are globally fresh (so an id map is safe — no resurrection of a removed
id), and ids are signed 64-bit (negative ids are legal keys). No reuse means removed
nodes can be dropped from the map permanently.

### TT6 — "must not modify the supplied sequences"
`initial_ids` and each op's `ids` list must not be mutated. The brute force's
`tabs[p:p]=...` mutates its *own* copy, not the input; the fuzzer explicitly asserts
the inputs are unchanged after the solution runs (they are).

### TT7 — reverse bounds: `0 <= left < right <= length` (half-open, `right` exclusive)
Reversed positions are `left … right-1`. Using an inclusive `right` is an off-by-one
that the fuzzer would catch immediately; pinned.

## Complexity note — what the bounds force
Input-bounded (ops, ids) but the reversal aggregate is explicitly unbounded ⇒ a
persistent mutable order structure with O(log n) reverse is mandatory; nothing simpler
(Fenwick/array) survives arbitrary reversals. The treap also answers `rank`/`node_at`
in O(log n), which covers the position query and the reselection scan (the scan's total
cost is O(Σremoved·log n), amortised over the run, because each removed tab is skipped
at most once).

### Honest performance caveat
The treap is **correct** (40k fuzz cases) and asymptotically right, but my pure-Python
recursive split/merge runs the 300k-tab / 200k-reverse ceiling in **~33s**. If the
hidden runtime limit is a few seconds, this correct solution still scores 0 on Python
alone; it would need an iterative (non-recursive) treap, slab-allocated arrays instead
of node objects, or a faster host. I can vouch for correctness, not for fitting an
unknown tight time budget in CPython. This is the one place the asymptotics are right
but the constant may not be.

## Genuine ambiguity (hedge recorded)
None I consider material. The one I double-checked: on `remove` when the selected tab
**survives**, it "remains selected" and I simply recompute its index post-removal — no
reselection scan runs. The reselection clause applies *only* when the selected tab is
itself removed. The fuzzer exercises both branches and agrees with the brute force.
