import sys
from pathlib import Path

_ROOT = str(Path(__file__).resolve().parents[2])  # project root (pages can be opened directly via URL / refresh)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import time

import pandas as pd
import streamlit as st

from frontend.client import ClientError
from frontend.components.state import bump_version, render_sidebar
from frontend.components.style import esc, note, page_header, section

ctx = render_sidebar()
page_header("Data Management", "Collect customer and company data, validate it, and run the analysis")
if ctx.company is None:
    st.info("👈 Create a company in the sidebar to get started.")
    st.stop()
client, cid = ctx.client, ctx.company["id"]
if _flash := st.session_state.pop("flash", None):
    st.success(_flash)


def _datasets():
    try:
        return client.list_datasets(cid)
    except ClientError as exc:
        st.error(str(exc))
        return []


def input_panel(kind: str, title: str, help_text: str) -> None:
    st.markdown(f"#### {title}")
    st.caption(help_text)
    method = st.radio("Input method", ["Upload file (CSV / Excel / TXT)", "Type or paste text", "Website URL"], horizontal=True, key=f"method_{kind}")
    if method.startswith("Upload"):
        f = st.file_uploader("Choose a file", type=["csv", "tsv", "xlsx", "xls", "txt", "json"], key=f"file_{kind}",
                             help="CSV/Excel need a text column (review, comment, text …). Optional: date, source, category, customer_id, rating.")
        if f is None:
            return
        content = f.getvalue()
        try:
            pv = client.preview_upload(content, f.name, kind)
        except ClientError as exc:
            st.error(f"❌ {exc}")
            return
        cols = ["(none)"] + pv["columns"]
        mapping_used = pv["mapping_used"] or {}
        with st.expander("Column mapping (auto-detected — adjust if needed)", expanded=False):
            m = {}
            grid = st.columns(3)
            for i, key in enumerate(["text", "date", "source", "category", "customer_id", "rating"]):
                cur = mapping_used.get(key)
                idx = cols.index(cur) if cur in cols else 0
                m[key] = grid[i % 3].selectbox(key.replace("_", " ").title(), cols, index=idx, key=f"map_{kind}_{key}_{f.name}")
            mapping = {k: (None if v == "(none)" else v) for k, v in m.items()}
        if mapping != {k: mapping_used.get(k) for k in mapping}:
            try:
                pv = client.preview_upload(content, f.name, kind, mapping)
            except ClientError as exc:
                st.error(f"❌ {exc}")
                return
        rep = pv["report"]
        for e in rep["errors"]:
            st.error(f"❌ {e}")
        for w in rep["warnings"]:
            st.warning(w)
        if rep["ok"]:
            st.success(f"✔ {rep['rows_valid']} of {rep['rows_in']} rows are valid")
        st.dataframe(pd.DataFrame(pv["preview"]).drop(columns=["metadata"], errors="ignore"), hide_index=True, width="stretch")
        name = st.text_input("Dataset name", value=f.name, key=f"name_{kind}_{f.name}")
        if st.button("💾 Save dataset", key=f"save_{kind}", type="primary", disabled=not rep["ok"]):
            try:
                with st.spinner("Saving…"):
                    ds = client.upload_dataset(cid, kind, content, f.name, mapping, name)
                st.session_state["flash"] = f"Saved '{ds['name']}' ({ds['n_records']} records)."
                st.rerun()
            except ClientError as exc:
                st.error(f"❌ {exc}")
    elif method.startswith("Type"):
        text = st.text_area("One record per line (or separate records with a blank line)", height=170, key=f"text_{kind}",
                            placeholder="The refund took 12 days.\nSupport never replied to my ticket." if kind == "customer" else "Free delivery on all orders above 499.\nOur new app is twice as fast.")
        src = st.text_input("Source label", value="manual_entry", key=f"src_{kind}")
        if st.button("➕ Add records", key=f"add_{kind}", type="primary"):
            try:
                ds = client.add_text(cid, kind, text, src)
                st.session_state["flash"] = f"Added {ds['n_records']} records. Note: manual text has no dates, so it does not contribute to trend analysis."
                st.rerun()
            except ClientError as exc:
                st.error(f"❌ {exc}")
    else:
        url = st.text_input("Public web page URL", placeholder="https://example.com/about", key=f"url_{kind}")
        note("Only public pages are fetched. robots.txt is respected; logins, CAPTCHAs and private network addresses are never bypassed. "
             "Pages rendered purely by JavaScript may return no text.")
        if st.button("🌐 Extract text & save", key=f"urlbtn_{kind}", type="primary", disabled=not url):
            try:
                with st.spinner("Fetching page…"):
                    ds = client.add_url(cid, kind, url)
                st.session_state["flash"] = f"Extracted {ds['n_records']} text blocks."
                st.rerun()
            except ClientError as exc:
                st.error(f"❌ {exc}")


tab_demo, tab_c, tab_k, tab_run, tab_hist = st.tabs(["🚀 Quick start", "1 · Customer data", "2 · Company data", "3 · Run analysis", "📜 Analysis history"])

with tab_demo:
    section("Try it instantly with the NovaCart demo", "A fictional e-commerce company with 130+ synthetic customer conversations and 34 synthetic company messages. No API keys needed.")
    note("All demo records are SYNTHETIC — generated to demonstrate the pipeline, not real customer feedback. They are labelled as such everywhere in the app.", warn=True)
    if st.button("📥 Load NovaCart demo data into this company", type="primary"):
        try:
            res = client.load_sample(cid)
            st.session_state["flash"] = res["message"]
            st.rerun()
        except ClientError as exc:
            st.error(f"❌ {exc}")
    st.caption("Then open the **Run analysis** tab. Tip: create a separate company for your own data so demo and real data never mix.")

with tab_c:
    input_panel("customer", "Customer data", "Reviews, social comments, forum posts, complaints, feedback — what customers say.")
with tab_k:
    input_panel("company", "Company data", "Website copy, product descriptions, ads, announcements, social posts — what the company says.")

all_ds = _datasets()
with tab_run:
    section("Datasets for this company")
    if not all_ds:
        st.info("No datasets yet. Load the demo data or add your own in the previous tabs.")
    else:
        df = pd.DataFrame(all_ds)
        st.dataframe(pd.DataFrame({"ID": df["id"], "Kind": df["kind"], "Name": df["name"], "Type": df["source_type"], "Records": df["n_records"],
                                   "Synthetic": df["is_synthetic"].map({True: "yes (demo)", False: ""}), "Added": df["created_at"].str[:16].str.replace("T", " ")}),
                     hide_index=True, width="stretch")
        with st.expander("Preview / delete a dataset"):
            pick = st.selectbox("Dataset", [d["id"] for d in all_ds], format_func=lambda i: next(f"#{d['id']} {d['name']}" for d in all_ds if d["id"] == i), key="ds_pick")
            c1, c2 = st.columns([4, 1])
            if c1.button("Show first 50 records"):
                try:
                    st.dataframe(pd.DataFrame(client.dataset_records(pick, 50)), hide_index=True, width="stretch")
                except ClientError as exc:
                    st.error(str(exc))
            if c2.button("🗑 Delete", key="del_ds"):
                try:
                    client.delete_dataset(pick)
                    st.rerun()
                except ClientError as exc:
                    st.error(str(exc))

    cust_ds = [d for d in all_ds if d["kind"] == "customer"]
    comp_ds = [d for d in all_ds if d["kind"] == "company"]
    section("Run the full analysis", "Sentiment → topics → expectations → company analysis → semantic gap → scoring → trends → recommendations")
    a, b = st.columns(2)
    # the key embeds the dataset ids so the default selection refreshes whenever datasets are added/removed
    ck = "-".join(str(d["id"]) for d in cust_ds)
    kk = "-".join(str(d["id"]) for d in comp_ds)
    sel_c = a.multiselect("Customer datasets", [d["id"] for d in cust_ds], default=[d["id"] for d in cust_ds],
                          format_func=lambda i: next(d["name"] for d in cust_ds if d["id"] == i), key=f"run_c_{cid}_{ck}")
    sel_k = b.multiselect("Company datasets", [d["id"] for d in comp_ds], default=[d["id"] for d in comp_ds],
                          format_func=lambda i: next(d["name"] for d in comp_ds if d["id"] == i), key=f"run_k_{cid}_{kk}")
    if not cust_ds or not comp_ds:
        st.warning("You need at least one customer dataset AND one company dataset.")
    if sel_c and sel_k and any(d["is_synthetic"] for d in all_ds if d["id"] in sel_c + sel_k) and not all(d["is_synthetic"] for d in all_ds if d["id"] in sel_c + sel_k):
        st.warning("You selected both synthetic demo data and other data. Results will mix them.")
    if st.button("🚀 Run analysis", type="primary", disabled=not (sel_c and sel_k)):
        try:
            sid = client.start_analysis(cid, sel_c, sel_k)
            bar = st.progress(0, text="Starting…")
            while True:
                s = client.analysis_status(sid)
                bar.progress(min(s["progress"], 100) / 100, text=f"{s['message']} ({s['progress']}%)")
                if s["status"] != "running":
                    break
                time.sleep(1.0)
            if s["status"] == "completed":
                bump_version()
                st.session_state["session_id"] = sid
                st.success("✅ Analysis complete. Open the Overview page from the sidebar to explore the results.")
                st.page_link("views/overview.py", label="Go to Overview →", icon="📊")
            else:
                st.error(f"❌ Analysis failed: {s['error']}")
        except ClientError as exc:
            st.error(f"❌ {exc}")

with tab_hist:
    section("Analysis history", "Every run is stored with its data, settings and results")
    if not ctx.sessions:
        st.info("No analyses yet.")
    else:
        h = pd.DataFrame(ctx.sessions)
        st.dataframe(pd.DataFrame({"ID": h["id"], "Status": h["status"], "Started": h["started_at"].str[:16].str.replace("T", " "), "Customer records": h["n_customer"],
                                   "Company messages": h["n_company"], "Topics": h["total_topics"], "Blind spots": h["total_blind_spots"],
                                   "Avg score": h["avg_blind_spot_score"].round(1), "Runtime (s)": h["runtime_seconds"], "Demo data": h["is_synthetic"].map({True: "yes", False: ""}),
                                   "Error": h["error"].fillna("")}), hide_index=True, width="stretch")
        done = [s["id"] for s in ctx.sessions if s["status"] == "completed"]
        c1, c2, c3 = st.columns([3, 1, 1])
        sid = c1.selectbox("Analysis", [s["id"] for s in ctx.sessions], format_func=lambda i: f"#{i}", key="hist_pick")
        if c2.button("Open", disabled=sid not in done):
            st.session_state["session_id"] = sid
            st.rerun()
        if c3.button("🗑 Delete", key="del_session"):
            try:
                client.delete_analysis(sid)
                st.session_state.pop("session_id", None)
                bump_version()
                st.rerun()
            except ClientError as exc:
                st.error(str(exc))
