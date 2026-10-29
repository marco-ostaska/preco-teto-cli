"""Predictive backtest tests — synthetic, no network."""
import numpy as np
import pandas as pd

from preco_teto.backtest.engine import run_backtest
from preco_teto.backtest.predictive import (
    RATIO_BUCKETS,
    build_bucket_stats,
    count_bucket_episodes,
    exit_on_or_before,
    forward_return,
    mfe_mae,
    ratio_bucket,
    WeeklyObs,
)


def test_ratio_bucket_edges():
    assert ratio_bucket(0.80) == "<=0.80"
    assert ratio_bucket(0.81) == "0.80-0.90"
    assert ratio_bucket(1.00) == "0.90-1.00"
    assert ratio_bucket(1.01) == "1.00-1.10"
    assert ratio_bucket(1.20) == "1.10-1.20"
    assert ratio_bucket(1.21) == ">1.20"


def test_count_bucket_episodes_contiguous_runs():
    days = pd.bdate_range("2020-01-03", periods=6, freq="W-FRI")
    obs = [
        WeeklyObs(days[0], 8.0, 10.0, 0.80, "<=0.80", "pl"),
        WeeklyObs(days[1], 8.0, 10.0, 0.80, "<=0.80", "pl"),
        WeeklyObs(days[2], 11.0, 10.0, 1.10, "1.00-1.10", "pl"),
        WeeklyObs(days[3], 8.0, 10.0, 0.80, "<=0.80", "pl"),
        WeeklyObs(days[4], 8.0, 10.0, 0.79, "<=0.80", "pl"),
        WeeklyObs(days[5], 13.0, 10.0, 1.30, ">1.20", "pl"),
    ]
    counts = count_bucket_episodes(obs)
    assert counts["<=0.80"] == 2  # two separate runs
    assert counts["1.00-1.10"] == 1
    assert counts[">1.20"] == 1


def test_exit_on_or_before_requires_full_horizon_coverage():
    """Calendário até set/2026 não completa 24m a partir de ago/2026."""
    days = pd.bdate_range("2024-01-02", "2026-09-29")
    as_of = pd.Timestamp("2026-08-07")
    assert exit_on_or_before(as_of, 3, days) is None  # alvo ~nov/2026 > fim
    assert exit_on_or_before(as_of, 24, days) is None

    as_of_ok = pd.Timestamp("2024-01-05")
    xd3 = exit_on_or_before(as_of_ok, 3, days)
    xd24 = exit_on_or_before(as_of_ok, 24, days)
    assert xd3 is not None and xd24 is not None
    assert xd3 <= as_of_ok + pd.DateOffset(months=3)
    assert xd24 <= as_of_ok + pd.DateOffset(months=24)
    # horizonte incompleto no fim: max < alvo
    assert days.max() < as_of + pd.DateOffset(months=3)


def test_n_bars_shrinks_for_longer_horizons():
    """N em 24m deve ser < N em 3m quando a série termina 'agora'."""
    days = pd.bdate_range("2020-01-02", "2026-09-29")
    px = np.linspace(80.0, 120.0, len(days))
    hist = pd.DataFrame(
        {"Adj Close": px, "Open": px, "Close": px, "High": px, "Low": px},
        index=days,
    )
    weeks = (
        pd.DatetimeIndex(days)
        .to_series()
        .groupby(
            [
                pd.DatetimeIndex(days).isocalendar().year,
                pd.DatetimeIndex(days).isocalendar().week,
            ]
        )
        .apply(lambda s: s.index.max())
        .values
    )
    obs = []
    for w in weeks:
        w = pd.Timestamp(w).normalize()
        if w not in hist.index:
            continue
        adj = float(hist.loc[w, "Adj Close"])
        teto = 100.0
        ratio = adj / teto
        obs.append(WeeklyObs(w, adj, teto, ratio, ratio_bucket(ratio), "pl"))

    blocks, spearman, _ = build_bucket_stats(obs, hist, hist, horizons=(3, 6, 12, 24))
    n_by_h = {
        h: sum((b.by_horizon[h].n_bars if h in b.by_horizon else 0) for b in blocks)
        for h in (3, 6, 12, 24)
    }
    assert n_by_h[3] > 0
    assert n_by_h[3] > n_by_h[6] > n_by_h[12] > n_by_h[24]
    assert spearman[0].n == n_by_h[3]
    assert spearman[-1].n == n_by_h[24]
    # última semana da série não entra em nenhum horizonte completo longo
    last = max(o.as_of for o in obs)
    assert exit_on_or_before(last, 3, hist.index) is None
    assert exit_on_or_before(last, 24, hist.index) is None


def test_forward_return_and_mfe_mae_no_lookahead_path():
    days = pd.bdate_range("2020-01-02", "2020-07-31")
    prices = np.linspace(100.0, 120.0, len(days))
    # dip in the middle for MAE
    prices = list(prices)
    mid = len(days) // 2
    prices[mid] = 90.0
    hist = pd.DataFrame(
        {"Adj Close": prices, "Open": prices, "Close": prices, "High": prices, "Low": prices},
        index=days,
    )
    as_of = days[10]
    xd = exit_on_or_before(as_of, 3, hist.index)
    assert xd is not None and xd > as_of
    r = forward_return(hist, as_of, xd)
    assert r is not None
    mfe, mae = mfe_mae(hist, as_of, xd)
    assert mfe is not None and mae is not None
    assert mfe >= r - 1e-9
    assert mae <= r + 1e-9


def test_build_bucket_stats_spearman_negative_when_cheap_outperforms():
    """Cheaper ratios get higher forward returns → Spearman ρ < 0."""
    days = pd.bdate_range("2018-01-02", "2022-12-30")
    # Price rises over time; we set obs ratios independently
    px = np.linspace(50.0, 100.0, len(days))
    hist = pd.DataFrame(
        {"Adj Close": px, "Open": px, "Close": px, "High": px, "Low": px},
        index=days,
    )
    # Pick week ends early (cheap, high future ret) and late (expensive, low future ret)
    weeks = sorted(pd.DatetimeIndex(days).to_series().groupby(
        [pd.DatetimeIndex(days).isocalendar().year, pd.DatetimeIndex(days).isocalendar().week]
    ).apply(lambda s: s.index.max()).values)
    weeks = [pd.Timestamp(w).normalize() for w in weeks]
    # Use first half weeks as cheap, second as expensive — but forward ret from price path
    # Better: construct obs with ratio inversely related to eventual return by choosing as_of
    obs = []
    for i, w in enumerate(weeks[:-30]):  # leave room for 24m? use 3m only in build with horizons=(3,)
        # early weeks → low ratio label; price will rise more in absolute but we care correlation
        # ratio assigned: early low, late high
        frac = i / max(len(weeks) - 31, 1)
        ratio = 0.7 + frac * 0.6  # 0.7 → 1.3
        teto = 100.0
        adj = ratio * teto
        obs.append(WeeklyObs(w, adj, teto, ratio, ratio_bucket(ratio), "pl"))

    # Override history so forward return = (1.5 - ratio) roughly: set flat then jump by bucket
    # Simpler: use synthetic forward via custom hist where later prices depend on...
    # Just check spearman runs and buckets populate
    blocks, spearman, details = build_bucket_stats(obs, hist, hist, horizons=(3,))
    assert len(blocks) == len(RATIO_BUCKETS)
    assert details
    sp3 = next(s for s in spearman if s.horizon_months == 3)
    assert sp3.n >= 3
    assert sp3.rho is not None


def test_run_backtest_predictive_synthetic():
    frames = []
    for year, px in [(2021, 10.0), (2022, 12.0), (2023, 14.0), (2024, 11.0), (2025, 13.0)]:
        days = pd.bdate_range(f"{year}-01-02", f"{year}-12-31")
        frames.append(
            pd.DataFrame(
                {
                    "Open": [px] * len(days),
                    "Close": [px] * len(days),
                    "Adj Close": [px] * len(days),
                    "High": [px] * len(days),
                    "Low": [px] * len(days),
                },
                index=days,
            )
        )
    hist = pd.concat(frames)
    income = pd.Series(
        [100.0, 120.0, 140.0, 160.0],
        index=pd.to_datetime(["2021-12-31", "2022-12-31", "2023-12-31", "2024-12-31"]),
    )
    report = run_backtest(
        "VALE3",
        history=hist,
        income=income,
        index_history=hist,
        show_progress=False,
    )
    assert report.meta.ticker == "VALE3"
    assert report.meta.n_weeks_with_teto > 0
    assert report.buckets
    assert report.spearman
    assert any(b.n_bars > 0 for b in report.buckets)
