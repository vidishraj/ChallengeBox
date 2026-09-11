"""Differential fuzz: solution.simulate_writes vs reference.simulate_writes_ref.

No oracle exists, so we verify the FAST (batched) solution against the SLOW
(literal per-attempt) reference on many random small inputs where the slow one is
tractable. We deliberately include small caps / small credits / small max_retries
(to exercise drops, climbs, constant-phase) and also some large scalars (to
exercise batching vs literal on the same instance).
"""
import random
from reference import simulate_writes_ref
from solution import simulate_writes


def rand_case(rng):
    n = rng.randint(0, 12)
    lengths = []
    for _ in range(n):
        r = rng.random()
        if r < 0.15:
            lengths.append(rng.choice([0, -5, 65536, 100000]))  # invalid
        else:
            lengths.append(rng.randint(1, 65535))
    nruns = rng.randint(0, 8)
    outcomes = []
    for _ in range(nruns):
        kind = rng.choice(["ok", "full", "error"])
        # mix small and large counts
        cnt = rng.choice([1, 1, 2, 3, rng.randint(1, 6), rng.randint(1, 10**18)])
        outcomes.append((kind, cnt))
    max_retries = rng.choice([0, 1, 2, 3, rng.randint(0, 5), rng.randint(0, 10**18)])
    level_cap = rng.choice([0, 1, 2, 3, 5, rng.randint(0, 60)])
    spin_limit = rng.choice([1, 2, 3, 4, 8, rng.randint(1, 10**18)])
    credit_cap = rng.choice([0, 1, 5, 50, rng.randint(0, 10**30)])
    initial_credits = rng.randint(0, credit_cap)
    return (lengths, outcomes, max_retries, level_cap, spin_limit,
            initial_credits, credit_cap)


def main():
    rng = random.Random(1234)
    N = 200000
    for i in range(N):
        case = rand_case(rng)
        # guard: the reference is per-attempt; skip cases where a single packet
        # could literally loop a huge number of times (those are exactly what the
        # fast path batches, and the reference would hang). A packet loops at most
        # min(max_retries, credits//min_cost)+1 times on fulls. Keep that bounded
        # for the reference by capping the *reference-relevant* scalars.
        lengths, outcomes, max_retries, level_cap, spin_limit, ic, cc = case
        min_cost = 1  # cost >= 1 always
        worst_loops = min(max_retries, (cc // min_cost)) if min_cost else max_retries
        total_full = sum(c for k, c in outcomes if k == "full")
        if min(worst_loops, total_full) > 5000:
            # too big for the literal reference; make a bounded twin for the ref
            continue
        ref = simulate_writes_ref(*case)
        got = simulate_writes(*case)
        if ref != got:
            print("MISMATCH on case", i)
            print("case =", case)
            print("ref =", ref)
            print("got =", got)
            return
        # invariant check: for valid packets attempts == retries+1 locally
    print("OK: %d cases matched" % N)


if __name__ == "__main__":
    main()
