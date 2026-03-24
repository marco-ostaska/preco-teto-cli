import pytest
import pandas as pd


@pytest.fixture
def mock_yf_info_br():
    return {
        "currentPrice": 58.20,
        "previousClose": 57.80,
        "regularMarketPrice": 58.10,
        "dividendRate": 3.60,
        "dividendYield": 0.062,
        "trailingEps": 5.50,
        "bookValue": 32.00,
        "freeCashflow": 15_000_000_000,
        "sharesOutstanding": 1_300_000_000,
        "beta": 0.95,
        "earningsGrowth": 0.12,
        "revenueGrowth": 0.08,
    }


@pytest.fixture
def mock_yf_info_us():
    return {
        "currentPrice": 189.50,
        "previousClose": 188.00,
        "dividendRate": 0.96,
        "dividendYield": 0.005,
        "trailingEps": 6.13,
        "bookValue": 4.00,
        "freeCashflow": 100_000_000_000,
        "sharesOutstanding": 15_500_000_000,
        "beta": 1.2,
        "earningsGrowth": 0.09,
    }


@pytest.fixture
def mock_income_stmt():
    years = pd.to_datetime(["2019-12-31", "2020-12-31", "2021-12-31", "2022-12-31", "2023-12-31"])
    return pd.DataFrame(
        {"Net Income": [10e9, 12e9, 14e9, 16e9, 18e9]},
        index=years
    ).T


@pytest.fixture
def mock_adj_close():
    dates = pd.date_range("2019-01-01", "2023-12-31", freq="B")
    import numpy as np
    np.random.seed(42)
    prices = 50 + np.cumsum(np.random.randn(len(dates)) * 0.5)
    return pd.DataFrame({"Close": prices}, index=dates)


# --- FII fixtures ---

FIISCOM_HTML = """
<html><body>
  <h1>HGLG11 - CGHG Logística</h1>
  <div class="headerTicker__content__name"><p>Fundo de Logística</p></div>
  <div class="item quotation"><span class="value">142,50</span></div>
  <div class="indicators">
    <div class="indicators__box">
      <p><b>17,01%</b></p><p>Dividend Yield</p>
    </div>
  </div>
  <div class="wrapper indicators">
    <div class="indicators__box">
      <p><b>151,30</b></p><p>Val. Patrimonial p/Cota</p>
    </div>
  </div>
</body></html>
"""

INVESTIDOR10_HTML = """
<html><body>
  <div class="item" data-label="P/VP"><span class="value">0,94</span></div>
  <div class="item" data-label="Dividend Yield"><span class="value">8,40%</span></div>
  <div class="item" data-label="Segmento"><span class="value">Logística</span></div>
</body></html>
"""


@pytest.fixture
def mock_fiiscom_html():
    return FIISCOM_HTML


@pytest.fixture
def mock_investidor10_html():
    return INVESTIDOR10_HTML


@pytest.fixture
def mock_dividends_series():
    # 12 months, last 3 months lower (declining trend)
    vals = [1.20, 1.18, 1.15, 1.30, 1.28, 1.25, 1.22, 1.20, 1.18, 1.16, 1.14, 1.12]
    dates = pd.date_range("2023-01-01", periods=12, freq="MS")
    return pd.Series(vals[::-1], index=dates[::-1])  # newest first


@pytest.fixture
def mock_dividends_3y():
    """Dividendos mensais cobrindo 3 anos completos (2021, 2022, 2023)."""
    dates = pd.date_range("2021-01-15", periods=36, freq="30D")
    # 2021: ~1.00/mês, 2022: ~1.20/mês, 2023: ~1.40/mês
    vals = (
        [1.00] * 12 +  # 2021: total 12.00
        [1.20] * 12 +  # 2022: total 14.40
        [1.40] * 12    # 2023: total 16.80
    )
    return pd.Series(vals, index=dates)


@pytest.fixture
def mock_dividends_1y():
    """Dividendos cobrindo apenas 1 ano completo (2023)."""
    dates = pd.date_range("2023-01-15", periods=12, freq="MS")
    vals = [1.40] * 12  # 2023: total 16.80
    return pd.Series(vals, index=dates)


@pytest.fixture
def mock_dividends_empty():
    """Sem histórico de dividendos."""
    return pd.Series([], dtype=float)
