"""Report types for predictive preço-teto backtest."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PredictiveMeta:
    ticker: str
    is_br: bool
    lag_days: int
    cascade: bool
    benchmark: str | None
    date_start: str | None
    date_end: str | None
    n_weeks_with_teto: int
    income_years: int
    ratio_min: float | None = None
    ratio_median: float | None = None
    notes: list[str] = field(default_factory=list)


@dataclass
class PredictiveReport:
    meta: PredictiveMeta
    buckets: list = field(default_factory=list)  # list[BucketBlock]
    spearman: list = field(default_factory=list)  # list[SpearmanRow]
    ni_sticky: list[dict] = field(default_factory=list)
    observations: list[dict] = field(default_factory=list)
