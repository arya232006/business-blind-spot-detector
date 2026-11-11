import sys
from pathlib import Path

_ROOT = str(Path(__file__).resolve().parents[2])  # project root (pages can be opened directly via URL / refresh)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import streamlit as st

from frontend.components.state import render_sidebar, require_analysis
from frontend.components.style import PRIORITY_COLORS, badge, class_badge, esc, kpi_row, note, page_header, priority_badge, quote, severity_badge
from ml.recommendations import CATEGORIES

ICONS = {"Product": "🛠️", "Customer Support": "🎧", "Operational": "⚙️", "Communication": "📣"}
ctx = render_sidebar()
page_header("Recommendations", "Actions grounded in the analysed data — every item cites its evidence and score")
if not require_analysis(ctx):
    st.stop()
recs = ctx.recs_f
if recs.empty:
    st.info("No recommendations for the current filters (nothing scored high enough, or all topics are aligned).")
    st.stop()

if ctx.meta.get("llm_used"):
    note("Wording of some recommendations was polished by the configured LLM. Scores, priorities and evidence are computed deterministically.")
else:
    note("Recommendations are generated deterministically from measured values (no LLM). Set LLM_PROVIDER=gemini and GEMINI_API_KEY to enable optional natural-language polishing.")

c1, c2 = st.columns(2)
cats = c1.multiselect("Category", CATEGORIES, default=CATEGORIES, key="rec_cat")
pris = sorted(recs["priority"].unique())
sel_p = c2.multiselect("Priority", pris, default=pris, key="rec_pri")
view = recs[recs["category"].isin(cats) & recs["priority"].isin(sel_p)].sort_values(["priority", "blind_spot_score"], ascending=[True, False])
kpi_row([("Recommendations", len(view), "after filters", "#4F46E5")] +
        [(c, int((view["category"] == c).sum()), ICONS[c], "#0EA5E9") for c in CATEGORIES])

for cat in CATEGORIES:
    g = view[view["category"] == cat]
    if g.empty:
        continue
    st.markdown(f"### {ICONS[cat]} {cat} recommendations")
    for _, r in g.iterrows():
        st.markdown(
            f'<div class="bb-card"><div style="display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap">'
            f'<h4>{esc(r["topic_label"])}</h4><div>{priority_badge(r["priority"])}{severity_badge(r["severity"])}{class_badge(r["classification"])}'
            f'<b>Score {r["blind_spot_score"]:.1f}</b></div></div>'
            f'<p><b>Identified problem.</b> {esc(r["problem"])}</p>'
            f'<p><b>Suggested action.</b> {esc(r["suggested_action"])}</p>'
            f'<p><b>Expected business impact.</b> {esc(r["expected_impact"])}</p></div>', unsafe_allow_html=True)
        ev = r["evidence"] or []
        if ev:
            with st.expander(f"Supporting customer evidence ({len(ev)} quotes)"):
                for e in ev:
                    st.markdown(quote(e["text"], f"{e.get('date') or ''}"), unsafe_allow_html=True)

export = view.drop(columns=["evidence"]).to_csv(index=False).encode()
st.download_button("⬇ Export recommendations (CSV)", export, "recommendations.csv", "text/csv")
