"""Problem 3: track_indicator — BRUTE-FORCE REFERENCE (correct by construction).

Plain Python list. Every reverse is a real slice reversal (O(len)), so this is
O(ops * len) and only tractable on small inputs — exactly the oracle we fuzz the
treap solution against.
"""


def track_indicator_brute(initial_ids, selected_index, operations):
    tabs = list(initial_ids)
    sel = None if not tabs else tabs[selected_index]
    res = []
    for op in operations:
        kind = op[0]
        if kind == "insert":
            _, p, ids = op
            was_empty = (len(tabs) == 0)
            tabs[p:p] = list(ids)
            if was_empty:
                sel = ids[0]
        elif kind == "remove":
            _, ids = op
            S = set(ids)
            if sel is not None and sel in S:
                pos = tabs.index(sel)
                new_sel = None
                for j in range(pos + 1, len(tabs)):
                    if tabs[j] not in S:
                        new_sel = tabs[j]
                        break
                if new_sel is None:
                    for j in range(pos - 1, -1, -1):
                        if tabs[j] not in S:
                            new_sel = tabs[j]
                            break
                sel = new_sel
            tabs = [t for t in tabs if t not in S]
        elif kind == "reverse":
            _, l, r = op
            tabs[l:r] = tabs[l:r][::-1]
        else:
            raise ValueError(kind)
        res.append(-1 if sel is None else tabs.index(sel))
    return res
