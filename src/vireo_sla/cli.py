"""
Command-line entry point.

  python -m vireo_sla run                  # deterministic core, writes outputs/, free
  python -m vireo_sla run --enrich bedrock # + LLM root-cause tags on controllable
                                           #   breaches (Amazon Nova Lite, ~paise each)
  python -m vireo_sla validate             # reconciliation checks on the engine

The core run makes zero paid API calls. Only --enrich bedrock touches AWS.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import config, enrich, report
from .dashboard import render_dashboard
from .ingest import clean_tickets
from .roster import Roster
from .sla import evaluate

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
OUT = ROOT / "outputs"


def _load(data_dir: Path):
    clean = clean_tickets(data_dir / "tickets.csv")
    roster = Roster.load(data_dir / "agents.csv")
    ev = evaluate(clean.tickets, roster)
    return clean, ev


def cmd_run(args):
    data_dir = Path(args.data) if args.data else DATA
    OUT.mkdir(exist_ok=True)
    clean, ev = _load(data_dir)

    print("== Ingest ==")
    for k, v in clean.notes.items():
        print(f"  {k}: {v}")

    # core report tables -------------------------------------------------------
    report.write_csv(report.weekly_by_agent_shift(ev), OUT / "weekly_breach_by_agent_shift.csv")
    report.write_csv(report.weekly_by_shift(ev), OUT / "weekly_breach_by_shift.csv")
    trend = report.monthly_trend(ev)
    report.write_csv(trend, OUT / "monthly_credit_trend.csv")

    bc = report.business_case(ev)
    leak = report.policy_leakage(ev)
    (OUT / "business_case.json").write_text(json.dumps(bc, indent=2))
    (OUT / "policy_leakage.json").write_text(json.dumps(leak, indent=2))

    print("\n== Business case ==")
    print(f"  pre-reshuffle breach rate : {bc['pre_window']['rate']:.1%}")
    print(f"  current breach rate       : {bc['post_window']['rate']:.1%}")
    print(f"  annual SLA credit now     : Rs {bc['annual_sla_credit_now_inr']:,}")
    print(f"  annual excess vs baseline : Rs {bc['annual_excess_credit_inr']:,}")
    print(f"  recoverable (night chat)  : Rs {bc['recoverable_structural_credit_per_year_inr']:,}/yr "
          f"(Rs {bc['recoverable_structural_credit_per_quarter_inr']:,}/qtr)")

    # optional AI enrichment ---------------------------------------------------
    enrich_rows = None
    if args.enrich:
        controllable = [e.t for e in ev
                        if e.attribution == "controllable" and e.t.usable_message]
        if args.limit:
            controllable = controllable[: args.limit]
        cost = enrich.estimate_cost(len(controllable))
        print(f"\n== Enrichment ({args.enrich}) on {len(controllable)} controllable breaches ==")
        if args.enrich == "bedrock":
            print(f"  est. Bedrock cost: Rs {cost['total_inr']:.2f} (${cost['total_usd']:.4f})")
        tags = enrich.enrich(controllable, backend=args.enrich)
        enrich_rows = [{"ticket_id": t.ticket_id, "cause": t.cause, "backend": t.backend}
                       for t in tags]
        report.write_csv(enrich_rows, OUT / "controllable_root_causes.csv")
        from collections import Counter
        for cause, n in Counter(t.cause for t in tags).most_common():
            print(f"    {cause:22} {n}")

    render_dashboard(trend, report.weekly_by_shift(ev), bc, leak,
                     enrich_rows, OUT / "dashboard.html")
    print(f"\nWrote outputs to {OUT}/  (open dashboard.html)")


def cmd_validate(args):
    from .validate import run_checks
    data_dir = Path(args.data) if args.data else DATA
    clean, ev = _load(data_dir)
    ok = run_checks(clean, ev)
    sys.exit(0 if ok else 1)


def main(argv=None):
    p = argparse.ArgumentParser(prog="vireo_sla")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="run the engine and write outputs")
    r.add_argument("--data", help="data directory (default: repo data/)")
    r.add_argument("--enrich", choices=["rules", "bedrock"], help="root-cause tagging backend")
    r.add_argument("--limit", type=int, help="cap tickets sent for enrichment")
    r.set_defaults(func=cmd_run)

    v = sub.add_parser("validate", help="run reconciliation checks")
    v.add_argument("--data")
    v.set_defaults(func=cmd_validate)

    args = p.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
