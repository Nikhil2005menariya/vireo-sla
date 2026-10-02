# Memo — First-response SLA breaches: who, which shift, and the part they can't control

**To:** Neha Kulkarni, Support Operations Manager
**From:** Vendor evaluation team
**Re:** The weekly breach report you asked for — plus what the numbers say about the credit line

---

You asked for a breach report by agent and shift, weekly, so you can have the
conversation with the right people. You have it (`weekly_breach_by_agent_shift.csv`,
and the dashboard). But before you walk into those conversations, one thing in the
data changes who the "right people" are.

## 1. The breach rate didn't drift up — it stepped up, in July 2025

From January to June 2025, first-response breaches ran at **9.3%**. From July 2025
onward they run at **24.9%** and have stayed there. That is not a gradual slide; it
is a step, and it lines up exactly with the **Indore reshuffle at the end of June**.

This settles the disagreement in the thread. Arjun is right that the SLA credit
line roughly tripled — in fact it went from about **Rs 24k/month to about
Rs 65k/month**, call it **5×**. Priya is right too, but only about the window she's
looking at: since July it *has* been flat — flat at the new, higher level. And the
thing Priya thought moved, CSAT, barely moved at all (it sits around 3.3–3.4
throughout). **What moved was the breach credit line, and it moved in July 2025.**

At today's run-rate the SLA credit line is about **Rs 780,000 a year**. About
**Rs 489,000 of that is new** since the reshuffle.

## 2. Most of the "morning team" breaches were lost before the morning team arrived

You said the morning team is the bulk of the breaches. That's true in the raw
report — but it's misleading, and it matters for who you talk to.

Chat has a 15-minute first-response target and is meant to be 24×7. After the June
reshuffle, the Indore **night** chat desk is gone — the roster shows those agents
moved to day shifts, and **no one replaced them on nights**. The proof is stark:
**every single chat ticket created in the night window (22:00–06:00 IST) breaches —
a 100% breach rate overnight.** Those tickets then sit in the queue until the
morning team logs in at 06:00 and gets recorded as the "resolving agent", so the
breach is charged to them. The typical first response on these is about **7 hours**
— not a slow agent, an empty chair.

So of the chat breaches since July:

- **~80% are structural** — created overnight, already breached before anyone was
  on shift. The morning team cannot prevent these.
- **~20% are controllable** — created during a staffed shift and still missed.
  These are the ones worth a coaching conversation.

The report now carries this split in two columns (`controllable_breaches`,
`structural_breaches`). Priya asked you not to build "a wall of red" the morning
team can't act on — this is how you avoid it: hold the team to the controllable
column, and route the structural column to whoever owns the night roster.

## 3. The number, and the fix that fits the headcount freeze

The structural night-chat carryover is worth about **Rs 362,000 a year in SLA
credits (~Rs 90,000 a quarter)** on its own — roughly three-quarters of the excess
since the reshuffle.

Night chat volume is tiny: about **2.8 tickets a night**. You do not need to hire
to cover it — Arjun has frozen headcount, and that's fine, because the reshuffle
that *removed* night cover was itself "cost-neutral". Reinstating a minimal
overnight chat presence (one seat, reallocated from the now-overstaffed morning
chat pool, or an explicit overflow rule) is the same cost-neutral move in reverse.

**The goal, stated as a number:** restore overnight chat cover and bring the chat
breach rate from ~27% back toward the single-digit level it held in H1 2025,
recovering on the order of **Rs 362k/year (Rs 90k/quarter)** in SLA credits — at
no net headcount cost.

## 4. For the coaching conversations: what the controllable breaches are about

For the ~20% that *are* controllable, the tool reads each ticket's text and tags
what it's about. The largest group is **hardware faults** (battery, audio,
pairing) — about 30% of controllable breaches. Per your own policy, hardware and
warranty cases are Tier-2, multi-touch work; if they are landing as first-contact
breaches on the Tier-1 frontline, that points at **routing**, not effort. Payment
and delivery queries make up most of the rest. This is the material for a targeted
conversation, not a blanket one.

## 5. One thing for Finance, unasked

Six tickets carry **both a refund and a replacement on the same order** — which
policy §5 forbids — totalling about **Rs 14,000**. IDs are in
`policy_leakage.json`. Small, but it's the kind of leak Arjun asked about, so it's
flagged.

---

### What this costs to run

The report itself costs nothing to produce — it's arithmetic, runs on a laptop,
no external services. The optional AI tagging of controllable breaches costs about
**Rs 0.50 to tag 250 tickets** (~Rs 0.002 each). At Vireo's ~650 tickets/week,
tagging only the controllable breaches would be **well under Rs 5 a week**.

### What to be cautious about

The breach counts are exact. The "controllable vs structural" split rests on one
defensible judgement — that a chat ticket created overnight was unpreventable —
which is documented and easy to change if your coverage assumptions differ. The
AI tags are ~92% accurate on a hand-checked sample; treat them as a guide to
themes, not gospel on any single ticket.
