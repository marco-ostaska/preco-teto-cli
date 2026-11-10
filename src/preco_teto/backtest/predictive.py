"""Predictive power of preço-teto: ratio buckets vs forward returns (no trading)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

import numpy as np
import pandas as pd
from dateutil.relativedelta import relativedelta
from scipy.stats import spearmanr

from preco_teto.backtest.pit import (
    HORIZONS,
    LAG_DAYS,
    previous_adj_close_asof,
    resolve_teto_asof,
)
from preco_teto.backtest.signal import week_end_dates

# Faixas de ratio = preço/teto (ordem de exibição)
RATIO_BUCKETS: tuple[str, ...] = (
    "<=0.80",
    "0.80-0.90",
    "0.90-1.00",
    "1.00-1.10",
    "1.10-1.20",
    ">1.20",
)


def ratio_bucket(ratio: float) -> str:
    if ratio <= 0.80:
        return "<=0.80"
    if ratio <= 0.90:
        return "0.80-0.90"
    if ratio <= 1.00:
        return "0.90-1.00"
    if ratio <= 1.10:
        return "1.00-1.10"
    if ratio <= 1.20:
        return "1.10-1.20"
    return ">1.20"


@dataclass(frozen=True)
class WeeklyObs:
    as_of: pd.Timestamp
    adj_close: float
    teto: float
    ratio: float
    bucket: str
    method: str | None


@dataclass
class HorizonBucketStats:
    horizon_months: int
    n_bars: int
    n_episodes: int
    mean: float | None
    median: float | None
    win_rate: float | None
    mfe_mean: float | None
    mae_mean: float | None
    excess_ibov_mean: float | None
    excess_ibov_median: float | None


@dataclass
class BucketBlock:
    bucket: str
    n_bars: int
    n_episodes: int
    by_horizon: dict[int, HorizonBucketStats] = field(default_factory=dict)


@dataclass
class SpearmanRow:
    horizon_months: int
    n: int
    rho: float | None
    pvalue: float | None


def exit_on_or_before(
    as_of: pd.Timestamp,
    horizon_months: int,
    calendar: pd.DatetimeIndex,
) -> pd.Timestamp | None:
    """Último pregão em <= as_of + H meses, estritamente após as_of.

    Retorna None se o calendário não cobre o horizonte completo
    (último pregão < alvo). Sem isso, ago/2026 com dados até set/2026
    entraria em 24m com ~1 mês de retorno.
    """
    as_of = pd.Timestamp(as_of).normalize()
    target = as_of + relativedelta(months=horizon_months)
    idx = pd.DatetimeIndex(calendar).normalize()
    if len(idx) == 0:
        return None
    if idx.max() < target:
        return None
    eligible = idx[(idx > as_of) & (idx <= target)]
    if len(eligible) == 0:
        return None
    return eligible[-1]


def forward_return(
    history: pd.DataFrame,
    as_of: pd.Timestamp,
    exit_day: pd.Timestamp,
) -> float | None:
    as_of = pd.Timestamp(as_of).normalize()
    exit_day = pd.Timestamp(exit_day).normalize()
    if as_of not in history.index or exit_day not in history.index:
        return None
    entry = float(history.loc[as_of, "Adj Close"])
    exit_px = float(history.loc[exit_day, "Adj Close"])
    if entry <= 0 or np.isnan(entry) or np.isnan(exit_px) or exit_px <= 0:
        return None
    return exit_px / entry - 1.0


def mfe_mae(
    history: pd.DataFrame,
    as_of: pd.Timestamp,
    exit_day: pd.Timestamp,
) -> tuple[float | None, float | None]:
    """
    MFE/MAE no caminho Adj Close (as_of, exit] vs preço em as_of.
    MFE = máximo retorno favorável; MAE = mínimo (mais adverso).
    """
    as_of = pd.Timestamp(as_of).normalize()
    exit_day = pd.Timestamp(exit_day).normalize()
    if as_of not in history.index:
        return None, None
    entry = float(history.loc[as_of, "Adj Close"])
    if entry <= 0 or np.isnan(entry):
        return None, None
    path = history.loc[(history.index > as_of) & (history.index <= exit_day), "Adj Close"].dropna()
    if path.empty:
        return None, None
    rets = path.astype(float) / entry - 1.0
    return float(rets.max()), float(rets.min())


def collect_weekly_obs(
    history: pd.DataFrame,
    income: pd.Series,
    *,
    cascade: bool = False,
    lag_days: int = LAG_DAYS,
    dividends=None,
    income_stmt=None,
    balance_sheet=None,
    shares_outstanding: float | None = None,
    is_br: bool = True,
    cdi_daily=None,
    ipca_atual: float | None = None,
) -> list[WeeklyObs]:
    """Uma observação por semana com teto PIT válido (sem look-ahead)."""
    if history is None or history.empty:
        return []
    hist = history.copy()
    hist.index = pd.to_datetime(hist.index).tz_localize(None).normalize()
    out: list[WeeklyObs] = []
    for as_of in week_end_dates(hist.index):
        adj = previous_adj_close_asof(hist, as_of)
        teto, method, _ = resolve_teto_asof(
            history=hist,
            income=income,
            as_of=as_of,
            lag_days=lag_days,
            cascade=cascade,
            dividends=dividends,
            income_stmt=income_stmt,
            balance_sheet=balance_sheet,
            shares_outstanding=shares_outstanding,
            is_br=is_br,
            cdi_daily=cdi_daily,
            ipca_atual=ipca_atual,
        )
        if adj is None or teto is None or teto <= 0:
            continue
        ratio = adj / float(teto)
        out.append(
            WeeklyObs(
                as_of=as_of,
                adj_close=float(adj),
                teto=float(teto),
                ratio=ratio,
                bucket=ratio_bucket(ratio),
                method=method,
            )
        )
    return out


def count_bucket_episodes(obs: Sequence[WeeklyObs]) -> dict[str, int]:
    """Episódios = trechos contíguos (em ordem temporal) na mesma faixa."""
    counts = {b: 0 for b in RATIO_BUCKETS}
    if not obs:
        return counts
    ordered = sorted(obs, key=lambda o: o.as_of)
    prev: str | None = None
    for o in ordered:
        if o.bucket != prev:
            counts[o.bucket] = counts.get(o.bucket, 0) + 1
            prev = o.bucket
    return counts


def _median(vals: list[float]) -> float | None:
    if not vals:
        return None
    s = sorted(vals)
    n = len(s)
    mid = n // 2
    if n % 2:
        return s[mid]
    return (s[mid - 1] + s[mid]) / 2


def build_bucket_stats(
    obs: Sequence[WeeklyObs],
    history: pd.DataFrame,
    index_history: pd.DataFrame | None,
    horizons: tuple[int, ...] = HORIZONS,
) -> tuple[list[BucketBlock], list[SpearmanRow], list[dict]]:
    """
    Para cada faixa e horizonte: stats de retorno futuro, MFE/MAE, excesso vs índice.
    Spearman ratio vs retorno em todas as barras com forward válido.
    """
    hist = history.copy()
    hist.index = pd.to_datetime(hist.index).tz_localize(None).normalize()
    idx_hist = None
    if index_history is not None and not index_history.empty:
        idx_hist = index_history.copy()
        idx_hist.index = pd.to_datetime(idx_hist.index).tz_localize(None).normalize()

    calendar = hist.index
    episode_counts = count_bucket_episodes(obs)

    rets: dict[tuple[str, int], list[float]] = {}
    mfes: dict[tuple[str, int], list[float]] = {}
    maes: dict[tuple[str, int], list[float]] = {}
    excess: dict[tuple[str, int], list[float]] = {}
    valid_obs_h: dict[int, list[WeeklyObs]] = {h: [] for h in horizons}
    spear_ratio: dict[int, list[float]] = {h: [] for h in horizons}
    spear_ret: dict[int, list[float]] = {h: [] for h in horizons}
    detail_rows: list[dict] = []

    for o in obs:
        for h in horizons:
            xd = exit_on_or_before(o.as_of, h, calendar)
            if xd is None:
                continue
            r = forward_return(hist, o.as_of, xd)
            if r is None:
                continue
            mfe, mae = mfe_mae(hist, o.as_of, xd)
            key = (o.bucket, h)
            rets.setdefault(key, []).append(r)
            valid_obs_h[h].append(o)
            if mfe is not None:
                mfes.setdefault(key, []).append(mfe)
            if mae is not None:
                maes.setdefault(key, []).append(mae)

            ex = None
            if idx_hist is not None:
                ri = forward_return(idx_hist, o.as_of, xd)
                if ri is not None:
                    ex = r - ri
                    excess.setdefault(key, []).append(ex)

            spear_ratio[h].append(o.ratio)
            spear_ret[h].append(r)
            detail_rows.append(
                {
                    "as_of": str(o.as_of.date()),
                    "ratio": o.ratio,
                    "bucket": o.bucket,
                    "horizon": h,
                    "ret": r,
                    "mfe": mfe,
                    "mae": mae,
                    "excess_ibov": ex,
                }
            )

    episodes_by_h = {h: count_bucket_episodes(valid_obs_h[h]) for h in horizons}

    blocks: list[BucketBlock] = []
    for bucket in RATIO_BUCKETS:
        n_bars_bucket = sum(1 for o in obs if o.bucket == bucket)
        block = BucketBlock(
            bucket=bucket,
            n_bars=n_bars_bucket,
            n_episodes=episode_counts.get(bucket, 0),
        )
        for h in horizons:
            key = (bucket, h)
            rv = rets.get(key, [])
            fv = mfes.get(key, [])
            av = maes.get(key, [])
            ev = excess.get(key, [])
            wins = sum(1 for x in rv if x > 0)
            block.by_horizon[h] = HorizonBucketStats(
                horizon_months=h,
                n_bars=len(rv),
                n_episodes=episodes_by_h[h].get(bucket, 0),
                mean=(sum(rv) / len(rv)) if rv else None,
                median=_median(rv),
                win_rate=(wins / len(rv)) if rv else None,
                mfe_mean=(sum(fv) / len(fv)) if fv else None,
                mae_mean=(sum(av) / len(av)) if av else None,
                excess_ibov_mean=(sum(ev) / len(ev)) if ev else None,
                excess_ibov_median=_median(ev),
            )
        blocks.append(block)

    spearman_rows: list[SpearmanRow] = []
    for h in horizons:
        xs, ys = spear_ratio[h], spear_ret[h]
        if len(xs) < 3:
            spearman_rows.append(SpearmanRow(horizon_months=h, n=len(xs), rho=None, pvalue=None))
            continue
        rho, p = spearmanr(xs, ys)
        spearman_rows.append(
            SpearmanRow(
                horizon_months=h,
                n=len(xs),
                rho=float(rho) if rho is not None and not np.isnan(rho) else None,
                pvalue=float(p) if p is not None and not np.isnan(p) else None,
            )
        )

    return blocks, spearman_rows, detail_rows
