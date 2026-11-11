import sys
from pathlib import Path

_ROOT = str(Path(__file__).resolve().parents[2])  # project root (pages can be opened directly via URL / refresh)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import streamlit as st

from frontend.components import charts
from frontend.components.state import render_sidebar, require_analysis
from frontend.components.style import (PALETTE, SEVERITY_COLORS, class_badge, esc, kpi_row, meter, note, page_header,
                                       section, severity_badge)

FLAGGED = {"genuine_blind_spot", "unmet_operational_need", "negative_experience", "communication_gap"}

ctx = render_sidebar()
page_header("Overview", f"{ctx.company['name']} · what customers say vs what the company communicates" if ctx.company else "Business Blind Spot Detector")
if not require_analysis(ctx):
    st.stop()

cf, bs, tf = ctx.customer_f, ctx.blind_spots_f, ctx.topics_f
min_score = ctx.meta.get("scoring_config", {}).get("min_score", 5)
flagged = bs[bs["classification"].isin(FLAGGED) & (bs["score"] >= min_score)]
visible_topics = set(tf["topic_id"])
emerging = [e for e in ctx.emerging if e["topic_id"] in visible_topics]
mean_sent = cf["compound"].mean()

kpi_row([
    ("Conversations analysed", f"{len(cf):,}", f"of {ctx.overview.get('total_conversations', len(cf)):,} total", PALETTE["primary"]),
    ("Topics detected", len(tf), f"{ctx.meta.get('topic_backend', '').upper()} discovery", "#0EA5E9"),
    ("Potential blind spots", len(flagged), f"{int((flagged['classification'] == 'genuine_blind_spot').sum())} genuine", PALETTE["neg"]),
    ("Emerging issues", len(emerging), "statistically significant growth", PALETTE["warn"]),
    ("Overall sentiment", f"{mean_sent:+.2f}", f"{(cf['label'] == 'positive').mean() * 100:.0f}% pos · {(cf['label'] == 'negative').mean() * 100:.0f}% neg",
     PALETTE["pos"] if mean_sent > 0.05 else PALETTE["neg"] if mean_sent < -0.05 else PALETTE["neu"]),
    ("Avg blind spot score", f"{flagged['score'].mean():.1f}" if len(flagged) else "—", "flagged blind spots, 0-100", "#7C3AED"),
])

c1, c2 = st.columns([1, 1.5])
with c1:
    section("Customer sentiment", "VADER compound score per conversation")
    st.plotly_chart(charts.sentiment_donut(cf), width="stretch")
with c2:
    section("Top customer concerns", "Statements per topic · colour = average sentiment")
    st.plotly_chart(charts.topic_bar(tf), width="stretch")

section("Highest-scoring blind spots", "Ranked by Blind Spot Score = Importance × Expectation Gap × Trend ÷ 10,000")
if len(bs) == 0:
    st.info("No blind spots match the current filters.")
for _, r in bs.sort_values("score", ascending=False).head(5).iterrows():
    color = SEVERITY_COLORS.get(r["severity"], "#64748B")
    st.markdown(
        f'<div class="bb-card"><div style="display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap">'
        f'<h4>#{int(r["rank"])} · {esc(r["topic_label"])}</h4><div>{class_badge(r["classification"])}{severity_badge(r["severity"])}'
        f'<b style="font-size:1.3rem;color:{color}">{r["score"]:.1f}</b><span style="color:#94A3B8"> /100</span></div></div>'
        f'{meter(r["score"], color)}'
        f'<p style="margin-top:8px"><b>Customer importance</b> {r["importance"]:.0f} · <b>Company coverage</b> {r["coverage_norm"]:.0f} · '
        f'<b>Gap</b> {r["gap"]:.0f} · <b>Negative</b> {r["negative_pct"]:.0f}% of {int(r["mentions"])} statements · '
        f'<b>Trend</b> {esc(r["trend_status"] or "n/a")}</p></div>', unsafe_allow_html=True)

section("Emerging issues", "Topics whose share of conversation is growing significantly AND is mostly negative")
if emerging:
    for e in emerging:
        st.markdown(f'<div class="bb-card"><h4>📈 {esc(e["topic_label"])} <span style="font-weight:500;color:#64748B">· {esc(e["status"])}</span></h4>'
                    f'<p>{esc(e["reason"])}</p></div>', unsafe_allow_html=True)
else:
    note(ctx.meta.get("trend_reason") or "No topic shows a statistically significant increase in negative conversation.")

notes = ctx.meta.get("notes", [])
if notes:
    with st.expander(f"Data-quality notes ({len(notes)})"):
        for n in notes:
            st.markdown(f"- {n}")
