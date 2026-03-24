from dataclasses import dataclass, field
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


@dataclass
class AcaoData:
    ticker: str
    is_br: bool
    cotacao: float | None
    dividend_rate: float | None
    dy_estimado: float | None
    lpa: float | None
    vpa: float | None
    free_cashflow: float | None
    shares_outstanding: float | None
    beta: float | None
    earnings_growth: float | None
    revenue_growth: float | None
    income_net: pd.Series = field(repr=False, default=None)  # Net Income series
    year_prices: dict = field(repr=False, default_factory=dict)
    previous_close: float | None = None


def fetch_acao(ticker: str) -> AcaoData:
    ticker = ticker.upper()
    is_br = _is_br(ticker)
    yf_ticker = f"{ticker}.SA" if is_br else ticker

    t = yf.Ticker(yf_ticker)
    info = t.info or {}
    history = t.history(period="5y")

    cotacao = _get_cotacao(info, history)
    year_px = _year_prices(history)

    # Net Income series from income_stmt
    income_net = None
    try:
        stmt = t.income_stmt
        if stmt is not None and "Net Income" in stmt.index:
            income_net = stmt.loc["Net Income"].dropna()
    except Exception:
        pass

    dy_estimado = None
    if info.get("dividendRate") and cotacao:
        dy_estimado = info["dividendRate"] / cotacao

    return AcaoData(
        ticker=ticker,
        is_br=is_br,
        cotacao=cotacao,
        dividend_rate=info.get("dividendRate"),
        dy_estimado=dy_estimado,
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
    )
