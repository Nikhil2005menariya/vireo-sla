"""
Measure the issue-type classifier against a hand-labelled gold set.

The gold set (tests/gold_issue_types.csv) was labelled by reading the actual
customer message and agent note for each ticket. We report accuracy and a
confusion matrix for whichever backend is requested, so the LLM tags come with
a measured error rate rather than a vibe.

  python -m vireo_sla.validate_classifier rules
  python -m vireo_sla.validate_classifier bedrock   # needs AWS creds
"""
from __future__ import annotations

import csv
import sys
from collections import Counter, defaultdict
from pathlib import Path

from . import enrich
from .ingest import clean_tickets

ROOT = Path(__file__).resolve().parents[2]


def load_gold(path: Path) -> dict[str, str]:
    with open(path, encoding="utf-8") as fh:
        return {r["ticket_id"]: r["gold_label"] for r in csv.DictReader(fh)}


def main(backend="rules"):
    gold = load_gold(ROOT / "tests" / "gold_issue_types.csv")
    clean = clean_tickets(ROOT / "data" / "tickets.csv")
    by_id = {t.ticket_id: t for t in clean.tickets}
    tickets = [by_id[tid] for tid in gold if tid in by_id]

    preds = {e.ticket_id: e.cause for e in enrich.enrich(tickets, backend=backend)}

    correct = 0
    confusion = defaultdict(Counter)
    misses = []
    for tid, g in gold.items():
        p = preds.get(tid, "?")
        confusion[g][p] += 1
        if p == g:
            correct += 1
        else:
            misses.append((tid, g, p))

    n = len(gold)
    print(f"== Classifier validation: backend={backend}, n={n} ==")
    print(f"accuracy: {correct}/{n} = {correct/n:.0%}\n")
    print("misclassifications (ticket, gold -> predicted):")
    for tid, g, p in misses:
        print(f"  {tid}  {g} -> {p}")
    print("\nby gold label (correct/total):")
    for g in sorted(confusion):
        tot = sum(confusion[g].values())
        print(f"  {g:24} {confusion[g][g]}/{tot}")
    return correct / n


if __name__ == "__main__":
    backend = sys.argv[1] if len(sys.argv) > 1 else "rules"
    main(backend)
