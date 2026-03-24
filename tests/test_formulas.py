import pytest
import pandas as pd
from preco_teto.formulas import teto_por_lucro


def make_income(values):
    """5 years of net income, indexed by year strings."""
    return pd.Series(values, index=["2019-12-31", "2020-12-31", "2021-12-31", "2022-12-31", "2023-12-31"])


def make_prices(year_price: dict):
    return year_price


def test_teto_por_lucro_growing():
    income = make_income([100, 120, 140, 160, 180])
    prices = {2019: 10.0, 2020: 12.0, 2021: 14.0, 2022: 16.0, 2023: 18.0}
    result = teto_por_lucro(income, prices, previous_close=18.0)
    assert result is not None
    assert result > 0


def test_teto_por_lucro_negative_income():
    income = make_income([100, 120, 140, 160, -50])
    prices = {2019: 10.0, 2020: 12.0, 2021: 14.0, 2022: 16.0, 2023: 8.0}
    result = teto_por_lucro(income, prices, previous_close=8.0)
    assert result is not None  # applies geometric adjustment


def test_teto_por_lucro_insufficient_data():
    income = pd.Series([100], index=["2023-12-31"])
    prices = {2023: 10.0}
    result = teto_por_lucro(income, prices, previous_close=10.0)
    assert result is None


def test_teto_por_lucro_zero_range():
    """All lucros equal → division by zero → None."""
    income = make_income([100, 100, 100, 100, 100])
    prices = {2019: 10.0, 2020: 10.0, 2021: 10.0, 2022: 10.0, 2023: 10.0}
    result = teto_por_lucro(income, prices, previous_close=10.0)
    assert result is None


# --- remaining formulas ---
from preco_teto.formulas import teto_por_dy, teto_bazin, teto_graham, teto_dcf


def test_teto_por_dy_positive():
    result = teto_por_dy(cotacao=50.0, dy_estimado=0.06, indice_base=13.75)
    assert result == pytest.approx(50.0 * 0.06 / 0.1375, rel=1e-3)


def test_teto_por_dy_zero_dy():
    result = teto_por_dy(cotacao=50.0, dy_estimado=0.0, indice_base=13.75)
    assert result is None


def test_teto_bazin_positive():
    result = teto_bazin(dividendo_anual=3.0, indice_base=13.75)
    assert result == pytest.approx(3.0 / 0.1375, rel=1e-3)


def test_teto_bazin_zero_dividendo():
    result = teto_bazin(dividendo_anual=0.0, indice_base=13.75)
    assert result is None


def test_teto_bazin_none_dividendo():
    result = teto_bazin(dividendo_anual=None, indice_base=13.75)
    assert result is None


def test_teto_graham_positive():
    result = teto_graham(lpa=5.0, vpa=20.0)
    from math import sqrt
    assert result == pytest.approx(sqrt(22.5 * 5.0 * 20.0), rel=1e-3)


def test_teto_graham_negative_lpa():
    result = teto_graham(lpa=-1.0, vpa=20.0)
    assert result is None


def test_teto_graham_none_vpa():
    result = teto_graham(lpa=5.0, vpa=None)
    assert result is None


def test_teto_dcf_complete():
    result = teto_dcf(
        free_cashflow=1_000_000_000,
        shares_outstanding=500_000_000,
        beta=1.1,
        earnings_growth=0.10,
        taxa_livre_risco=13.75,
        premio_risco=5.5,
        inflacao=4.8,
    )
    assert result is not None
    assert result > 0


def test_teto_dcf_missing_fcl():
    result = teto_dcf(
        free_cashflow=None,
        shares_outstanding=500_000_000,
        beta=1.1,
        earnings_growth=0.10,
        taxa_livre_risco=13.75,
        premio_risco=5.5,
        inflacao=4.8,
    )
    assert result is None


def test_teto_dcf_missing_beta():
    result = teto_dcf(
        free_cashflow=1_000_000_000,
        shares_outstanding=500_000_000,
        beta=None,
        earnings_growth=0.10,
        taxa_livre_risco=13.75,
        premio_risco=5.5,
        inflacao=4.8,
    )
    assert result is None


def test_teto_dcf_growth_clamp_high():
    """earningsGrowth acima de 30% deve ser clampado a 30%."""
    r1 = teto_dcf(1e9, 5e8, 1.0, 0.30, 13.75, 5.5, 4.8)
    r2 = teto_dcf(1e9, 5e8, 1.0, 0.99, 13.75, 5.5, 4.8)
    assert r1 == pytest.approx(r2, rel=1e-6)


def test_teto_dcf_growth_clamp_low():
    """earningsGrowth abaixo de -20% deve ser clampado a -20%."""
    r1 = teto_dcf(1e9, 5e8, 1.0, -0.20, 13.75, 5.5, 4.8)
    r2 = teto_dcf(1e9, 5e8, 1.0, -0.99, 13.75, 5.5, 4.8)
    assert r1 == pytest.approx(r2, rel=1e-6)
