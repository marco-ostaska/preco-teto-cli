from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd
import requests
import yfinance as yf

_PTAX_URL = (
    "https://api.bcb.gov.br/dados/serie/bcdata.sgs.1/dados"
    "?formato=json&dataInicial={inicio}&dataFinal={fim}"
)
_COT_URL = "https://publicreporting.cftc.gov/resource/gpe5-46if.json"
_COT_CONTRATO_REAL = "102741"  # BRAZILIAN REAL - CME (232741 é o dólar australiano)
_TIMEOUT = 30
_JANELA_FLUXO = 60
_DXY = "DX-Y.NYB"
_EWZ = "EWZ"
_IBOV = "^BVSP"


@dataclass
class CotData:
    data: date
    lev_net_pct: float
    am_net_pct: float
    lev_pctl: float
    am_pctl: float
    serie_lev_net: pd.Series
    serie_am_net: pd.Series


@dataclass
class UsdData:
    spot: float | None          # PTAX (BCB) — oficial, pode atrasar 1 dia útil
    data_spot: date | None
    spot_comercial: float | None  # BRL=X — intradía / mais fresco
    ptax: pd.Series
    low_52: float | None
    high_52: float | None
    margem_52: float | None
    dxy: float | None
    dxy_pctl: float | None
    dxy_hist: pd.Series
    cot: CotData | None
    k_hat: float | None
    ibov: float | None
    ewz: float | None
    desvio_z: float | None
    uup: tuple[float | None, float | None]
    udn: tuple[float | None, float | None]

    @property
    def spot_ref(self) -> float | None:
        """Âncora potencial/carrego/COT: comercial se houver, senão PTAX."""
        return self.spot_comercial if self.spot_comercial is not None else self.spot


def _anos_ptax(anos: int) -> list[int]:
    hoje = date.today()
    return list(range(hoje.year - anos + 1, hoje.year + 1))


def _fetch_ptax_ano(ano: int) -> pd.Series:
    url = _PTAX_URL.format(inicio=f"01/01/{ano}", fim=f"31/12/{ano}")
    try:
        resp = requests.get(url, timeout=_TIMEOUT)
        if resp.status_code != 200 or not resp.text.strip().startswith("["):
            return pd.Series(dtype=float)
        dados = resp.json()
    except Exception:
        return pd.Series(dtype=float)
    try:
        idx = pd.to_datetime([row["data"] for row in dados], dayfirst=True)
        valores = [float(row["valor"].replace(",", ".")) for row in dados]
        return pd.Series(valores, index=pd.DatetimeIndex(idx)).sort_index()
    except Exception:
        return pd.Series(dtype=float)


def fetch_ptax(anos: int = 3) -> pd.Series:
    """
    USD/BRL PTAX venda (série 1 do BCB), diária.
    A API do BCB falha em ranges longos, então a busca é ano a ano.
    """
    partes = [p for p in (_fetch_ptax_ano(ano) for ano in _anos_ptax(anos)) if not p.empty]
    if not partes:
        return pd.Series(dtype=float)
    return pd.concat(partes).sort_index()


def fetch_cot_real(semanas: int = 260) -> CotData | None:
    """
    COT do Real (Traders in Financial Futures, CFTC).
    Posicionamento líquido em % do open interest — nível, não absurdo de escala.
    """
    params = {
        "$limit": max(semanas * 4, 4),
        "$order": "report_date_as_yyyy_mm_dd DESC",
        "$where": f"cftc_contract_market_code='{_COT_CONTRATO_REAL}'",
        "$select": (
            "report_date_as_yyyy_mm_dd,open_interest_all,"
            "lev_money_positions_long,lev_money_positions_short,"
            "asset_mgr_positions_long,asset_mgr_positions_short"
        ),
    }
    try:
        resp = requests.get(_COT_URL, params=params, timeout=_TIMEOUT)
        resp.raise_for_status()
        linhas = resp.json()
    except Exception:
        return None
    if not linhas:
        return None
    try:
        df = pd.DataFrame(linhas)
        colunas = (
            "open_interest_all",
            "lev_money_positions_long",
            "lev_money_positions_short",
            "asset_mgr_positions_long",
            "asset_mgr_positions_short",
        )
        for coluna in colunas:
            df[coluna] = df[coluna].astype(float)
        df.index = pd.to_datetime(df["report_date_as_yyyy_mm_dd"].str[:10])
        df = df.sort_index()
        oi = df["open_interest_all"].replace(0, np.nan)
        lev_net = (
            (df["lev_money_positions_long"] - df["lev_money_positions_short"]) / oi * 100
        ).dropna()
        am_net = (
            (df["asset_mgr_positions_long"] - df["asset_mgr_positions_short"]) / oi * 100
        ).dropna()
        if lev_net.empty:
            return None
        janela = lev_net.tail(semanas)
        atual_lev = float(lev_net.iloc[-1])
        atual_am = float(am_net.iloc[-1]) if not am_net.empty else 0.0
        return CotData(
            data=lev_net.index[-1].date(),
            lev_net_pct=round(atual_lev, 1),
            am_net_pct=round(atual_am, 1),
            lev_pctl=round(float((janela < atual_lev).mean() * 100), 1),
            am_pctl=round(float((am_net.tail(semanas) < atual_am).mean() * 100), 1)
            if not am_net.empty
            else 0.0,
            serie_lev_net=lev_net,
            serie_am_net=am_net,
        )
    except Exception:
        return None


def _fetch_history(ticker: str, periodo: str = "5y") -> pd.Series:
    """Fechamento diário sem timezone — os índices não batem entre si com tz."""
    try:
        fechamentos = yf.Ticker(ticker).history(period=periodo)["Close"].dropna()
        fechamentos.index = pd.to_datetime(fechamentos.index).tz_localize(None).normalize()
        return fechamentos
    except Exception:
        return pd.Series(dtype=float)


def _quote(ticker: str) -> tuple[float | None, float | None]:
    try:
        info = yf.Ticker(ticker).info or {}
        preco = info.get("currentPrice") or info.get("previousClose") or info.get("regularMarketPrice")
        return preco, info.get("navPrice")
    except Exception:
        return None, None


def _fluxo_equity(
    ptax: pd.Series,
    ewz: pd.Series,
    ibov: pd.Series,
) -> tuple[float | None, float | None, float | None, float | None]:
    """
    Calibra k = EWZ × USD/BRL / IBOV na mediana recente.
    Devolve (k_hat, IBOV atual, EWZ atual, z do desvio) — o desvio mostra se o
    câmbio andou mais do que o fluxo de equity justifica.
    """
    base = pd.concat(
        [ptax.rename("brl"), ewz.rename("ewz"), ibov.rename("ibov")],
        axis=1,
        sort=True,
    ).dropna()
    if len(base) < _JANELA_FLUXO:
        return None, None, None, None
    k = base["ewz"] * base["brl"] / base["ibov"]
    k_hat = float(k.tail(_JANELA_FLUXO).median())
    desvios = (np.log(k) - np.log(k.rolling(_JANELA_FLUXO).median())).dropna()
    desvio_z = None
    if not desvios.empty and float(desvios.std()) > 0:
        desvio_z = round(float(desvios.iloc[-1] / desvios.std()), 2)
    return k_hat, float(base["ibov"].iloc[-1]), float(base["ewz"].iloc[-1]), desvio_z


def fetch_usd(anos: int = 3) -> UsdData:
    """Painel USD/BRL: PTAX, spot comercial, DXY, COT do Real, fluxo via EWZ e UUP/UDN."""
    ptax = fetch_ptax(anos)
    dxy_hist = _fetch_history(_DXY)
    ewz_hist = _fetch_history(_EWZ)
    ibov_hist = _fetch_history(_IBOV)
    cot = fetch_cot_real()
    spot_comercial, _ = _quote("BRL=X")
    uup = _quote("UUP")
    udn = _quote("UDN")

    spot = float(ptax.iloc[-1]) if not ptax.empty else None
    data_spot = ptax.index[-1].date() if not ptax.empty else None
    janela_52 = ptax.tail(252)
    low_52 = float(janela_52.min()) if not janela_52.empty else None
    high_52 = float(janela_52.max()) if not janela_52.empty else None
    margem_52 = None
    if spot is not None and low_52 is not None and high_52 is not None and high_52 > low_52:
        margem_52 = round((spot - low_52) / (high_52 - low_52), 4)

    dxy = dxy_pctl = None
    if not dxy_hist.empty:
        janela_dxy = dxy_hist.tail(252 * 3)
        dxy = float(dxy_hist.iloc[-1])
        dxy_pctl = round(float((janela_dxy < dxy).mean() * 100), 1)

    k_hat, ibov, ewz, desvio_z = _fluxo_equity(ptax, ewz_hist, ibov_hist)

    return UsdData(
        spot=spot,
        data_spot=data_spot,
        spot_comercial=float(spot_comercial) if spot_comercial is not None else None,
        ptax=ptax,
        low_52=low_52,
        high_52=high_52,
        margem_52=margem_52,
        dxy=dxy,
        dxy_pctl=dxy_pctl,
        dxy_hist=dxy_hist,
        cot=cot,
        k_hat=k_hat,
        ibov=ibov,
        ewz=ewz,
        desvio_z=desvio_z,
        uup=uup,
        udn=udn,
    )
