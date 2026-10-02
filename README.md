# Vireo Audio — First-Response SLA Breach Report

A tool for Neha Kulkarni (Support Operations) that produces a **weekly
first-response SLA breach report by agent and shift** — and, going beyond the
literal ask, separates breaches the agent could prevent from breaches that were
already lost to overnight queue carryover, so the conversation lands on the right
people.

It also settles the question Finance and CX disagreed on in the email thread:
**the SLA credit line did not stay flat — it stepped up ~5× after the June 2025
Indore reshuffle, while CSAT barely moved.**

## The headline number

| | |
|---|---|
| First-response breach rate, H1 2025 (pre-reshuffle) | **9.3%** |
| First-response breach rate, Jul 2025 → Jun 2026 | **24.9%** |
| SLA credit line now (Rs 350 × breaches) | **~Rs 780k / year** |
| Excess vs the old baseline | **~Rs 489k / year** |
| Of that, structural **night-chat carryover** (recoverable) | **~Rs 362k / year ≈ Rs 90k / quarter** |

80% of chat breaches are created in the IST night window (22:00–06:00), where —
since the reshuffle — there is **zero chat coverage** (night-chat breach rate is
100%). The helpdesk blames the morning team for them; the median response on
those tickets is ~7 hours because nobody is online, not because anyone is slow.

Full reasoning is in [`docs/MEMO.md`](docs/MEMO.md) (the one-pager for Neha) and
[`docs/DECISIONS.md`](docs/DECISIONS.md) (what I chose to leave out, and why).

## Quick start (clean machine)

The **core report needs only Python 3.10+ — no pip install, no internet, no
keys.** Everything required ships in `data/`.

```bash
git clone <this repo> && cd vireo-sla

# 1. produce the report (deterministic, free)
PYTHONPATH=src python3 -m vireo_sla run

# 2. check the engine is correct (whole-dataset reconciliation)
PYTHONPATH=src python3 -m vireo_sla validate
```

Outputs land in `outputs/`:

| file | what |
|---|---|
| `dashboard.html` | self-contained dashboard (open in a browser; no server/CDN) |
| `weekly_breach_by_agent_shift.csv` | **the ask** — week × agent × shift, with a controllable/structural split |
| `weekly_breach_by_shift.csv` | the shift-level roll-up Neha reads first |
| `monthly_credit_trend.csv` | breach rate, SLA credit and CSAT by month (the Arjun-vs-Priya chart) |
| `business_case.json` | the money, computed from the data |
| `policy_leakage.json` | bonus: tickets with both a refund and a replacement (policy §5 breach) |

## Optional: AI issue-type tagging

For the *controllable* breaches, an LLM tags what each ticket is **about**
(delivery / payment / hardware fault / wrong item / account-app), so Neha can see
what her frontline is breaching on during staffed hours. Uses the model-agnostic
Amazon Bedrock Converse API (default model: Amazon Nova Lite).

```bash
# needs a Bedrock credential; copy .env.example to .env and fill it in
set -a; . ./.env; set +a
PYTHONPATH=src python3 -m vireo_sla run --enrich bedrock --limit 250
```

One run over 250 tickets costs **~Rs 0.48** (see cost note in the memo). The core
run above makes **zero** paid calls.

## How I know it works

- **Deterministic engine** — `python3 -m vireo_sla validate` runs 7 whole-dataset
  reconciliation checks (dedup completeness, breach flag vs target, every breach
  categorised, credit arithmetic ties out, …). All pass.
- **Unit tests** — `python3 -m pytest tests/` pins the SLA maths at the exact
  minute boundaries, the UTC→IST shift cut-offs, the carryover rule, and the
  point-in-time roster join across the June reshuffle. 9 tests, all pass.
- **AI classifier** — measured against a 25-ticket hand-labelled gold set
  (`tests/gold_issue_types.csv`): **Nova Lite 92%** vs the keyword-rules baseline
  **64%**. Run it yourself:
  ```bash
  PYTHONPATH=src python3 -m vireo_sla.validate_classifier bedrock
  ```

## Layout

```
src/vireo_sla/
  config.py      policy constants (SLA targets, costs, shifts) — single source of truth
  ingest.py      load + clean (dedup, UTC→IST, csat 0→null, flag unusable messages)
  roster.py      point-in-time roster join (handles the June shift changes)
  sla.py         breach computation + controllable/structural attribution
  report.py      the report tables + business case + policy-leakage check
  enrich.py      optional LLM issue-type tagging (Bedrock) + keyword fallback
  dashboard.py   self-contained HTML
  validate.py              whole-dataset reconciliation
  validate_classifier.py   AI classifier accuracy vs gold set
tests/           unit tests + gold label set
data/            the provided pack, renamed
```

## Design notes

- **No AI in the numbers.** The breach counts and money are pure arithmetic on
  timestamps — auditable and reproducible to the minute. AI is used only where it
  beats a deterministic baseline: reading free text (92% vs 64%).
- **Zero-dependency core** so it runs anywhere the client can run `python3`.
- Timestamps are treated as UTC and converted to IST for every shift decision
  (per Sameer's note and policy §7/§9).
