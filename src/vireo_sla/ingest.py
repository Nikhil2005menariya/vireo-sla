"""
Load and clean the ticket export.

Every cleaning step maps to a specific caveat raised in the email thread or the
policy, and every step is counted so the run is auditable (see `clean_tickets`
return value `.notes`). Pure Python standard library: no third-party deps, so the
core runs on a clean machine.
"""
from __future__ import annotations

import csv
import datetime as dt
from dataclasses import dataclass, field
from pathlib import Path

from . import config

# Markers that identify a failed / non-actionable IVR or intake message.
# Sameer: "About forty messages are failed IVR transcripts." We flag rather than
# drop, so breach timing is unaffected but free-text enrichment can skip them.
_UNUSABLE_MARKERS = ("[inaudible]", "[crosstalk]", "hello hello can you hear",
                     "can you hear me")
_UNUSABLE_SHORT = {"-", "...", "??", "?", "test", "."}


def _parse_ts(s: str) -> dt.datetime | None:
    s = (s or "").strip()
    if not s:
        return None
    # timestamps look like "2025-01-01 06:12" (minute precision)
    return dt.datetime.strptime(s[:16], "%Y-%m-%d %H:%M")


@dataclass
class Ticket:
    ticket_id: str
    created_utc: dt.datetime
    first_response_utc: dt.datetime | None
    resolved_utc: dt.datetime | None
    status: str
    channel: str
    customer_id: str
    order_id: str
    product_sku: str
    category: str
    priority: str
    assigned_team: str
    agent_id: str
    transfers: str
    csat: int | None          # None = no response (blank OR legacy 0)
    refund_amount_inr: float | None
    refund_reason_code: str
    replacement_issued: bool
    customer_message: str
    agent_notes: str
    source_system: str
    usable_message: bool = True

    # derived (filled by sla.py); kept here so the type is one object end-to-end
    created_ist: dt.datetime = field(default=None)
    first_response_ist: dt.datetime = field(default=None)


@dataclass
class CleanResult:
    tickets: list[Ticket]
    notes: dict  # audit counters


def _to_ist(utc: dt.datetime | None) -> dt.datetime | None:
    return None if utc is None else utc + config.IST_OFFSET


def _is_usable(msg: str) -> bool:
    m = (msg or "").strip().lower()
    if m in _UNUSABLE_SHORT or len(m) < 3:
        return False
    return not any(k in m for k in _UNUSABLE_MARKERS)


def load_raw(path: str | Path) -> list[dict]:
    with open(path, encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def clean_tickets(path: str | Path) -> CleanResult:
    raw = load_raw(path)
    notes = {"raw_rows": len(raw)}

    # --- de-duplicate migration re-imports (policy s9 + Sameer) ---------------
    # A ticket_id can appear twice: once helpdesk, once legacy_fd. The current
    # helpdesk is authoritative, so keep it and drop the legacy twin.
    groups: dict[str, list[dict]] = {}
    for r in raw:
        groups.setdefault(r["ticket_id"], []).append(r)
    deduped = []
    dup_dropped = 0
    for rows in groups.values():
        if len(rows) == 1:
            deduped.append(rows[0])
            continue
        hd = [x for x in rows if x["source_system"] == "helpdesk"]
        keep = hd[0] if hd else rows[0]
        deduped.append(keep)
        dup_dropped += len(rows) - 1
    notes["duplicate_rows_dropped"] = dup_dropped
    notes["unique_tickets"] = len(deduped)

    tickets: list[Ticket] = []
    csat_zeroed = 0
    unusable = 0
    missing_fr = 0
    for r in deduped:
        # csat: blank OR legacy 0 both mean "no response" -> None (policy s8)
        cs_raw = (r.get("csat_score") or "").strip()
        if cs_raw == "" or cs_raw == "0":
            csat = None
            if cs_raw == "0":
                csat_zeroed += 1
        else:
            csat = int(cs_raw)

        refund = (r.get("refund_amount_inr") or "").strip()
        refund_val = float(refund) if refund else None

        created = _parse_ts(r["created_at"])
        fr = _parse_ts(r["first_response_at"])
        if fr is None:
            missing_fr += 1
        usable = _is_usable(r.get("customer_message", ""))
        if not usable:
            unusable += 1

        t = Ticket(
            ticket_id=r["ticket_id"],
            created_utc=created,
            first_response_utc=fr,
            resolved_utc=_parse_ts(r.get("resolved_at", "")),
            status=r["status"],
            channel=r["channel"],
            customer_id=r["customer_id"],
            order_id=r.get("order_id", ""),
            product_sku=r.get("product_sku", ""),
            category=r.get("category", ""),
            priority=r.get("priority", ""),
            assigned_team=r.get("assigned_team", ""),
            agent_id=r.get("agent_id", ""),
            transfers=r.get("transfers", ""),
            csat=csat,
            refund_amount_inr=refund_val,
            refund_reason_code=r.get("refund_reason_code", ""),
            replacement_issued=(r.get("replacement_issued", "N") == "Y"),
            customer_message=r.get("customer_message", ""),
            agent_notes=r.get("agent_notes", ""),
            source_system=r.get("source_system", ""),
            usable_message=usable,
            created_ist=_to_ist(created),
            first_response_ist=_to_ist(fr),
        )
        tickets.append(t)

    notes["csat_legacy_zero_to_null"] = csat_zeroed
    notes["unusable_messages_flagged"] = unusable
    notes["missing_first_response"] = missing_fr
    return CleanResult(tickets=tickets, notes=notes)
