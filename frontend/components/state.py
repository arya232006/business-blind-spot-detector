"""Shared sidebar, company/analysis selection, data loading and global filters (used by every page)."""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd
import streamlit as st

from frontend.client import ClientError, build_client
from frontend.components.style import esc, inject_css, note

SENTIMENTS = ["positive", "neutral", "negative"]
SEVERITIES = ["Low", "Moderate", "Significant", "High", "Critical"]


@st.cache_resource(show_spinner="Starting up…")
def get_client():
    return build_client()


@st.cache_data(show_spinner="Loading analysis…", ttl=600)
def _load_bundle(_client, mode: str, session_id: int, version: int) -> dict:
    return _client.get_bundle(session_id)


def bump_version() -> None:
    st.session_state["bundle_version"] = st.session_state.get("bundle_version", 0) + 1


@dataclass
class Ctx:
    client: object
    companies: list = field(default_factory=list)
    company: dict | None = None
    sessions: list = field(default_factory=list)
    session_id: int | None = None
    bundle: dict | None = None
    customer: pd.DataFrame = field(default_factory=pd.DataFrame)
    customer_f: pd.DataFrame = field(default_factory=pd.DataFrame)
    mentions: pd.DataFrame = field(default_factory=pd.DataFrame)
    mentions_f: pd.DataFrame = field(default_factory=pd.DataFrame)
    topics: pd.DataFrame = field(default_factory=pd.DataFrame)
    topics_f: pd.DataFrame = field(default_factory=pd.DataFrame)
    blind_spots: pd.DataFrame = field(default_factory=pd.DataFrame)
    blind_spots_f: pd.DataFrame = field(default_factory=pd.DataFrame)
    recs_f: pd.DataFrame = field(default_factory=pd.DataFrame)
    expectations_f: pd.DataFrame = field(default_factory=pd.DataFrame)
    themes: pd.DataFrame = field(default_factory=pd.DataFrame)
    series: pd.DataFrame = field(default_factory=pd.DataFrame)
    overall: pd.DataFrame = field(default_factory=pd.DataFrame)
    trend_summary: pd.DataFrame = field(default_factory=pd.DataFrame)
    spikes: pd.DataFrame = field(default_factory=pd.DataFrame)
    emerging: list = field(default_factory=list)
    filters: dict = field(default_factory=dict)

    @property
    def ready(self) -> bool:
        return self.bundle is not None

    @property
    def meta(self) -> dict:
        return (self.bundle or {}).get("meta", {})

    @property
    def overview(self) -> dict:
        return (self.bundle or {}).get("overview", {})

    @property
    def topic_labels(self) -> dict:
        return dict(zip(self.topics["topic_id"], self.topics["label"])) if len(self.topics) else {}


def _df(records: list, date_cols: tuple = ()) -> pd.DataFrame:
    df = pd.DataFrame(records or [])
    for c in date_cols:
        if c in df:
            df[c] = pd.to_datetime(df[c], errors="coerce")
    return df


def _frames(b: dict) -> dict:
    return {
        "customer": _df(b["customer"], ("date",)), "mentions": _df(b["mentions"]), "topics": _df(b["topics"]),
        "blind_spots": _df(b["blind_spots"]), "recs": _df(b["recommendations"]), "expectations": _df(b["expectations"]),
        "themes": _df(b["company_themes"]), "series": _df(b["trend_series"], ("period",)),
        "overall": _df(b["trend_overall"], ("period",)), "summary": _df(b["trend_summary"]),
        "spikes": _df(b["trend_spikes"], ("period",)),
    }


def render_sidebar() -> Ctx:
    """Render brand + company/analysis pickers + filters. Returns the context every page works from."""
    inject_css()
    client = get_client()
    ctx = Ctx(client=client)
    with st.sidebar:
        st.markdown("### 🔍 Blind Spot Detector")
        st.caption("Customer intelligence & business gap analysis")
        try:
            ctx.companies = client.list_companies()
        except ClientError as exc:
            st.error(str(exc))
            return ctx

        if ctx.companies:
            names = {c["id"]: c["name"] for c in ctx.companies}
            ids = list(names)
            cur = st.session_state.get("company_id")
            idx = ids.index(cur) if cur in ids else 0
            cid = st.selectbox("Company", ids, index=idx, format_func=lambda i: names[i], key="company_select")
            if cid != st.session_state.get("company_id"):
                st.session_state["company_id"] = cid
                st.session_state.pop("session_id", None)
            ctx.company = next(c for c in ctx.companies if c["id"] == cid)
        with st.expander("＋ New company", expanded=not ctx.companies):
            with st.form("new_company", clear_on_submit=True):
                name = st.text_input("Company name")
                industry = st.text_input("Industry (optional)")
                if st.form_submit_button("Create company", width="stretch"):
                    try:
                        c = client.create_company(name, industry or None)
                        st.session_state["company_id"] = c["id"]
                        st.rerun()
                    except ClientError as exc:
                        st.error(str(exc))
        if ctx.company is None:
            return ctx

        try:
            ctx.sessions = [s for s in client.list_analyses(ctx.company["id"])]
        except ClientError as exc:
            st.error(str(exc))
            return ctx
        done = [s for s in ctx.sessions if s["status"] == "completed"]
        if done:
            sids = [s["id"] for s in done]
            labels = {s["id"]: f"#{s['id']} · {s['started_at'][:16].replace('T', ' ')} · {s['n_customer']} conv." + (" · demo" if s["is_synthetic"] else "") for s in done}
            cur = st.session_state.get("session_id")
            sid = st.selectbox("Analysis", sids, index=sids.index(cur) if cur in sids else 0, format_func=lambda i: labels[i], key="analysis_select")
            st.session_state["session_id"] = sid
            ctx.session_id = sid
        else:
            st.caption("No completed analysis yet.")

        if ctx.session_id is not None:
            try:
                ctx.bundle = _load_bundle(client, client.mode, ctx.session_id, st.session_state.get("bundle_version", 0))
            except ClientError as exc:
                st.error(str(exc))
        if ctx.ready:
            _build_and_filter(ctx)
        st.divider()
        st.caption(f"Mode: **{client.mode}** · Embeddings: **{ctx.meta.get('embedding_backend', '—')}**")
    return ctx


def _build_and_filter(ctx: Ctx) -> None:
    f = _frames(ctx.bundle)
    cust, ment, topics = f["customer"], f["mentions"], f["topics"]
    ctx.customer, ctx.mentions, ctx.topics, ctx.blind_spots = cust, ment, topics, f["blind_spots"]
    ctx.themes, ctx.series, ctx.overall, ctx.trend_summary, ctx.spikes = f["themes"], f["series"], f["overall"], f["summary"], f["spikes"]
    ctx.emerging = ctx.bundle["trend_emerging"]
    if len(ment) and len(cust):
        ment = ment.merge(cust[["record_id", "date", "customer_id", "source"]], on="record_id", how="left")
        ctx.mentions = ment

    st.markdown("##### Filters")
    labels = ctx.topic_labels
    sel_topics = st.multiselect("Topic", list(labels), format_func=lambda i: labels[i], key="f_topic", placeholder="All topics")
    sel_sent = st.multiselect("Sentiment", SENTIMENTS, key="f_sent", placeholder="All sentiments")
    sel_sev = st.multiselect("Severity", SEVERITIES, key="f_sev", placeholder="All severities")
    sources = sorted(cust["source"].dropna().unique().tolist()) if len(cust) else []
    sel_src = st.multiselect("Data source", sources, key="f_src", placeholder="All sources")
    date_range = None
    if len(cust) and cust["date"].notna().any():
        dmin, dmax = cust["date"].min().date(), cust["date"].max().date()
        if dmin < dmax:
            date_range = st.date_input("Date range", (dmin, dmax), min_value=dmin, max_value=dmax, key="f_date")
        else:
            st.caption(f"All records dated {dmin}")
    else:
        st.caption("No dates in this dataset.")
    ctx.filters = {"topics": sel_topics, "sentiments": sel_sent, "severities": sel_sev, "sources": sel_src, "dates": date_range}

    cf = cust.copy()
    if sel_topics:
        cf = cf[cf["topic_id"].isin(sel_topics)]
    if sel_sent:
        cf = cf[cf["label"].isin(sel_sent)]
    if sel_src:
        cf = cf[cf["source"].isin(sel_src)]
    if date_range is not None and len(date_range) == 2 and (date_range[0] != dmin or date_range[1] != dmax):
        cf = cf[cf["date"].between(pd.Timestamp(date_range[0]), pd.Timestamp(date_range[1]) + pd.Timedelta(days=1))]
    ctx.customer_f = cf

    mf = ctx.mentions[ctx.mentions["record_id"].isin(cf["record_id"])] if len(ctx.mentions) else ctx.mentions
    if sel_topics and len(mf):
        mf = mf[mf["topic_id"].isin(sel_topics)]
    if sel_sent and len(mf):
        mf = mf[mf["label"].isin(sel_sent)]
    ctx.mentions_f = mf

    tf = topics.copy()
    if sel_topics:
        tf = tf[tf["topic_id"].isin(sel_topics)]
    ctx.topics_f = _topic_stats_filtered(tf, mf)

    bs = ctx.blind_spots.copy()
    if sel_topics:
        bs = bs[bs["topic_id"].isin(sel_topics)]
    if sel_sev:
        bs = bs[bs["severity"].isin(sel_sev)]
    ctx.blind_spots_f = bs
    recs = f["recs"]
    if len(recs):
        if sel_topics:
            recs = recs[recs["topic_id"].isin(sel_topics)]
        if sel_sev:
            recs = recs[recs["severity"].isin(sel_sev)]
    ctx.recs_f = recs
    ex = f["expectations"]
    if len(ex) and sel_topics:
        ex = ex[ex["topic_id"].isin(sel_topics)]
    ctx.expectations_f = ex


def _topic_stats_filtered(topics: pd.DataFrame, mentions: pd.DataFrame) -> pd.DataFrame:
    """Recompute volume/sentiment statistics for the CURRENT filters (scores/importance stay as analysed)."""
    if not len(topics):
        return topics
    out = topics.copy()
    if not len(mentions):
        for c in ("mentions", "conversations", "unique_customers"):
            out[c] = 0
        for c in ("avg_sentiment", "positive_pct", "negative_pct", "neutral_pct"):
            out[c] = 0.0
        return out
    g = mentions.groupby("topic_id")
    agg = pd.DataFrame({
        "mentions": g.size(), "conversations": g["record_id"].nunique(),
        "unique_customers": g["customer_id"].apply(lambda s: s.dropna().nunique() + int(s.isna().sum())),
        "avg_sentiment": g["compound"].mean(),
        "positive_pct": g["label"].apply(lambda s: (s == "positive").mean() * 100),
        "negative_pct": g["label"].apply(lambda s: (s == "negative").mean() * 100),
        "neutral_pct": g["label"].apply(lambda s: (s == "neutral").mean() * 100),
    }).reset_index()
    out = out.drop(columns=[c for c in agg.columns if c != "topic_id" and c in out.columns]).merge(agg, on="topic_id", how="left")
    out[["mentions", "conversations", "unique_customers"]] = out[["mentions", "conversations", "unique_customers"]].fillna(0).astype(int)
    out["share_pct"] = out["mentions"] / max(out["mentions"].sum(), 1) * 100
    return out


def require_analysis(ctx: Ctx) -> bool:
    """Show a friendly empty state when no analysis is available. Returns True if the page can render."""
    if ctx.company is None:
        st.info("👈 Create a company in the sidebar to get started.")
        return False
    if not ctx.ready:
        st.markdown(f"### No analysis for **{esc(ctx.company['name'])}** yet")
        note("Go to **Data Management** → load the NovaCart demo data (or upload your own customer + company datasets) and click **Run analysis**.")
        st.page_link("views/data_management.py", label="Open Data Management →", icon="🗂️")
        return False
    if ctx.session_id is not None and ctx.bundle["session"].get("is_synthetic"):
        st.markdown('<div class="bb-synth">⚠ SYNTHETIC DEMO DATA — every record in this analysis was generated for demonstration; it is not real customer feedback.</div>', unsafe_allow_html=True)
    if len(ctx.customer_f) == 0:
        st.warning("The current filters exclude every record. Clear some filters in the sidebar.")
        return False
    return True
