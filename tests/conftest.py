"""Test configuration: fully offline (TF-IDF embeddings, no BERTopic download), temporary SQLite database."""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
_TMP = tempfile.mkdtemp(prefix="bbsd_test_")
os.environ["EMBEDDING_BACKEND"] = "tfidf"
os.environ["USE_BERTOPIC"] = "false"
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP}/test.db"
os.environ["LOG_DIR"] = _TMP
os.environ["LLM_PROVIDER"] = "none"

import pandas as pd  # noqa: E402
import pytest  # noqa: E402

from config.settings import ScoringConfig  # noqa: E402


@pytest.fixture(scope="session")
def cfg() -> ScoringConfig:
    return ScoringConfig()


@pytest.fixture(scope="session")
def sample_frames():
    from ml.ingestion import standardize

    cust, _ = standardize(pd.read_csv(ROOT / "data" / "sample_customer_data.csv"), "customer")
    comp, _ = standardize(pd.read_csv(ROOT / "data" / "sample_company_data.csv"), "company")
    return cust, comp


@pytest.fixture(scope="session")
def pipeline_result(sample_frames, cfg):
    from backend.services.pipeline import run_pipeline

    return run_pipeline(sample_frames[0], sample_frames[1], cfg, use_llm=False)
