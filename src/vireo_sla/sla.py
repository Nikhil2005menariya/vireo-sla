"""
Breach computation and fair attribution.

Two things happen here:

1. `evaluate` decides, deterministically, whether each ticket breached its
   first-response target (policy s3). This is arithmetic on timestamps -- no AI,
   because the number has to be auditable and reproducible to the minute.

2. `attribute` splits each breach into CONTROLLABLE vs STRUCTURAL.

   The policy charges a breach "against the resolving agent" (s3). But a chat
   ticket created at 02:00 IST is already hours past its 15-minute target before
   any morning agent logs in -- the morning agent inherits a breach they could
   not have prevented. We therefore classify a breach as STRUCTURAL when the SLA
   deadline fell inside a window where that channel had no staffed coverage, and
   CONTROLLABLE when the deadline fell inside the resolving agent's own shift.
   Neha asked for the report "by agent and shift"; this column is what lets her
   have the conversation with the *right* people instead of a wall of red.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from . import config
from .ingest import Ticket
from .roster import Roster

# Channels that are supposed to be covered 24x7 (policy s2). For these, a breach
# whose deadline lands in an unstaffed window is structural. Email/voice/social
# are queue- or callback-based with long targets, so we only treat chat carryover
# as structural by coverage; others are structural only if created out-of-hours
# for that channel's stated service hours.
_ALWAYS_ON = {"chat", "email"}  # email accepted 24x7, worked in queue order


@dataclass
class Evaluated:
    t: Ticket
    response_min: float | None
    breach: bool
    create_shift: str          # shift the ticket was CREATED in (IST clock)
    agent_shift: str           # resolving agent's rostered shift that day
    agent_site: str
    agent_team: str
    agent_tier: str
    agent_name: str
    attribution: str           # "controllable" | "structural" | "n/a"
    ist_week: str              # ISO week label for weekly rollup


def _iso_week(d: dt.datetime) -> str:
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def evaluate(tickets: list[Ticket], roster: Roster) -> list[Evaluated]:
    out: list[Evaluated] = []
    for t in tickets:
        # response time / breach ------------------------------------------------
        if t.first_response_utc is None or t.created_utc is None:
            resp = None
            breach = False
        else:
            resp = (t.first_response_utc - t.created_utc).total_seconds() / 60.0
            target = config.FIRST_RESPONSE_TARGET_MIN.get(t.channel)
            breach = target is not None and resp > target

        create_shift = config.shift_for_hour(t.created_ist.hour) if t.created_ist else "?"

        # roster join -----------------------------------------------------------
        asg = roster.lookup(t.agent_id, t.created_ist.date()) if t.created_ist else None
        agent_shift = asg.shift if asg else "?"
        out.append(Evaluated(
            t=t,
            response_min=resp,
            breach=breach,
            create_shift=create_shift,
            agent_shift=agent_shift,
            agent_site=asg.site if asg else "?",
            agent_team=asg.team if asg else "?",
            agent_tier=asg.tier if asg else "?",
            agent_name=asg.name if asg else t.agent_id,
            attribution=_attribute(t, breach, create_shift, agent_shift),
            ist_week=_iso_week(t.created_ist) if t.created_ist else "?",
        ))
    return out


def _attribute(t: Ticket, breach: bool, create_shift: str, agent_shift: str) -> str:
    """
    Classify a breach as controllable or structural.

    Rule: a breach is CONTROLLABLE if the ticket was created during a shift that
    is staffed for that channel (so an agent was -- or should have been -- online
    to answer within target). It is STRUCTURAL if it was created in a window with
    no live coverage for that channel, so the clock ran out before anyone could
    respond. For chat (15-min target, supposedly 24x7) the Night window is the
    structural trap after the June-2025 reshuffle removed night chat staffing.
    """
    if not breach:
        return "n/a"
    # Chat: 15-minute target means only live, in-shift coverage can save it.
    if t.channel == "chat":
        return "structural" if create_shift == "Night" else "controllable"
    # Social (4h) is worked by the chat team; night creation with no cover is structural.
    if t.channel == "social":
        return "structural" if create_shift == "Night" else "controllable"
    # Voice callbacks only accepted 08:00-22:00 IST; a 2h target started late in
    # the evening can run into unstaffed hours -> structural.
    if t.channel == "voice":
        created_h = t.created_ist.hour if t.created_ist else 12
        return "structural" if created_h >= 20 or created_h < 8 else "controllable"
    # Email: 8h target, 24x7 queue. Long target means in-hours slippage is
    # genuinely controllable; treat as controllable by default.
    return "controllable"
