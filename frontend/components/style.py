"""Visual system: CSS, KPI cards, badges, section headers. All user-provided text is HTML-escaped."""
from __future__ import annotations

import html

import streamlit as st

PALETTE = {"primary": "#4F46E5", "pos": "#10B981", "neu": "#94A3B8", "neg": "#EF4444", "warn": "#F59E0B",
           "ink": "#0F172A", "muted": "#64748B", "line": "#E2E8F0", "bg": "#F6F7FB"}
SEVERITY_COLORS = {"Low": "#10B981", "Moderate": "#EAB308", "Significant": "#F97316", "High": "#EF4444", "Critical": "#991B1B"}
CLASS_COLORS = {"genuine_blind_spot": "#B91C1C", "unmet_operational_need": "#C2410C", "negative_experience": "#D97706",
                "communication_gap": "#2563EB", "misplaced_emphasis": "#7C3AED", "aligned": "#64748B"}
CLASS_LABELS = {"genuine_blind_spot": "Genuine blind spot", "unmet_operational_need": "Unmet operational need",
                "negative_experience": "Negative experience", "communication_gap": "Communication gap",
                "misplaced_emphasis": "Misplaced emphasis", "aligned": "Aligned / low priority"}
PRIORITY_COLORS = {"P0": "#991B1B", "P1": "#EF4444", "P2": "#F97316", "P3": "#EAB308", "P4": "#64748B"}

_CSS = """
<style>
html, body, [class*="css"] { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }
.block-container { padding-top: 3.4rem; padding-bottom: 3rem; max-width: 1400px; }
[data-testid="stSidebar"] { background: #0F172A; }
[data-testid="stSidebar"] * { color: #E2E8F0; }
[data-testid="stSidebar"] .stSelectbox label, [data-testid="stSidebar"] .stMultiSelect label,
[data-testid="stSidebar"] .stDateInput label, [data-testid="stSidebar"] .stTextInput label { color: #94A3B8 !important; font-size: .78rem; text-transform: uppercase; letter-spacing: .04em; }
[data-testid="stSidebar"] [data-baseweb="select"] * { color: #0F172A !important; }
[data-testid="stSidebar"] [data-testid="stSelectbox"] input, [data-testid="stSidebar"] [data-testid="stMultiSelect"] input, [data-testid="stSidebar"] [data-baseweb="select"] input { color: #0F172A !important; -webkit-text-fill-color: #0F172A !important; }
[data-testid="stSidebar"] [data-baseweb="select"] input::placeholder { color: #64748B !important; opacity: 1; }
[data-testid="stSidebar"] [data-baseweb="tag"] { background-color: #4F46E5 !important; }
[data-testid="stSidebar"] [data-baseweb="tag"] * { color: #fff !important; }
[data-testid="stSidebar"] [data-testid="stTextInput"] input, [data-testid="stSidebar"] [data-testid="stDateInput"] input { color: #0F172A !important; -webkit-text-fill-color: #0F172A !important; }
[data-testid="stSidebar"] [data-testid="stExpander"] { border-color: #334155; }
[data-testid="stSidebar"] .stButton > button, [data-testid="stSidebar"] [data-testid="stFormSubmitButton"] > button { background:#4F46E5; color:#fff; border:0; }
[data-testid="stSidebar"] hr { border-color: #1E293B; }
h1, h2, h3 { letter-spacing: -0.02em; color: #0F172A; }
.bb-page-title { font-size: 1.7rem; font-weight: 750; margin: 0; color:#0F172A; }
.bb-page-sub { color: #64748B; margin: .15rem 0 1.1rem 0; font-size: .95rem; }
.bb-kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(148px, 1fr)); gap: 14px; margin: .4rem 0 1.2rem 0; }
.bb-kpi { background: #fff; border: 1px solid #E2E8F0; border-radius: 14px; padding: 16px 18px; box-shadow: 0 1px 2px rgba(15,23,42,.04); position: relative; overflow: hidden; }
.bb-kpi:before { content:""; position:absolute; left:0; top:0; bottom:0; width:4px; background: var(--accent, #4F46E5); }
.bb-kpi .lbl { color:#64748B; font-size:.74rem; font-weight:600; text-transform:uppercase; letter-spacing:.05em; }
.bb-kpi .val { color:#0F172A; font-size:1.9rem; font-weight:760; line-height:1.15; margin-top:4px; }
.bb-kpi .sub { color:#64748B; font-size:.78rem; margin-top:2px; }
.bb-card { background:#fff; border:1px solid #E2E8F0; border-radius:14px; padding:16px 18px; margin-bottom:12px; box-shadow: 0 1px 2px rgba(15,23,42,.04); }
.bb-card h4 { margin: 0 0 6px 0; font-size: 1.02rem; color:#0F172A; }
.bb-card p { margin: .25rem 0; color:#334155; font-size:.92rem; line-height:1.45; }
.bb-badge { display:inline-block; padding: 2px 10px; border-radius: 999px; font-size:.72rem; font-weight:650; color:#fff; margin-right:6px; vertical-align: middle; }
.bb-badge.soft { background:#EEF2FF !important; color:#3730A3; border:1px solid #C7D2FE; }
.bb-quote { border-left: 3px solid #CBD5E1; padding: 2px 0 2px 10px; margin: 6px 0; color:#334155; font-size:.88rem; font-style: italic; }
.bb-note { background:#EFF6FF; border:1px solid #BFDBFE; color:#1E3A8A; border-radius:10px; padding:10px 14px; font-size:.88rem; margin: 6px 0 12px 0;}
.bb-warn { background:#FFFBEB; border:1px solid #FDE68A; color:#92400E; border-radius:10px; padding:10px 14px; font-size:.88rem; margin: 6px 0 12px 0;}
.bb-synth { background:#FEF3C7; border:1px solid #FCD34D; color:#78350F; border-radius:10px; padding:8px 14px; font-size:.85rem; margin-bottom: 10px; font-weight:600;}
.bb-meter { height:8px; background:#E2E8F0; border-radius:99px; overflow:hidden; margin-top:6px;}
.bb-meter > span { display:block; height:100%; border-radius:99px; }
.bb-section { font-size:1.12rem; font-weight:700; margin: 1.1rem 0 .1rem 0; color:#0F172A; }
.bb-section-sub { color:#64748B; font-size:.86rem; margin-bottom:.6rem; }
div[data-testid="stTabs"] button[role="tab"] { font-weight:600; }
.stButton > button { border-radius: 10px; font-weight:600; }
</style>
"""


def inject_css() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)


def esc(x) -> str:
    return html.escape("" if x is None else str(x))


def page_header(title: str, subtitle: str = "") -> None:
    st.markdown(f'<div class="bb-page-title">{esc(title)}</div><div class="bb-page-sub">{esc(subtitle)}</div>', unsafe_allow_html=True)


def section(title: str, subtitle: str = "") -> None:
    sub = f'<div class="bb-section-sub">{esc(subtitle)}</div>' if subtitle else ""
    st.markdown(f'<div class="bb-section">{esc(title)}</div>{sub}', unsafe_allow_html=True)


def kpi_row(items: list[tuple]) -> None:
    """items: (label, value, sub, accent_color)"""
    cards = ""
    for it in items:
        label, value, sub, accent = (list(it) + [None, None])[:4]
        cards += (f'<div class="bb-kpi" style="--accent:{accent or PALETTE["primary"]}"><div class="lbl">{esc(label)}</div>'
                  f'<div class="val">{esc(value)}</div><div class="sub">{esc(sub or "")}</div></div>')
    st.markdown(f'<div class="bb-kpis">{cards}</div>', unsafe_allow_html=True)


def badge(text: str, color: str = "#4F46E5", soft: bool = False) -> str:
    if soft:
        return f'<span class="bb-badge soft">{esc(text)}</span>'
    return f'<span class="bb-badge" style="background:{color}">{esc(text)}</span>'


def severity_badge(sev: str) -> str:
    return badge(sev, SEVERITY_COLORS.get(sev, "#64748B"))


def class_badge(cls: str) -> str:
    return badge(CLASS_LABELS.get(cls, cls), CLASS_COLORS.get(cls, "#64748B"))


def priority_badge(p: str) -> str:
    return badge(p, PRIORITY_COLORS.get(str(p)[:2], "#64748B"))


def meter(value: float, color: str = "#4F46E5") -> str:
    v = max(0, min(100, float(value or 0)))
    return f'<div class="bb-meter"><span style="width:{v:.0f}%;background:{color}"></span></div>'


def note(text: str, warn: bool = False) -> None:
    st.markdown(f'<div class="{"bb-warn" if warn else "bb-note"}">{esc(text)}</div>', unsafe_allow_html=True)


def quote(text: str, meta: str = "") -> str:
    m = f' <span style="color:#94A3B8;font-style:normal">{esc(meta)}</span>' if meta else ""
    return f'<div class="bb-quote">“{esc(text)}”{m}</div>'
