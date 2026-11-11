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
page_header("Company Communication", "What the company is actually telling its customers (analysed separately from customer data)")
if not require_analysis(ctx):
    st.stop()
th, bs, meta = ctx.themes, ctx.blind_spots_f, ctx.meta

kpi_row([("Company messages analysed", ctx.overview.get("total_company_messages", 0), "after cleaning", PALETTE["warn"]),
         ("Messaging themes", len(th), "discovered by clustering", PALETTE["primary"]),
         ("Messages with promises/claims", len(meta.get("promises", [])), "speed · price · trust · rewards …", "#0EA5E9"),
         ("Off-topic share", f"{ctx.overview.get('offtopic_company_share_pct', 0):.0f}%", "messages unrelated to any customer topic", PALETTE["neu"])])

a, b = st.columns(2)
with a:
    section("Main messaging themes", "Share = messages in the theme ÷ all company messages × 100")
    if len(th):
        st.plotly_chart(charts.theme_bar(th), width="stretch")
with b:
    section("Communication coverage by customer topic", "Share of company messaging that semantically addresses each topic customers discuss")
    if len(bs):
        st.plotly_chart(charts.coverage_bar(bs), width="stretch")

section("Theme details", "Keywords come from class-based TF-IDF; examples are real messages from the dataset")
for _, r in th.iterrows():
    with st.expander(f"{r['label']} — {r['share_pct']:.0f}% of messages ({int(r['n_messages'])})"):
        st.markdown("**Keywords:** " + ", ".join(r["keywords"] or []))
        for ex in r["examples"] or []:
            st.markdown(f"- “{esc(ex)}”", unsafe_allow_html=True)

c, d = st.columns(2)
with c:
    section("Most promoted features, services & words", "Number of messages containing each word")
    if meta.get("company_keywords"):
        st.plotly_chart(charts.keyword_bar(meta["company_keywords"]), width="stretch")
with d:
    section("Company promises & benefits detected")
    prom = pd.DataFrame(meta.get("promises", []))
    if len(prom):
        types = prom.explode("promise_types")["promise_types"].value_counts()
        st.dataframe(pd.DataFrame({"Promise type": types.index, "Messages": types.values}), hide_index=True, width="stretch")
        with st.expander("All promise messages"):
            st.dataframe(pd.DataFrame({"Message": prom["text"], "Types": prom["promise_types"].map(", ".join)}), hide_index=True, width="stretch")
    else:
        st.info("No explicit promises detected.")

section("Closest company messages for each customer topic", "Semantic (SBERT cosine) similarity between a customer topic and the company's messages — shows what the company says nearest to each concern")
for _, r in bs.sort_values("coverage_norm").iterrows():
    msgs = r["closest_company_messages"] or []
    best = msgs[0]["similarity"] if msgs else 0
    with st.expander(f"{r['topic_label']} — coverage index {r['coverage_norm']:.0f}/100 · best match similarity {best:.2f}"):
        for m in msgs:
            st.markdown(f"- “{esc(m['text'])}” — similarity **{m['similarity']:.2f}**", unsafe_allow_html=True)
if meta.get("embedding_backend", "").startswith("tfidf"):
    note("Offline TF-IDF embeddings were used, so semantic matching is weaker than with SBERT.", warn=True)
