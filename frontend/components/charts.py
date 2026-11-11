"""Plotly figure builders. Every figure is built from analysed data passed in - nothing is hardcoded."""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from frontend.components.style import PALETTE, SEVERITY_COLORS

_FONT = dict(family="-apple-system, Segoe UI, Roboto, sans-serif", color="#334155", size=12)
SENT_COLORS = {"positive": PALETTE["pos"], "neutral": PALETTE["neu"], "negative": PALETTE["neg"]}


def _style(fig: go.Figure, height: int = 360, legend: bool = True) -> go.Figure:
    fig.update_layout(height=height, margin=dict(l=10, r=10, t=36, b=10), font=_FONT, paper_bgcolor="rgba(0,0,0,0)",
                      plot_bgcolor="rgba(0,0,0,0)", showlegend=legend, hoverlabel=dict(bgcolor="white", font_size=12),
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0))
    fig.update_xaxes(gridcolor="#EEF2F6", zerolinecolor="#E2E8F0")
    fig.update_yaxes(gridcolor="#EEF2F6", zerolinecolor="#E2E8F0")
    return fig


def _short(s: str, n: int = 34) -> str:
    return s if len(s) <= n else s[: n - 1] + "…"


def sentiment_donut(customer: pd.DataFrame) -> go.Figure:
    vc = customer["label"].value_counts().reindex(["positive", "neutral", "negative"]).fillna(0)
    fig = go.Figure(go.Pie(labels=vc.index.str.title(), values=vc.values, hole=.62, sort=False,
                           marker=dict(colors=[SENT_COLORS[k] for k in vc.index]), textinfo="percent",
                           hovertemplate="%{label}: %{value} conversations (%{percent})<extra></extra>"))
    fig.add_annotation(text=f"<b>{int(vc.sum())}</b><br><span style='font-size:11px;color:#64748B'>conversations</span>",
                       showarrow=False, font=dict(size=20))
    return _style(fig, 300)


def sentiment_histogram(customer: pd.DataFrame) -> go.Figure:
    fig = px.histogram(customer, x="compound", nbins=30, color="label", color_discrete_map=SENT_COLORS,
                       category_orders={"label": ["negative", "neutral", "positive"]},
                       labels={"compound": "Sentiment score (-1 … +1)", "label": ""})
    fig.update_layout(bargap=.05, yaxis_title="Conversations")
    return _style(fig, 300)


def topic_bar(topics: pd.DataFrame, x: str = "mentions", title_x: str = "Statements") -> go.Figure:
    d = topics.sort_values(x)
    fig = go.Figure(go.Bar(
        x=d[x], y=d["label"].map(_short), orientation="h",
        marker=dict(color=d["avg_sentiment"], colorscale=[[0, PALETTE["neg"]], [.5, "#FDE68A"], [1, PALETTE["pos"]]],
                    cmin=-.6, cmax=.6, colorbar=dict(title="Avg<br>sentiment", thickness=10, len=.7)),
        customdata=np.stack([d["avg_sentiment"], d["negative_pct"], d["conversations"]], axis=1),
        hovertemplate="<b>%{y}</b><br>" + title_x + ": %{x}<br>Avg sentiment: %{customdata[0]:.2f}<br>Negative: %{customdata[1]:.0f}%<br>Conversations: %{customdata[2]}<extra></extra>"))
    fig.update_layout(xaxis_title=title_x)
    return _style(fig, max(260, 52 * len(d) + 60), legend=False)


def topic_sentiment_stack(topics: pd.DataFrame) -> go.Figure:
    d = topics.sort_values("negative_pct")
    fig = go.Figure()
    for col, name in (("negative_pct", "Negative"), ("neutral_pct", "Neutral"), ("positive_pct", "Positive")):
        fig.add_bar(y=d["label"].map(_short), x=d[col], name=name, orientation="h", marker_color=SENT_COLORS[name.lower()],
                    hovertemplate="%{y}<br>" + name + ": %{x:.0f}%<extra></extra>")
    fig.update_layout(barmode="stack", xaxis_title="% of statements", xaxis_range=[0, 100])
    return _style(fig, max(260, 46 * len(d) + 70))


def source_negative_bar(customer: pd.DataFrame) -> go.Figure:
    g = customer.groupby("source")["label"].apply(lambda s: (s == "negative").mean() * 100).sort_values()
    fig = go.Figure(go.Bar(x=g.values, y=g.index, orientation="h", marker_color=PALETTE["neg"],
                           hovertemplate="%{y}: %{x:.0f}% negative<extra></extra>"))
    fig.update_layout(xaxis_title="% negative conversations")
    return _style(fig, max(240, 40 * len(g) + 60), legend=False)


def importance_vs_coverage(bs: pd.DataFrame) -> go.Figure:
    d = bs.sort_values("importance")
    fig = go.Figure()
    fig.add_bar(y=d["topic_label"].map(_short), x=d["importance"], name="Customer importance", orientation="h", marker_color=PALETTE["primary"],
                hovertemplate="%{y}<br>Customer importance: %{x:.0f}<extra></extra>")
    fig.add_bar(y=d["topic_label"].map(_short), x=d["coverage_norm"], name="Company coverage", orientation="h", marker_color="#F59E0B",
                hovertemplate="%{y}<br>Company coverage index: %{x:.0f}<extra></extra>")
    fig.update_layout(barmode="group", xaxis_title="Index (0-100)", xaxis_range=[0, 100])
    return _style(fig, max(300, 70 * len(d) + 70))


def gap_scatter(bs: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    for sev, g in bs.groupby("severity"):
        fig.add_trace(go.Scatter(
            x=g["coverage_norm"], y=g["importance"], mode="markers+text", name=sev, text=g["rank"].map(lambda r: f"#{int(r)}"),
            textposition="middle center", textfont=dict(color="white", size=12), hovertext=g["topic_label"], marker=dict(size=np.clip(g["mentions"] * 0.9, 24, 60), color=SEVERITY_COLORS.get(sev, "#64748B"),
                                                   line=dict(width=1, color="white"), opacity=.85),
            customdata=np.stack([g["score"], g["gap"], g["mentions"]], axis=1),
            hovertemplate="<b>%{hovertext}</b><br>Coverage: %{x:.0f}<br>Importance: %{y:.0f}<br>Gap: %{customdata[1]:.0f}<br>Score: %{customdata[0]:.1f}<extra></extra>"))
    fig.add_shape(type="rect", x0=0, x1=30, y0=50, y1=105, fillcolor="rgba(239,68,68,.06)", line_width=0, layer="below")
    fig.add_annotation(x=2, y=102, text="High importance · low coverage", showarrow=False, xanchor="left", font=dict(size=11, color="#B91C1C"))
    fig.update_layout(xaxis_title="Company coverage index (0-100) →", yaxis_title="Customer importance (0-100) →",
                      xaxis_range=[-5, 108], yaxis_range=[0, 108])
    return _style(fig, 430)


def score_bar(bs: pd.DataFrame) -> go.Figure:
    d = bs.sort_values("score")
    fig = go.Figure(go.Bar(x=d["score"], y=d["topic_label"].map(_short), orientation="h",
                           marker_color=[SEVERITY_COLORS.get(s, "#64748B") for s in d["severity"]],
                           text=[f"{v:.1f}" for v in d["score"]], textposition="outside",
                           hovertemplate="%{y}<br>Blind Spot Score: %{x:.1f}<extra></extra>"))
    for edge in (20, 40, 60, 80):
        fig.add_vline(x=edge, line_dash="dot", line_color="#CBD5E1")
    fig.update_layout(xaxis_title="Blind Spot Score (0-100)", xaxis_range=[0, 100])
    return _style(fig, max(260, 48 * len(d) + 70), legend=False)


def component_bars(row: pd.Series) -> go.Figure:
    vals = [("Customer importance", row["importance"], PALETTE["primary"]), ("Expectation gap", row["gap"], "#F97316"),
            ("Issue trend" + ("" if row["trend_available"] else " (neutral fallback)"), row["trend_used"], "#0EA5E9"),
            ("Blind Spot Score", row["score"], SEVERITY_COLORS.get(row["severity"], "#64748B"))]
    fig = go.Figure(go.Bar(x=[v[1] for v in vals], y=[v[0] for v in vals], orientation="h", marker_color=[v[2] for v in vals],
                           text=[f"{v[1]:.1f}" for v in vals], textposition="outside"))
    fig.update_layout(xaxis_range=[0, 110], yaxis=dict(autorange="reversed"))
    return _style(fig, 230, legend=False)


def theme_bar(themes: pd.DataFrame) -> go.Figure:
    d = themes.sort_values("share_pct")
    fig = go.Figure(go.Bar(x=d["share_pct"], y=d["label"].map(_short), orientation="h", marker_color="#F59E0B",
                           text=[f"{v:.0f}%" for v in d["share_pct"]], textposition="outside",
                           hovertemplate="%{y}<br>%{x:.1f}% of company messages<extra></extra>"))
    fig.update_layout(xaxis_title="% of company messages", xaxis_range=[0, max(100, d["share_pct"].max() * 1.15)])
    return _style(fig, max(260, 50 * len(d) + 60), legend=False)


def coverage_bar(bs: pd.DataFrame) -> go.Figure:
    d = bs.sort_values("coverage_share")
    fig = go.Figure(go.Bar(x=d["coverage_share"] * 100, y=d["topic_label"].map(_short), orientation="h", marker_color="#F59E0B",
                           text=[f"{v * 100:.0f}%" for v in d["coverage_share"]], textposition="outside"))
    fig.update_layout(xaxis_title="% of company messaging addressing the topic")
    return _style(fig, max(260, 50 * len(d) + 60), legend=False)


def keyword_bar(pairs: list, n: int = 15) -> go.Figure:
    d = pd.DataFrame(pairs[:n], columns=["word", "messages"]).sort_values("messages")
    fig = go.Figure(go.Bar(x=d["messages"], y=d["word"], orientation="h", marker_color=PALETTE["primary"]))
    fig.update_layout(xaxis_title="Messages containing the word")
    return _style(fig, max(260, 26 * len(d) + 60), legend=False)


def topic_volume_lines(series: pd.DataFrame, labels: dict, topic_ids: list, metric: str = "volume") -> go.Figure:
    fig = go.Figure()
    colors = px.colors.qualitative.Set2 + px.colors.qualitative.Pastel
    for i, tid in enumerate(topic_ids):
        g = series[series["topic_id"] == tid].sort_values("period")
        c = colors[i % len(colors)]
        name = _short(labels.get(tid, str(tid)), 28)
        fig.add_trace(go.Scatter(x=g["period"], y=g[metric], mode="lines+markers", name=name, line=dict(color=c, width=2), marker=dict(size=5)))
        if metric == "volume" and "volume_ma" in g:
            fig.add_trace(go.Scatter(x=g["period"], y=g["volume_ma"], mode="lines", name=f"{name} (3-pt avg)", line=dict(color=c, width=1.5, dash="dot"),
                                     showlegend=False, hoverinfo="skip"))
    fig.update_layout(yaxis_title={"volume": "Statements per period", "share": "% of all statements in period", "neg_count": "Negative statements"}.get(metric, metric),
                      hovermode="x unified")
    return _style(fig, 380)


def sentiment_trend(overall: pd.DataFrame) -> go.Figure:
    d = overall.sort_values("period")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=d["period"], y=d["avg_sentiment"], mode="markers", name="Avg sentiment", marker=dict(color="#94A3B8", size=6)))
    fig.add_trace(go.Scatter(x=d["period"], y=d["sentiment_ma"], mode="lines", name="3-period moving avg", line=dict(color=PALETTE["primary"], width=3)))
    fig.add_hline(y=0, line_color="#CBD5E1")
    fig.update_layout(yaxis_title="Avg sentiment (-1 … +1)", yaxis_range=[-1, 1])
    return _style(fig, 330)


def negative_share_trend(overall: pd.DataFrame) -> go.Figure:
    d = overall.sort_values("period")
    fig = go.Figure(go.Scatter(x=d["period"], y=d["negative_share"], mode="lines+markers", line=dict(color=PALETTE["neg"], width=2.5),
                               fill="tozeroy", fillcolor="rgba(239,68,68,.10)", name="% negative"))
    fig.update_layout(yaxis_title="% negative conversations", yaxis_range=[0, 100])
    return _style(fig, 330, legend=False)


def negative_heatmap(series: pd.DataFrame, labels: dict) -> go.Figure:
    pv = series.pivot_table(index="topic_id", columns="period", values="neg_count", aggfunc="sum").fillna(0)
    pv.index = [_short(labels.get(i, str(i)), 30) for i in pv.index]
    fig = go.Figure(go.Heatmap(z=pv.values, x=pv.columns, y=pv.index, colorscale="Reds", hovertemplate="%{y}<br>%{x|%b %d}: %{z} negative<extra></extra>",
                               colorbar=dict(title="Negative<br>statements", thickness=10)))
    return _style(fig, max(260, 44 * len(pv) + 80), legend=False)
