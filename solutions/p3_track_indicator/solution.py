"""Problem 3: track_indicator — SUBMISSION SOLUTION.

Standard library only, no I/O, does not mutate supplied sequences.

Complexity trap (flagged in the statement): "Reversed ranges have no bound on
their combined length." A literal slice-reverse is O(range) and the combined
length is unbounded, so O(ops * len) TLEs. An implicit treap with a lazy
reversal flag does each insert / reverse / remove-one / position-query in
O(log n). Selection is tracked by a stable node reference; the reported index is
rank(node) recomputed on demand.

Reselection on removing the selected tab is a bounded outward scan (skipping the
other tabs being removed); total scan work is O(sum of removed ids) because each
removed tab is skipped at most once across the whole run.
"""
import random
import sys

sys.setrecursionlimit(1 << 20)  # split/merge recurse to tree height


class _Node:
    __slots__ = ("id", "prio", "size", "left", "right", "rev", "par")

    def __init__(self, id_, prio):
        self.id = id_
        self.prio = prio
        self.size = 1
        self.left = None
        self.right = None
        self.rev = False
        self.par = None


def _sz(n):
    return n.size if n else 0


def _push(n):
    if n.rev:
        n.left, n.right = n.right, n.left
        if n.left:
            n.left.rev = not n.left.rev
        if n.right:
            n.right.rev = not n.right.rev
        n.rev = False


def _upd(n):
    n.size = 1 + _sz(n.left) + _sz(n.right)
    if n.left:
        n.left.par = n
    if n.right:
        n.right.par = n
    n.par = None


def _merge(a, b):
    if a is None:
        return b
    if b is None:
        return a
    if a.prio < b.prio:
        _push(a)
        a.right = _merge(a.right, b)
        _upd(a)
        return a
    else:
        _push(b)
        b.left = _merge(a, b.left)
        _upd(b)
        return b


def _split(t, k):
    # first k nodes -> left tree, rest -> right tree
    if t is None:
        return None, None
    _push(t)
    ls = _sz(t.left)
    if k <= ls:
        a, b = _split(t.left, k)
        t.left = b
        _upd(t)
        if a:
            a.par = None
        return a, t
    else:
        a, b = _split(t.right, k - ls - 1)
        t.right = a
        _upd(t)
        if b:
            b.par = None
        return t, b


class _Strip:
    def __init__(self):
        self.root = None
        self.rng = random.Random(88172645463325252)

    def _node(self, id_):
        return _Node(id_, self.rng.getrandbits(48))

    def node_at(self, idx):
        cur = self.root
        while True:
            _push(cur)
            ls = _sz(cur.left)
            if idx < ls:
                cur = cur.left
            elif idx == ls:
                return cur
            else:
                idx -= ls + 1
                cur = cur.right

    def rank(self, node):
        # clear lazy flags along root..node, then sum left-subtree sizes upward
        path = []
        cur = node
        while cur is not None:
            path.append(cur)
            cur = cur.par
        for p in reversed(path):
            _push(p)
        r = _sz(node.left)
        cur = node
        while cur.par is not None:
            p = cur.par
            if cur is p.right:
                r += _sz(p.left) + 1
            cur = p
        return r

    def insert_at(self, p, nodes):
        # build a treap of the new nodes (preserving order) then splice before p
        mid = None
        for nd in nodes:
            mid = _merge(mid, nd)
        a, b = _split(self.root, p)
        self.root = _merge(_merge(a, mid), b)

    def reverse_range(self, l, r):
        a, b = _split(self.root, l)
        m, c = _split(b, r - l)
        if m:
            m.rev = not m.rev
        self.root = _merge(_merge(a, m), c)

    def delete_at(self, pos):
        a, b = _split(self.root, pos)
        _, c = _split(b, 1)
        self.root = _merge(a, c)


def track_indicator(initial_ids, selected_index, operations):
    strip = _Strip()
    id2node = {}
    nodes = [strip._node(i) for i in initial_ids]
    for nd in nodes:
        id2node[nd.id] = nd
    mid = None
    for nd in nodes:
        mid = _merge(mid, nd)
    strip.root = mid

    selected = None if not initial_ids else nodes[selected_index]

    res = []
    for op in operations:
        kind = op[0]
        if kind == "insert":
            _, p, ids = op
            was_empty = strip.root is None
            new_nodes = [strip._node(i) for i in ids]
            for nd in new_nodes:
                id2node[nd.id] = nd
            strip.insert_at(p, new_nodes)
            if was_empty:
                selected = new_nodes[0]
        elif kind == "remove":
            _, ids = op
            S = set(ids)
            n = _sz(strip.root)
            if selected is not None and selected.id in S:
                pos = strip.rank(selected)
                new_sel = None
                j = pos + 1
                while j < n:
                    nd = strip.node_at(j)
                    if nd.id not in S:
                        new_sel = nd
                        break
                    j += 1
                if new_sel is None:
                    j = pos - 1
                    while j >= 0:
                        nd = strip.node_at(j)
                        if nd.id not in S:
                            new_sel = nd
                            break
                        j -= 1
                selected = new_sel
            # delete all removed nodes (highest position first keeps ranks valid)
            rm_nodes = [id2node[i] for i in ids]
            for nd in sorted(rm_nodes, key=strip.rank, reverse=True):
                strip.delete_at(strip.rank(nd))
                del id2node[nd.id]
        elif kind == "reverse":
            _, l, r = op
            strip.reverse_range(l, r)
        else:
            raise ValueError(kind)
        res.append(-1 if selected is None else strip.rank(selected))
    return res
