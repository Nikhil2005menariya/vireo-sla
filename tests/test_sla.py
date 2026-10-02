"""
Unit tests for the deterministic engine. Run: pytest -q  (from repo root)

These pin the SLA arithmetic at the exact minute boundaries from policy s3, the
UTC->IST shift assignment, and the carryover attribution rule. If any of these
move, a breach count in the memo would be wrong -- so they are the first line of
defence, ahead of the whole-dataset reconciliation in validate.py.
"""
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from vireo_sla import config
from vireo_sla.ingest import Ticket, _is_usable
from vireo_sla.roster import Roster, Assignment
from vireo_sla.sla import evaluate


def _mk(channel, created, first_resp, agent_id="A1"):
    c = dt.datetime.fromisoformat(created)
    fr = dt.datetime.fromisoformat(first_resp)
    t = Ticket(
        ticket_id="T", created_utc=c, first_response_utc=fr, resolved_utc=None,
        status="resolved", channel=channel, customer_id="C", order_id="", product_sku="",
        category="", priority="Normal", assigned_team="", agent_id=agent_id, transfers="0",
        csat=None, refund_amount_inr=None, refund_reason_code="", replacement_issued=False,
        customer_message="hi", agent_notes="note", source_system="helpdesk",
        created_ist=c + config.IST_OFFSET, first_response_ist=fr + config.IST_OFFSET)
    return t


def _roster(shift="Morning"):
    return Roster([Assignment("A1", "Agent", "Bengaluru", "Chat Frontline", shift,
                              "1", dt.date(2024, 1, 1), dt.date(2100, 1, 1))])


# --- breach boundary: chat target is 15 minutes -----------------------------
def test_chat_exactly_at_target_is_not_breach():
    ev = evaluate([_mk("chat", "2025-03-01T06:00", "2025-03-01T06:15")], _roster())[0]
    assert ev.response_min == 15 and ev.breach is False

def test_chat_one_minute_over_is_breach():
    ev = evaluate([_mk("chat", "2025-03-01T06:00", "2025-03-01T06:16")], _roster())[0]
    assert ev.breach is True

def test_email_eight_hour_boundary():
    on = evaluate([_mk("email", "2025-03-01T00:00", "2025-03-01T08:00")], _roster())[0]
    over = evaluate([_mk("email", "2025-03-01T00:00", "2025-03-01T08:01")], _roster())[0]
    assert on.breach is False and over.breach is True


# --- UTC -> IST shift assignment (IST = UTC + 5:30) --------------------------
def test_creation_shift_uses_ist_clock():
    # 02:00 UTC == 07:30 IST -> Morning
    ev = evaluate([_mk("chat", "2025-03-01T02:00", "2025-03-01T02:10")], _roster())[0]
    assert ev.create_shift == "Morning"

def test_night_window_is_ist_2200_to_0600():
    # 18:00 UTC == 23:30 IST -> Night
    ev = evaluate([_mk("chat", "2025-03-01T18:00", "2025-03-01T18:10")], _roster())[0]
    assert ev.create_shift == "Night"


# --- carryover attribution ---------------------------------------------------
def test_night_chat_breach_is_structural():
    # created 23:30 IST, answered next morning -> structural (unstaffed overnight)
    ev = evaluate([_mk("chat", "2025-03-01T18:00", "2025-03-02T01:00")], _roster())[0]
    assert ev.breach and ev.attribution == "structural"

def test_daytime_chat_breach_is_controllable():
    # created 10:00 IST (04:30 UTC), answered 40 min later -> controllable
    ev = evaluate([_mk("chat", "2025-03-01T04:30", "2025-03-01T05:10")], _roster())[0]
    assert ev.breach and ev.attribution == "controllable"


# --- point-in-time roster join (the June reshuffle) --------------------------
def test_roster_respects_from_to_dates():
    r = Roster([
        Assignment("A1", "X", "Indore", "Chat Frontline", "Night", "1",
                   dt.date(2025, 1, 1), dt.date(2025, 6, 29)),
        Assignment("A1", "X", "Indore", "Chat Frontline", "Day", "1",
                   dt.date(2025, 6, 30), dt.date(2100, 1, 1)),
    ])
    before = r.lookup("A1", dt.date(2025, 6, 1))
    after = r.lookup("A1", dt.date(2025, 7, 1))
    assert before.shift == "Night" and after.shift == "Day"


# --- unusable-message detection ---------------------------------------------
def test_unusable_messages():
    assert _is_usable("[IVR transcript] [inaudible] ... refund") is False
    assert _is_usable("...") is False
    assert _is_usable("left side has no audio at all") is True
