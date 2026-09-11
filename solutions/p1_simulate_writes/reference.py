"""Problem 1: simulate_writes — BRUTE-FORCE REFERENCE (correct by construction, slow).

Per-attempt literal simulation. O(total attempts). Used only as the oracle for
differential fuzzing against the fast solution. NOT suitable for max inputs
(a single packet can schedule up to max_retries = 1e18 retries).
"""


def simulate_writes_ref(lengths, outcomes, max_retries, level_cap, spin_limit,
                        initial_credits, credit_cap):
    level = 0
    credits = initial_credits
    packets = []
    tel = dict(sent=0, dropped=0, errors=0, invalid=0, attempts=0,
               spins=0, yields=0, final_level=0, final_credits=0)

    # outcome cursor over RLE runs; implicit "error" after exhaustion
    run_idx = 0
    run_off = 0
    nruns = len(outcomes)

    def next_outcome():
        nonlocal run_idx, run_off
        while run_idx < nruns:
            kind, cnt = outcomes[run_idx]
            if run_off < cnt:
                run_off += 1
                return kind
            run_idx += 1
            run_off = 0
        return "error"  # implicit, unlimited

    for L in lengths:
        if not (1 <= L <= 65535):
            packets.append(("INVALID", 0, 0, 0))
            tel['invalid'] += 1
            continue
        retries = 0
        spins = 0
        yields = 0
        status = None
        while True:
            kind = next_outcome()
            tel['attempts'] += 1
            if kind == "ok":
                level = max(0, level - 1)
                credits = min(credit_cap, credits + L)
                status = "SENT"
                break
            elif kind == "error":
                level = 0
                status = "ERROR"
                break
            else:  # full
                old_level = level
                level = min(level_cap, level + 1)          # raised unconditionally
                cost = min(1 << old_level, spin_limit)
                if retries < max_retries and credits >= cost:
                    retries += 1
                    credits -= cost
                    spins += cost
                    if (1 << old_level) > spin_limit:
                        yields += 1
                    # schedule another attempt -> loop
                else:
                    status = "DROPPED"                      # final full: no spin/yield/credit
                    break
        packets.append((status, retries, spins, yields))
        tel['spins'] += spins
        tel['yields'] += yields
        if status == "SENT":
            tel['sent'] += 1
        elif status == "ERROR":
            tel['errors'] += 1
        elif status == "DROPPED":
            tel['dropped'] += 1

    tel['final_level'] = level
    tel['final_credits'] = credits
    return {"packets": packets, "telemetry": tel}
