"""
Single source of truth for every policy constant used in the report.

Everything here is lifted directly from support-policy.pdf v3.2 (section numbers
in comments) so that an analyst can audit the numbers against the policy without
reading the code. If the policy changes, change it here and nowhere else.
"""
from __future__ import annotations
from datetime import timedelta

# --- Section 3: First-response targets (minutes from ticket creation) ----------
FIRST_RESPONSE_TARGET_MIN = {
    "chat": 15,
    "voice": 120,   # voice callback 2 hours
    "social": 240,  # 4 hours
    "email": 480,   # 8 hours
}

# --- Section 3: breach credit -------------------------------------------------
# Every missed first-response target issues a store credit on resolution,
# charged to the SLA credit line in the support P&L.
BREACH_CREDIT_INR = 350

# --- Section 4: cost standards (FY26 planning) --------------------------------
COST_PER_CONTACT_INR = {"chat": 210, "email": 260, "voice": 520, "social": 240}
BLENDED_COST_PER_CONTACT_INR = 290
COST_PER_TRANSFER_INR = 305
AGENT_COST_PER_HOUR_INR = 165
SHIFT_HOURS = 8

# --- Section 7: shifts, defined in IST ----------------------------------------
# Morning 06:00-14:00, Day 14:00-22:00, Night 22:00-06:00
IST_OFFSET = timedelta(hours=5, minutes=30)  # export is UTC (README + Sameer's email)


def shift_for_hour(ist_hour: int) -> str:
    """Return the shift name for an IST hour (0-23)."""
    if 6 <= ist_hour < 14:
        return "Morning"
    if 14 <= ist_hour < 22:
        return "Day"
    return "Night"


# --- Section 9: systems -------------------------------------------------------
HELPDESK_GO_LIVE = "2025-09-14"   # tickets before this were migrated from Freshdesk

# --- Section 5: refund reason codes (for the policy-leakage side report) -------
REFUND_REASON_CODES = {
    "GW-OTHER": "Goodwill / Other",
    "DOA-REPL": "Dead on arrival, refund chosen",
    "LOST-TRANSIT": "Lost or undelivered",
    "DUP-PAYMENT": "Duplicate or failed payment",
    "CANCEL": "Cancellation before dispatch",
    "PRICE-ADJ": "Price or coupon adjustment",
    "RETURN-QC-OK": "Return received and passed QC",
    "WTY-BUYBACK": "Warranty buy-back",
}

# Channels whose first response is a human agent reply we can hold an agent to.
# (All four channels have a target in section 3.)
SLA_CHANNELS = set(FIRST_RESPONSE_TARGET_MIN)
