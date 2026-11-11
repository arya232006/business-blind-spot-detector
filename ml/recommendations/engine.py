"""Module 10 - business recommendations.

Deterministic and grounded: every recommendation is built from measured values (counts, shares, scores, quotes,
numbers customers themselves mention such as 'waited 12 days'). No uplift percentages are invented - the
'expected impact' states what is at stake in the data and is explicitly directional.
An optional LLM (see llm.py) may only REWORD text afterwards; it never changes scores, priorities or evidence."""
from __future__ import annotations

import re
from statistics import median

import numpy as np
import pandas as pd

from ml.embeddings import Embedder, cosine_matrix

CATEGORIES = ["Product", "Customer Support", "Operational", "Communication"]
_PROTOTYPES = {
    "Customer Support": "customer support helpdesk agent chatbot ticket response time escalation human contact service",
    "Product": "product quality app features performance bugs crashes usability design feature request items",
    "Operational": "delivery shipping refund processing returns payment logistics fulfilment orders courier warehouse",
    "Communication": "marketing messaging transparency pricing information discounts offers promises announcements",
}
_KEYWORD_RULES = [
    ("Customer Support", re.compile(r"\b(support|agent|ticket|chatbot|helpdesk|human|customer service|callback|escalat\w*)\b", re.I)),
    ("Operational", re.compile(r"\b(deliver\w*|shipping|refund\w*|return\w*|payment\w*|courier|parcel|package|charged|logistics|exchange)\b", re.I)),
    ("Product", re.compile(r"\b(app|crash\w*|feature\w*|quality|load\w*|screen|design|search|wishlist|dark mode|product|item)\b", re.I)),
]
_PRIORITY = {"Critical": "P0 - Critical", "High": "P1 - High", "Significant": "P2 - Medium", "Moderate": "P3 - Low", "Low": "P4 - Monitor"}
_BUMP = {"P3 - Low": "P2 - Medium", "P2 - Medium": "P1 - High", "P1 - High": "P0 - Critical"}
_WAIT = re.compile(r"\b(\d{1,3})\s*(?:\+\s*)?(?:working |business )?(day|days|week|weeks)\b", re.I)

ACTIONS = {
    "Customer Support": "Make a human agent reachable (e.g. live chat/phone/callback with a published response-time target), "
                        "let customers escalate out of the chatbot, and track first-response and resolution times for '{label}'.",
    "Operational": "Review the end-to-end workflow behind '{label}': find where cases stall, add status tracking/notifications "
                   "and publish realistic timelines that operations can actually meet.",
    "Product": "Investigate and fix the product/app issues behind '{label}', prioritising the most-reported problems, "
               "and ship the explicitly requested changes where feasible.",
    "Communication": "Address '{label}' openly in company communication: acknowledge the issue, explain what is changing, "
                     "and make sure public promises (site, ads, FAQs) match what operations deliver.",
}


def extract_wait_days(texts: list[str]) -> list[float]:
    days = []
    for t in texts:
        for num, unit in _WAIT.findall(t):
            days.append(float(num) * (7 if unit.lower().startswith("week") else 1))
    return days


def categorize_topics(topics: list[dict], embedder: Embedder | None) -> dict[int, str]:
    """Map each discovered topic to a recommendation category (keyword rules first, embeddings as tie-breaker)."""
    out: dict[int, str] = {}
    protos = list(_PROTOTYPES)
    proto_emb = embedder.encode([_PROTOTYPES[p] for p in protos]) if (embedder is not None and embedder.is_semantic) else None
    for t in topics:
        text = " ".join([t["label"], *t.get("keywords", [])[:5]])
        hits = {cat: len(pat.findall(text)) for cat, pat in _KEYWORD_RULES}
        best = max(hits, key=hits.get)
        if hits[best] > 0:
            out[t["topic_id"]] = best
        elif proto_emb is not None:
            doc = " ".join([text, *t.get("representative_docs", [])[:2]])
            sims = cosine_matrix(embedder.encode([doc]), proto_emb)[0]
            out[t["topic_id"]] = protos[int(np.argmax(sims))]
        else:
            out[t["topic_id"]] = "Product"
    return out


def _bump(priority: str, status: str | None) -> str:
    return _BUMP.get(priority, priority) if status in ("emerging", "increasing") else priority


def generate_recommendations(blind_spots: pd.DataFrame, expectations: pd.DataFrame, topic_category: dict[int, str],
                             company_summary: dict | None = None) -> pd.DataFrame:
    """One primary recommendation per qualifying topic (+ a communication recommendation when messaging is part of the gap)."""
    cols = ["topic_id", "topic_label", "category", "problem", "evidence", "blind_spot_score", "severity",
            "suggested_action", "expected_impact", "priority", "classification", "llm_enhanced"]
    rows: list[dict] = []
    if blind_spots is None or blind_spots.empty:
        return pd.DataFrame(columns=cols)
    inferred = {}
    if expectations is not None and len(expectations):
        for _, e in expectations[expectations["kind"] == "inferred_expectation"].iterrows():
            inferred[int(e["topic_id"])] = e["summary"]

    for _, b in blind_spots.sort_values("score", ascending=False).iterrows():
        cls = b["classification"]
        tid, label = int(b["topic_id"]), b["topic_label"]
        if cls == "aligned":
            continue
        if cls == "misplaced_emphasis":
            top = blind_spots[blind_spots["classification"].isin(["genuine_blind_spot", "unmet_operational_need"])].head(2)
            targets = ", ".join(f"'{x}'" for x in top["topic_label"]) or "the issues customers raise most"
            rows.append(_row(b, "Communication",
                             problem=f"Company messaging gives '{label}' a coverage index of {b['coverage_norm']:.0f}/100 while it ranks only {b['importance']:.0f}/100 in customer importance (a gap of {b['coverage_norm'] - b['importance']:.0f} points).",
                             action=f"Rebalance communication: shift part of the attention on '{label}' towards {targets}.",
                             impact="Customers' top concerns would see more of the company's attention. Directional - not a forecast.",
                             priority="P3 - Low"))
            continue
        if b["score"] < 5 and cls != "unmet_operational_need":
            continue
        cat = topic_category.get(tid, "Operational")
        priority = _bump(_PRIORITY[b["severity"]], b.get("trend_status"))
        ev = b.get("evidence_quotes") or []
        texts = [e["text"] for e in ev]
        waits = extract_wait_days(texts)
        wait_txt = f" Customers who quantify the wait mention a median of {median(waits):.0f} days (n={len(waits)})." if len(waits) >= 2 else ""
        problem = (f"'{label}': {b['neg_pct']:.0f}% of {int(b['mentions'])} statements from {int(b['unique_customers'])} customers are negative; "
                   f"company coverage index {b['coverage_norm']:.0f}/100 ({CLASS_TEXT.get(cls, cls)}).{wait_txt}")
        if tid in inferred:
            problem += " " + inferred[tid]
        action = ACTIONS[cat].format(label=label)
        if cls == "negative_experience":
            action = "Close the promise-versus-reality gap: " + action[0].lower() + action[1:]
        impact = (f"At stake: {b['neg_pct']:.0f}% negative sentiment across {int(b['mentions'])} '{label}' statements "
                  f"({b['share_pct']:.0f}% of all customer conversation)"
                  + (", with volume rising" if b.get("trend_status") in ("emerging", "increasing") else "")
                  + ". Directional estimate from this dataset - not a forecast.")
        rows.append(_row(b, cat, problem, action, impact, priority))
        if cls in ("genuine_blind_spot", "communication_gap") and cat != "Communication":
            rows.append(_row(b, "Communication",
                             problem=f"Company communication barely addresses '{label}' (coverage index {b['coverage_norm']:.0f}/100) although it is a prominent customer topic.",
                             action=ACTIONS["Communication"].format(label=label),
                             impact="Customers would see the issue acknowledged; this does not replace fixing the underlying cause. Directional - not a forecast.",
                             priority=_PRIORITY["Moderate"] if b["severity"] in ("Low", "Moderate") else "P2 - Medium"))
    return pd.DataFrame(rows, columns=cols)


CLASS_TEXT = {
    "genuine_blind_spot": "genuine blind spot", "unmet_operational_need": "unmet operational need",
    "negative_experience": "negative experience despite company messaging", "communication_gap": "communication gap",
}


def _row(b, category, problem, action, impact, priority) -> dict:
    return {
        "topic_id": int(b["topic_id"]), "topic_label": b["topic_label"], "category": category, "problem": problem,
        "evidence": b.get("evidence_quotes") or [], "blind_spot_score": float(b["score"]), "severity": b["severity"],
        "suggested_action": action, "expected_impact": impact, "priority": priority,
        "classification": b["classification"], "llm_enhanced": False,
    }
