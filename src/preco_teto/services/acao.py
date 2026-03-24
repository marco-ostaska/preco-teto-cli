from dataclasses import dataclass, field
from datetime import datetime
import pandas as pd
import yfinance as yf
from scipy.stats import trim_mean


def _is_br(ticker: str) -> bool:
    return ticker[-1].isdigit()


def _get_cotacao(info: dict, history: pd.DataFrame) -> float | None:
    if "currentPrice" in info:
        return info["currentPrice"]
    if "previousClose" in info:
        return info["previousClose"]
    if "regularMarketPrice" in info:
        return info["regularMarketPrice"]
    try:
        return float(history["Close"].iloc[-1])
    except Exception:
        return None


def _year_prices(history: pd.DataFrame) -> dict[int, float]:
    """trim_mean(10%) dos últimos 30 pregões de cada ano no histórico."""
    result = {}
    if history.empty:
        return result
    history = history.copy()
    history.index = pd.to_datetime(history.index)
    for year in history.index.year.unique():
        mask = history.index.year == year
        vals = history.loc[mask, "Close"].tail(30).values
        if len(vals) > 0:
            result[int(year)] = float(trim_mean(vals, proportiontocut=0.1))
    return result


def _dividendo_medio(dividends: pd.Series, dividend_rate: float | None) -> float | None:
    """
    Calcula dividendo anual médio dos últimos 3 anos completos.
    Fallback: dividend_rate do yfinance se sem histórico completo.
    """
    try:
        if dividends is None or dividends.empty:
            return dividend_rate or None
        dividends = dividends.copy()
        dividends.index = pd.to_datetime(dividends.index)
        ano_atual = datetime.now().year
        por_ano = dividends.groupby(dividends.index.year).sum()
        anos_completos = por_ano[por_ano.index < ano_atual]
        if anos_completos.empty:
            return dividend_rate or None
        ultimos = anos_completos.tail(3)
        return round(float(ultimos.mean()), 4)
    except Exception:
        return dividend_rate or None


@dataclass
class AcaoData:
    ticker: str
    is_br: bool
    cotacao: float | None
    dividend_rate: float | None
    dividendo_medio: float | None   # média anual 3 anos (ou fallback dividend_rate)
    lpa: float | None
    vpa: float | None
    free_cashflow: float | None
    shares_outstanding: float | None
    beta: float | None
    earnings_growth: float | None
    revenue_growth: float | None
    income_net: pd.Series = field(repr=False, default=None)
    year_prices: dict = field(repr=False, default_factory=dict)
    previous_close: float | None = None
    low_52: float | None = None
    high_52: float | None = None


def fetch_acao(ticker: str) -> AcaoData:
    ticker = ticker.upper()
    is_br = _is_br(ticker)
    yf_ticker = f"{ticker}.SA" if is_br else ticker

    t = yf.Ticker(yf_ticker)
    info = t.info or {}
    history = t.history(period="5y")

    cotacao = _get_cotacao(info, history)
    year_px = _year_prices(history)

    income_net = None
    try:
        stmt = t.income_stmt
        if stmt is not None and "Net Income" in stmt.index:
            income_net = stmt.loc["Net Income"].dropna()
    except Exception:
        pass

    dividends = None
    try:
        dividends = t.dividends
    except Exception:
        pass

    dividend_rate = info.get("dividendRate")
    div_medio = _dividendo_medio(dividends, dividend_rate)

    return AcaoData(
        ticker=ticker,
        is_br=is_br,
        cotacao=cotacao,
        dividend_rate=dividend_rate,
        dividendo_medio=div_medio,
        lpa=info.get("trailingEps"),
        vpa=info.get("bookValue"),
        free_cashflow=info.get("freeCashflow"),
        shares_outstanding=info.get("sharesOutstanding"),
        beta=info.get("beta"),
        earnings_growth=info.get("earningsGrowth") or info.get("revenueGrowth"),
        revenue_growth=info.get("revenueGrowth"),
        income_net=income_net,
        year_prices=year_px,
        previous_close=info.get("previousClose") or info.get("regularMarketPreviousClose"),
        low_52=info.get("fiftyTwoWeekLow"),
        high_52=info.get("fiftyTwoWeekHigh"),
    )
