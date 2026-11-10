"""Point-in-time teto cascade: PL → DY médio 3a → VPA/ROE (CDI/Fed)."""
from __future__ import annotations

from datetime import timedelta
from typing import Literal

import pandas as pd
import yfinance as yf
from scipy.stats import linregress

from preco_teto.formulas import teto_por_dy, teto_por_lucro, teto_vpa_roe
from preco_teto.services.acao import _is_br, _year_prices
from preco_teto.services.banco_central import (
    cdi_anualizado_asof,
    fetch_cdi_daily_series,
    fetch_ipca,
    melhor_indice_br,
)
from preco_teto.services.referencia import FED_FUNDS_US

THRESHOLD = 1.0
LAG_DAYS = 90
HORIZONS = (3, 6, 12, 24)
MC_N = 1000
DEFAULT_SEED = 42
BENCHMARK_BR = "^BVSP"
BENCHMARK_US = "^GSPC"

TetoMethod = Literal["pl", "dy", "vpa_roe"]


def is_action_ticker(ticker: str) -> bool:
    t = ticker.upper()
    if t.endswith("11"):
        return False
    if _is_br(t):
        return True
    return t.isalpha()


def yf_symbol(ticker: str) -> tuple[str, bool]:
    ticker = ticker.upper()
    is_br = _is_br(ticker)
    return (f"{ticker}.SA" if is_br else ticker), is_br


def fetch_ohlcv(ticker: str, period: str = "max") -> pd.DataFrame:
    symbol, _ = yf_symbol(ticker)
    t = yf.Ticker(symbol)
    history = t.history(period=period, auto_adjust=False)
    if history is None or history.empty:
        return pd.DataFrame()
    history = history.copy()
    history.index = pd.to_datetime(history.index).tz_localize(None)
    cols = [c for c in ("Open", "High", "Low", "Close", "Adj Close") if c in history.columns]
    return history[cols].dropna(how="all")


def fetch_income_net(ticker: str) -> pd.Series | None:
    symbol, _ = yf_symbol(ticker)
    t = yf.Ticker(symbol)
    try:
        stmt = t.income_stmt
        if stmt is None or "Net Income" not in stmt.index:
            return None
        income = stmt.loc["Net Income"].dropna()
        income.index = pd.to_datetime(income.index).tz_localize(None)
        return income
    except Exception:
        return None


def fetch_fundamentals_bundle(ticker: str) -> dict:
    """One yfinance round-trip for statements + dividends + shares."""
    symbol, is_br = yf_symbol(ticker)
    t = yf.Ticker(symbol)
    info = t.info or {}
    income_stmt = None
    balance_sheet = None
    dividends = None
    try:
        income_stmt = t.income_stmt
    except Exception:
        pass
    try:
        balance_sheet = t.balance_sheet
    except Exception:
        pass
    try:
        dividends = t.dividends
        if dividends is not None and not dividends.empty:
            dividends = dividends.copy()
            dividends.index = pd.to_datetime(dividends.index).tz_localize(None)
    except Exception:
        pass
    income_net = None
    if income_stmt is not None and "Net Income" in income_stmt.index:
        income_net = income_stmt.loc["Net Income"].dropna()
        income_net.index = pd.to_datetime(income_net.index).tz_localize(None)
    shares = info.get("sharesOutstanding")
    try:
        shares = float(shares) if shares is not None else None
    except (TypeError, ValueError):
        shares = None
    return {
        "is_br": is_br,
        "income_net": income_net,
        "income_stmt": income_stmt,
        "balance_sheet": balance_sheet,
        "dividends": dividends,
        "shares_outstanding": shares,
    }


def fetch_benchmark_ohlcv(is_br: bool, period: str = "max") -> pd.DataFrame:
    symbol = BENCHMARK_BR if is_br else BENCHMARK_US
    t = yf.Ticker(symbol)
    history = t.history(period=period, auto_adjust=False)
    if history is None or history.empty:
        return pd.DataFrame()
    history = history.copy()
    history.index = pd.to_datetime(history.index).tz_localize(None)
    cols = [c for c in ("Open", "High", "Low", "Close", "Adj Close") if c in history.columns]
    return history[cols].dropna(how="all")


def income_asof(
    income: pd.Series,
    as_of: pd.Timestamp,
    lag_days: int = LAG_DAYS,
) -> pd.Series:
    """
    Net Income anual sticky (conjunto PIT).

    Cada YE entra em available_date = YE + lag_days e permanece no conjunto
    para sempre (não expira). O último NI conhecido continua válido até o fim
    dos preços — `income_asof` só filtra por disponibilidade, nunca remove NIs
    já liberados.
    """
    if income is None or income.empty:
        return pd.Series(dtype=float)
    as_of = pd.Timestamp(as_of).normalize()
    keep = []
    for period_end, value in income.items():
        pe = pd.Timestamp(period_end).normalize()
        available = pe + timedelta(days=lag_days)
        if available <= as_of:
            keep.append((pe, value))
    if not keep:
        return pd.Series(dtype=float)
    idx, vals = zip(*keep)
    return pd.Series(vals, index=pd.DatetimeIndex(idx))


def ni_sticky_records(
    income: pd.Series | None,
    *,
    last_price_date: pd.Timestamp,
    lag_days: int = LAG_DAYS,
) -> list[dict]:
    """
    Um registro por NI anual com intervalo em que foi o release mais recente.

    - available_date = year_end + lag_days
    - used_from = available_date
    - used_until = dia anterior ao available do próximo YE; o último vai até
      last_price_date (não expira)
    No conjunto PIT (income_asof), todos os NIs já liberados coexistem.
    """
    if income is None or income.empty:
        return []
    last_price_date = pd.Timestamp(last_price_date).normalize()
    rows = []
    for pe, val in income.items():
        pe_ts = pd.Timestamp(pe).normalize()
        rows.append(
            {
                "year_end": pe_ts,
                "available_date": pe_ts + timedelta(days=lag_days),
                "net_income": float(val),
            }
        )
    rows.sort(key=lambda r: r["year_end"])
    out: list[dict] = []
    for i, r in enumerate(rows):
        used_from = r["available_date"]
        if i + 1 < len(rows):
            used_until = rows[i + 1]["available_date"] - timedelta(days=1)
        else:
            used_until = last_price_date
        out.append(
            {
                "year_end": str(r["year_end"].date()),
                "available_date": str(r["available_date"].date()),
                "net_income": r["net_income"],
                "used_from": str(used_from.date()),
                "used_until": str(used_until.date()),
            }
        )
    return out


def year_prices_asof(history: pd.DataFrame, as_of: pd.Timestamp) -> dict[int, float]:
    as_of = pd.Timestamp(as_of).normalize()
    if history is None or history.empty:
        return {}
    hist = history.copy()
    hist.index = pd.to_datetime(hist.index).tz_localize(None)
    hist = hist.loc[hist.index <= as_of]
    return _year_prices(hist)


def previous_adj_close_asof(history: pd.DataFrame, as_of: pd.Timestamp) -> float | None:
    as_of = pd.Timestamp(as_of).normalize()
    if history is None or history.empty:
        return None
    hist = history.copy()
    hist.index = pd.to_datetime(hist.index).tz_localize(None)
    hist = hist.loc[hist.index <= as_of]
    if hist.empty or "Adj Close" not in hist.columns:
        return None
    val = hist["Adj Close"].dropna()
    if val.empty:
        return None
    return float(val.iloc[-1])


def teto_pl_asof(
    history: pd.DataFrame,
    income: pd.Series,
    as_of: pd.Timestamp,
    lag_days: int = LAG_DAYS,
) -> float | None:
    inc = income_asof(income, as_of, lag_days)
    if inc is None or len(inc.dropna()) < 2:
        return None
    yp = year_prices_asof(history, as_of)
    prev = previous_adj_close_asof(history, as_of)
    if prev is None:
        return None
    return teto_por_lucro(inc, yp, prev)


def dividendo_medio_asof(
    dividends: pd.Series | None,
    as_of: pd.Timestamp,
) -> float | None:
    """Média dos dividendos anuais dos últimos 3 anos civis completos ≤ as_of."""
    if dividends is None or dividends.empty:
        return None
    as_of = pd.Timestamp(as_of).normalize()
    div = dividends.copy()
    div.index = pd.to_datetime(div.index).tz_localize(None)
    div = div.loc[div.index <= as_of]
    if div.empty:
        return None
    por_ano = div.groupby(div.index.year).sum()
    anos_completos = por_ano[por_ano.index < as_of.year]
    if anos_completos.empty:
        return None
    ultimos = anos_completos.tail(3)
    return round(float(ultimos.mean()), 4)


def indice_base_asof(
    is_br: bool,
    as_of: pd.Timestamp,
    *,
    cdi_daily: pd.Series | None = None,
    ipca_atual: float | None = None,
) -> float | None:
    """BR: melhor_indice(CDI as-of, IPCA atual sticky). US: Fed Funds constante."""
    if not is_br:
        return FED_FUNDS_US
    cdi = cdi_anualizado_asof(cdi_daily, as_of) if cdi_daily is not None else None
    return melhor_indice_br(cdi, ipca_atual)


def taxa_vpa_roe_asof(
    is_br: bool,
    as_of: pd.Timestamp,
    *,
    cdi_daily: pd.Series | None = None,
) -> float | None:
    """Taxa para teto_vpa_roe: CDI as-of (BR) ou Fed Funds (US)."""
    if not is_br:
        return FED_FUNDS_US
    return cdi_anualizado_asof(cdi_daily, as_of) if cdi_daily is not None else None


def _stmt_series_asof(statement: pd.DataFrame | None, *labels: str, as_of, lag_days) -> pd.Series:
    if not isinstance(statement, pd.DataFrame) or statement.empty:
        return pd.Series(dtype=float)
    row = next((name for name in labels if name in statement.index), None)
    if row is None:
        return pd.Series(dtype=float)
    s = pd.to_numeric(statement.loc[row], errors="coerce").dropna()
    s.index = pd.to_datetime(s.index).tz_localize(None)
    as_of = pd.Timestamp(as_of).normalize()
    keep = {}
    for pe, val in s.items():
        pe_ts = pd.Timestamp(pe).normalize()
        if pe_ts + timedelta(days=lag_days) <= as_of:
            keep[pe_ts] = float(val)
    if not keep:
        return pd.Series(dtype=float)
    return pd.Series(keep).sort_index()


def vpa_roe_asof(
    income_stmt: pd.DataFrame | None,
    balance_sheet: pd.DataFrame | None,
    shares_outstanding: float | None,
    as_of: pd.Timestamp,
    lag_days: int = LAG_DAYS,
) -> tuple[float | None, float | None]:
    """
    VPA = último equity disponível / shares; ROE ajustado como em acao._roe_historico
    só com exercícios publicados (YE+lag ≤ as_of).
    """
    income = _stmt_series_asof(
        income_stmt, "Net Income", "Net Income Common Stockholders",
        as_of=as_of, lag_days=lag_days,
    )
    equity = _stmt_series_asof(
        balance_sheet,
        "Stockholders Equity", "Common Stock Equity", "Total Equity Gross Minority Interest",
        as_of=as_of, lag_days=lag_days,
    )
    vpa = None
    if not equity.empty and shares_outstanding and shares_outstanding > 0:
        vpa = round(float(equity.iloc[-1]) / shares_outstanding, 2)

    roe_ajustado = None
    try:
        values = pd.concat([income.rename("income"), equity.rename("equity")], axis=1).dropna().sort_index()
        if len(values) >= 2:
            previous_equity = values["equity"].shift(1)
            average_equity = values["equity"].where(
                previous_equity.isna(), (values["equity"] + previous_equity) / 2
            )
            roe_values = (
                (values["income"] / average_equity * 100)
                .replace([float("inf"), -float("inf")], pd.NA)
                .dropna()
                .tail(5)
            )
            if len(roe_values) >= 2:
                regression = linregress(range(len(roe_values)), roe_values.values)
                media = float(roe_values.mean())
                tendencia = float(regression.slope)
                roe_ajustado = round(media + max(-5.0, min(5.0, tendencia)), 2)
    except Exception:
        roe_ajustado = None
    return vpa, roe_ajustado


def teto_dy_asof(
    dividends: pd.Series | None,
    as_of: pd.Timestamp,
    indice_base: float | None,
) -> float | None:
    div = dividendo_medio_asof(dividends, as_of)
    return teto_por_dy(div, indice_base) if indice_base else None


def teto_vpa_roe_taxa_asof(
    income_stmt,
    balance_sheet,
    shares_outstanding,
    as_of: pd.Timestamp,
    taxa: float | None,
    lag_days: int = LAG_DAYS,
) -> float | None:
    vpa, roe = vpa_roe_asof(
        income_stmt, balance_sheet, shares_outstanding, as_of, lag_days=lag_days,
    )
    return teto_vpa_roe(vpa, roe, taxa)


def resolve_teto_asof(
    *,
    history: pd.DataFrame,
    income: pd.Series | None,
    as_of: pd.Timestamp,
    lag_days: int = LAG_DAYS,
    cascade: bool = False,
    dividends: pd.Series | None = None,
    income_stmt=None,
    balance_sheet=None,
    shares_outstanding: float | None = None,
    is_br: bool = True,
    cdi_daily: pd.Series | None = None,
    ipca_atual: float | None = None,
) -> tuple[float | None, TetoMethod | None, list[str]]:
    """
    Default: só PL.
    Com cascade=True: PL → DY médio 3a → VPA/ROE (CDI/Fed), com avisos em cada fallback.
    """
    avisos: list[str] = []
    pl = teto_pl_asof(history, income if income is not None else pd.Series(dtype=float), as_of, lag_days)
    if pl is not None:
        return pl, "pl", avisos

    if not cascade:
        return None, None, avisos

    avisos.append("PL ruim/indisponível — usando Teto por DY (DY médio 3a)")
    indice = indice_base_asof(is_br, as_of, cdi_daily=cdi_daily, ipca_atual=ipca_atual)
    dy = teto_dy_asof(dividends, as_of, indice)
    if dy is not None:
        return dy, "dy", avisos

    avisos.append("DY médio 3a ruim/indisponível — usando Teto VPA/ROE (CDI/Fed Funds)")
    taxa = taxa_vpa_roe_asof(is_br, as_of, cdi_daily=cdi_daily)
    vr = teto_vpa_roe_taxa_asof(
        income_stmt, balance_sheet, shares_outstanding, as_of, taxa, lag_days=lag_days,
    )
    if vr is not None:
        return vr, "vpa_roe", avisos

    avisos.append("VPA/ROE (CDI/Fed) ruim/indisponível")
    return None, None, avisos


def load_rate_context(is_br: bool) -> dict:
    """Fetch rate series once per backtest run."""
    if not is_br:
        return {"cdi_daily": None, "ipca_atual": None}
    return {
        "cdi_daily": fetch_cdi_daily_series(anos=25),
        "ipca_atual": fetch_ipca(),
    }
