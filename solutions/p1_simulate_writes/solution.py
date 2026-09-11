"""Problem 1: simulate_writes — SUBMISSION SOLUTION.

Standard library only, no I/O. Defines simulate_writes(...).

Complexity trap: max_retries <= 1e18 and outcome run counts <= 1e18, so a single
packet can schedule astronomically many retries on a run of "full" outcomes. A
literal per-attempt loop is O(sum of attempts) and TLEs. Key observations that
make O(1) batching possible within a run of "full":

  * The congestion level only rises on "full" and is capped at level_cap (<= 60).
    Within one packet it climbs monotonically, so there are at most 60 distinct
    "climb" steps with varying cost; we simulate those individually.
  * Once level == level_cap, old_level is constant, so cost = min(2**level_cap,
    spin_limit) is constant and the per-retry yield flag is constant. A block of
    k constant-cost retries is pure arithmetic: retries+=k, credits-=k*cost,
    spins+=k*cost, yields+=k*(2**level_cap>spin_limit). We take the largest k
    allowed by (max_retries-retries), (credits//cost) and (fulls left in run).

Total work: O(60) climb per packet + O(1) per (packet, run) touch. A packet only
advances to the next run when it exhausts the current one, so (packet, run)
touches sum to O(#packets + #runs).
"""


def simulate_writes(lengths, outcomes, max_retries, level_cap, spin_limit,
                    initial_credits, credit_cap):
    level = 0
    credits = initial_credits
    packets = []
    sent = dropped = errors = invalid = 0
    attempts = 0
    spins_total = 0
    yields_total = 0

    run_idx = 0
    run_off = 0
    nruns = len(outcomes)

    cost_cap = None  # min(2**level_cap, spin_limit); cached lazily

    for L in lengths:
        if not (1 <= L <= 65535):
            packets.append(("INVALID", 0, 0, 0))
            invalid += 1
            continue

        retries = 0
        spins = 0
        yields = 0
        status = None

        while status is None:
            if run_idx >= nruns:
                # implicit error (unlimited) — one attempt, resets level, ends packet
                attempts += 1
                level = 0
                status = "ERROR"
                break

            kind, cnt = outcomes[run_idx]

            if kind == "ok":
                attempts += 1
                run_off += 1
                if run_off == cnt:
                    run_idx += 1
                    run_off = 0
                level = level - 1 if level > 0 else 0
                credits += L
                if credits > credit_cap:
                    credits = credit_cap
                status = "SENT"
                break

            if kind == "error":
                attempts += 1
                run_off += 1
                if run_off == cnt:
                    run_idx += 1
                    run_off = 0
                level = 0
                status = "ERROR"
                break

            # kind == "full": batch across this run
            remaining = cnt - run_off
            consumed = 0

            while remaining > 0 and status is None:
                old_level = level
                if old_level < level_cap:
                    # individual climb step (at most 60 per packet total)
                    cost = 1 << old_level
                    if cost > spin_limit:
                        cost = spin_limit
                    level = old_level + 1  # min(level_cap, old_level+1)
                    if retries < max_retries and credits >= cost:
                        retries += 1
                        credits -= cost
                        spins += cost
                        if (1 << old_level) > spin_limit:
                            yields += 1
                        consumed += 1
                        remaining -= 1
                    else:
                        consumed += 1
                        remaining -= 1
                        status = "DROPPED"
                else:
                    # constant-cost phase at level_cap
                    if cost_cap is None:
                        cc = 1 << level_cap
                        cost_cap = cc if cc <= spin_limit else spin_limit
                    cost = cost_cap
                    yield_each = (1 << level_cap) > spin_limit
                    if retries >= max_retries or credits < cost:
                        # this full drops immediately; level stays at cap
                        consumed += 1
                        remaining -= 1
                        status = "DROPPED"
                        break
                    n_ret = max_retries - retries
                    n_cred = credits // cost
                    n = n_ret if n_ret < n_cred else n_cred
                    if remaining < n:
                        n = remaining
                    retries += n
                    credits -= n * cost
                    spins += n * cost
                    if yield_each:
                        yields += n
                    consumed += n
                    remaining -= n
                    if remaining == 0:
                        break  # run exhausted, packet continues on next run
                    # another full remains but we can no longer retry -> it drops
                    consumed += 1
                    remaining -= 1
                    status = "DROPPED"
                    break

            # advance cursor over consumed fulls (stays within this run)
            attempts += consumed
            run_off += consumed
            if run_off == cnt:
                run_idx += 1
                run_off = 0
            # if status still None here, run exhausted -> outer loop reads next run

        packets.append((status, retries, spins, yields))
        spins_total += spins
        yields_total += yields
        if status == "SENT":
            sent += 1
        elif status == "ERROR":
            errors += 1
        else:
            dropped += 1

    telemetry = {
        "sent": sent, "dropped": dropped, "errors": errors, "invalid": invalid,
        "attempts": attempts, "spins": spins_total, "yields": yields_total,
        "final_level": level, "final_credits": credits,
    }
    return {"packets": packets, "telemetry": telemetry}
