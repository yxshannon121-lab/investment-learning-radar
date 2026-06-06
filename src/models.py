from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl


ImpactDirection = Literal["利好", "利空", "不确定"]


class NewsItem(BaseModel):
    title: str
    source: str
    url: HttpUrl
    published_at: datetime
    raw_summary: str = ""
    raw_content: str = ""


class ScoredNews(BaseModel):
    item: NewsItem
    score: float
    reasons: list[str] = Field(default_factory=list)


class AIAnalysis(BaseModel):
    confirmed_facts_zh: list[str] = Field(default_factory=list)
    ai_analysis_zh: str = ""
    affected_sectors: list[str] = Field(default_factory=list)
    impact_direction: ImpactDirection = "不确定"
    observed_etfs: list[str] = Field(default_factory=list)
    observed_stocks: list[str] = Field(default_factory=list)
    observation_reason_zh: str = ""
    uncertainties_zh: list[str] = Field(default_factory=list)
    risk_note_zh: str = "这不是投资建议，只是学习和观察。"

