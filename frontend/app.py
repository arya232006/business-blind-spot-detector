"""Streamlit entry point.   Run from the project root:   streamlit run frontend/app.py"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st  # noqa: E402

st.set_page_config(page_title="Business Blind Spot Detector", page_icon="🔍", layout="wide", initial_sidebar_state="expanded")

pages = [
    st.Page("views/overview.py", title="Overview", icon="📊", default=True),
    st.Page("views/customer_intelligence.py", title="Customer Intelligence", icon="🗣️"),
    st.Page("views/company_communication.py", title="Company Communication", icon="📣"),
    st.Page("views/blind_spots.py", title="Blind Spot Analysis", icon="🎯"),
    st.Page("views/trends.py", title="Trend Analysis", icon="📈"),
    st.Page("views/recommendations.py", title="Recommendations", icon="💡"),
    st.Page("views/data_management.py", title="Data Management", icon="🗂️"),
    st.Page("views/methodology.py", title="Methodology & Limits", icon="📘"),
]
st.navigation(pages).run()
