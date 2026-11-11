import sys
from pathlib import Path

_ROOT = str(Path(__file__).resolve().parents[2])  # project root (pages can be opened directly via URL / refresh)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import json

import streamlit as st

from frontend.components.state import render_sidebar
from frontend.components.style import note, page_header, section
from ml.scoring.engine import SEVERITY_BANDS

ctx = render_sidebar()
page_header("Methodology & Limits", "How every number in this application is calculated, and what it cannot tell you")

section("Pipeline")
st.markdown("""
1. **Collect** customer data (reviews, comments, complaints …) and company data (website copy, ads, posts …) — kept separate.
2. **Preprocess**: HTML/URL removal, whitespace and unicode normalisation, spam filter, duplicate/empty removal, language check. The original text is always kept; negations, punctuation and emojis are preserved.
3. **Sentiment**: VADER baseline (+ optional Hugging Face transformer). Aspect-based: each review is split into clauses, scored separately and linked to a topic.
4. **Topics**: BERTopic (SBERT → UMAP → HDBSCAN → c-TF-IDF) discovers topics from *your* data; KMeans fallback for small datasets.
5. **Needs & expectations**: cue-pattern detection of explicit requests/expectations/unmet needs + SBERT clustering of complaints; implied expectations are labelled *inferred*.
6. **Company communication**: separate clustering into themes; share % = messages in theme ÷ all messages.
7. **Semantic gap**: customer topics and company messages are compared with SBERT cosine similarity (no keyword matching alone).
8. **Scoring, trends, recommendations** (below). Everything after step 3 is deterministic and unit-tested.
""")

section("Blind Spot Score")
st.latex(r"\text{Blind Spot Score} = \frac{\text{Customer Importance} \times \text{Expectation Gap} \times \text{Issue Trend}}{100 \times 100}")
st.markdown("""
Each component is normalised to **0–100** before multiplication. Worked example: 85 × 90 × 80 ÷ 10,000 = **61.2 → High**.

| Component | How it is computed |
|---|---|
| **Customer Importance** | Weighted sum of four 0–100 scores: *frequency* (statements ÷ max over topics), *unique customers* (÷ max), *sentiment* (0.7 × negative share + 0.3 × negative intensity), *explicit requests* (share of statements that are explicit requests/expectations/unmet needs, 30 % ⇒ 100). Default weights 0.30 / 0.25 / 0.30 / 0.15. |
| **Expectation Gap** | 0.6 × (100 − *coverage index*) + 0.4 × (100 − *semantic-similarity index*). **Coverage index** = share of company communication that semantically addresses the topic (softmax over SBERT cosine similarities to topic centroids; messages below a similarity floor count as off-topic), scaled so the best-covered topic = 100. **Similarity index** = mean of the 3 closest company messages' similarity, min-max scaled across topics. |
| **Issue Trend** | 50 = unchanged, 100 = strongly growing and more negative, 0 = strongly falling. 0.6 × volume-growth score + 0.4 × negativity-change score, comparing the *recent third* of the time span with the earlier period on **shares** (not raw counts) and shrinking weak evidence toward 50 using a two-proportion z-test. Clipped below at the trend floor (default 10) so a fading issue is dampened but never erased. |
""")
note("Missing history: if there are fewer than 20 dated records, fewer than 7 days of data, or fewer than 8 statements for a topic, the trend is marked UNAVAILABLE and a neutral value (50) is used in the formula — the app never pretends an issue is increasing.")
st.markdown("**Severity bands:** " + " · ".join(f"**{n}** ≤ {u}" for u, n in SEVERITY_BANDS) + " (0–20 Low, 21–40 Moderate, 41–60 Significant, 61–80 High, 81–100 Critical).")

section("Four different things that are easy to confuse")
st.markdown("""
| Class | Meaning |
|---|---|
| **Genuine blind spot** | Important to customers, clearly negative, large gap, and the company barely mentions it (coverage < 15). |
| **Unmet operational need** | Negative and dominated by explicit "I can't…/please add…/I expect…" statements — a product/operations gap messaging alone won't fix. |
| **Negative customer experience** | Customers are unhappy although the company *does* communicate about the topic — possible promise-vs-reality mismatch. |
| **Communication gap** | Customers discuss it (not mainly negatively) but the company says little — a messaging opportunity. |
| **Misplaced emphasis** | The company communicates about it heavily (coverage ≥ 50) and far beyond its customer importance (coverage − importance ≥ 35). |

*A lack of marketing coverage does not prove the company lacks the capability* — it proves the topic is not being communicated.
""")

section("Trend method")
st.markdown("""
Buckets are day/week/month depending on the data span. Moving averages use 3 buckets. A topic is **increasing/declining** only if its recent vs historical share differs with p < 0.10; **emerging** if it was ~absent before and now has ≥ 3 statements. Spikes use a robust (median/MAD) z-score ≥ 2.5 on negative counts. Growth in sample volume alone therefore does not create a trend.
""")

section("Assumptions & known limitations")
st.markdown("""
- **VADER is lexicon-based.** It misses sarcasm and implicit complaints; we add a documented domain lexicon and "service-failure" cue rules, but accuracy is not that of a fine-tuned model. Enable the optional transformer for context.
- **Offline fallback embeddings (TF-IDF/LSA)** capture word co-occurrence, not true paraphrase — SBERT is strongly preferred for the semantic comparison.
- **Topic discovery is unsupervised** — topic labels are keywords, and similar topics can merge or split. Small datasets (< 30 records) use KMeans and give low-confidence topics.
- **Expectation cues are regex-based** and English-only; inferred expectations are hypotheses, flagged as such.
- **Coverage is relative** (best-covered topic = 100), so values compare topics within one analysis, not across companies.
- **Correlation, not causation**: a high score means customers care and the company is quiet — it does not prove the company is unaware or incapable.
- Data you upload is only as representative as its sources; review platforms over-represent extreme opinions.
- Web extraction handles only public, server-rendered pages and respects robots.txt.
""")

section("Current default scoring configuration")
try:
    st.code(json.dumps(ctx.client.get_scoring_config(), indent=2), language="json")
except Exception as exc:  # noqa: BLE001
    st.caption(f"Configuration unavailable: {exc}")
