"""
AI enrichment -- root-cause tagging of CONTROLLABLE breaches from free text.

Design principle: AI is used only where it earns its place. The breach numbers
themselves are never produced by a model -- that is deterministic arithmetic in
sla.py. What a model is genuinely good at is reading the agent's closing note and
the customer's opening message and saying *why* an in-shift breach happened, so
Neha walks into a coaching conversation with a reason, not just a red cell.

Two backends:
  * "rules"  -- a transparent keyword classifier. Zero cost, zero dependencies,
                runs on a clean machine. This is the DEFAULT so the tool works
                for anyone with no API key.
  * "claude" -- Claude Haiku 4.5 on Amazon Bedrock for higher-quality tags on
                ambiguous notes. Opt-in; needs boto3 + a Bedrock credential
                (AWS_BEARER_TOKEN_BEDROCK or standard AWS creds) and AWS_REGION.

Both return the same schema, so downstream code and validation don't care which
ran. `estimate_cost` reports what a Claude run would cost at Vireo's volume.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass

# Issue-type taxonomy. We tag WHAT the controllable breach is about -- which the
# free text actually supports -- rather than why the reply was late, which the
# notes do not record. This tells Neha which ticket types her frontline is
# breaching on during staffed hours (e.g. hardware/warranty cases are multi-touch
# and may be mis-routed to Tier 1).
CAUSES = [
    "delivery_logistics",     # not delivered, tracking, lost in transit, address
    "wrong_or_damaged_item",  # wrong item, DOA, damaged on arrival
    "payment_billing",        # refund delay, duplicate/failed payment, invoice, coupon
    "hardware_fault",         # audio/battery/pairing faults, repair/RMA/warranty
    "account_app",            # login, app crashes/bugs, OTP
    "other",                  # none of the above / too thin to tell
]

_RULES = [
    ("payment_billing",       r"\b(refund|payment|invoice|coupon|promo|gst|duplicate|utr|charged|txn|gateway)\b"),
    ("delivery_logistics",    r"\b(deliver|tracking|courier|awb|transit|shipping|address|dispatch|not received|lost)\b"),
    ("wrong_or_damaged_item", r"\b(wrong item|wrong colour|wrong color|not what|incorrect product|damaged|doa|dead on arrival)\b"),
    ("hardware_fault",        r"\b(batter|audio|pairing|sound|rma|warranty|repair|charg|distort|bt |bluetooth|no audio)\b"),
    ("account_app",           r"\b(login|log in|app|otp|account|loading screen|reinstall|update failed|crash)\b"),
]


@dataclass
class Enrichment:
    ticket_id: str
    cause: str
    backend: str


def _rule_classify(customer_msg: str, agent_notes: str) -> str:
    text = f"{customer_msg}\n{agent_notes}".lower()
    for cause, pat in _RULES:
        if re.search(pat, text):
            return cause
    return "other"


def classify_rules(tickets) -> list[Enrichment]:
    return [Enrichment(t.ticket_id, _rule_classify(t.customer_message, t.agent_notes),
                       "rules") for t in tickets]


# --------------------------------------------------------------------------- #
# Bedrock backend (opt-in)                                                     #
# --------------------------------------------------------------------------- #
# We use the model-agnostic Bedrock Converse API, so the model is swappable via
# BEDROCK_MODEL_ID. Default is Amazon Nova Lite: a first-party Amazon model that
# bills through normal AWS (no AWS Marketplace subscription / payment instrument,
# which Anthropic-on-Bedrock requires and which this account does not have).
_SYSTEM = (
    "You categorise a customer-support ticket by the TYPE of issue it is about, "
    "based on the customer's message and the agent's closing note. "
    f"Reply with exactly one label from this list: {', '.join(CAUSES)}. "
    "Use 'other' only if none fit. Reply with the label only, nothing else."
)

BEDROCK_MODEL = os.environ.get("BEDROCK_MODEL_ID", "amazon.nova-lite-v1:0")


def classify_bedrock(tickets, model=BEDROCK_MODEL, region=None) -> list[Enrichment]:
    """Classify via the Bedrock Converse API (boto3, bearer-token auth)."""
    try:
        import boto3
    except ImportError as e:  # pragma: no cover
        raise RuntimeError("pip install boto3 to use the Bedrock backend") from e
    region = region or os.environ.get("AWS_REGION", "us-east-1")
    rt = boto3.client("bedrock-runtime", region_name=region)
    valid = set(CAUSES)
    out = []
    for t in tickets:
        resp = rt.converse(
            modelId=model,
            system=[{"text": _SYSTEM}],
            messages=[{"role": "user", "content": [{"text":
                       f"Customer: {t.customer_message[:500]}\n"
                       f"Agent note: {t.agent_notes[:500]}"}]}],
            inferenceConfig={"maxTokens": 12, "temperature": 0},
        )
        raw = resp["output"]["message"]["content"][0]["text"].strip().lower()
        # the model may wrap the label in punctuation/words; match the first cause
        label = next((c for c in valid if c in raw), "unclear")
        out.append(Enrichment(t.ticket_id, label, "bedrock"))
    return out


def enrich(tickets, backend="rules", **kw) -> list[Enrichment]:
    return classify_bedrock(tickets, **kw) if backend == "bedrock" else classify_rules(tickets)


# --------------------------------------------------------------------------- #
# cost model                                                                   #
# --------------------------------------------------------------------------- #
def estimate_cost(n_tickets: int, usd_to_inr: float = 88.0) -> dict:
    """
    Amazon Nova Lite on Bedrock (us-east-1): $0.06 / 1M input, $0.24 / 1M output.
    Each call: ~350 input tokens (system + two truncated fields) + ~3 output.
    We only enrich CONTROLLABLE breaches, not every ticket.
    """
    in_tok, out_tok = 350, 3
    in_price, out_price = 0.06 / 1e6, 0.24 / 1e6
    per_call_usd = in_tok * in_price + out_tok * out_price
    return {
        "per_ticket_usd": round(per_call_usd, 6),
        "per_ticket_inr": round(per_call_usd * usd_to_inr, 4),
        "n_tickets": n_tickets,
        "total_usd": round(per_call_usd * n_tickets, 4),
        "total_inr": round(per_call_usd * n_tickets * usd_to_inr, 2),
    }
