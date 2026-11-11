"""Normalised schema. Every analysis artefact hangs off ``analysis_sessions`` which belongs to ONE company, so
results from different companies can never mix. Evidence (quotes, closest company messages, scoring components) is
stored with each result so any number on the dashboard can be explained and reproduced.

Entity map (spec section 5):
 1 companies               7 sentiment_results (+ aspect_sentiments)
 2 customer_conversations  8 customer_expectations
 3 company_communications  9 company_messaging_themes
 4 data_sources           10 blind_spot_results
 5 analysis_sessions      11 trend_metrics
 6 detected_topics        12 business_recommendations"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def _now() -> datetime:
    return datetime.utcnow()


class Company(Base):
    __tablename__ = "companies"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    industry: Mapped[str | None] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    data_sources: Mapped[list["DataSource"]] = relationship(back_populates="company", cascade="all, delete-orphan")
    sessions: Mapped[list["AnalysisSession"]] = relationship(back_populates="company", cascade="all, delete-orphan")


class DataSource(Base):
    """One uploaded / entered / extracted dataset (a batch of records)."""
    __tablename__ = "data_sources"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(20))  # customer | company
    source_type: Mapped[str] = mapped_column(String(20))  # csv | excel | txt | manual | url | sample
    name: Mapped[str] = mapped_column(String(300))
    filename: Mapped[str | None] = mapped_column(String(300))
    origin_url: Mapped[str | None] = mapped_column(String(1000))
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False)
    n_records: Mapped[int] = mapped_column(Integer, default=0)
    validation: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    company: Mapped[Company] = relationship(back_populates="data_sources")


class CustomerConversation(Base):
    __tablename__ = "customer_conversations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    data_source_id: Mapped[int] = mapped_column(ForeignKey("data_sources.id", ondelete="CASCADE"), index=True)
    text: Mapped[str] = mapped_column(Text)
    source: Mapped[str | None] = mapped_column(String(200))
    date: Mapped[datetime | None] = mapped_column(DateTime)
    category: Mapped[str | None] = mapped_column(String(120))
    customer_id: Mapped[str | None] = mapped_column(String(120))
    rating: Mapped[float | None] = mapped_column(Float)
    extra: Mapped[dict | None] = mapped_column(JSON)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False)


class CompanyCommunication(Base):
    __tablename__ = "company_communications"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    data_source_id: Mapped[int] = mapped_column(ForeignKey("data_sources.id", ondelete="CASCADE"), index=True)
    text: Mapped[str] = mapped_column(Text)
    source: Mapped[str | None] = mapped_column(String(200))
    date: Mapped[datetime | None] = mapped_column(DateTime)
    category: Mapped[str | None] = mapped_column(String(120))
    extra: Mapped[dict | None] = mapped_column(JSON)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False)


class AnalysisSession(Base):
    __tablename__ = "analysis_sessions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="running")  # running | completed | failed
    progress: Mapped[int] = mapped_column(Integer, default=0)
    message: Mapped[str | None] = mapped_column(String(300))
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    customer_source_ids: Mapped[list | None] = mapped_column(JSON)
    company_source_ids: Mapped[list | None] = mapped_column(JSON)
    n_customer: Mapped[int] = mapped_column(Integer, default=0)
    n_company: Mapped[int] = mapped_column(Integer, default=0)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False)
    overview: Mapped[dict | None] = mapped_column(JSON)
    meta: Mapped[dict | None] = mapped_column(JSON)  # backends, models, notes, scoring config, preprocessing reports
    company: Mapped[Company] = relationship(back_populates="sessions")




class DetectedTopic(Base):
    __tablename__ = "detected_topics"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("analysis_sessions.id", ondelete="CASCADE"), index=True)
    topic_id: Mapped[int] = mapped_column(Integer)
    label: Mapped[str] = mapped_column(String(300))
    category: Mapped[str | None] = mapped_column(String(60))
    keywords: Mapped[list | None] = mapped_column(JSON)
    representative_docs: Mapped[list | None] = mapped_column(JSON)
    mentions: Mapped[int] = mapped_column(Integer, default=0)
    conversations: Mapped[int] = mapped_column(Integer, default=0)
    unique_customers: Mapped[int] = mapped_column(Integer, default=0)
    share_pct: Mapped[float] = mapped_column(Float, default=0)
    avg_sentiment: Mapped[float] = mapped_column(Float, default=0)
    positive_pct: Mapped[float] = mapped_column(Float, default=0)
    negative_pct: Mapped[float] = mapped_column(Float, default=0)
    neutral_pct: Mapped[float] = mapped_column(Float, default=0)
    neg_intensity: Mapped[float] = mapped_column(Float, default=0)
    explicit_share_pct: Mapped[float] = mapped_column(Float, default=0)
    frequency_score: Mapped[float] = mapped_column(Float, default=0)
    customers_score: Mapped[float] = mapped_column(Float, default=0)
    sentiment_score: Mapped[float] = mapped_column(Float, default=0)
    explicit_score: Mapped[float] = mapped_column(Float, default=0)
    importance: Mapped[float] = mapped_column(Float, default=0)
    volume_change_pct: Mapped[float | None] = mapped_column(Float)
    trend_status: Mapped[str | None] = mapped_column(String(40))
    score: Mapped[float | None] = mapped_column(Float)
    severity: Mapped[str | None] = mapped_column(String(20))
    classification: Mapped[str | None] = mapped_column(String(40))
    __table_args__ = (UniqueConstraint("session_id", "topic_id"),)


class SentimentResult(Base):
    """Document-level sentiment for each analysed customer conversation."""
    __tablename__ = "sentiment_results"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("analysis_sessions.id", ondelete="CASCADE"), index=True)
    conversation_id: Mapped[int | None] = mapped_column(ForeignKey("customer_conversations.id", ondelete="SET NULL"))
    record_id: Mapped[int] = mapped_column(Integer)
    text_original: Mapped[str] = mapped_column(Text)
    text_clean: Mapped[str] = mapped_column(Text)
    language: Mapped[str | None] = mapped_column(String(10))
    source: Mapped[str | None] = mapped_column(String(200))
    date: Mapped[datetime | None] = mapped_column(DateTime)
    customer_id: Mapped[str | None] = mapped_column(String(120))
    vader_compound: Mapped[float] = mapped_column(Float)
    transformer_score: Mapped[float | None] = mapped_column(Float)
    compound: Mapped[float] = mapped_column(Float)
    label: Mapped[str] = mapped_column(String(12))
    model: Mapped[str] = mapped_column(String(200))
    topic_id: Mapped[int | None] = mapped_column(Integer)
    __table_args__ = (Index("ix_sentiment_session_topic", "session_id", "topic_id"),)


class AspectSentiment(Base):
    """Aspect-level (clause x topic) sentiment mentions."""
    __tablename__ = "aspect_sentiments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("analysis_sessions.id", ondelete="CASCADE"), index=True)
    record_id: Mapped[int] = mapped_column(Integer)
    topic_id: Mapped[int] = mapped_column(Integer)
    clause: Mapped[str] = mapped_column(Text)
    aspect: Mapped[str | None] = mapped_column(String(120))
    compound: Mapped[float] = mapped_column(Float)
    label: Mapped[str] = mapped_column(String(12))
    similarity: Mapped[float | None] = mapped_column(Float)
    explicit: Mapped[bool] = mapped_column(Boolean, default=False)
    signals: Mapped[list | None] = mapped_column(JSON)
    __table_args__ = (Index("ix_aspect_session_topic", "session_id", "topic_id"),)


class CustomerExpectation(Base):
    __tablename__ = "customer_expectations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("analysis_sessions.id", ondelete="CASCADE"), index=True)
    topic_id: Mapped[int] = mapped_column(Integer)
    topic_label: Mapped[str | None] = mapped_column(String(300))
    kind: Mapped[str] = mapped_column(String(40))
    summary: Mapped[str] = mapped_column(Text)
    is_inferred: Mapped[bool] = mapped_column(Boolean, default=False)
    support_count: Mapped[int] = mapped_column(Integer, default=0)
    share_pct: Mapped[float] = mapped_column(Float, default=0)
    keywords: Mapped[list | None] = mapped_column(JSON)
    evidence: Mapped[list | None] = mapped_column(JSON)


class CompanyMessagingTheme(Base):
    __tablename__ = "company_messaging_themes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("analysis_sessions.id", ondelete="CASCADE"), index=True)
    theme_id: Mapped[int] = mapped_column(Integer)
    label: Mapped[str] = mapped_column(String(300))
    keywords: Mapped[list | None] = mapped_column(JSON)
    n_messages: Mapped[int] = mapped_column(Integer, default=0)
    share_pct: Mapped[float] = mapped_column(Float, default=0)
    examples: Mapped[list | None] = mapped_column(JSON)
    sources: Mapped[dict | None] = mapped_column(JSON)


class BlindSpotResult(Base):
    __tablename__ = "blind_spot_results"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("analysis_sessions.id", ondelete="CASCADE"), index=True)
    topic_id: Mapped[int] = mapped_column(Integer)
    topic_label: Mapped[str] = mapped_column(String(300))
    keywords: Mapped[list | None] = mapped_column(JSON)
    rank: Mapped[int] = mapped_column(Integer, default=0)
    classification: Mapped[str] = mapped_column(String(40))
    severity: Mapped[str] = mapped_column(String(20))
    score: Mapped[float] = mapped_column(Float)
    importance: Mapped[float] = mapped_column(Float)
    gap: Mapped[float] = mapped_column(Float)
    trend: Mapped[float | None] = mapped_column(Float)
    trend_used: Mapped[float] = mapped_column(Float)
    trend_available: Mapped[bool] = mapped_column(Boolean, default=False)
    trend_status: Mapped[str | None] = mapped_column(String(40))
    # stored components -> allows deterministic re-scoring with different weights without re-running NLP
    mentions: Mapped[int] = mapped_column(Integer, default=0)
    unique_customers: Mapped[int] = mapped_column(Integer, default=0)
    share_pct: Mapped[float] = mapped_column(Float, default=0)
    negative_pct: Mapped[float] = mapped_column(Float, default=0)
    neg_pct: Mapped[float] = mapped_column(Float, default=0)
    explicit_share_pct: Mapped[float] = mapped_column(Float, default=0)
    frequency_score: Mapped[float] = mapped_column(Float, default=0)
    customers_score: Mapped[float] = mapped_column(Float, default=0)
    sentiment_score: Mapped[float] = mapped_column(Float, default=0)
    explicit_score: Mapped[float] = mapped_column(Float, default=0)
    coverage_share: Mapped[float] = mapped_column(Float, default=0)
    coverage_norm: Mapped[float] = mapped_column(Float, default=0)
    similarity: Mapped[float] = mapped_column(Float, default=0)
    similarity_norm: Mapped[float] = mapped_column(Float, default=0)
    growth_score: Mapped[float | None] = mapped_column(Float)
    negative_trend_score: Mapped[float | None] = mapped_column(Float)
    trend_enough: Mapped[bool] = mapped_column(Boolean, default=False)
    recurring: Mapped[bool] = mapped_column(Boolean, default=False)
    evidence_quotes: Mapped[list | None] = mapped_column(JSON)
    closest_company_messages: Mapped[list | None] = mapped_column(JSON)


class TrendMetric(Base):
    """Time-series rows and per-topic trend summaries. kind: series | overall | summary | spike | emerging."""
    __tablename__ = "trend_metrics"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("analysis_sessions.id", ondelete="CASCADE"), index=True)
    topic_id: Mapped[int | None] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(20))
    period: Mapped[datetime | None] = mapped_column(DateTime)
    payload: Mapped[dict | None] = mapped_column(JSON)
    __table_args__ = (Index("ix_trend_session_kind", "session_id", "kind"),)


class BusinessRecommendation(Base):
    __tablename__ = "business_recommendations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("analysis_sessions.id", ondelete="CASCADE"), index=True)
    topic_id: Mapped[int] = mapped_column(Integer)
    topic_label: Mapped[str] = mapped_column(String(300))
    category: Mapped[str] = mapped_column(String(40))
    problem: Mapped[str] = mapped_column(Text)
    evidence: Mapped[list | None] = mapped_column(JSON)
    blind_spot_score: Mapped[float] = mapped_column(Float)
    severity: Mapped[str] = mapped_column(String(20))
    suggested_action: Mapped[str] = mapped_column(Text)
    expected_impact: Mapped[str] = mapped_column(Text)
    priority: Mapped[str] = mapped_column(String(20))
    classification: Mapped[str | None] = mapped_column(String(40))
    llm_enhanced: Mapped[bool] = mapped_column(Boolean, default=False)
