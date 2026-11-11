"""Pydantic request/response models for the REST API."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class CompanyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200, examples=["NovaCart"])
    industry: str | None = Field(None, max_length=120)
    description: str | None = None


class CompanyOut(BaseModel):
    id: int
    name: str
    industry: str | None = None
    description: str | None = None
    created_at: str
    n_analyses: int = 0
    n_datasets: int = 0


class TextIngest(BaseModel):
    kind: str = Field(..., pattern="^(customer|company)$")
    text: str = Field(..., min_length=1, description="One record per line (or blank-line separated blocks)")
    source: str = "manual_entry"
    name: str | None = None


class UrlIngest(BaseModel):
    kind: str = Field("company", pattern="^(customer|company)$")
    url: str = Field(..., min_length=4)


class AnalysisRequest(BaseModel):
    customer_source_ids: list[int] | None = Field(None, description="Datasets to use (default: all customer datasets)")
    company_source_ids: list[int] | None = Field(None, description="Datasets to use (default: all company datasets)")
    scoring: dict[str, float] | None = Field(None, description="Overrides for ScoringConfig fields")


class AnalysisStarted(BaseModel):
    session_id: int
    status: str = "running"


class AnalysisStatus(BaseModel):
    id: int
    company_id: int
    status: str
    progress: int
    message: str | None = None
    error: str | None = None
    steps: int = 12


class RescoreRequest(BaseModel):
    config: dict[str, float] = Field(default_factory=dict)
    persist: bool = False


class ScoringConfigModel(BaseModel):
    w_frequency: float = Field(0.30, ge=0)
    w_unique_customers: float = Field(0.25, ge=0)
    w_sentiment: float = Field(0.30, ge=0)
    w_explicit_requests: float = Field(0.15, ge=0)
    w_coverage: float = Field(0.60, ge=0)
    w_similarity: float = Field(0.40, ge=0)
    w_volume_trend: float = Field(0.60, ge=0)
    w_negative_trend: float = Field(0.40, ge=0)
    neutral_trend: float = Field(50.0, ge=0, le=100)
    trend_floor: float = Field(10.0, ge=0, le=100)
    min_records_for_trend: int = Field(20, ge=5)
    min_importance: float = Field(35.0, ge=0, le=100)
    min_gap: float = Field(40.0, ge=0, le=100)
    min_score: float = Field(5.0, ge=0, le=100)
    low_coverage: float = Field(15.0, ge=0, le=100)
    min_emphasis_gap: float = Field(35.0, ge=0, le=100)


class Message(BaseModel):
    detail: str
    data: Any | None = None
