import sys
from pathlib import Path

_ROOT = str(Path(__file__).resolve().parents[2])  # project root (pages can be opened directly via URL / refresh)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import pandas as pd
import streamlit as st

from frontend.components import charts
from frontend.components.state import render_sidebar, require_analysis
from frontend.components.style import PALETTE, esc, kpi_row, note, page_header, section

ctx = render_sidebar()
page_header("Trend Analysis", "Which issues are growing, which are fading — corrected for changes in sample volume")
if not require_analysis(ctx):
    st.stop()
meta = ctx.meta
if not meta.get("trend_available"):
    note(meta.get("trend_reason") or "Trend analysis is unavailable for this dataset (no usable dates).", warn=True)
    st.markdown("Upload a customer dataset with a **date** column (at least 20 dated records spanning 1+ week) to enable trends.")
    st.stop()

labels, series, summ = ctx.topic_labels, ctx.series, ctx.trend_summary
visible = set(ctx.topics_f["topic_id"])
series, summ = series[series["topic_id"].isin(visible)], summ[summ["topic_id"].isin(visible)]
freq_name = {"D": "day", "W": "week", "M": "month"}[meta.get("trend_freq", "W")]
emerging = [e for e in ctx.emerging if e["topic_id"] in visible]
inc = int((summ["status"].isin(["increasing", "emerging"])).sum())
dec = int((summ["status"] == "declining").sum())
kpi_row([("Time bucket", freq_name.title(), f"recent window starts {str(meta.get('recent_start', ''))[:10]}", PALETTE["primary"]),
         ("Emerging issues", len(emerging), "growing + mostly negative", PALETTE["warn"]),
         ("Growing topics", inc, "significant increase in share", PALETTE["neg"]),
         ("Declining topics", dec, "significant decrease in share", PALETTE["pos"]),
         ("Negative spikes", len(ctx.spikes), "anomalous buckets", "#7C3AED")])

section("Topic volume over time", f"Per {freq_name}. 'Share' divides by all statements in the period so growth in raw volume alone is not mistaken for a trend.")
c1, c2 = st.columns([3, 1])
metric = c2.radio("Metric", ["volume", "share", "neg_count"], format_func={"volume": "Statements", "share": "Share of period (%)", "neg_count": "Negative statements"}.get, key="trend_metric")
default = summ.sort_values("recent_n", ascending=False)["topic_id"].head(4).tolist()
chosen = c2.multiselect("Topics", sorted(visible), default=[d for d in default if d in visible], format_func=lambda i: labels.get(i, i), key="trend_topics")
with c1:
    if chosen:
        st.plotly_chart(charts.topic_volume_lines(series, labels, chosen, metric), width="stretch")
    else:
        st.info("Select at least one topic.")

a, b = st.columns(2)
with a:
    section("Overall sentiment trend")
    if len(ctx.overall):
        st.plotly_chart(charts.sentiment_trend(ctx.overall), width="stretch")
with b:
    section("Negative conversations over time")
    if len(ctx.overall):
        st.plotly_chart(charts.negative_share_trend(ctx.overall), width="stretch")

section("Negative feedback heatmap", "Darker = more negative statements in that period")
if len(series):
    st.plotly_chart(charts.negative_heatmap(series, labels), width="stretch")

section("Emerging issues & increasing complaints")
if emerging:
    for e in emerging:
        st.markdown(f'<div class="bb-card"><h4>📈 {esc(e["topic_label"])} · {esc(e["status"])}</h4><p>{esc(e["reason"])}</p></div>', unsafe_allow_html=True)
else:
    note("No topic shows a statistically significant increase in negative conversation.")

section("Trend table", "p-values come from a two-proportion z-test of recent vs historical share; low-confidence changes are shrunk toward neutral (50)")
t = summ.copy()
st.dataframe(pd.DataFrame({
    "Topic": t["topic_label"], "Status": t["status"], "Trend score": t["trend_score"].round(0),
    "Recent n": t["recent_n"], "History n": t["history_n"], "Recent share %": t["recent_share_pct"].round(1), "History share %": t["history_share_pct"].round(1),
    "Volume Δ%": t["volume_change_pct"].round(0), "p-value": t["volume_p_value"].round(3), "Neg. Δ pts": t["negative_delta_pct"].round(1),
    "Sentiment slope/wk": t["sentiment_slope_per_week"].round(3)}).sort_values("Trend score", ascending=False, na_position="last"),
    hide_index=True, width="stretch")

section("Sudden spikes in negative feedback", "Buckets whose negative count is an outlier vs the topic's own history (robust z-score ≥ 2.5, ≥ 3 statements)")
sp = ctx.spikes
sp = sp[sp["topic_id"].isin(visible)] if len(sp) else sp
if len(sp):
    st.dataframe(pd.DataFrame({"Topic": sp["topic_label"], "Period starting": sp["period"].dt.strftime("%Y-%m-%d"), "Negative statements": sp["negative_count"],
                               "Robust z": sp["z_score"].round(1)}).sort_values("Period starting"), hide_index=True, width="stretch")
else:
    st.info("No anomalous spikes detected.")
