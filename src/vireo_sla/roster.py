"""
Point-in-time roster lookup.

The roster has one row per assignment with from/to dates (policy s7). An agent
keeps the same agent_id across moves, so to know an agent's shift/site/team on
the day they handled a ticket we must pick the assignment row whose [from, to]
window contains that date -- not just the latest row. The June 2025 reshuffle is
exactly why this matters: the same agent_id is Night before 30 Jun and Day after.
"""
from __future__ import annotations

import csv
import datetime as dt
from dataclasses import dataclass
from pathlib import Path

_FAR_FUTURE = dt.date(2100, 1, 1)


@dataclass
class Assignment:
    agent_id: str
    name: str
    site: str
    team: str
    shift: str
    tier: str
    from_date: dt.date
    to_date: dt.date


class Roster:
    def __init__(self, assignments: list[Assignment]):
        self._by_agent: dict[str, list[Assignment]] = {}
        for a in assignments:
            self._by_agent.setdefault(a.agent_id, []).append(a)

    @classmethod
    def load(cls, path: str | Path) -> "Roster":
        out = []
        with open(path, encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                out.append(Assignment(
                    agent_id=r["agent_id"],
                    name=r["name"],
                    site=r["site"],
                    team=r["team"],
                    shift=r["shift"],
                    tier=r["tier"],
                    from_date=dt.datetime.strptime(r["from_date"], "%Y-%m-%d").date(),
                    to_date=(dt.datetime.strptime(r["to_date"], "%Y-%m-%d").date()
                             if r["to_date"].strip() else _FAR_FUTURE),
                ))
        return cls(out)

    def lookup(self, agent_id: str, on: dt.date) -> Assignment | None:
        """Assignment in force for `agent_id` on date `on` (IST date of the ticket)."""
        cands = self._by_agent.get(agent_id, [])
        for a in cands:
            if a.from_date <= on <= a.to_date:
                return a
        # Fall back to the nearest assignment so a ticket is never unattributable;
        # this covers the handful of tickets whose date sits just outside a window.
        if cands:
            return min(cands, key=lambda a: min(abs((a.from_date - on).days),
                                                abs((a.to_date - on).days)))
        return None
