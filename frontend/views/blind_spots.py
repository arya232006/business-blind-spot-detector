import sys
from pathlib import Path

_ROOT = str(Path(__file__).resolve().parents[2])  # project root (pages can be opened directly via URL / refresh)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import pandas as pd
import streamlit as st

from frontend.client import ClientError
from frontend.components import charts
from frontend.components.state import bump_version, render_sidebar, require_analysis
from frontend.components.style import (CLASS_LABELS, SEVERITY_COLORS, badge, class_badge, esc, kpi_row, note, page_header, quote,
                                       section, severity_badge)
from ml.gap_analysis import CAVEAT, CLASS_EXPLANATIONS
from ml.scoring.engine import SEVERITY_BANDS

ICON = {"Low": "🟢", "Moderate": "🟡", "Significant": "🟠", "High": "🔴", "Critical": "⚫"}
ctx = render_sidebar()
page_header("Blind Spot Analysis", "Where customer priorities and company communication diverge — ranked and scored")
if not require_analysis(ctx):
    st.stop()
bs = ctx.blind_spots_f.sort_values("score", ascending=False)
if bs.empty:
    st.info("No blind spots match the current filters.")
    st.stop()

sev_counts = bs["severity"].value_counts()
kpi_row([(s, int(sev_counts.get(s, 0)), f"score {lo}-{hi}", SEVERITY_COLORS[s]) for (hi, s), lo in zip(SEVERITY_BANDS, [0, 21, 41, 61, 81])])

section("Ranked blind spots")
table = pd.DataFrame({
    "Rank": bs["rank"], "Topic": bs["topic_label"], "Type": bs["classification"].map(CLASS_LABELS),
    "Importance": bs["importance"].round(0), "Company coverage": bs["coverage_norm"].round(0), "Gap": bs["gap"].round(0),
    "Trend": bs.apply(lambda r: f"{r['trend_used']:.0f}" + ("" if r["trend_available"] else " (neutral)"), axis=1),
    "Score": bs["score"].round(1), "Severity": bs["severity"].map(lambda s: f"{ICON.get(s, '')} {s}"),
})
st.dataframe(table, hide_index=True, width="stretch", column_config={
    "Rank": st.column_config.NumberColumn(width=50), "Trend": st.column_config.TextColumn(width=80),
    "Severity": st.column_config.TextColumn(width=110), "Topic": st.column_config.TextColumn(width=170),
    "Type": st.column_config.TextColumn(width=150),
    "Importance": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%d", width=100),
    "Company coverage": st.column_config.ProgressColumn("Coverage", min_value=0, max_value=100, format="%d", width=100),
    "Gap": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%d", width=90),
    "Score": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.1f", width=100)})
st.download_button("⬇ Download ranked blind spots (CSV)", table.to_csv(index=False).encode(), "blind_spots.csv", "text/csv")

a, b = st.columns(2)
with a:
    section("Customer importance vs company coverage", "The gap between the bars is the mismatch")
    st.plotly_chart(charts.importance_vs_coverage(bs), width="stretch")
with b:
    section("Importance × coverage map", "Labels = rank in the table · bubble size = statements · shaded zone = high importance, low coverage")
    st.plotly_chart(charts.gap_scatter(bs), width="stretch")
section("Blind Spot Score", "Dotted lines mark severity bands (20 / 40 / 60 / 80)")
st.plotly_chart(charts.score_bar(bs), width="stretch")

# ------------------------------------------------------------------------------------------------ detail
section("Inspect a blind spot", "Evidence behind the score")
choice = st.selectbox("Topic", bs["topic_id"].tolist(), format_func=lambda i: f"#{int(bs.set_index('topic_id').loc[i, 'rank'])} · {bs.set_index('topic_id').loc[i, 'topic_label']}", key="bs_pick")
r = bs[bs["topic_id"] == choice].iloc[0]
st.markdown(f"{class_badge(r['classification'])}{severity_badge(r['severity'])} **{esc(r['topic_label'])}** — score **{r['score']:.1f}**", unsafe_allow_html=True)
st.markdown(f"_{CLASS_EXPLANATIONS[r['classification']]}_")
if r["classification"] in ("genuine_blind_spot", "communication_gap", "unmet_operational_need"):
    note(CAVEAT)
c1, c2 = st.columns([1, 1])
with c1:
    st.plotly_chart(charts.component_bars(r), width="stretch")
    st.markdown(f"**Calculation:** {r['importance']:.1f} × {r['gap']:.1f} × {r['trend_used']:.1f} ÷ 10,000 = **{r['score']:.1f}**")
    if not r["trend_available"]:
        note("Not enough dated history for this topic: a neutral trend value was used instead of guessing a direction.", warn=True)
    st.markdown(f"Trend status: **{r['trend_status'] or 'unavailable'}** · customers: **{int(r['unique_customers'])}** · statements: **{int(r['mentions'])}** · negative: **{r['negative_pct']:.0f}%**"
                + (" · 🔁 recurring frustration" if r["recurring"] else ""))
with c2:
    st.markdown("**Customer evidence (most negative statements)**")
    for e in r["evidence_quotes"] or []:
        st.markdown(quote(e["text"], f"{e.get('date') or ''} · {e['compound']:+.2f}"), unsafe_allow_html=True)
    st.markdown("**Closest company messages**")
    for m in r["closest_company_messages"] or []:
        st.markdown(f"- “{esc(m['text'])}” — similarity {m['similarity']:.2f}", unsafe_allow_html=True)
ex = ctx.expectations_f[ctx.expectations_f["topic_id"] == choice] if len(ctx.expectations_f) else ctx.expectations_f
if len(ex):
    with st.expander("What customers expect on this topic"):
        for _, e in ex.iterrows():
            st.markdown(f"- {badge('inferred' if e['is_inferred'] else 'observed', '#64748B' if e['is_inferred'] else '#059669', soft=True)} {esc(e['summary'])}", unsafe_allow_html=True)

# ------------------------------------------------------------------------------------------------ scoring settings
section("Scoring weights & thresholds", "All parameters are configurable. Re-scoring re-uses stored components, so no NLP re-run is needed.")
cfg = ctx.meta.get("scoring_config", {})
with st.form("scoring_form"):
    st.markdown("**Customer importance weights**")
    k1, k2, k3, k4 = st.columns(4)
    w_f = k1.slider("Topic frequency", 0.0, 1.0, float(cfg.get("w_frequency", .3)), .05)
    w_u = k2.slider("Unique customers", 0.0, 1.0, float(cfg.get("w_unique_customers", .25)), .05)
    w_s = k3.slider("Negative sentiment", 0.0, 1.0, float(cfg.get("w_sentiment", .3)), .05)
    w_e = k4.slider("Explicit requests", 0.0, 1.0, float(cfg.get("w_explicit_requests", .15)), .05)
    g1, g2, g3, g4 = st.columns(4)
    w_c = g1.slider("Gap: coverage weight", 0.0, 1.0, float(cfg.get("w_coverage", .6)), .05)
    w_m = g2.slider("Gap: similarity weight", 0.0, 1.0, float(cfg.get("w_similarity", .4)), .05)
    w_v = g3.slider("Trend: volume weight", 0.0, 1.0, float(cfg.get("w_volume_trend", .6)), .05)
    w_n = g4.slider("Trend: negativity weight", 0.0, 1.0, float(cfg.get("w_negative_trend", .4)), .05)
    h1, h2, h3, h4 = st.columns(4)
    t_imp = h1.slider("Min importance to flag", 0, 100, int(cfg.get("min_importance", 35)))
    t_gap = h2.slider("Min gap to flag", 0, 100, int(cfg.get("min_gap", 40)))
    t_cov = h3.slider("'Low coverage' below", 0, 100, int(cfg.get("low_coverage", 15)))
    t_flo = h4.slider("Trend floor", 0, 50, int(cfg.get("trend_floor", 10)))
    b1, b2, b3 = st.columns(3)
    preview = b1.form_submit_button("👁 Preview new scores", width="stretch")
    apply = b2.form_submit_button("✅ Apply to this analysis", width="stretch")
    save_default = b3.form_submit_button("💾 Save as default", width="stretch")
overrides = {"w_frequency": w_f, "w_unique_customers": w_u, "w_sentiment": w_s, "w_explicit_requests": w_e, "w_coverage": w_c,
             "w_similarity": w_m, "w_volume_trend": w_v, "w_negative_trend": w_n, "min_importance": t_imp, "min_gap": t_gap,
             "low_coverage": t_cov, "trend_floor": t_flo}
try:
    if preview:
        res = ctx.client.rescore(ctx.session_id, overrides, persist=False)
        new = pd.DataFrame(res["blind_spots"]).set_index("topic_id")
        old = bs.set_index("topic_id")
        cmp = pd.DataFrame({"Topic": new["topic_label"], "Old score": old["score"].reindex(new.index).round(1), "New score": new["score"].round(1),
                            "Old severity": old["severity"].reindex(new.index), "New severity": new["severity"],
                            "New type": new["classification"].map(CLASS_LABELS)}).sort_values("New score", ascending=False)
        st.dataframe(cmp, hide_index=True, width="stretch")
        st.caption("Preview only — nothing was saved.")
    if apply:
        ctx.client.rescore(ctx.session_id, overrides, persist=True)
        bump_version()
        st.success("Scores updated for this analysis.")
        st.rerun()
    if save_default:
        base = ctx.client.get_scoring_config()
        ctx.client.save_scoring_config({**base, **overrides})
        st.success("Saved as the default for future analyses.")
except ClientError as exc:
    st.error(str(exc))
