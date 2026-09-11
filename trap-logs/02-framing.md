# Trap log — framed segmented-text delivery (1c182498…, rust)

**Status:** ground-truth simulator solved and verified — Rust literal simulator matches
an independent Python twin over 3,000 random cases + 5 hand-computed cases pinning the
spec edges. **The fast (non-TLE) version is designed but NOT implemented/verified** —
see the complexity note; this is the weakest of my three as a *scored* submission.
Files: `solutions/p2_framing/{main.rs,twin.py,fuzz.py}`.

## The model
Process chars `L..=R` left to right, packing into chunks. A new chunk begins when there
is no open chunk, **or** the char is in a different source segment than the open chunk,
**or** adding it would exceed the payload cap `C`. Each new chunk costs one `H`-byte
header (wire only, not counted toward `C`). Budget `B` caps total wire bytes. Output 7
fields: `payload wire characters last chunks last_chunk_payload cause`.

## Traps, in the order they bite

### TR1 — Σ(R−L+1) is the unbounded quantity ⇒ per-query must be sublinear *(the real trap; it caught my submission)*
N,Q ≤ 5×10⁵ each look friendly, but nothing bounds the **sum** of request spans:
Q requests each spanning all N chars ⇒ ~2.5×10¹¹ char-steps. My literal simulator is
O(Σspan) and will TLE on the hidden max case. **This is the trap I did not fully
defuse** — I have the correct oracle but the scored-fast version is only designed (see
end). A model that writes the obvious per-char loop passes the samples and scores 0 on
the max test.

### TR2 — "Before sending a char, include its width and (if new chunk) one header; if this would exceed B, stop before that char." *(off-by-one commit semantics; caught me once)*
Three subtleties packed into one sentence:
- The header is charged **together with the first char** of a chunk and **never
  alone** ("A header is never sent without at least one character"). So if `char+header`
  would exceed `B`, the chunk is never opened — you stop, you don't emit a lone header.
- "exceed" is **strictly greater**: `wire+incr > B` stops; `wire+incr == B` is allowed
  (you may fill the budget exactly). I initially reached for `>=`; the word "exceed"
  settles it. Hand case pins `B` hit exactly.
- The check is **before** committing the char, so a budget cutoff leaves the char
  unsent and `last` at the previous position.

### TR3 — three independent reasons to open a new chunk, each charging a header
`need_new = (no open chunk) || (segment changed) || (payload_so_far + w > C)`. The
segment-boundary reason is easy to forget because it's phrased passively ("A chunk
cannot cross a source-segment boundary. Reaching that boundary closes it."). Each
reason charges `H`. Hand cases pin both the C-overflow split and the segment-boundary
split independently.

### TR4 — `C` is a PAYLOAD cap; `H` is wire-only; `B` caps the SUM
Headers never count toward `C` but always count toward `B`. So a chunk can hold up to
`C` payload bytes regardless of `H`, but `H` eats into the shared `B`. Mixing these
(e.g. counting headers toward `C`, or forgetting them in `B`) is the obvious bug.

### TR5 — `last_chunk_payload` is the payload of the FINAL chunk, 0 if none
Not the last char's width; the accumulated payload of whichever chunk was open when
transmission stopped. "The final nonempty chunk closes when transmission stops" just
means: count/close it normally; its payload is reported. `0` when nothing was sent.

### TR6 — `cause`: END iff char R was transmitted; otherwise LIMIT
The only stop reason other than finishing the range is the budget, so `cause=LIMIT`
exactly when we broke before reaching R (including the degenerate "couldn't even send
char L", which yields `0 0 0 0 0 0 LIMIT`). `L<=R` is guaranteed, so there's no empty
range.

### TR7 — numeric domain: choose the integer type deliberately (Rust-specific)
`C,H,B ≤ 10¹⁸`. The comparison `wire+incr` can reach ~`B+H+4 ≈ 2×10¹⁸`, which fits u64
(max 1.8×10¹⁹) but is close enough that I compare in **u128** to be provably
overflow-free. `payload/chars/chunks` stay small (≤4·N / ≤N). Codepoints parse from
hex **without** a `U+` prefix; widths by UTF-8 range 1/2/3/4 with surrogates excluded
(guaranteed absent).

### TR8 — output is token-compared on ASCII whitespace 0x09–0x0D and 0x20
So exact integer formatting, 7 tokens/request, any whitespace separators. I emit
`"%d %d %d %d %d %d %s\n"`; safe under the stated comparison.

## Complexity note — what the bounds force (the fast design)
The literal sim is O(N+S+Σspan); the bound gap (TR1) forces O((N+Q)·log N):

1. **Per-position chunk boundary.** For every start position `s`, the greedy chunk
   beginning at `s` ends at a deterministic `e(s)` (first position where either `C`
   would overflow or a segment boundary is hit). `e(s)` is monotonic in `s`, so a
   two-pointer sweep computes it for all `s` in O(N). Define `next(s)=e(s)+1`.
2. **Binary lifting over the chunk functional graph.** Tabulate `jump[k][s]` (start
   after 2ᵏ chunks) with prefix sums of per-chunk payload, header count, and char count.
3. **Answer a request** `(L,R,B)` by: (a) binary-lifting from `L` to count whole chunks
   that fit under `R` **and** under `B` (wire = payload + H·chunks), then (b) a
   within-chunk binary search using prefix-sums of widths to find where `B` cuts the
   final partial chunk (or whether its header can even be afforded). O(log N) per query.
   Segment restarts are already baked into `e(s)`, so the first partial segment at `L`
   needs no special case beyond starting the walk at `L`.

I'm confident in this design; I did **not** code or fuzz it, so I do not present it as
verified ground truth. For the three sample files (small N,Q) the literal simulator is
the correct answer and the one I'd submit for them.

## Genuine ambiguity (hedge recorded)
"A chunk contains at most `C` UTF-8 payload bytes and never splits a character." With
`C ≥ 4` and every char ≤ 4 bytes, a single char always fits alone, so `C` never makes a
char unsendable — only `B` can. I read "at most `C`" as allowing a chunk to stop
**below** `C` when the next char wouldn't fit (greedy, no look-ahead packing). A
non-greedy/optimal packing reading would change `chunks`/headers, but "process a
consecutive range from left to right" and the per-char "before sending" rule make the
greedy reading unambiguous to me. Flagged because it's the one place an "optimize the
packing" instinct could diverge.
