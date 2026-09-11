"""Cross-check Rust ground-truth simulator vs Python twin on random inputs, plus
hand-computed cases that pin specific spec edges."""
import random
import subprocess
import sys
from twin import solve


def build():
    r = subprocess.run(["rustc", "-O", "main.rs", "-o", "main_bin"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr)
        sys.exit(1)


def run_rust(text):
    return subprocess.run(["./main_bin"], input=text, capture_output=True,
                          text=True).stdout


def gen(rng):
    n = rng.randint(1, 12)
    # segments: random composition of n
    s_cuts = sorted(rng.sample(range(1, n), min(rng.randint(0, n - 1), n - 1))) if n > 1 else []
    seglens = []
    prev = 0
    for cut in s_cuts:
        seglens.append(cut - prev)
        prev = cut
    seglens.append(n - prev)
    s = len(seglens)
    q = rng.randint(1, 6)
    C = rng.choice([4, 4, 5, 6, 8, rng.randint(4, 20)])
    H = rng.choice([0, 0, 1, 2, 3, rng.randint(0, 5)])
    # codepoints spanning all width classes incl 4-byte
    cps = []
    for _ in range(n):
        klass = rng.choice([1, 2, 3, 4])
        if klass == 1:
            cps.append(rng.randint(0x0, 0x7F))
        elif klass == 2:
            cps.append(rng.randint(0x80, 0x7FF))
        elif klass == 3:
            cp = rng.randint(0x800, 0xFFFF)
            while 0xD800 <= cp <= 0xDFFF:
                cp = rng.randint(0x800, 0xFFFF)
            cps.append(cp)
        else:
            cps.append(rng.randint(0x10000, 0x10FFFF))
    reqs = []
    for _ in range(q):
        L = rng.randint(1, n)
        R = rng.randint(L, n)
        B = rng.choice([0, 1, 2, 3, 5, 10, rng.randint(0, 40)])
        reqs.append((L, R, B))
    toks = ["%d %d %d %d %d" % (n, s, q, C, H)]
    toks.append(" ".join("%x" % c for c in cps))
    toks.append(" ".join(str(x) for x in seglens))
    for (L, R, B) in reqs:
        toks.append("%d %d %d" % (L, R, B))
    return "\n".join(toks) + "\n"


def hand_cases():
    # (input, expected) pinned by manual reading of the spec.
    cases = []
    # 1 char 'A'(1B), 1 seg, C big, H=2, B big => one chunk, payload1 wire3 chars1 last1 chunks1 lastpay1 END
    cases.append(("1 1 1 100 2\n41\n1\n1 1 1000\n",
                  "1 3 1 1 1 1 END\n"))
    # B too small to even open (need 1+2=3 > B=2) => nothing, cause LIMIT
    cases.append(("1 1 1 100 2\n41\n1\n1 1 2\n",
                  "0 0 0 0 0 0 LIMIT\n"))
    # two 1-byte chars, C=1 so each needs its own chunk; H=0; B big.
    # char1: new chunk payload1; char2: cur+1=2>1 -> new chunk. chunks2 payload2 wire2 last2 lastpay1 END
    cases.append(("2 1 1 1 0\n41 42\n2\n1 2 1000\n",
                  "2 2 2 2 2 1 END\n"))
    # wait: C>=4 in real constraints, but simulator handles C=1 fine; keep as logic check.
    # segment boundary forces new chunk: 2 chars, 2 segments of len1, C big, H=1, B big
    # char1 new chunk (hdr) payload1 wire2; char2 diff seg -> new chunk (hdr) payload2 wire4 chunks2 lastpay1
    cases.append(("2 2 1 100 1\n41 42\n1 1\n1 2 1000\n",
                  "2 4 2 2 2 1 END\n"))
    # budget cuts mid second char: 3 one-byte chars, 1 seg, C big, H=0, B=2 -> only 2 chars, LIMIT
    cases.append(("3 1 1 100 0\n41 42 43\n3\n1 3 2\n",
                  "2 2 2 2 1 2 LIMIT\n"))
    return cases


def main():
    build()
    # hand cases first
    for inp, exp in hand_cases():
        got_r = run_rust(inp)
        got_t = solve(inp)
        if got_r != exp or got_t != exp:
            print("HAND CASE FAIL")
            print("input=", repr(inp))
            print("exp  =", repr(exp))
            print("rust =", repr(got_r))
            print("twin =", repr(got_t))
            return
    print("hand cases OK")
    rng = random.Random(99)
    N = 3000
    for i in range(N):
        inp = gen(rng)
        gr = run_rust(inp)
        gt = solve(inp)
        if gr != gt:
            print("MISMATCH case", i)
            print("input=\n" + inp)
            print("rust=\n" + gr)
            print("twin=\n" + gt)
            return
    print("OK: %d random cases matched (rust == twin)" % N)


if __name__ == "__main__":
    main()
