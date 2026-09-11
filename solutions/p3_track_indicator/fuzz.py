"""Differential fuzz: treap solution vs plain-list brute force for track_indicator.

Random op sequences that exercise empty->insert, reverse (incl. selected inside
and outside the range), remove of the selected tab with survivors on the right,
only on the left, and none (strip goes unselected), and interleavings.
"""
import random
from brute import track_indicator_brute
from solution import track_indicator


def gen_case(rng):
    next_id = [1]

    def fresh(k):
        out = []
        for _ in range(k):
            out.append(next_id[0])
            next_id[0] += 1
        return out

    start = rng.random()
    if start < 0.3:
        initial = []
        sel = -1
    else:
        initial = fresh(rng.randint(1, 6))
        sel = rng.randint(0, len(initial) - 1)

    # model current length + present ids to generate valid ops
    present = list(initial)
    ops = []
    nops = rng.randint(1, 25)
    for _ in range(nops):
        L = len(present)
        choices = ["insert"]
        if L > 0:
            choices += ["remove"]
        if L >= 2:
            choices += ["reverse"]
        k = rng.choice(choices)
        if k == "insert":
            p = rng.randint(0, L)
            ids = fresh(rng.randint(1, 4))
            ops.append(("insert", p, ids))
            present[p:p] = ids
        elif k == "remove":
            m = rng.randint(1, L)
            victims = rng.sample(present, m)
            ops.append(("remove", victims))
            vs = set(victims)
            present = [x for x in present if x not in vs]
        else:
            l = rng.randint(0, L - 1)
            r = rng.randint(l + 1, L)
            ops.append(("reverse", l, r))
            present[l:r] = present[l:r][::-1]
    return initial, sel, ops


def main():
    rng = random.Random(2024)
    N = 40000
    for i in range(N):
        initial, sel, ops = gen_case(rng)
        exp = track_indicator_brute(initial, sel, ops)
        # guard against mutation of inputs
        initial_copy = list(initial)
        ops_copy = [tuple(o) for o in ops]
        got = track_indicator(initial, sel, ops)
        if initial != initial_copy or [tuple(o) for o in ops] != ops_copy:
            print("MUTATED INPUT on case", i)
            return
        if exp != got:
            print("MISMATCH on case", i)
            print("initial=", initial, "sel=", sel)
            print("ops=", ops)
            print("exp=", exp)
            print("got=", got)
            return
    print("OK: %d cases matched" % N)


if __name__ == "__main__":
    main()
