"""Independent Python re-implementation of the Problem 2 spec, used to
cross-check the Rust ground-truth simulator (catches transcription bugs). Both
being wrong the SAME way is still possible, so the trap log also argues the spec
edges by hand and hand-checked cases are in fuzz.py."""
import sys


def width(cp):
    if cp <= 0x7F:
        return 1
    if cp <= 0x7FF:
        return 2
    if cp <= 0xFFFF:
        return 3
    return 4


def solve(text):
    it = iter(text.split())

    def nxt():
        return next(it)

    n = int(nxt()); s = int(nxt()); q = int(nxt()); C = int(nxt()); H = int(nxt())
    w = [0] * (n + 1)
    for i in range(1, n + 1):
        w[i] = width(int(nxt(), 16))
    seg_of = [0] * (n + 1)
    idx = 1
    for seg in range(s):
        ln = int(nxt())
        for _ in range(ln):
            seg_of[idx] = seg
            idx += 1
    lines = []
    for _ in range(q):
        L = int(nxt()); R = int(nxt()); B = int(nxt())
        payload = wire = chars = chunks = last = last_chunk_payload = 0
        open_ = False
        cur_seg = 0
        cur_chunk_payload = 0
        cause = "END"
        i = L
        while i <= R:
            wi = w[i]
            need_new = (not open_) or seg_of[i] != cur_seg or cur_chunk_payload + wi > C
            incr = wi + (H if need_new else 0)
            if wire + incr > B:
                cause = "LIMIT"
                break
            wire += incr
            payload += wi
            chars += 1
            last = i
            if need_new:
                chunks += 1
                cur_chunk_payload = wi
                cur_seg = seg_of[i]
                open_ = True
            else:
                cur_chunk_payload += wi
            last_chunk_payload = cur_chunk_payload
            i += 1
        lines.append("%d %d %d %d %d %d %s" %
                     (payload, wire, chars, last, chunks, last_chunk_payload, cause))
    return "\n".join(lines) + ("\n" if lines else "")


if __name__ == "__main__":
    sys.stdout.write(solve(sys.stdin.read()))
