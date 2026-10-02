"""
Render a single self-contained HTML file (inline SVG, no server, no CDN).

The dashboard is deliberately NOT a league table of agents. Priya warned against
"a wall of red" aimed at the morning team. So the headline view is the monthly
credit trend (settles Arjun vs Priya) and the controllable-vs-structural split
by shift (shows who can actually act). The per-agent table is there, but scoped
to CONTROLLABLE breaches only -- the coachable ones.
"""
from __future__ import annotations

import html
from pathlib import Path


def _bar_svg(rows, value_key, label_key, w=760, bar_h=22, gap=8, color="#c0504d"):
    if not rows:
        return "<p>no data</p>"
    vmax = max(r[value_key] for r in rows) or 1
    h = len(rows) * (bar_h + gap) + 10
    out = [f'<svg width="{w}" height="{h}" font-family="system-ui" font-size="12">']
    for i, r in enumerate(rows):
        y = i * (bar_h + gap) + 5
        bw = int((r[value_key] / vmax) * (w - 230))
        out.append(f'<text x="0" y="{y+15}" fill="#333">{html.escape(str(r[label_key]))}</text>')
        out.append(f'<rect x="150" y="{y}" width="{bw}" height="{bar_h}" fill="{color}" rx="3"/>')
        out.append(f'<text x="{150+bw+6}" y="{y+15}" fill="#333">{r[value_key]}</text>')
    out.append("</svg>")
    return "".join(out)


def _dual_line_svg(trend, w=820, h=260):
    """Two series on one chart: breach rate (%) and SLA credit (Rs), monthly."""
    if not trend:
        return "<p>no data</p>"
    months = [r["month"] for r in trend]
    rate = [r["breach_rate"] for r in trend]
    credit = [r["sla_credit_inr"] for r in trend]
    pad = 50
    pw, ph = w - 2 * pad, h - 2 * pad
    rmax = max(rate) or 1
    cmax = max(credit) or 1
    n = len(months)
    def x(i): return pad + (pw * i / max(n - 1, 1))
    def yr(v): return pad + ph - (v / rmax) * ph
    def yc(v): return pad + ph - (v / cmax) * ph
    out = [f'<svg width="{w}" height="{h}" font-family="system-ui" font-size="11">']
    # axes
    out.append(f'<line x1="{pad}" y1="{pad+ph}" x2="{pad+pw}" y2="{pad+ph}" stroke="#ccc"/>')
    # credit bars (light)
    bw = pw / n * 0.6
    for i, c in enumerate(credit):
        bh = (c / cmax) * ph
        out.append(f'<rect x="{x(i)-bw/2:.0f}" y="{yc(c):.0f}" width="{bw:.0f}" '
                   f'height="{bh:.0f}" fill="#dbe5f1"/>')
    # breach-rate line (red)
    pts = " ".join(f"{x(i):.0f},{yr(v):.0f}" for i, v in enumerate(rate))
    out.append(f'<polyline points="{pts}" fill="none" stroke="#c0504d" stroke-width="2.5"/>')
    for i, v in enumerate(rate):
        out.append(f'<circle cx="{x(i):.0f}" cy="{yr(v):.0f}" r="2.5" fill="#c0504d"/>')
    # month labels (every other)
    for i, m in enumerate(months):
        if i % 2 == 0:
            out.append(f'<text x="{x(i):.0f}" y="{pad+ph+15}" text-anchor="middle" '
                       f'fill="#666">{m[2:]}</text>')
    out.append(f'<text x="{pad}" y="20" fill="#c0504d">━ breach rate (line)</text>')
    out.append(f'<text x="{pad+170}" y="20" fill="#9bb">■ SLA credit Rs (bars)</text>')
    out.append("</svg>")
    return "".join(out)


def render_dashboard(trend, by_shift, bc, leak, enrich_rows, path: str | Path):
    # shift split: structural vs controllable (latest 12 weeks aggregated)
    agg = {}
    for r in by_shift:
        s = agg.setdefault(r["shift"], {"shift": r["shift"], "controllable": 0, "structural": 0})
        s["controllable"] += r["controllable_breaches"]
        s["structural"] += r["structural_breaches"]
    shift_rows = sorted(agg.values(), key=lambda d: -(d["controllable"] + d["structural"]))

    cause_html = ""
    if enrich_rows:
        from collections import Counter
        c = Counter(r["cause"] for r in enrich_rows)
        cause_rows = [{"cause": k, "n": v} for k, v in c.most_common()]
        cause_html = ("<h2>Why the <em>controllable</em> chat breaches happen "
                      f"(AI-tagged, n={len(enrich_rows)})</h2>"
                      + _bar_svg(cause_rows, "n", "cause", color="#4f81bd"))

    doc = f"""<!doctype html><html><head><meta charset="utf-8">
<title>Vireo Audio - First-Response SLA Breach Report</title>
<style>
 body{{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;max-width:900px;
   margin:30px auto;color:#222;padding:0 16px;line-height:1.5}}
 h1{{font-size:22px}} h2{{font-size:16px;margin-top:34px;border-bottom:1px solid #eee;padding-bottom:4px}}
 .kpis{{display:flex;gap:14px;flex-wrap:wrap;margin:16px 0}}
 .kpi{{background:#f7f7f9;border:1px solid #e6e6ea;border-radius:8px;padding:12px 16px;min-width:160px}}
 .kpi .v{{font-size:22px;font-weight:600}} .kpi .l{{font-size:12px;color:#666}}
 .note{{background:#fff8e6;border:1px solid #f0e0a8;border-radius:8px;padding:10px 14px;font-size:13px}}
 table{{border-collapse:collapse;width:100%;font-size:13px}} td,th{{border:1px solid #eee;padding:5px 8px;text-align:left}}
 .muted{{color:#777;font-size:12px}}
</style></head><body>
<h1>Vireo Audio &mdash; First-Response SLA Breach Report</h1>
<p class="muted">Generated by the vireo_sla engine. Timestamps converted UTC&rarr;IST;
migration duplicates removed; legacy csat 0 treated as no-response.</p>

<div class="kpis">
  <div class="kpi"><div class="v">{bc['post_window']['rate']:.0%}</div><div class="l">current breach rate</div></div>
  <div class="kpi"><div class="v">{bc['pre_window']['rate']:.0%}</div><div class="l">pre-reshuffle (H1 2025)</div></div>
  <div class="kpi"><div class="v">Rs {bc['annual_sla_credit_now_inr']:,}</div><div class="l">SLA credit / year now</div></div>
  <div class="kpi"><div class="v">Rs {bc['recoverable_structural_credit_per_year_inr']:,}</div><div class="l">recoverable / year</div></div>
</div>

<div class="note"><b>Read this first.</b> The SLA credit line stepped up ~5&times; after the
June&nbsp;2025 Indore reshuffle removed overnight chat cover &mdash; it is not flat, and CSAT
barely moved. {bc['chat_structural_breaches_post']} of the post-reshuffle chat breaches are
<b>structural night-queue carryover</b>: the ticket breached its 15-minute target overnight,
before any morning agent logged in. Those are a coverage problem, not a people problem.</div>

<h2>Monthly breach rate vs SLA credit</h2>
{_dual_line_svg(trend)}

<h2>Breaches by shift &mdash; what each team can actually act on</h2>
<p class="muted">Blue = controllable (created during a staffed shift). Red = structural
(created in the unstaffed night window; the breach was locked in before the shift started).</p>
<table><tr><th>Shift</th><th>Controllable</th><th>Structural (carryover)</th></tr>
{''.join(f"<tr><td>{html.escape(r['shift'])}</td><td>{r['controllable']}</td><td>{r['structural']}</td></tr>" for r in shift_rows)}
</table>

{cause_html}

<h2>Policy leakage (bonus check)</h2>
<p>Tickets with <b>both a refund and a replacement</b> on the same order (policy &sect;5
forbids this): <b>{leak['refund_and_replacement_same_ticket']}</b>,
Rs {leak['refund_value_at_risk_inr']:,} at risk. IDs:
<span class="muted">{html.escape(', '.join(leak['ticket_ids']) or 'none')}</span></p>

<p class="muted">Full weekly breakdown by agent and shift is in
<code>weekly_breach_by_agent_shift.csv</code>.</p>
</body></html>"""
    Path(path).write_text(doc, encoding="utf-8")
