# Decisions & scope — what I chose, and what I left out

The brief says there is more here than fits in five hours, on purpose, and that
what I leave out (and whether I can say why) matters as much as what I build. So
here is the ledger.

## Decisions I made (and why)

1. **UTC → IST for every shift decision.** The export is UTC (Sameer, policy §9);
   shifts are defined in IST (policy §7). IST = UTC+5:30 is applied before any
   shift or "night window" logic. Getting this wrong would move ~15% of tickets
   into the wrong shift.

2. **Dedup rule: keep `helpdesk`, drop the `legacy_fd` twin.** 616 ticket_ids
   appear twice (migration re-import). The current helpdesk is authoritative
   (policy §9), so its row wins. Verified the pairs are otherwise identical.

3. **csat: blank *and* legacy `0` both mean "no response" → null.** Policy §8 is
   explicit. Treating 0 as a real score would drag every average down.

4. **The report attributes breaches two ways, not one.** Policy §3 says breaches
   are charged to the *resolving* agent, and the raw report does that. But I added
   a **controllable vs structural** split, because the literal attribution blames
   the morning team for overnight carryover they can't prevent — which is exactly
   what Priya flagged and what makes the report usable. This is the one real
   judgement call in the tool; it's isolated in `sla._attribute()` and easy to
   retune.

5. **"Structural" = created in an unstaffed window for that channel.** For chat
   that's the IST night window (no night cover post-reshuffle). For voice it's
   outside the 08:00–22:00 callback window. This is a defensible proxy, not ground
   truth — documented so the client can disagree with the boundary.

6. **AI tags *issue type*, not "breach cause".** My first cut tried to classify
   *why* a ticket breached. The agent notes don't record that — they describe the
   resolution — so the model was guessing (it over-assigned "high backlog", which
   the notes never mention). I pivoted to what the text actually supports: the
   issue type. That change took the classifier from guesswork to 92% accuracy.

7. **No LLM in the numbers.** The breach count and the money are arithmetic. Using
   a model for them would make them unauditable and non-reproducible, for no gain.

## What I deliberately left out (and why that, not something else)

- **Handle-time / resolution-time analysis and Tier-2 day-based metrics.** Policy
  §6 is explicit that Tier-2 is measured on resolution days, not tickets, and must
  not be compared to Tier-1 on volume. Neha asked specifically about
  *first-response* SLA, so I scoped to that and left Tier-2 productivity alone
  rather than build a metric the policy warns against.

- **The legacy monetary-unit conversion.** Policy §9 says the legacy tool stored
  money in its own unit. I checked: it doesn't affect my headline number, because
  the SLA credit is a flat Rs 350 per breach that I compute myself — I never rely
  on the exported `refund_amount` for the credit line. So I flagged the caveat but
  didn't build a converter I don't need. (The one place refund amounts appear —
  the policy-leakage side check — is explicitly "bonus" and low-stakes.)

- **CSAT driver modelling.** Priya raised CSAT; I checked it moved very little and
  said so, but I didn't build a CSAT model — it's not what Neha asked for and the
  data says it isn't the story.

- **A live/served dashboard, auth, scheduling, a database.** A static self-
  contained HTML file answers the question today. A server is scope the brief
  didn't ask for and I can't justify in the time.

- **Enriching all breaches with the LLM.** I tag only *controllable* breaches
  (the coachable ones). Tagging the 80% structural ones adds cost for no decision
  value — their issue is coverage, not content.

## Things I know are rough

- The controllable/structural boundary is a single rule, not a learned model. It's
  right for chat (the dominant case) and defensible elsewhere; email in-hours is
  assumed controllable, which could over-count a little.
- Enrichment runs tickets sequentially (~0.85s each). Fine at Vireo's volume;
  Bedrock batch or threads would be the move at 10×.
- The AI tags are 92% on 25 hand-labelled tickets — a small gold set. It's enough
  to show the LLM beats the keyword baseline (64%) and where it errs, not enough
  to quote three significant figures.
