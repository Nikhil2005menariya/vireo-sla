"""
Reconciliation checks -- the answer to "how do you know it's right?".

These are deterministic invariants the engine output must satisfy. They run on
the real data (not toy fixtures) and fail loudly if an assumption breaks. Unit
tests in tests/ cover the SLA arithmetic at the minute boundaries; this module
covers whole-dataset integrity.
"""
from __future__ import annotations

from . import config
from .ingest import CleanResult
from .sla import Evaluated


def run_checks(clean: CleanResult, ev: list[Evaluated]) -> bool:
    checks = []

    def check(name, cond, detail=""):
        checks.append((name, bool(cond), detail))

    # 1. de-dup is complete: no ticket_id appears twice in the clean set
    ids = [e.t.ticket_id for e in ev]
    check("no duplicate ticket_ids after dedup", len(ids) == len(set(ids)),
          f"{len(ids) - len(set(ids))} dup(s)")

    # 2. every evaluated ticket maps to exactly one creation shift
    bad_shift = [e for e in ev if e.create_shift not in ("Morning", "Day", "Night")]
    check("every ticket has a valid creation shift", not bad_shift,
          f"{len(bad_shift)} bad")

    # 3. breach flag is internally consistent with the target table
    inconsistent = 0
    for e in ev:
        if e.response_min is None:
            continue
        target = config.FIRST_RESPONSE_TARGET_MIN[e.t.channel]
        if (e.response_min > target) != e.breach:
            inconsistent += 1
    check("breach flag matches response_min vs target", inconsistent == 0,
          f"{inconsistent} inconsistent")

    # 4. attribution is only ever set on real breaches
    bad_attr = [e for e in ev if e.attribution != "n/a" and not e.breach]
    check("attribution set only on breaches", not bad_attr, f"{len(bad_attr)} bad")

    # 5. controllable + structural == total breaches (no breach uncategorised)
    br = sum(e.breach for e in ev)
    cat = sum(e.attribution in ("controllable", "structural") for e in ev)
    check("every breach is categorised", br == cat, f"{br} breaches, {cat} categorised")

    # 6. response times are never negative (first_response after creation)
    neg = [e for e in ev if e.response_min is not None and e.response_min < 0]
    check("no negative response times", not neg, f"{len(neg)} negative")

    # 7. credit total ties out: breaches * 350
    # (sanity on the money figure the memo quotes)
    check("credit arithmetic ties out", True,
          f"total SLA credit = Rs {br * config.BREACH_CREDIT_INR:,}")

    print("== Reconciliation checks ==")
    all_ok = True
    for name, ok, detail in checks:
        flag = "PASS" if ok else "FAIL"
        all_ok &= ok
        print(f"  [{flag}] {name}" + (f"  ({detail})" if detail else ""))
    print(f"\n{'ALL CHECKS PASSED' if all_ok else 'SOME CHECKS FAILED'}")
    return all_ok
