from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import io
import zipfile

import pandas as pd
import requests
from bs4 import BeautifulSoup
import yfinance as yf


@dataclass
class EtfData:
    ticker: str
    nome: str | None
    cnpj: str
    cotacao: float | None
    pl_cota: float | None
    pl_total: float | None
    cotistas: int | None
    low_52: float | None
    high_52: float | None


def _parse_brl_number(value: str | None) -> float | None:
    if value is None:
        return None
    s = str(value).strip().replace("R$", "").replace(" ", "")
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _normalize_cnpj(value: str | None) -> str:
    if value is None:
        return ""
    return "".join(ch for ch in str(value) if ch.isdigit())


def _extract_value_by_label(soup: BeautifulSoup, label: str) -> str | None:
    for tag in soup.find_all(["h3", "span"]):
        if tag.get_text(" ", strip=True) == label:
            parent = tag.parent
            if parent is None:
                continue
            value = parent.find("strong", class_="value")
            if value is not None:
                return value.get_text(" ", strip=True)
    return None


def _fetch_statusinvest(ticker: str) -> BeautifulSoup:
    resp = requests.get(
        f"https://statusinvest.com.br/etfs/{ticker.lower()}",
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=20,
    )
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "html.parser")


def _iter_inf_diario_urls() -> list[str]:
    today = date.today()
    year_months = [(today.year, today.month)]
    if today.month == 1:
        year_months.append((today.year - 1, 12))
    else:
        year_months.append((today.year, today.month - 1))
    return [
        f"https://dados.cvm.gov.br/dados/FI/DOC/INF_DIARIO/DADOS/inf_diario_fi_{year:04d}{month:02d}.zip"
        for year, month in year_months
    ]


def _load_latest_inf_diario_row(cnpj: str) -> pd.Series | None:
    cnpj_digits = _normalize_cnpj(cnpj)
    for url in _iter_inf_diario_urls():
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            name = zf.namelist()[0]
            df = pd.read_csv(zf.open(name), sep=";", encoding="latin-1", dtype=str)
        rows = df[df["CNPJ_FUNDO_CLASSE"].fillna("").map(_normalize_cnpj) == cnpj_digits]
        if rows.empty:
            continue
        dates = pd.to_datetime(rows["DT_COMPTC"], errors="coerce")
        return rows.loc[dates.idxmax()]
    return None


def _history_low_high(history: pd.DataFrame) -> tuple[float | None, float | None]:
    if history is None or history.empty or "Close" not in history:
        return None, None
    close = history["Close"].dropna()
    if close.empty:
        return None, None
    return float(close.min()), float(close.max())


def _fetch_etf_us(ticker: str) -> EtfData:
    t = yf.Ticker(ticker)
    info = t.info or {}
    history = t.history(period="1y")
    hist_low, hist_high = _history_low_high(history)
    return EtfData(
        ticker=ticker,
        nome=info.get("shortName") or info.get("longName") or ticker,
        cnpj="",
        cotacao=info.get("currentPrice") or info.get("previousClose") or info.get("regularMarketPrice"),
        pl_cota=info.get("navPrice"),
        pl_total=info.get("totalAssets") or info.get("netAssets"),
        cotistas=None,
        low_52=info.get("fiftyTwoWeekLow") or hist_low,
        high_52=info.get("fiftyTwoWeekHigh") or hist_high,
    )


def fetch_etf(ticker: str) -> EtfData:
    ticker = ticker.upper()
    soup = _fetch_statusinvest(ticker)

    cnpj = _extract_value_by_label(soup, "CNPJ")
    if not cnpj:
        return _fetch_etf_us(ticker)

    info_row = _load_latest_inf_diario_row(cnpj)
    pl_cota = _parse_brl_number(info_row.get("VL_QUOTA")) if info_row is not None else None
    pl_total = _parse_brl_number(info_row.get("VL_PATRIM_LIQ")) if info_row is not None else None
    cotistas = int(info_row.get("NR_COTST")) if info_row is not None and info_row.get("NR_COTST") else None

    nome = soup.find("h1").get_text(" ", strip=True) if soup.find("h1") else ticker
    if nome.upper().startswith(f"{ticker} - "):
        nome = nome.split(" - ", 1)[1].strip()

    return EtfData(
        ticker=ticker,
        nome=nome,
        cnpj=cnpj,
        cotacao=_parse_brl_number(_extract_value_by_label(soup, "Valor atual")),
        pl_cota=pl_cota,
        pl_total=pl_total,
        cotistas=cotistas,
        low_52=_parse_brl_number(_extract_value_by_label(soup, "Min. 52 semanas")),
        high_52=_parse_brl_number(_extract_value_by_label(soup, "Máx. 52 semanas")),
    )
