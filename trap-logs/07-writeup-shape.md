# Submission write-up — SHAPE (not prose yet)

Owner: workbench_client (whole + voice). Sections marked **[me]**, **[builder2]**,
**[client2]** by who supplies the raw material; I own assembly and voice throughout.
**Drafting of prose waits until the build workstreams deliver the manifest items below.**

Governing constraint (from the lead, and from two projects of scar tissue): **under-claim
and be exactly right.** Every capability statement must be backed by an artifact the
reader can check. The assignment scores 0/1 binary and hidden; we *raise P(correct)*, we
do not *prove* correct — the document must say exactly that and never imply more.

The assignment demands three questions answered (README "What We Want From You"):
Q1 how the system finds & handles traps · Q2 how it verifies without public examples ·
Q3 what it does when running out of time — plus "cost optimization in architecture."
Those three span all three workstreams, which is why one owner assembles the whole — a
doc stitched from three drafts reads as three docs.

---

## Proposed sections

### 0. TL;DR + claim boundary  **[me]**
One paragraph: a system that reads a problem JSON, detects its traps, produces a
solution, verifies it without public examples, and submits before the deadline — and a
two-sentence honest boundary ("what we prove / what we don't"). Must answer: what the
system is, and the exact shape of our confidence.

### 1. Core thesis: the input-bound vs derived-bound gap  **[me]**
The finding that shapes the architecture: traps live in the gap between bounded inputs
and a huge/unbounded *derived* quantity, and "the number of ⟨derived⟩ is at most Y" is an
*instruction*, not a constraint. Must answer: what a trap empirically *is*, why a single
"write the code" prompt fails. Evidence: taxonomy + the 6/7 generalisation result.

### 2. Finding & handling traps (Q1)
- **2a Trap catalogue** **[me]** — 14 categories grouped, with derivation/provenance
  (3→test-against-7→+5). Evidence: 05-MASTER-v2.
- **2b The detector** **[builder2]** — the bounds-diff in its strong form, open-world
  residue flagging, and "NO-trap-here" as a first-class verdict. Must answer: mechanically,
  how a problem JSON becomes a list of (trap, evidence-sentence, forced-technique) + a
  possible no-trap verdict. Evidence: detector I/O contract + one real run.
- **2c Worked examples** **[me]** — the 3 solved problems as detector→technique traces
  (counter-not-a-loop → batching; unbounded aggregate → binary lifting; unbounded reversal
  → lazy treap). Evidence: the committed solutions.
- Must answer overall: found *how*, handled *how*, shown on real problems.

### 3. Verifying without public examples (Q2) — the crux
- **3a Independence is CONSTRUCTED, not assumed** **[client2]** — the candidate mix and
  the concrete mechanism that decorrelates candidates (different model / prompt / algorithm
  family). Must answer: why two "independent" candidates are actually independent.
- **3b The verification ladder** **[builder2]+[me]** — differential agreement (valid only
  where output is a unique scalar/tuple), edge-biased fuzzing, max-scale timing. Evidence:
  sandbox description + fuzz counts (mine: 200k/40k/3k on the 3 samples).
- **3c The two checks that need NO second candidate to be right** **[me]+[builder2]** —
  name them explicitly: (i) **output property assertions** (canonical-form/N4), (ii)
  **structural invariants** (e.g. `attempts==retries+1`). Must answer: what we trust when
  candidates might share an error.
- **3d The known hole + its mitigation** **[me]+[client2]** — three readings can agree and
  all be wrong (shared comprehension error); the rejected 4th-axis (correlated, harmful)
  and the accepted ambiguity-triage (candidate-readings + discriminating input, **never a
  gate**). Evidence: 06.
- Must answer: how correctness is checked with no oracle, and **where the check is
  insufficient** (said out loud).

### 4. Running out of time (Q3)  **[client2]+[me]**
- **4a Time-budget architecture** **[client2]** — staging (detect→draft→verify→escalate)
  inside 300s; what is time-boxed.
- **4b Degradation ladder** **[client2]** — ordered list of what is sacrificed as the
  deadline nears, and the *final fallback* (what is submitted if verification didn't
  finish). Must answer: deterministic behaviour under pressure.
- **4c The correctness/throughput tension** **[me]** — "ship the verified-correct
  candidate" is NOT always safe: a correct-but-slow solution TLEs and scores 0 (P2 literal
  simulator; P3 33s CPython). The fallback must weigh *proven-correct* against
  *fast-enough*. Must answer: why the fallback is not simply "submit the one we trust."

### 5. Cost optimization  **[client2]+[builder2]**
Model tiering (cheap for mechanical/bounds-diff, expensive for ambiguous clauses &
adjudication), caching/replay, when NOT to call the expensive model. Must answer the
README's explicit "consider cost optimization."

### 6. What we have NOT proven (the honesty section — the lead's priority)  **[me]+all]**
- Catalogue **not converged**: singleton evidence (6/14 singletons; 10th problem still
  added one; Chao1≈22, wide bars), open-world requirement, **K=0**. **[me]**
- Differential agreement is **neither necessary nor sufficient** under canonical output. **[me]**
- **Replay honesty**: what replay/caching does and explicitly does *not* do. **[client2]**
- Correct asymptotics ≠ fast enough (CPython); P2 fast path designed-not-verified. **[me]**
- The 4th-axis we **rejected** and why — shows method, not just result. **[me]**
- **Coverage**: which of the 10 the end-to-end system has actually solved+verified —
  stated as a number, not implied. **[builder2]**
- Must answer: the exact boundary of every claim in §§1–5.

### 7. Appendix — provenance & reproducible evidence  **[me]**
The trail (00→04→05→06→07), the 3 solved solutions + fuzzers, how to re-run them.

---

## Manifest — what I need, from whom, in what form
(Routing via the lead, who will ensure delivery. I will not chase the others directly.)

### From **workbench_builder2** (detector / bounds-diff / verification / sandbox)
- **B1 Detector I/O contract** + ONE real run on a named sample: given the JSON, what does
  it emit? Does it implement the *strong* form (derived-bound-as-instruction) and
  open-world residue flagging, and can it return "no trap"? If any of these is aspirational
  not built, say so — I document *actual*.
- **B2 Sandbox facts:** how Python (`entrypoint` fn) and Rust (`main`, stdin/stdout) are
  executed; real time/memory limits; how fuzz inputs are generated and outputs compared.
- **B3 Assertion framework:** does it support output **property assertions** and
  **structural invariants**, or only differential? Which samples have assertions written?
- **B4 Coverage number:** which of the 10 samples the system has produced a solution for
  end-to-end **and** verified — the honest count for §6.
- Form: short structured note per item + one concrete artifact (example I/O) each.

### From **workbench_client2** (transport / independence / triage / degradation / replay)
- **C1 Candidate mix:** how many candidates, produced how, and the concrete decorrelation
  mechanism ("independence constructed not assumed") — the §3a material.
- **C2 Triage ladder:** the escalation from cheap checks to expensive adjudication, with
  the gate/no-gate line drawn (my "never a gate" constraint carried verbatim).
- **C3 Degradation path:** ordered list of what is cut as 300s approaches + the final
  fallback actually submitted.
- **C4 Replay-honesty paragraph:** what replay/caching does and does NOT do — exact wording
  I can quote.
- **C5 Transport seam:** JSON in / solution out; any assumptions or limits.
- Form: editable prose paragraphs (I'll set voice) + hard numbers (candidate count,
  timeouts, tier thresholds).

### From the **lead** (scope confirmation)
- **L1** Primary artifact: "running code" **or** "architecture document"? (README accepts
  either; even with code the three questions are required.) My default assumption unless
  told otherwise: **running code is the primary deliverable; this document is the
  accompanying architecture + evidence write-up.** Confirm so §0 frames it right.
- **L2** Audience/length: a grader reading for rigour — I'll target tight and
  evidence-dense over comprehensive. Confirm if there's a length or format expectation.

## Sequencing
1. Lead confirms L1/L2. 2. builder2 + client2 deliver the manifest (B1–B4, C1–C5).
3. I draft §§1,2a,2c,3c,3d,4c,6,7 **now-ish** (they're mine and the evidence exists); the
   rest fills in as the manifest lands. 4. Full assembly + voice pass. 5. Lead review →
   mayor. Nothing I write will claim a capability the build side hasn't handed me an
   artifact for.
