"""
Build the deliverables Neha asked for, plus the fair-attribution view and the
business case. All numbers derive from `sla.evaluate` output.
"""
from __future__ import annotations

import collections
import csv
import datetime as dt
from pathlib import Path

from . import config
from .sla import Evaluated


def _rate(n, d):
    return (n / d) if d else 0.0


# --------------------------------------------------------------------------- #
# 1. Weekly breach report BY AGENT AND SHIFT  (the literal ask)               #
# --------------------------------------------------------------------------- #
def weekly_by_agent_shift(ev: list[Evaluated]) -> list[dict]:
    key = lambda e: (e.ist_week, e.t.agent_id, e.agent_name, e.agent_shift,
                     e.agent_site, e.agent_team)
    agg = collections.defaultdict(lambda: collections.Counter())
    for e in ev:
        if e.response_min is None:
            continue
        g = agg[key(e)]
        g["attended"] += 1
        g["breaches"] += int(e.breach)
        g["controllable"] += int(e.attribution == "controllable")
        g["structural"] += int(e.attribution == "structural")
    rows = []
    for (week, aid, name, shift, site, team), c in sorted(agg.items()):
        rows.append({
            "week": week, "agent_id": aid, "agent_name": name, "shift": shift,
            "site": site, "team": team,
            "attended": c["attended"], "breaches": c["breaches"],
            "breach_rate": round(_rate(c["breaches"], c["attended"]), 4),
            "controllable_breaches": c["controllable"],
            "structural_breaches": c["structural"],
            "controllable_rate": round(_rate(c["controllable"], c["attended"]), 4),
            "credit_inr": c["breaches"] * config.BREACH_CREDIT_INR,
        })
    return rows


# --------------------------------------------------------------------------- #
# 2. Shift-level summary (weekly) -- what Neha reads first                     #
# --------------------------------------------------------------------------- #
def weekly_by_shift(ev: list[Evaluated]) -> list[dict]:
    agg = collections.defaultdict(lambda: collections.Counter())
    for e in ev:
        if e.response_min is None:
            continue
        c = agg[(e.ist_week, e.agent_shift)]
        c["attended"] += 1
        c["breaches"] += int(e.breach)
        c["controllable"] += int(e.attribution == "controllable")
        c["structural"] += int(e.attribution == "structural")
    rows = []
    for (week, shift), c in sorted(agg.items()):
        rows.append({
            "week": week, "shift": shift,
            "attended": c["attended"], "breaches": c["breaches"],
            "breach_rate": round(_rate(c["breaches"], c["attended"]), 4),
            "controllable_breaches": c["controllable"],
            "structural_breaches": c["structural"],
            "credit_inr": c["breaches"] * config.BREACH_CREDIT_INR,
        })
    return rows


# --------------------------------------------------------------------------- #
# 3. Monthly credit trend -- settles the Arjun vs Priya disagreement          #
# --------------------------------------------------------------------------- #
def monthly_trend(ev: list[Evaluated]) -> list[dict]:
    agg = collections.defaultdict(lambda: collections.Counter())
    csat = collections.defaultdict(list)
    for e in ev:
        if e.t.created_ist is None:
            continue
        m = e.t.created_ist.strftime("%Y-%m")
        c = agg[m]
        c["tickets"] += 1
        if e.response_min is not None:
            c["eligible"] += 1
            c["breaches"] += int(e.breach)
            if e.t.channel == "chat":
                c["chat_eligible"] += 1
                c["chat_breaches"] += int(e.breach)
        if e.t.csat is not None:
            csat[m].append(e.t.csat)
    rows = []
    for m in sorted(agg):
        c = agg[m]
        cs = csat[m]
        rows.append({
            "month": m, "tickets": c["tickets"],
            "breaches": c["breaches"],
            "breach_rate": round(_rate(c["breaches"], c["eligible"]), 4),
            "chat_breach_rate": round(_rate(c["chat_breaches"], c["chat_eligible"]), 4),
            "sla_credit_inr": c["breaches"] * config.BREACH_CREDIT_INR,
            "csat_mean": round(sum(cs) / len(cs), 3) if cs else None,
            "csat_responses": len(cs),
        })
    return rows


# --------------------------------------------------------------------------- #
# 4. Business case                                                            #
# --------------------------------------------------------------------------- #
def business_case(ev: list[Evaluated], reshuffle_month="2025-07") -> dict:
    """
    Quantify the recoverable money. We compare the pre-reshuffle baseline breach
    rate to the current run-rate, and isolate the structural night-chat carryover
    that a cost-neutral coverage fix can remove.
    """
    def month(e):
        return e.t.created_ist.strftime("%Y-%m") if e.t.created_ist else "?"

    pre = [e for e in ev if e.response_min is not None and month(e) < reshuffle_month
           and month(e) != "?"]
    post = [e for e in ev if e.response_min is not None and month(e) >= reshuffle_month]

    def br(rows):
        b = sum(e.breach for e in rows)
        return b, len(rows), _rate(b, len(rows))

    pre_b, pre_n, pre_rate = br(pre)
    post_b, post_n, post_rate = br(post)

    # months in each window (for annualising)
    post_months = len({month(e) for e in post})

    # structural chat carryover in the post window
    chat_struct = [e for e in post if e.t.channel == "chat"
                   and e.attribution == "structural"]
    chat_ctrl = [e for e in post if e.t.channel == "chat"
                 and e.attribution == "controllable"]

    struct_credit_yr = len(chat_struct) * config.BREACH_CREDIT_INR / post_months * 12
    ctrl_credit_yr = len(chat_ctrl) * config.BREACH_CREDIT_INR / post_months * 12

    # excess credit vs baseline (what Arjun saw triple)
    post_credit_yr = post_b * config.BREACH_CREDIT_INR / post_months * 12
    baseline_rate = pre_rate
    baseline_credit_yr = baseline_rate * post_n * config.BREACH_CREDIT_INR / post_months * 12
    excess_yr = post_credit_yr - baseline_credit_yr

    return {
        "pre_window": {"breaches": pre_b, "tickets": pre_n, "rate": round(pre_rate, 4)},
        "post_window": {"breaches": post_b, "tickets": post_n, "rate": round(post_rate, 4),
                        "months": post_months},
        "annual_sla_credit_now_inr": round(post_credit_yr),
        "annual_sla_credit_at_baseline_inr": round(baseline_credit_yr),
        "annual_excess_credit_inr": round(excess_yr),
        "chat_structural_breaches_post": len(chat_struct),
        "chat_controllable_breaches_post": len(chat_ctrl),
        "recoverable_structural_credit_per_year_inr": round(struct_credit_yr),
        "recoverable_structural_credit_per_quarter_inr": round(struct_credit_yr / 4),
        "coachable_credit_per_year_inr": round(ctrl_credit_yr),
    }


# --------------------------------------------------------------------------- #
# 5. Policy-leakage side report (nobody asked; Finance will care)             #
# --------------------------------------------------------------------------- #
def policy_leakage(ev: list[Evaluated]) -> dict:
    double = [e for e in ev if e.t.replacement_issued
              and e.t.refund_amount_inr and e.t.refund_amount_inr > 0]
    return {
        "refund_and_replacement_same_ticket": len(double),
        "refund_value_at_risk_inr": round(sum(e.t.refund_amount_inr for e in double)),
        "ticket_ids": [e.t.ticket_id for e in double],
    }


# --------------------------------------------------------------------------- #
# writers                                                                      #
# --------------------------------------------------------------------------- #
def write_csv(rows: list[dict], path: str | Path):
    if not rows:
        Path(path).write_text("")
        return
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
