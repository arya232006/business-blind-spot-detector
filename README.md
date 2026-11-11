# 🔍 Business Blind Spot Detector

**An AI-powered customer-intelligence and business-gap analysis platform.**
It compares *what a company communicates* (website copy, ads, posts, announcements) with *what customers actually say and expect* (reviews, comments, complaints), finds the mismatches, scores them, tracks whether they are getting worse, and recommends what to do.

> Not just sentiment analysis. The core question is: **"Which important customer concerns is the company talking about too little — and what should it prioritise?"**

| The five business questions | Where answered |
|---|---|
| What are customers talking about? | *Customer Intelligence → Topics* (BERTopic, discovered from the data) |
| What do customers actually want and expect? | *Customer Intelligence → Needs & expectations* (observed vs **inferred**) |
| What is the company currently communicating? | *Company Communication* (themes, promises, coverage) |
| What important concerns is it overlooking? | *Blind Spot Analysis* (ranked, scored, with evidence) |
| What should it prioritise? | *Recommendations* (product / support / operations / communication) |

> ⚠️ The bundled **NovaCart** dataset is **synthetic**: a fictional e-commerce company with generated records, clearly labelled `is_synthetic=True` / `data_origin=synthetic_demo` and flagged in the UI. It is not real customer feedback.

---

## Table of contents
1. [Quick start](#1-quick-start) · 2. [Technology stack](#2-technology-stack) · 3. [Architecture](#3-architecture) · 4. [Installation](#4-installation) · 5. [Environment setup](#5-environment-setup) · 6. [Running the app](#6-running-the-app) · 7. [Using the sample data](#7-using-the-sample-data) · 8. [Uploading your own data](#8-uploading-your-own-data) · 9. [How each ML component works](#9-how-each-ml-component-works) · 10. [How the Blind Spot Score is calculated](#10-how-the-blind-spot-score-is-calculated) · 11. [API documentation](#11-api-documentation) · 12. [Database](#12-database) · 13. [Testing](#13-testing) · 14. [Docker](#14-docker) · 15. [Project structure](#15-project-structure) · 16. [Assumptions & known limitations](#16-assumptions--known-limitations) · 17. [Troubleshooting](#17-troubleshooting)

---

## 1. Quick start

```bash
# Python 3.10 – 3.12 recommended (3.11 tested). Python 3.13+ may lack wheels for torch/numba.
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt          # exact tested versions: requirements.lock.txt

streamlit run frontend/app.py            # opens http://localhost:8501
```

In the app: **Data Management → Quick start → "Load NovaCart demo data" → Run analysis** (≈10 s). No API keys, no external services. The first run downloads a ~90 MB sentence-embedding model once (then fully cached); see [offline mode](#offline--no-download-mode).

Terminal-only check (no UI): `python scripts/run_demo.py`

## 2. Technology stack

| Layer | Technology |
|---|---|
| Language | Python 3.11 (3.10–3.12 supported) |
| Data | Pandas, NumPy, SciPy |
| NLP / ML | **VADER**, Hugging Face **Transformers** (optional), **Sentence-Transformers (SBERT)**, **BERTopic**, **UMAP**, **HDBSCAN**, Scikit-learn, langdetect |
| Semantic search | **FAISS** (`IndexFlatIP`, exact cosine search over SBERT vectors; automatic NumPy fallback) |
| Backend | **FastAPI**, Pydantic v2, SQLAlchemy 2 |
| Frontend | **Next.js 16** (React, TypeScript, Tailwind, Recharts) in `web/` — and the original **Streamlit** + **Plotly** dashboard in `frontend/` |
| Database | **PostgreSQL** (Docker / production) or **SQLite** (default, zero setup) |
| Extraction | Requests, BeautifulSoup4, lxml |
| Optional LLM | Gemini REST API (wording polish only; analytics never depend on it) |
| Deployment | Docker, Docker Compose |

## 3. Architecture

```
            ┌────────────────────────── Streamlit dashboard (frontend/) ──────────────────────────┐
            │ Overview · Customer Intelligence · Company Communication · Blind Spots · Trends ·    │
            │ Recommendations · Data Management · Methodology                                      │
            └───────────────┬──────────────────────────────────────────────┬──────────────────────┘
        BLINDSPOT_MODE=local│ (in-process calls)             BLINDSPOT_MODE=api│ (HTTP/JSON)
                            ▼                                                  ▼
                   ┌────────────────────────── backend/ ──────────────────────────┐
                   │ api/routes.py (FastAPI)  →  services/ (companies, datasets,  │
                   │                              analysis jobs, persistence)      │
                   │                              services/pipeline.py  ◄─ one call runs everything
                   └───────┬─────────────────────────────────────────┬────────────┘
                           ▼                                         ▼
   ml/  ingestion → preprocessing → sentiment → topic_modeling → expectation_detection
        company_analysis → gap_analysis → trend_detection → scoring → recommendations
                           ▼
                   database/ (SQLAlchemy models, SQLite | PostgreSQL)
```

* **Each ML module has one responsibility** and is independently testable. `scoring/`, `gap_analysis/`, `trend_detection/` and `recommendations/` are fully **deterministic** (no models involved).
* **Local vs API mode:** `local` (default) lets Streamlit call the same service layer the REST API uses — one process, one command. `api` (used by Docker Compose) makes the dashboard talk to FastAPI. Both go through the same `frontend/client.py` interface.
* **Analyses run as background jobs** with live progress (12 steps). Results are persisted, so every run is reproducible and browsable in *Analysis history*.
* **Company isolation:** every dataset, analysis and result belongs to exactly one company (foreign keys + scoped queries; covered by a test).

## 4. Installation

```bash
git clone <repo> && cd business-blind-spot-detector
python3.11 -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

`requirements.txt` holds compatible minimum versions; `requirements.lock.txt` is the exact set this project was developed and tested with (`pip install -r requirements.lock.txt`).
**NLTK / spaCy:** the original brief suggests one of them for preprocessing. This project deliberately uses scikit-learn's English stop-word list plus regular expressions instead (`ml/text_utils.py`, `ml/preprocessing`): both libraries need a separate corpus/model download at runtime, which would make results depend on the machine and break the offline guarantee. Negation words are removed from the stop-word list so they are never dropped.

## 5. Environment setup

```bash
cp .env.example .env     # then edit; nothing is hardcoded, secrets live only in .env
```

| Variable | Default | Meaning |
|---|---|---|
| `DATABASE_URL` | `sqlite:///data/blindspot.db` | e.g. `postgresql+psycopg2://user:pass@localhost:5432/blindspot` |
| `BLINDSPOT_MODE` | `local` | `local` = in-process, `api` = Streamlit → FastAPI |
| `BLINDSPOT_API_URL` | `http://localhost:8000` | used when mode = `api` |
| `EMBEDDING_BACKEND` | `sbert` | `sbert` or `tfidf` (offline lightweight fallback) |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | any SentenceTransformer model |
| `USE_BERTOPIC` | `true` | `false` forces the KMeans topic fallback |
| `USE_TRANSFORMER_SENTIMENT` | `false` | adds a Hugging Face model next to VADER |
| `TRANSFORMER_SENTIMENT_MODEL` | `distilbert-base-uncased-finetuned-sst-2-english` | any text-classification model |
| `LLM_PROVIDER` / `GEMINI_API_KEY` / `GEMINI_MODEL` | `none` | optional wording polish for recommendations |
| `LOG_LEVEL`, `HTTP_TIMEOUT`, `MAX_UPLOAD_MB`, `RANDOM_SEED` | `INFO`, 15, 25, 42 | misc |

Scoring weights/thresholds are stored in `config/scoring_config.json` (created when you press **Save as default**) and can be changed in the **Blind Spot Analysis** page.

### Offline / no-download mode
`EMBEDDING_BACKEND=tfidf USE_BERTOPIC=false streamlit run frontend/app.py` runs everything with zero downloads. It also activates **automatically** if SBERT cannot be loaded. Semantic matching is weaker (TF-IDF + LSA captures word co-occurrence, not paraphrase) and the app says so in the data-quality notes.

## 6. Running the app

**Everything in one process (simplest):**
```bash
streamlit run frontend/app.py                 # http://localhost:8501
```

**Separate backend + frontend (client/server):**
```bash
# terminal 1 – REST API (docs: http://localhost:8000/docs)
uvicorn backend.main:app --reload --port 8000
# terminal 2 – dashboard talking to the API
BLINDSPOT_MODE=api BLINDSPOT_API_URL=http://localhost:8000 streamlit run frontend/app.py
```
`make api`, `make ui`, `make test`, `make demo` are provided as shortcuts.

### Next.js frontend (`web/`)
A full second frontend with the same 8 pages, built for hosting on Vercel. It calls the FastAPI backend from the browser:

```bash
uvicorn backend.main:app --port 8000      # backend
cd web && npm install && npm run dev       # http://localhost:3000
```
See [`web/README.md`](web/README.md) for Vercel deployment and for **`scripts/share.sh`**, which exposes the backend on your machine through a free tunnel so anyone can use the hosted site while your machine is running. CORS is an explicit allow-list (`CORS_ORIGINS`) by default because the API has no authentication; `PUBLIC_MODE=true` (set by `share.sh`) disables destructive endpoints and permits `CORS_ORIGINS=*`.

## 7. Using the sample data

`data/sample_customer_data.csv` (136 customer conversations) and `data/sample_company_data.csv` (34 company messages) describe the fictional app **NovaCart** over 13 weeks (2026-08-03 → 2026-11-01). They intentionally contain:

* **Refund complaints** rising sharply (spike mid-October) while the company barely mentions refunds;
* **Support** complaints (unreachable humans, chatbot loops) rising while company copy only says *"we are always here for you"*;
* **Delivery delays** while the company promises *"lightning-fast delivery"* (→ *negative customer experience*, not a blind spot);
* **Discounts & features** promoted heavily and received mostly positively (→ *misplaced emphasis*);
* **App performance** complaints early, fading later (a *declining* trend); explicit **feature requests**; positive, neutral and negative feedback; repeat complainers; multi-aspect reviews ("fast app, but refunds are slow").

Load it with one click (*Data Management → Quick start*), or `python scripts/run_demo.py`. Regenerate with `python data/generate_sample_data.py` (deterministic, seed 42). The generator also writes a `generator_label` column used **only for evaluation** — the pipeline never reads it.

Typical result (may vary slightly across machines): 5 topics; *refunds* ranks first (importance ≈ 76, coverage ≈ 8, gap ≈ 74, score ≈ 37 "Moderate", classified *genuine blind spot*, status *increasing*), *support* second, *delivery* a *negative experience*, *discounts* *misplaced emphasis*.

## 8. Uploading your own data

*Data Management* has separate **Customer data** and **Company data** tabs. Each supports **CSV / Excel / TXT upload**, **typed text**, and **website URL extraction**.

| Column | Required | Aliases recognised |
|---|---|---|
| text | **yes** | `review`, `comment`, `content`, `body`, `message`, `feedback`, `tweet`, … (otherwise the column with the longest text is used, with a warning) |
| date | recommended (needed for trends) | `date`, `created_at`, `timestamp`, `posted`, … |
| source | optional | `source`, `platform`, `channel` |
| category | optional | `category`, `type`, `topic` |
| customer_id | optional (customer data) | `user_id`, `author`, `username` … – used for *unique customers* |
| rating | optional | `rating`, `stars` |

Other columns are kept as metadata. You see a **validation report, auto-detected column mapping (editable) and a preview** before anything is saved. Handled: empty/malformed files, unsupported types, missing/unparseable dates, empty rows, too few records, non-English text (reported and excluded), duplicates and spam. TXT: one record per line, or blank-line-separated paragraphs.

**URL extraction** only fetches public pages, respects `robots.txt`, identifies itself, never logs in or solves CAPTCHAs, and refuses localhost/private addresses. Pages rendered purely by JavaScript return no text (reported clearly). No social-media API is hardwired: use CSV exports, which are fully supported.

**Tip:** create a separate company for real data so demo and real records never mix.

## 9. How each ML component works

| Module | Method | Output |
|---|---|---|
| **Ingestion** `ml/ingestion` | Parse → map columns → validate (see above) | standard schema `text, source, date, category, customer_id, rating, metadata` |
| **Preprocessing** `ml/preprocessing` | HTML/URL/mention removal, unicode & whitespace normalisation, elongation squashing, duplicate/empty/spam filtering, conservative language detection. **Original text always kept**; negations, emojis and `!?` preserved; stop-words removed only in a separate keyword column | `text_original`, `text_clean`, `text_keywords`, `language` |
| **Embeddings** `ml/embeddings.py` | SBERT `all-MiniLM-L6-v2` (cached per process), L2-normalised; automatic TF-IDF/LSA fallback | vectors for cosine similarity |
| **Sentiment** `ml/sentiment` | **VADER** baseline (compound, ±0.05 thresholds) + a documented customer-service domain lexicon and "service-failure" cue rules (VADER scores *"never called"* as +0.36). Optional **transformer** blended 50/50 with VADER. **Aspect-based:** reviews are split into clauses, each clause scored and linked to a topic by SBERT similarity — "camera amazing, but battery disappointing" → camera positive, battery negative | document sentiment + clause-level *mentions* |
| **Topics** `ml/topic_modeling` | **BERTopic** (SBERT → UMAP → HDBSCAN → c-TF-IDF), outliers re-assigned to the nearest topic if close enough; **KMeans + silhouette** fallback for small/uniform data or failures. Labels = distinctive keywords (must appear in ≥ 2 documents) | topics, keywords, representative quotes, centroids |
| **Expectations** `ml/expectation_detection` | Transparent regex cue lexicons classify each statement as *complaint / explicit expectation / feature request / unmet need*; complaints are clustered by SBERT similarity into need groups; **recurring frustration** = mostly-negative topic persisting over ≥ 3 weeks or raised repeatedly by the same customers. What complaints *imply* ("faster refunds", "access to a human") is generated separately and **always marked `INFERRED`** | `customer_expectations` rows with evidence |
| **Company analysis** `ml/company_analysis` | Company messages are embedded and clustered **separately** (KMeans on SBERT + TF-IDF hybrid) into themes; share % = messages ÷ total × 100. Promise/benefit cue detection | themes, promises, keywords, channel mix |
| **Gap analysis** `ml/gap_analysis` | Customer topic centroids vs company message vectors (cosine). *Coverage* = softmax-attention share of company messaging addressing each topic (off-topic floor); *similarity* = mean of the 3 closest messages. Rule-based classification (below) | coverage / similarity indices, classification |
| **Trends** `ml/trend_detection` | Auto day/week/month buckets, 3-point moving averages, **share-based** change (recent third vs earlier) with a two-proportion z-test, significance-shrunk trend score, robust (median/MAD) spike detection, emerging-topic detection | trend scores, status, spikes, emerging issues |
| **Scoring** `ml/scoring` | Deterministic formula below | score 0–100 + severity |
| **Recommendations** `ml/recommendations` | Template rules over measured values; cites counts, shares, quotes and any waits customers quantify ("median 13 days"); categories Product / Customer Support / Operational / Communication; priority from severity, bumped one level if the issue is emerging/increasing. Optional LLM may only *reword* | recommendations with problem, evidence, score, action, impact, priority |

**Classification (what a "blind spot" is — and is not).** A lack of marketing coverage does not prove a missing capability, so the system separates:
*Genuine blind spot* (important + negative + large gap + company barely mentions it) · *Unmet operational need* (negative, dominated by explicit "can't/please add/I expect" statements) · *Negative customer experience* (company **does** talk about it, customers disagree) · *Communication gap* (discussed, not mainly negatively, company silent) · *Misplaced emphasis* (heavily promoted, low customer importance) · *Aligned*.

## 10. How the Blind Spot Score is calculated

```
Blind Spot Score = Customer Importance × Expectation Gap × Issue Trend ÷ 100²        (0–100)
```
Each component is normalised to 0–100 first. Example: 85 × 90 × 80 ÷ 10,000 = **61.2 → High**.

| Component | Definition (defaults, all configurable) |
|---|---|
| **Customer Importance** | 0.30 · *frequency* (statements ÷ max over topics) + 0.25 · *unique customers* (÷ max) + 0.30 · *sentiment* (0.7 × negative share + 0.3 × negative intensity) + 0.15 · *explicit requests* (share of explicit request/expectation/unmet-need statements; 30 % ⇒ 100) |
| **Expectation Gap** | 0.6 · (100 − *coverage index*) + 0.4 · (100 − *similarity index*). Coverage index: topic's share of company messaging scaled so the best-covered topic = 100. Similarity index: top-3 message similarity, min-max scaled across topics |
| **Issue Trend** | 50 = unchanged · 100 = strongly growing & more negative · 0 = strongly falling. 0.6 · volume-growth + 0.4 · negativity-change on **shares** (not raw counts), shrunk toward 50 when the z-test is weak; clipped at a floor (10) so a fading issue is dampened, not erased |

**Missing history:** with < 20 dated records, < 7 days of data, or < 8 statements for a topic, the trend is marked **unavailable** and the documented neutral value (50) is used — never an invented direction. The UI labels such rows "(neutral)".

**Severity:** 0–20 Low · 21–40 Moderate · 41–60 Significant · 61–80 High · 81–100 Critical.

Weights and thresholds can be changed in **Blind Spot Analysis → Scoring weights** (*Preview*, *Apply to this analysis*, *Save as default*). Re-scoring re-uses stored components, so no NLP re-run is needed. The same methodology is documented inside the app (*Methodology & Limits*).

## 11. API documentation

Interactive docs: **http://localhost:8000/docs** (Swagger) and `/redoc`.

| Method & path | Purpose |
|---|---|
| `GET /health` | liveness |
| `GET/PUT /config/scoring` | read / save default scoring configuration |
| `POST/GET /companies`, `GET/DELETE /companies/{id}` | company CRUD (`409` duplicate, `404` unknown) |
| `POST /datasets/preview` | validate an upload without saving (mapping, preview, report) |
| `GET /companies/{id}/datasets` | list datasets |
| `POST /companies/{id}/datasets/upload` | CSV/Excel/TXT upload (`kind`, optional `mapping`, `name`) |
| `POST /companies/{id}/datasets/text` · `/url` · `/sample` | manual text · URL extraction · load synthetic demo |
| `GET /datasets/{id}/records`, `DELETE /datasets/{id}` | inspect / remove a dataset |
| `POST /companies/{id}/analyses` → `202 {session_id}` | start the full pipeline in the background |
| `GET /analyses/{id}/status` | progress (0–100), message, error |
| `GET /companies/{id}/analyses` | analysis history |
| `GET /analyses/{id}` | **complete bundle**: overview, topics, sentiment, mentions, expectations, company themes, blind spots, trends, recommendations |
| `GET /analyses/{id}/topics/{topic_id}/conversations` | the customer statements behind a topic |
| `POST /analyses/{id}/rescore` | re-score with other weights (`persist` optional) |
| `DELETE /analyses/{id}` | delete an analysis |

```bash
curl -X POST localhost:8000/companies -H 'content-type: application/json' -d '{"name":"NovaCart"}'
curl -X POST localhost:8000/companies/1/datasets/sample
curl -X POST localhost:8000/companies/1/analyses            # {"session_id":1,"status":"running"}
curl localhost:8000/analyses/1/status
curl localhost:8000/analyses/1 | jq '.blind_spots[0]'
```

## 12. Database

Normalised schema, all result tables keyed by `analysis_sessions` → `companies`: `companies`, `data_sources`, `customer_conversations`, `company_communications`, `analysis_sessions`, `detected_topics`, `sentiment_results` (+ `aspect_sentiments`), `customer_expectations`, `company_messaging_themes`, `blind_spot_results`, `trend_metrics`, `business_recommendations`. Evidence (quotes, closest company messages, every scoring component, configuration, model names, notes) is stored with each result so any number can be explained and reproduced. Tables are created automatically; reference DDL for PostgreSQL/SQLite is in `database/migrations/` (`python database/migrations/generate_schema.py`).

## 13. Testing

```bash
pytest -q          # 96 tests, ~7 s, fully offline (TF-IDF embeddings, temporary SQLite)
```
Covers: scoring formula & severity bands, configurable weights, neutral-trend fallback, re-scoring; preprocessing (negation/emoji preservation, spam, duplicates, language); ingestion (CSV/Excel/TXT, mapping, missing dates, malformed files, SSRF protection); sentiment incl. aspect-level and domain rules; expectation detection (observed vs inferred); coverage / classification; trend significance, **volume-change-is-not-a-trend**, spike detection, insufficient history; recommendations grounding; embeddings incl. an SBERT paraphrase test (auto-skipped offline); the full pipeline on the demo data; REST API workflow, validation errors and **company isolation**.

## 14. Docker

```bash
cp .env.example .env
docker compose up --build        # PostgreSQL + API (:8000) + dashboard (:8501)
```
The dashboard runs in `api` mode against the backend; PostgreSQL data, the Hugging Face model cache and logs live in named volumes. *Note: the Docker files could not be built in the environment this project was written in (no Docker available), and PostgreSQL was verified only through DDL generation — all application logic was tested on SQLite. Please report any compose issue.*

## 15. Project structure

```
web/        Next.js dashboard (app/ pages, components/, lib/)
frontend/   Streamlit dashboard: app.py (navigation) · views/ (8 dashboard pages) · components/ (state, filters, charts, style) · client.py
backend/    main.py · api/routes.py · schemas/ · services/ (pipeline, analysis jobs, persistence, datasets, companies)
ml/         ingestion · preprocessing · sentiment · topic_modeling · expectation_detection · company_analysis
            gap_analysis · scoring · trend_detection · recommendations   (+ embeddings.py, text_utils.py)
database/   models.py · connection.py · migrations/
config/     settings.py (env + ScoringConfig) · logging_config.py
data/       sample_customer_data.csv · sample_company_data.csv · generate_sample_data.py
tests/  notebooks/  scripts/run_demo.py  Dockerfile  docker-compose.yml  Makefile  requirements*.txt  .env.example
```
(`frontend/views/` is deliberately not called `pages/`: Streamlit auto-detects a `pages/` folder as the legacy multipage layout, which breaks deep links and the custom navigation.)

## 16. Assumptions & known limitations

* **Synthetic demo data** demonstrates the pipeline; its numbers say nothing about real companies.
* **VADER is lexicon-based**: sarcasm and subtle implicit complaints are missed; we mitigate with a documented domain lexicon and failure-phrase rules, but accuracy is below a fine-tuned model. The optional SST-2 transformer is binary (no neutral class) and tends to be over-confident; it is blended with VADER rather than trusted alone. Sentiment is English-only.
* **Unsupervised topics** are keyword-labelled and can merge/split related issues; with < 30 records KMeans replaces BERTopic and results are low-confidence (the app warns).
* **Expectation cues are regex-based** and English-only. *Inferred* expectations are hypotheses, never claims.
* **Coverage is relative**: the best-covered topic defines 100, so indices compare topics *within one analysis*, not across companies. Company themes come from clustering ~30 short slogans and are approximate.
* **Offline TF-IDF embeddings** do not understand paraphrase; SBERT is strongly preferred for the semantic comparison.
* **Trends** compare shares: a topic can show as "declining" because another one grew. Trends need ≥ 20 dated records spanning ≥ 7 days. Manual text and web extraction carry no real historical dates.
* **Scores measure prominence, not causation.** A high score means customers care and the company is quiet; it does not prove the company is unaware or incapable, and recommendations' "expected impact" is explicitly directional (no forecasts are invented).
* **Data representativeness**: review platforms over-represent extreme opinions; results are only as good as the sources uploaded.
* **Scale**: tuned for a laptop and a few thousand records. Embeddings are computed in-process (no FAISS index needed at this size).
* **Web extraction** works on public, server-rendered pages only. No social-media API is wired in (no credentials are assumed) — export to CSV instead.
* **Security**: no authentication layer — intended for local/demo use; put it behind a proxy with auth before exposing it.

## 17. Troubleshooting

| Symptom | Fix |
|---|---|
| `pip` cannot find torch/numba wheels | use Python 3.10–3.12 (3.11 recommended) |
| First analysis is slow / "SBERT unavailable" note | the ~90 MB model is downloading or blocked; use `EMBEDDING_BACKEND=tfidf` to run offline |
| `RuntimeWarning … encountered in matmul` | harmless numpy/Accelerate noise on macOS; filtered automatically |
| "An analysis is already running" | wait for it to finish (interrupted runs are auto-marked failed on restart) |
| Trend page says unavailable | add a `date` column with ≥ 20 dated records spanning ≥ 1 week |
| Port busy | `streamlit run frontend/app.py --server.port 8502` |
