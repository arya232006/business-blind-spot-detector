"""Module 5 - customer need & expectation detection.

Goes beyond 'what are customers talking about' to 'what do they want'.

Every output row has ``kind`` and ``is_inferred``:
  complaint             - negative statements about a topic                                  (observed)
  explicit_expectation  - customer states what should happen ("should", "promised", "I expect") (observed)
  feature_request       - customer asks for something to be added/changed ("please add ...")    (observed)
  unmet_need            - customer cannot do/find something ("no way to ...", "can't reach ...") (observed)
  recurring_frustration - strongly negative topic that persists over time / repeat customers   (derived)
  inferred_expectation  - what complaints IMPLY customers expect ("faster refunds")            (INFERRED)

Inferred expectations are never presented as things customers explicitly said.
Method: regex cue lexicons (transparent, testable) + SBERT clustering of complaint clauses into 'need groups'
+ keyphrase extraction + extractive summarisation (the clause closest to each cluster centroid)."""
from __future__ import annotations

import re
from typing import Sequence

import numpy as np
import pandas as pd

from config.logging_config import get_logger
from ml.embeddings import Embedder, l2_normalize
from ml.text_utils import top_keywords, truncate

log = get_logger(__name__)

FEATURE_REQUEST = re.compile(
    r"\b(please (add|allow|let|make|give|introduce|include|bring)|can you (add|make|allow|please)|could you (add|make|allow)|"
    r"would (love|like) (a|an|to|it)|i wish|wish (there|you|the|it)|it would be (great|nice|good|helpful)|would be (great|nice) (if|to)|"
    r"(add|introduce|include) (a|an|the|more)|should (add|allow|offer|include|have a)|allow us to|let us|give us|need a way|"
    r"want (a|an|to be able)|can we (get|have))\b", re.I)
EXPLICIT_EXPECTATION = re.compile(
    r"\b(i (just )?(expect|expected|want|wanted|need|needed)|we expect|should (be|take|have|not|never)|supposed to|"
    r"promised|was promised|i only wanted|deserve|at least|must (be|have)|expected to|is not acceptable|unacceptable)\b", re.I)
UNMET_NEED = re.compile(
    r"\b(no way to|there is no|there's no|can'?t (find|reach|track|contact|get)|cannot (find|reach|track|contact|get)|unable to|"
    r"no option|not possible|no phone|no number|nowhere|how do i|why is it so hard|hard to (reach|contact|find)|"
    r"without (a|any) way)\b", re.I)
# "nobody replied" style statements are complaints (observed failures), not explicit statements of a missing capability
NO_RESPONSE = re.compile(
    r"\b(no (update|updates|explanation|timeline|response|reply)|never (replied|responded|called|answered|came|showed)|"
    r"nobody (responds|replies|answers|called|came|showed)|no one (responds|replies|answers|called))\b", re.I)

# complaint pattern -> expectation it implies (ordered, transparent, extendable)
EXPECTATION_CUES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b(waiting|waited|days|weeks|slow|forever|delay\w*|late|took (so )?long|ages|taking long|week)\b", re.I), "faster resolution and turnaround"),
    (re.compile(r"\b(nobody|no one|never (replied|responded|answered|called)|ignored|no response|no reply|no update\w*|no explanation|no timeline|zero repl\w+|not clear)\b", re.I), "timely responses and proactive status updates"),
    (re.compile(r"\b(real person|actual (person|human)|human|live agent|agent|phone number|callback|call back|chatbot|bot\b|speak to)\b", re.I), "easy access to a human support agent"),
    (re.compile(r"\b(misleading|promised|not true|inflated|different answer|different pages|confusing|contradict\w*)\b", re.I), "honest and consistent promises/information"),
    (re.compile(r"\b(crash\w*|hang\w*|freez\w*|laggy|lag\b|blank screen|glitch\w*|load\w* (slowly|ages|forever))\b", re.I), "stable and fast app performance"),
    (re.compile(r"\b(wrong item|damaged|broken|faulty|cracked|stopped working|poor quality|cheap|scratch\w*|worse than)\b", re.I), "accurate fulfilment and reliable product quality"),
    (re.compile(r"\b(track\w*|where is|status|out for delivery|no movement)\b", re.I), "transparent order/refund tracking"),
    (re.compile(r"\b(charged twice|deducted|double charge|payment failed|declined|timed out|billed)\b", re.I), "reliable payments and prompt reversal of failed charges"),
    (re.compile(r"\b(partial|rejected|closed (automatically|as)|without (any )?explanation|store credit)\b", re.I), "fair, clearly explained resolutions"),
]


def classify_statement(text: str, compound: float) -> list[str]:
    """Return the signals present in one statement. Pure function -> unit tested."""
    signals = []
    if FEATURE_REQUEST.search(text):
        signals.append("feature_request")
    if EXPLICIT_EXPECTATION.search(text):
        signals.append("explicit_expectation")
    if UNMET_NEED.search(text):
        signals.append("unmet_need")
    if compound <= -0.05 or ((UNMET_NEED.search(text) or NO_RESPONSE.search(text)) and compound < 0.05):
        signals.append("complaint")
    return signals


def infer_expectations(complaint_texts: Sequence[str], top_k: int = 2, min_share: float = 0.15) -> list[tuple[str, float]]:
    """Which expectations do these complaints imply, and in what share of the complaints?"""
    n = len(complaint_texts)
    if n == 0:
        return []
    counts = []
    for _, phrase in EXPECTATION_CUES:
        counts.append(0)
    for t in complaint_texts:
        for i, (pat, _) in enumerate(EXPECTATION_CUES):
            if pat.search(t):
                counts[i] += 1
    ranked = sorted(((EXPECTATION_CUES[i][1], c / n) for i, c in enumerate(counts) if c / n >= min_share), key=lambda x: -x[1])
    return ranked[:top_k]


def _cluster_clauses(emb: np.ndarray, distance_threshold: float) -> np.ndarray:
    from sklearn.cluster import AgglomerativeClustering

    if len(emb) < 2:
        return np.zeros(len(emb), dtype=int)
    return AgglomerativeClustering(n_clusters=None, metric="cosine", linkage="average",
                                   distance_threshold=distance_threshold).fit_predict(emb)


def _evidence(rows: pd.DataFrame, k: int = 5) -> list[dict]:
    out = []
    for _, r in rows.head(k).iterrows():
        out.append({
            "record_id": int(r["record_id"]),
            "text": truncate(str(r.get("clause") or r.get("text_clean") or ""), 240),
            "date": None if pd.isna(r.get("date")) else pd.Timestamp(r["date"]).strftime("%Y-%m-%d"),
            "customer_id": None if pd.isna(r.get("customer_id")) else str(r["customer_id"]),
            "compound": round(float(r["compound"]), 3),
        })
    return out


def detect_expectations(
    mentions: pd.DataFrame,
    records: pd.DataFrame,
    topics: list[dict],
    embedder: Embedder,
) -> pd.DataFrame:
    """Build the customer expectation table.

    mentions : output of ml.sentiment.extract_aspect_mentions (record_id, clause, topic_id, compound, label)
    records  : preprocessed customer records (record_id, customer_id, date, text_clean ...)
    topics   : topic dicts from discover_topics (topic_id, label, keywords)"""
    cols = ["topic_id", "topic_label", "kind", "summary", "is_inferred", "support_count", "share_pct", "keywords", "evidence"]
    if mentions is None or mentions.empty:
        return pd.DataFrame(columns=cols)

    extra = [c for c in ("customer_id", "date", "text_clean") if c not in mentions.columns]
    m = mentions.merge(records[["record_id", *extra]], on="record_id", how="left") if extra else mentions.copy()
    m["signals"] = [classify_statement(c, s) for c, s in zip(m["clause"], m["compound"])]
    label_of = {t["topic_id"]: t["label"] for t in topics}
    rows: list[dict] = []

    for tid, g in m.groupby("topic_id"):
        label = label_of.get(tid, f"topic {tid}")
        n = len(g)
        complaints = g[g["signals"].map(lambda s: "complaint" in s)].sort_values("compound")
        pct = len(complaints) / n * 100

        # --- complaint groups (SBERT clustering of complaint clauses into specific needs) --------------
        if len(complaints) >= 2:
            emb = l2_normalize(embedder.encode(complaints["clause"].tolist()))
            thr = 0.55 if embedder.is_semantic else 0.85
            grp = _cluster_clauses(emb, thr)
            complaints = complaints.assign(group=grp)
            cent_rows = []
            for gid, gg in complaints.groupby("group"):
                idx = [complaints.index.get_loc(i) for i in gg.index]
                cent = l2_normalize(emb[idx].mean(axis=0, keepdims=True))[0]
                best = gg.iloc[int(np.argmax(emb[idx] @ cent))]
                cent_rows.append((len(gg), gid, best, gg))
            cent_rows.sort(key=lambda x: -x[0])
        else:
            cent_rows = [(len(complaints), 0, complaints.iloc[0], complaints)] if len(complaints) else []

        if len(complaints):
            groups_desc = [
                f"“{truncate(best['clause'], 110)}” ({cnt}x)" for cnt, _, best, _ in cent_rows[:3]
            ]
            rows.append({
                "topic_id": int(tid), "topic_label": label, "kind": "complaint", "is_inferred": False,
                "summary": f"{len(complaints)} of {n} statements about '{label}' are complaints ({pct:.0f}%). "
                           f"Most common complaint patterns: " + "; ".join(groups_desc) + ".",
                "support_count": int(len(complaints)), "share_pct": round(pct, 1),
                "keywords": top_keywords(complaints["clause"], 6), "evidence": _evidence(complaints),
            })
            inferred = infer_expectations(complaints["clause"].tolist())
            if inferred:
                phrase = " and ".join(p for p, _ in inferred)
                rows.append({
                    "topic_id": int(tid), "topic_label": label, "kind": "inferred_expectation", "is_inferred": True,
                    "summary": f"INFERRED: customers appear to expect {phrase} regarding '{label}' "
                               f"(derived from {len(complaints)} complaints - not explicitly requested).",
                    "support_count": int(len(complaints)),
                    "share_pct": round(max(s for _, s in inferred) * 100, 1),
                    "keywords": top_keywords(complaints["clause"], 6), "evidence": _evidence(complaints, 3),
                })

        # --- explicit statements --------------------------------------------------------------------
        for kind in ("explicit_expectation", "feature_request", "unmet_need"):
            sel = g[g["signals"].map(lambda s, k=kind: k in s)]
            if sel.empty:
                continue
            if kind == "feature_request" and len(sel) >= 2:  # one row per distinct request
                emb = l2_normalize(embedder.encode(sel["clause"].tolist()))
                grp = _cluster_clauses(emb, 0.6 if embedder.is_semantic else 0.9)
                sel = sel.assign(group=grp)
                for _, gg in sel.groupby("group"):
                    rows.append(_explicit_row(tid, label, kind, gg, n))
            else:
                rows.append(_explicit_row(tid, label, kind, sel, n))

        # --- recurring frustration ------------------------------------------------------------------
        neg_pct = float((g["label"] == "negative").mean() * 100)
        weeks_active = g["date"].dropna().dt.to_period("W").nunique() if g["date"].notna().any() else 0
        per_customer = g.dropna(subset=["customer_id"]).groupby("customer_id")["record_id"].nunique()
        repeaters = int((per_customer >= 2).sum())
        if n >= 5 and neg_pct >= 50 and (weeks_active >= 3 or repeaters >= 1):
            why = []
            if weeks_active >= 3:
                why.append(f"reported in {weeks_active} different weeks")
            if repeaters:
                why.append(f"{repeaters} customers raised it more than once")
            rows.append({
                "topic_id": int(tid), "topic_label": label, "kind": "recurring_frustration", "is_inferred": False,
                "summary": f"Recurring frustration around '{label}': {neg_pct:.0f}% negative across {n} statements, " + ", ".join(why) + ".",
                "support_count": int(n), "share_pct": round(neg_pct, 1),
                "keywords": top_keywords(complaints["clause"], 6) if len(complaints) else [],
                "evidence": _evidence(complaints if len(complaints) else g, 3),
            })
    out = pd.DataFrame(rows, columns=cols)
    log.info("Expectation detection produced %d rows (%s)", len(out), out["kind"].value_counts().to_dict() if len(out) else {})
    return out


_KIND_TEXT = {
    "explicit_expectation": "Customers explicitly state expectations about '{label}'",
    "feature_request": "Explicit feature request about '{label}'",
    "unmet_need": "Unmet need around '{label}'",
}


def _explicit_row(tid, label, kind, sel: pd.DataFrame, n_topic: int) -> dict:
    sel = sel.sort_values("compound")
    rep = sel.iloc[0]["clause"]
    return {
        "topic_id": int(tid), "topic_label": label, "kind": kind, "is_inferred": False,
        "summary": f"{_KIND_TEXT[kind].format(label=label)}: “{truncate(rep, 150)}”"
                   + (f" (+{len(sel) - 1} similar)" if len(sel) > 1 else "") + ".",
        "support_count": int(len(sel)), "share_pct": round(len(sel) / n_topic * 100, 1),
        "keywords": top_keywords(sel["clause"], 5), "evidence": _evidence(sel, 4),
    }
