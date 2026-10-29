"""Point-in-time PL tests — no network."""
from datetime import timedelta

import pandas as pd
import pytest

from preco_teto.backtest.pit import (
    income_asof,
    previous_adj_close_asof,
    teto_pl_asof,
    year_prices_asof,
)
from preco_teto.formulas import teto_por_lucro


def _income_years():
    idx = pd.to_datetime(["2020-12-31", "2021-12-31", "2022-12-31", "2023-12-31"])
    return pd.Series([100.0, 120.0, 140.0, 160.0], index=idx)


def test_income_year_blocked_until_fye_plus_90d():
    income = _income_years()
    # 2023-12-31 + 90d = 2024-03-30; day before must exclude 2023
    as_of = pd.Timestamp("2023-12-31") + timedelta(days=89)
    filtered = income_asof(income, as_of, lag_days=90)
    years = set(pd.to_datetime(filtered.index).year)
    assert 2023 not in years
    assert 2022 in years


def test_income_year_released_on_or_after_fye_plus_90d():
    income = _income_years()
    as_of = pd.Timestamp("2023-12-31") + timedelta(days=90)
    filtered = income_asof(income, as_of, lag_days=90)
    years = set(pd.to_datetime(filtered.index).year)
    assert 2023 in years


def test_income_excludes_future_fiscal_years_at_as_of():
    income = _income_years()
    as_of = pd.Timestamp("2022-06-15")
    filtered = income_asof(income, as_of, lag_days=90)
    years = set(pd.to_datetime(filtered.index).year)
    assert 2022 not in years
    assert 2023 not in years
    assert 2021 in years


def test_year_prices_uses_only_sessions_on_or_before_as_of():
    # Build Jan–Mar 2023 closes; as_of mid-Feb must not see March
    days = pd.bdate_range("2023-01-02", "2023-03-31")
    closes = [10.0] * len(days)
    # Mark March days at 999 so look-ahead would dominate trim_mean
    for i, d in enumerate(days):
        if d.month == 3:
            closes[i] = 999.0
        elif d.month == 2:
            closes[i] = 20.0
        else:
            closes[i] = 10.0
    hist = pd.DataFrame({"Close": closes, "Adj Close": closes}, index=days)
    as_of = pd.Timestamp("2023-02-15")
    yp = year_prices_asof(hist, as_of)
    assert 2023 in yp
    assert yp[2023] < 100  # must not include March 999s


def test_previous_close_is_adj_close_on_as_of():
    days = pd.bdate_range("2023-01-02", "2023-01-10")
    hist = pd.DataFrame(
        {
            "Close": [10.0] * len(days),
            "Adj Close": [5.0 + i for i in range(len(days))],
            "Open": [10.0] * len(days),
        },
        index=days,
    )
    as_of = days[3]
    assert previous_adj_close_asof(hist, as_of) == pytest.approx(5.0 + 3)


def test_teto_pl_asof_delegates_to_teto_por_lucro_unchanged():
    income = _income_years()
    # Enough daily bars per year for year_prices
    frames = []
    for year, px in [(2020, 10.0), (2021, 12.0), (2022, 14.0), (2023, 16.0)]:
        days = pd.bdate_range(f"{year}-11-01", f"{year}-12-31")
        frames.append(
            pd.DataFrame(
                {"Close": [px] * len(days), "Adj Close": [px] * len(days), "Open": [px] * len(days)},
                index=days,
            )
        )
    hist = pd.concat(frames)
    as_of = pd.Timestamp("2023-12-31") + timedelta(days=90)
    via_pit = teto_pl_asof(hist, income, as_of, lag_days=90)
    inc = income_asof(income, as_of, lag_days=90)
    yp = year_prices_asof(hist, as_of)
    prev = previous_adj_close_asof(hist, as_of)
    direct = teto_por_lucro(inc, yp, prev)
    assert via_pit == direct
    assert via_pit is not None


def test_teto_pl_asof_none_when_pl_inputs_incomplete():
    income = pd.Series([100.0], index=pd.to_datetime(["2023-12-31"]))
    days = pd.bdate_range("2023-01-02", "2023-12-29")
    hist = pd.DataFrame(
        {"Close": [10.0] * len(days), "Adj Close": [10.0] * len(days), "Open": [10.0] * len(days)},
        index=days,
    )
    as_of = pd.Timestamp("2024-06-01")
    assert teto_pl_asof(hist, income, as_of) is None


def test_income_asof_last_ni_never_expires_through_last_price():
    """Último NI liberado permanece no conjunto até o fim dos preços."""
    income = _income_years()
    last = pd.Timestamp("2026-09-29")
    # YE 2023 available 2024-03-30; long after that all 4 still present
    filtered = income_asof(income, last, lag_days=90)
    years = set(pd.to_datetime(filtered.index).year)
    assert years == {2020, 2021, 2022, 2023}


def test_ni_sticky_records_intervals_last_until_end():
    from preco_teto.backtest.pit import ni_sticky_records

    income = _income_years()
    last = pd.Timestamp("2026-09-29")
    recs = ni_sticky_records(income, last_price_date=last, lag_days=90)
    assert len(recs) == 4
    assert recs[0]["year_end"] == "2020-12-31"
    assert recs[0]["available_date"] == "2021-03-31"
    assert recs[0]["used_from"] == "2021-03-31"
    # until day before next available (2021-12-31+90=2022-03-31 → until 2022-03-30)
    assert recs[0]["used_until"] == "2022-03-30"
    assert recs[-1]["year_end"] == "2023-12-31"
    assert recs[-1]["available_date"] == "2024-03-30"
    assert recs[-1]["used_until"] == "2026-09-29"
    # mid records don't expire from the set — income_asof still has them after next release
    mid = income_asof(income, pd.Timestamp("2025-01-01"), lag_days=90)
    assert 2020 in set(pd.to_datetime(mid.index).year)
    assert 2023 in set(pd.to_datetime(mid.index).year)


def test_resolve_default_pl_only_no_cascade_fallback():
    from preco_teto.backtest.pit import resolve_teto_asof

    # Only 1 NI year → PL None; without cascade must stay None even with dividends
    income = pd.Series([100.0], index=pd.to_datetime(["2023-12-31"]))
    days = pd.bdate_range("2021-01-02", "2024-06-28")
    hist = pd.DataFrame(
        {"Close": [10.0] * len(days), "Adj Close": [10.0] * len(days), "Open": [10.0] * len(days)},
        index=days,
    )
    dividends = pd.Series(
        [1.0] * 6,
        index=pd.to_datetime(
            ["2021-06-01", "2021-12-01", "2022-06-01", "2022-12-01", "2023-06-01", "2023-12-01"]
        ),
    )
    as_of = pd.Timestamp("2024-06-01")
    teto, method, avisos = resolve_teto_asof(
        history=hist,
        income=income,
        as_of=as_of,
        cascade=False,
        dividends=dividends,
        is_br=False,
    )
    assert teto is None
    assert method is None
    assert avisos == []


def test_resolve_cascade_falls_to_dy_with_aviso():
    from preco_teto.backtest.pit import resolve_teto_asof
    from preco_teto.services.referencia import FED_FUNDS_US

    income = pd.Series([100.0], index=pd.to_datetime(["2023-12-31"]))  # PL incomplete
    days = pd.bdate_range("2021-01-02", "2024-06-28")
    hist = pd.DataFrame(
        {"Close": [10.0] * len(days), "Adj Close": [10.0] * len(days), "Open": [10.0] * len(days)},
        index=days,
    )
    # ~2.0/year average over 3 complete years → teto = 2 / (5.25/100)
    dividends = pd.Series(
        [2.0, 2.0, 2.0],
        index=pd.to_datetime(["2021-12-15", "2022-12-15", "2023-12-15"]),
    )
    as_of = pd.Timestamp("2024-06-01")
    teto, method, avisos = resolve_teto_asof(
        history=hist,
        income=income,
        as_of=as_of,
        cascade=True,
        dividends=dividends,
        is_br=False,
    )
    assert method == "dy"
    assert teto == pytest.approx(2.0 / (FED_FUNDS_US / 100), rel=1e-3)
    assert any("PL ruim" in a for a in avisos)
    assert any("DY" in a for a in avisos)


def test_resolve_cascade_falls_to_vpa_roe_when_dy_also_bad():
    from preco_teto.backtest.pit import resolve_teto_asof
    from preco_teto.formulas import teto_vpa_roe
    from preco_teto.services.referencia import FED_FUNDS_US

    income = pd.Series([100.0], index=pd.to_datetime(["2023-12-31"]))
    days = pd.bdate_range("2020-01-02", "2024-06-28")
    hist = pd.DataFrame(
        {"Close": [10.0] * len(days), "Adj Close": [10.0] * len(days), "Open": [10.0] * len(days)},
        index=days,
    )
    # Build stmt so VPA/ROE works: 2+ years equity + NI
    cols = pd.to_datetime(["2021-12-31", "2022-12-31", "2023-12-31"])
    income_stmt = pd.DataFrame(
        [[80.0, 100.0, 120.0]],
        index=["Net Income"],
        columns=cols,
    )
    balance_sheet = pd.DataFrame(
        [[800.0, 900.0, 1000.0]],
        index=["Stockholders Equity"],
        columns=cols,
    )
    shares = 100.0
    as_of = pd.Timestamp("2024-06-01")  # after YE2023+90d
    teto, method, avisos = resolve_teto_asof(
        history=hist,
        income=income,
        as_of=as_of,
        cascade=True,
        dividends=None,
        income_stmt=income_stmt,
        balance_sheet=balance_sheet,
        shares_outstanding=shares,
        is_br=False,
    )
    assert method == "vpa_roe"
    assert teto is not None
    assert any("PL ruim" in a for a in avisos)
    assert any("DY" in a for a in avisos)
    # Sanity vs live formula with same VPA path
    from preco_teto.backtest.pit import vpa_roe_asof

    vpa, roe = vpa_roe_asof(income_stmt, balance_sheet, shares, as_of)
    assert teto == teto_vpa_roe(vpa, roe, FED_FUNDS_US)