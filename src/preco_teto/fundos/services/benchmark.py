from __future__ import annotations
from datetime import date
import requests
import pandas as pd
import yfinance as yf

_BCB_SERIE_12 = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.12/dados"
_BCB_SERIE_1 = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.1/dados"
_MARKET_TICKERS = {
    "DIVO11": "DIVO11.SA",
    "IVV": "IVV",
    "BTC": "BTC-USD",
}
_SUPPORTED_BENCHMARKS = {"CDI", "DIVO11", "IVV", "BTC", "USD"}


def normalize_benchmark(value: str | None) -> str | None:
    if value is None:
        return None
    bench = str(value).strip().upper()
    return bench if bench in _SUPPORTED_BENCHMARKS else None


def fetch_cdi_historico(inicio: date, fim: date) -> pd.DataFrame:
    """
    Returns DataFrame [data (datetime), taxa (float %)] from BCB série 12.
    taxa is the daily DI rate in %, e.g. 0.052319.
    """
    fmt = "%d/%m/%Y"
    url = (
        f"{_BCB_SERIE_12}?formato=json"
        f"&dataInicial={inicio.strftime(fmt)}"
        f"&dataFinal={fim.strftime(fmt)}"
    )
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    df = pd.DataFrame(data)
    df["data"] = pd.to_datetime(df["data"], format="%d/%m/%Y")
    df["taxa"] = df["valor"].str.replace(",", ".").astype(float)
    return df[["data", "taxa"]].reset_index(drop=True)


def fetch_usd_historico(inicio: date, fim: date) -> pd.DataFrame:
    fmt = "%d/%m/%Y"
    url = (
        f"{_BCB_SERIE_1}?formato=json"
        f"&dataInicial={inicio.strftime(fmt)}"
        f"&dataFinal={fim.strftime(fmt)}"
    )
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    df = pd.DataFrame(data)
    df["data"] = pd.to_datetime(df["data"], format="%d/%m/%Y")
    df["valor"] = df["valor"].str.replace(",", ".").astype(float)
    return df[["data", "valor"]].reset_index(drop=True)


def fetch_market_historico(benchmark: str, inicio: date, fim: date) -> pd.DataFrame:
    ticker = _MARKET_TICKERS[benchmark]
    history = yf.Ticker(ticker).history(
        start=inicio,
        end=fim + pd.Timedelta(days=1),
        auto_adjust=True,
    )
    if history.empty:
        return pd.DataFrame(columns=["data", "valor"])
    close_col = "Close" if "Close" in history.columns else "Adj Close"
    df = history.reset_index()
    df["data"] = pd.to_datetime(df.iloc[:, 0]).dt.tz_localize(None)
    df["valor"] = df[close_col].astype(float)
    return df[["data", "valor"]].reset_index(drop=True)


def fetch_benchmark_historico(benchmark: str, inicio: date, fim: date) -> pd.DataFrame:
    benchmark_key = normalize_benchmark(benchmark)
    if benchmark_key is None:
        raise ValueError(f"Benchmark inválido: {benchmark!r}.")
    if benchmark_key == "CDI":
        return fetch_cdi_historico(inicio, fim)
    if benchmark_key == "USD":
        return fetch_usd_historico(inicio, fim)
    return fetch_market_historico(benchmark_key, inicio, fim)
