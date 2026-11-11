import sys
from pathlib import Path

_ROOT = str(Path(__file__).resolve().parents[2])  # project root (pages can be opened directly via URL / refresh)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import pandas as pd
import streamlit as st

from frontend.components import charts
from frontend.components.state import render_sidebar, require_analysis
from frontend.components.style import PALETTE, badge, esc, kpi_row, note, page_header, quote, section

KIND_NAMES = {"complaint": "Complaint", "explicit_expectation": "Explicit expectation", "feature_request": "Feature request",
              "unmet_need": "Unmet need", "recurring_frustration": "Recurring frustration", "inferred_expectation": "Inferred expectation"}
KIND_COLORS = {"complaint": "#DC2626", "explicit_expectation": "#2563EB", "feature_request": "#059669", "unmet_need": "#D97706",
               "recurring_frustration": "#7C3AED", "inferred_expectation": "#64748B"}

ctx = render_sidebar()
page_header("Customer Intelligence", "What customers talk about, how they feel, and what they actually want")
if not require_analysis(ctx):
    st.stop()
cf, mf, tf, labels = ctx.customer_f, ctx.mentions_f, ctx.topics_f, ctx.topic_labels
tab_sent, tab_topics, tab_exp, tab_neg, tab_explore = st.tabs(["Sentiment", "Topics", "Needs & expectations", "Negative feedback", "Review explorer"])

# ----------------------------------------------------------------------------------------------- sentiment
with tab_sent:
    vc = cf["label"].value_counts(normalize=True) * 100
    kpi_row([("Positive", f"{vc.get('positive', 0):.0f}%", "of conversations", PALETTE["pos"]),
             ("Neutral", f"{vc.get('neutral', 0):.0f}%", "of conversations", PALETTE["neu"]),
             ("Negative", f"{vc.get('negative', 0):.0f}%", "of conversations", PALETTE["neg"]),
             ("Mean score", f"{cf['compound'].mean():+.2f}", ctx.meta.get("sentiment_model", "vader"), PALETTE["primary"])])
    a, b = st.columns(2)
    with a:
        section("Sentiment distribution")
        st.plotly_chart(charts.sentiment_donut(cf), width="stretch")
    with b:
        section("Score histogram", "Compound score from -1 (very negative) to +1 (very positive)")
        st.plotly_chart(charts.sentiment_histogram(cf), width="stretch")
    section("Sentiment by topic (aspect-level)", "Each statement (clause) is scored separately and linked to its topic - one review can be positive about one topic and negative about another")
    if len(tf) and tf["mentions"].sum() > 0:
        st.plotly_chart(charts.topic_sentiment_stack(tf[tf["mentions"] > 0]), width="stretch", key="stack_sent_tab")
    mixed = mf.groupby("record_id").filter(lambda g: g["label"].nunique() > 1 and {"positive", "negative"} <= set(g["label"])) if len(mf) else mf
    if len(mixed):
        with st.expander(f"Reviews with mixed aspect sentiment ({mixed['record_id'].nunique()})"):
            for rid, g in list(mixed.groupby("record_id"))[:12]:
                txt = cf.loc[cf["record_id"] == rid, "text_original"]
                st.markdown(f"**{esc(txt.iloc[0]) if len(txt) else ''}**", unsafe_allow_html=True)
                for _, r in g.iterrows():
                    st.markdown(f"&nbsp;&nbsp;{'🟢' if r['label']=='positive' else '🔴' if r['label']=='negative' else '⚪'} **{labels.get(r['topic_id'], r['topic_id'])}** → _{esc(r['clause'])}_ ({r['compound']:+.2f})", unsafe_allow_html=True)

# ----------------------------------------------------------------------------------------------- topics
with tab_topics:
    section("Discovered topics", f"Found automatically by {ctx.meta.get('topic_backend', '').upper()} from your data. Select a row to read the underlying conversations.")
    t = tf[tf["mentions"] > 0].sort_values("mentions", ascending=False).reset_index(drop=True)
    if t.empty:
        st.info("No topic statements under the current filters.")
    else:
        view = pd.DataFrame({
            "Topic": t["label"], "Statements": t["mentions"], "Conversations": t["conversations"], "Customers": t["unique_customers"],
            "Avg sentiment": t["avg_sentiment"].round(2), "% negative": t["negative_pct"].round(0), "% positive": t["positive_pct"].round(0),
            "Importance": t["importance"].round(0),
            "Volume change": t["volume_change_pct"].map(lambda v: "new/NA" if pd.isna(v) else f"{v:+.0f}%"),
        })
        ev = st.dataframe(view, hide_index=True, width="stretch", on_select="rerun", selection_mode="single-row", key="topic_table",
                          column_config={"Importance": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%d"),
                                         "% negative": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%d%%")})
        a, b = st.columns(2)
        with a:
            st.plotly_chart(charts.topic_bar(t), width="stretch")
        with b:
            st.plotly_chart(charts.topic_sentiment_stack(t), width="stretch", key="stack_topics_tab")
        rows = ev.selection.rows if ev and ev.selection else []
        if rows:
            tid = int(t.iloc[rows[0]]["topic_id"])
            section(f"Conversations about: {t.iloc[rows[0]]['label']}", "Most negative first. 'Statement' is the clause matched to this topic.")
            m = mf[mf["topic_id"] == tid].merge(cf[["record_id", "text_original"]], on="record_id", how="left").sort_values("compound")
            st.dataframe(pd.DataFrame({"Date": m["date"].dt.strftime("%Y-%m-%d"), "Source": m["source"], "Customer": m["customer_id"],
                                       "Sentiment": m["label"], "Score": m["compound"].round(2), "Statement": m["clause"],
                                       "Full text": m["text_original"]}), hide_index=True, width="stretch")
        else:
            note("Click a topic row above to inspect its customer conversations.")

# ----------------------------------------------------------------------------------------------- expectations
with tab_exp:
    ex = ctx.expectations_f
    section("What customers actually want", "Observed = said by customers. Inferred = what complaints imply (never presented as an explicit request).")
    if ex.empty:
        st.info("No expectations detected for the current filters.")
    else:
        inf = ex[ex["kind"] == "inferred_expectation"].sort_values("support_count", ascending=False)
        if len(inf):
            st.markdown("**Summary of expectations (inferred from complaints)**")
            for _, r in inf.iterrows():
                st.markdown(f"- {badge('INFERRED', '#64748B')} {esc(r['summary'].replace('INFERRED: ', ''))}", unsafe_allow_html=True)
        kinds = st.multiselect("Show", list(KIND_NAMES.values()), default=list(KIND_NAMES.values()), key="exp_kinds")
        show = ex[ex["kind"].map(KIND_NAMES).isin(kinds)]
        for tid, g in show.groupby("topic_id", sort=False):
            with st.expander(f"{labels.get(tid, tid)} — {len(g)} insight(s)", expanded=False):
                for _, r in g.sort_values("kind").iterrows():
                    tag = badge(KIND_NAMES[r["kind"]], KIND_COLORS[r["kind"]]) + (badge("inferred", "#64748B", soft=True) if r["is_inferred"] else badge("observed", "#059669", soft=True))
                    st.markdown(f"{tag} {esc(r['summary'])}  \n<span style='color:#64748B;font-size:.82rem'>{int(r['support_count'])} supporting statement(s) · {r['share_pct']:.0f}% of topic</span>", unsafe_allow_html=True)
                    for e in (r["evidence"] or [])[:3]:
                        st.markdown(quote(e["text"], f"{e.get('date') or ''}"), unsafe_allow_html=True)

# ----------------------------------------------------------------------------------------------- negative
with tab_neg:
    neg = cf[cf["label"] == "negative"].sort_values("compound")
    kpi_row([("Negative conversations", f"{len(neg):,}", f"{len(neg) / max(len(cf), 1) * 100:.0f}% of filtered", PALETTE["neg"]),
             ("Most negative topic", (tf.sort_values("negative_pct", ascending=False).iloc[0]["label"] if len(tf) else "—")[:26],
              f"{tf['negative_pct'].max():.0f}% negative" if len(tf) else "", "#B91C1C")])
    a, b = st.columns(2)
    with a:
        section("Negative share by topic")
        if len(tf):
            st.plotly_chart(charts.topic_sentiment_stack(tf[tf["mentions"] > 0]), width="stretch", key="stack_neg_tab")
    with b:
        section("Negative share by data source")
        if cf["source"].notna().any():
            st.plotly_chart(charts.source_negative_bar(cf.dropna(subset=["source"])), width="stretch")
    section("Most negative conversations")
    topic_of = ctx.topic_labels
    st.dataframe(pd.DataFrame({"Date": neg["date"].dt.strftime("%Y-%m-%d"), "Source": neg["source"], "Score": neg["compound"].round(2),
                               "Topic": neg["topic_id"].map(topic_of), "Conversation": neg["text_original"]}).head(50),
                 hide_index=True, width="stretch")

# ----------------------------------------------------------------------------------------------- explorer
with tab_explore:
    section("Review explorer", "Search and inspect individual conversations (respects the sidebar filters)")
    q = st.text_input("Search text", placeholder="e.g. refund, chatbot, late …", key="explore_q")
    d = cf[cf["text_original"].str.contains(q, case=False, regex=False, na=False)] if q else cf
    d = d.sort_values("date", ascending=False)
    table = pd.DataFrame({"Date": d["date"].dt.strftime("%Y-%m-%d"), "Source": d["source"], "Customer": d["customer_id"], "Sentiment": d["label"],
                          "Score": d["compound"].round(2), "Topic": d["topic_id"].map(ctx.topic_labels), "Text": d["text_original"]})
    st.caption(f"{len(table):,} conversations")
    ev = st.dataframe(table, hide_index=True, width="stretch", height=360, on_select="rerun", selection_mode="single-row", key="explore_table")
    st.download_button("⬇ Download filtered conversations (CSV)", table.to_csv(index=False).encode(), "conversations.csv", "text/csv")
    if ev and ev.selection.rows:
        rec = d.iloc[ev.selection.rows[0]]
        st.markdown(f"**Selected:** {esc(rec['text_original'])}", unsafe_allow_html=True)
        m = ctx.mentions[ctx.mentions["record_id"] == rec["record_id"]]
        if len(m):
            st.dataframe(pd.DataFrame({"Statement": m["clause"], "Aspect": m["aspect"], "Topic": m["topic_id"].map(ctx.topic_labels),
                                       "Sentiment": m["label"], "Score": m["compound"].round(2), "Signals": m["signals"].map(lambda s: ", ".join(s) if s else "")}),
                         hide_index=True, width="stretch")
