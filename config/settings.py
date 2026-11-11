"""Central configuration. Every secret / environment-specific value comes from
environment variables (optionally loaded from a ``.env`` file). Nothing is hardcoded."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path

try:  # python-dotenv is optional at import time
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
except Exception:  # pragma: no cover
    pass

ROOT_DIR = Path(__file__).resolve().parents[1]


def _bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    root_dir: Path = ROOT_DIR
    # --- database -------------------------------------------------------
    # SQLite by default (zero setup). Set DATABASE_URL=postgresql+psycopg2://... for PostgreSQL.
    database_url: str = field(
        default_factory=lambda: os.getenv("DATABASE_URL", f"sqlite:///{ROOT_DIR / 'data' / 'blindspot.db'}")
    )
    # --- app wiring -----------------------------------------------------
    # "local": Streamlit calls the service layer in-process. "api": Streamlit talks to FastAPI over HTTP.
    frontend_mode: str = field(default_factory=lambda: os.getenv("BLINDSPOT_MODE", "local").lower())
    api_url: str = field(default_factory=lambda: os.getenv("BLINDSPOT_API_URL", "http://localhost:8000"))
    # Browser origins allowed to call the API (comma-separated). The backend has NO authentication, so this must stay an
    # explicit list - never a wildcard. Add your deployed frontend origin here, e.g. https://my-app.vercel.app
    cors_origins: tuple = field(default_factory=lambda: tuple(
        o.strip().rstrip("/") for o in os.getenv(
            "CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000,http://localhost:8501,http://127.0.0.1:8501").split(",") if o.strip()))
    # --- NLP models -----------------------------------------------------
    # "sbert" = SentenceTransformer (needs a one-time model download), "tfidf" = offline lightweight fallback.
    embedding_backend: str = field(default_factory=lambda: os.getenv("EMBEDDING_BACKEND", "sbert").lower())
    embedding_model: str = field(default_factory=lambda: os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2"))
    use_transformer_sentiment: bool = field(default_factory=lambda: _bool("USE_TRANSFORMER_SENTIMENT", False))
    transformer_sentiment_model: str = field(
        default_factory=lambda: os.getenv(
            "TRANSFORMER_SENTIMENT_MODEL", "distilbert-base-uncased-finetuned-sst-2-english"
        )
    )
    use_bertopic: bool = field(default_factory=lambda: _bool("USE_BERTOPIC", True))
    random_seed: int = field(default_factory=lambda: int(os.getenv("RANDOM_SEED", "42")))
    # --- optional LLM (core analytics never depend on it) ---------------
    llm_provider: str = field(default_factory=lambda: os.getenv("LLM_PROVIDER", "none").lower())  # none | gemini
    gemini_api_key: str = field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))
    gemini_model: str = field(default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-1.5-flash"))
    # --- data extraction --------------------------------------------------
    http_timeout: int = field(default_factory=lambda: int(os.getenv("HTTP_TIMEOUT", "15")))
    user_agent: str = field(
        default_factory=lambda: os.getenv("SCRAPER_USER_AGENT", "BusinessBlindSpotDetector/1.0 (academic project)")
    )
    max_upload_mb: int = field(default_factory=lambda: int(os.getenv("MAX_UPLOAD_MB", "25")))
    # --- logging --------------------------------------------------------
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO").upper())
    log_dir: Path = field(default_factory=lambda: Path(os.getenv("LOG_DIR", str(ROOT_DIR / "logs"))))
    sample_customer_csv: Path = ROOT_DIR / "data" / "sample_customer_data.csv"
    sample_company_csv: Path = ROOT_DIR / "data" / "sample_company_data.csv"
    scoring_config_path: Path = ROOT_DIR / "config" / "scoring_config.json"


settings = Settings()


# ---------------------------------------------------------------------------
# Blind-spot scoring configuration (weights are user-configurable)
# ---------------------------------------------------------------------------
@dataclass
class ScoringConfig:
    """All tunable parameters of the Blind Spot Scoring Engine.

    Blind Spot Score = Customer Importance x Expectation Gap x Issue Trend / 100^2
    Each component is normalised to 0-100 first (see ml/scoring/engine.py)."""

    # Customer Importance sub-weights (re-normalised to sum to 1)
    w_frequency: float = 0.30
    w_unique_customers: float = 0.25
    w_sentiment: float = 0.30
    w_explicit_requests: float = 0.15
    # Expectation Gap sub-weights
    w_coverage: float = 0.60  # 1 - normalised company coverage
    w_similarity: float = 0.40  # 1 - normalised semantic similarity to company messaging
    # Issue Trend sub-weights
    w_volume_trend: float = 0.60
    w_negative_trend: float = 0.40
    # Behaviour
    neutral_trend: float = 50.0  # used when history is insufficient (clearly flagged in results)
    trend_floor: float = 10.0  # lower clip for trend so a falling trend dampens but never zeroes a score
    min_records_for_trend: int = 20
    # Blind-spot qualification thresholds (0-100 scale)
    min_importance: float = 35.0
    min_gap: float = 40.0
    min_score: float = 5.0
    low_coverage: float = 15.0  # coverage index below this = 'company barely mentions it'
    min_emphasis_gap: float = 35.0  # coverage_norm - importance above this (and coverage >= 50) = misplaced emphasis

    def normalised(self, *names: str) -> dict[str, float]:
        vals = {n: max(float(getattr(self, n)), 0.0) for n in names}
        total = sum(vals.values()) or 1.0
        return {n: v / total for n, v in vals.items()}

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict | None) -> "ScoringConfig":
        data = data or {}
        valid = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**valid)


def load_scoring_config(path: Path | None = None) -> ScoringConfig:
    path = path or settings.scoring_config_path
    if path.exists():
        try:
            return ScoringConfig.from_dict(json.loads(path.read_text()))
        except (json.JSONDecodeError, TypeError, OSError):
            pass
    return ScoringConfig()


def save_scoring_config(cfg: ScoringConfig, path: Path | None = None) -> None:
    path = path or settings.scoring_config_path
    path.write_text(json.dumps(cfg.to_dict(), indent=2))
