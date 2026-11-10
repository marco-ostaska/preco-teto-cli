from __future__ import annotations

from dataclasses import dataclass
import os
import time

import pandas as pd
import requests
import yfinance as yf

from preco_teto.formulas import teto_margem, teto_por_regressao

_CG_BASE_DEMO = "https://api.coingecko.com/api/v3"
_CG_BASE_PRO = "https://pro-api.coingecko.com/api/v3"
_TIMEOUT = 30
_SOURCE_YF = "Yahoo Finance"
_SOURCE_HYBRID = "Yahoo Finance + CoinGecko"
_DXY = "DX-Y.NYB"  # peer usd.py:19
_GOLD = "GC=F"
_CG_RETRIES = 3
_CG_RETRY_SLEEP_S = 12


class CryptoFetchError(Exception):
    pass


@dataclass
class CryptoData:
    id: str
    symbol: str
    name: str
    cotacao: float | None
    low_52: float | None
    high_52: float | None
    margem_52: float | None
    ath: float | None
    ath_change_pct: float | None
    mcap: float | None
    rank: int | None
    circ_supply: float | None
    max_supply: float | None
    volume_24h: float | None
    change_30d: float | None
    change_1y: float | None
    price_hist: pd.Series
    btc_hist: pd.Series
    btc_dominance_pct: float | None
    source: str
    dxy: float | None
    dxy_hist: pd.Series
    gold: float | None
    gold_hist: pd.Series


def _cg_enabled() -> bool:
    return bool(os.environ.get("COINGECKO_API_KEY"))


def _cg_plan() -> str:
    """demo (default) | pro — Pro usa host distinto."""
    return os.environ.get("COINGECKO_API_PLAN", "demo").lower()


def _cg_base() -> str:
    return _CG_BASE_PRO if _cg_plan() == "pro" else _CG_BASE_DEMO


def _cg_headers() -> dict[str, str]:
    key = os.environ.get("COINGECKO_API_KEY")
    if not key:
        return {}
    if _cg_plan() == "pro":
        return {"x-cg-pro-api-key": key}
    return {"x-cg-demo-api-key": key}


def _normalize_query(ticker: str) -> str:
    t = ticker.strip().upper()
    for suf in ("-USD", "/USD"):
        if t.endswith(suf):
            t = t[: -len(suf)].rstrip("-/")
            break
    if t.endswith("USD") and len(t) > 3:
        t = t[:-3]
    return t


def _yf_symbol(ticker: str) -> str:
    """Spot crypto no Yahoo é SYMBOL-USD (BTC cru = ETF)."""
    return f"{_normalize_query(ticker)}-USD"


def _chart_to_series(prices: list) -> pd.Series:
    if not prices:
        return pd.Series(dtype=float)
    try:
        idx = pd.to_datetime([row[0] for row in prices], unit="ms").tz_localize(None).normalize()
        vals = [float(row[1]) for row in prices]
        serie = pd.Series(vals, index=pd.DatetimeIndex(idx)).sort_index()
        if serie.index.has_duplicates:
            serie = serie.groupby(serie.index).last()
        return serie
    except Exception:
        return pd.Series(dtype=float)


def _get_json(path: str, params: dict | None = None) -> dict | list:
    url = f"{_cg_base()}{path}"
    headers = _cg_headers()
    last_status = None
    for attempt in range(_CG_RETRIES):
        try:
            resp = requests.get(url, params=params, headers=headers, timeout=_TIMEOUT)
        except Exception as exc:
            raise CryptoFetchError(f"CoinGecko indisponível: {exc}") from exc
        last_status = resp.status_code
        if resp.status_code == 429:
            if attempt + 1 < _CG_RETRIES:
                time.sleep(_CG_RETRY_SLEEP_S)
                continue
            dica = (
                "Crie uma Demo key gratuita em https://www.coingecko.com/en/api "
                "e exporte COINGECKO_API_KEY=... (COINGECKO_API_PLAN=demo)."
            )
            raise CryptoFetchError(f"CoinGecko rate limit (429). {dica}")
        if resp.status_code != 200:
            raise CryptoFetchError(f"CoinGecko HTTP {resp.status_code}")
        try:
            return resp.json()
        except Exception as exc:
            raise CryptoFetchError("CoinGecko payload inválido") from exc
    raise CryptoFetchError(f"CoinGecko HTTP {last_status}")


def resolve_coin_id(ticker: str) -> tuple[str, str, str]:
    """Resolve id CoinGecko via /search (só enrichment; requer key)."""
    query = _normalize_query(ticker)
    if not query:
        raise CryptoFetchError(f"{ticker} — ticker não disponível na API.")
    payload = _get_json("/search", params={"query": query})
    coins = payload.get("coins") if isinstance(payload, dict) else None
    if not coins:
        raise CryptoFetchError(f"{ticker} — ticker não disponível na API.")

    q_lower = query.lower()
    symbol_hits = [
        c for c in coins
        if str(c.get("symbol", "")).lower() == q_lower
    ]
    if symbol_hits:
        def rank_key(c):
            r = c.get("market_cap_rank")
            return r if isinstance(r, int) else 10**9
        best = min(symbol_hits, key=rank_key)
        return str(best["id"]), str(best.get("symbol", query)), str(best.get("name", query))

    for c in coins:
        if str(c.get("id", "")).lower() == q_lower:
            return str(c["id"]), str(c.get("symbol", query)), str(c.get("name", query))

    raise CryptoFetchError(f"{ticker} — ticker não disponível na API.")


def _usd_field(md: dict, key: str) -> float | None:
    val = md.get(key)
    if isinstance(val, dict):
        raw = val.get("usd")
    else:
        raw = val
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _fetch_history(ticker: str, periodo: str = "1y") -> pd.Series:
    """Peer de usd._fetch_history (usd.py:157-164) — duplicado de propósito."""
    try:
        fechamentos = yf.Ticker(ticker).history(period=periodo)["Close"].dropna()
        fechamentos.index = pd.to_datetime(fechamentos.index).tz_localize(None).normalize()
        if fechamentos.index.has_duplicates:
            fechamentos = fechamentos.groupby(fechamentos.index).last()
        return fechamentos
    except Exception:
        return pd.Series(dtype=float)


def _pct_change(hist: pd.Series, dias: int) -> float | None:
    if hist.empty or len(hist) < 2:
        return None
    try:
        alvo = hist.index[-1] - pd.Timedelta(days=dias)
        base = hist.loc[hist.index <= alvo]
        if base.empty:
            return None
        antigo = float(base.iloc[-1])
        atual = float(hist.iloc[-1])
        if antigo == 0:
            return None
        return round((atual / antigo - 1.0) * 100.0, 2)
    except Exception:
        return None


def _float_info(info: dict, *keys: str) -> float | None:
    for key in keys:
        raw = info.get(key)
        if raw is None:
            continue
        try:
            val = float(raw)
        except (TypeError, ValueError):
            continue
        # Yahoo usa 0 como “sem max supply” em alguns coins
        if key in ("maxSupply",) and val <= 0:
            continue
        return val
    return None


def _fetch_yf_meta(yf_ticker: str) -> dict:
    """Spot + metadados Yahoo (ATH/mcap/supply/vol). Rejeita ETF via quoteType."""
    try:
        info = yf.Ticker(yf_ticker).info or {}
    except Exception:
        return {}
    qtype = (info.get("quoteType") or "").upper()
    nome = info.get("shortName") or info.get("longName")
    preco = _float_info(info, "currentPrice", "regularMarketPrice", "previousClose")
    ath = _float_info(info, "allTimeHigh", "ath")
    ath_change_pct = None
    if ath is not None and preco is not None and ath > 0:
        ath_change_pct = round((preco / ath - 1.0) * 100.0, 2)
    return {
        "cotacao": preco,
        "nome": nome,
        "quoteType": qtype,
        "ath": ath,
        "ath_change_pct": ath_change_pct,
        "mcap": _float_info(info, "marketCap"),
        "volume_24h": _float_info(info, "volume24Hr", "volume", "regularMarketVolume"),
        "circ_supply": _float_info(info, "circulatingSupply", "totalSupply"),
        "max_supply": _float_info(info, "maxSupply"),
    }


def _enrich_coingecko(ticker: str) -> dict:
    """Enrichment opcional; falha soft → dict parcial/vazio (nunca derruba YF)."""
    out: dict = {}
    if not _cg_enabled():
        return out
    try:
        coin_id, _sym, name = resolve_coin_id(ticker)
        out["id"] = coin_id
        out["name"] = name
        coin = _get_json(
            f"/coins/{coin_id}",
            params={
                "localization": "false",
                "tickers": "false",
                "community_data": "false",
                "developer_data": "false",
                "sparkline": "false",
            },
        )
        if not isinstance(coin, dict):
            return out
        md = coin.get("market_data") or {}
        out["ath"] = _usd_field(md, "ath")
        out["ath_change_pct"] = _usd_field(md, "ath_change_percentage")
        out["mcap"] = _usd_field(md, "market_cap")
        out["volume_24h"] = _usd_field(md, "total_volume")
        circ = md.get("circulating_supply")
        max_s = md.get("max_supply")
        try:
            out["circ_supply"] = float(circ) if circ is not None else None
        except (TypeError, ValueError):
            out["circ_supply"] = None
        try:
            out["max_supply"] = float(max_s) if max_s is not None else None
        except (TypeError, ValueError):
            out["max_supply"] = None
        rank = coin.get("market_cap_rank")
        try:
            out["rank"] = int(rank) if rank is not None else None
        except (TypeError, ValueError):
            out["rank"] = None
        try:
            payload = _get_json("/global")
            pct = ((payload.get("data") or {}).get("market_cap_percentage") or {}).get("btc")
            out["btc_dominance_pct"] = float(pct) if pct is not None else None
        except (CryptoFetchError, TypeError, ValueError):
            out["btc_dominance_pct"] = None
    except CryptoFetchError:
        return out
    return out


def fetch_crypto(ticker: str) -> CryptoData:
    symbol = _normalize_query(ticker)
    if not symbol:
        raise CryptoFetchError(f"{ticker} — ticker não disponível na API.")

    yf_ticker = _yf_symbol(ticker)
    price_hist = _fetch_history(yf_ticker, periodo="1y")
    meta = _fetch_yf_meta(yf_ticker)
    cotacao = meta.get("cotacao")
    qtype = meta.get("quoteType") or ""

    if qtype and qtype not in ("CRYPTOCURRENCY", "CRYPTO", ""):
        # Defesa: se Yahoo devolver ETF/equity no par -USD, rejeita
        if qtype in ("ETF", "EQUITY", "MUTUALFUND"):
            raise CryptoFetchError(
                f"{ticker} — ticker não disponível na API (Yahoo {yf_ticker} é {qtype}, não crypto spot)."
            )

    if cotacao is None and not price_hist.empty:
        cotacao = float(price_hist.iloc[-1])
    if price_hist.empty or cotacao is None:
        raise CryptoFetchError(f"{ticker} — ticker não disponível na API.")

    low_52 = float(price_hist.min())
    high_52 = float(price_hist.max())
    margem_52 = None
    if high_52 > low_52:
        margem_52 = round((cotacao - low_52) / (high_52 - low_52), 4)

    # id canônico mínimo p/ skip vs_btc; enrichment CG pode sobrescrever
    coin_id = "bitcoin" if symbol == "BTC" else symbol.lower()
    name = meta.get("nome") or symbol

    if symbol == "BTC":
        btc_hist = pd.Series(dtype=float)
    else:
        btc_hist = _fetch_history("BTC-USD", periodo="1y")

    dxy_hist = _fetch_history(_DXY, periodo="1y")
    gold_hist = _fetch_history(_GOLD, periodo="1y")
    dxy = float(dxy_hist.iloc[-1]) if not dxy_hist.empty else None
    gold = float(gold_hist.iloc[-1]) if not gold_hist.empty else None

    # YF já cobre ATH/mcap/supply/vol; CG (se key) sobrescreve / completa rank+dominance
    ath = meta.get("ath")
    ath_change_pct = meta.get("ath_change_pct")
    mcap = meta.get("mcap")
    volume_24h = meta.get("volume_24h")
    circ_supply = meta.get("circ_supply")
    max_supply = meta.get("max_supply")
    rank = None
    btc_dominance_pct = None
    source = _SOURCE_YF

    enrich = _enrich_coingecko(ticker)
    if enrich:
        source = _SOURCE_HYBRID
        if enrich.get("id"):
            coin_id = str(enrich["id"])
        if enrich.get("name"):
            name = str(enrich["name"])
        ath = enrich.get("ath", ath)
        ath_change_pct = enrich.get("ath_change_pct", ath_change_pct)
        mcap = enrich.get("mcap", mcap)
        volume_24h = enrich.get("volume_24h", volume_24h)
        circ_supply = enrich.get("circ_supply", circ_supply)
        max_supply = enrich.get("max_supply", max_supply)
        rank = enrich.get("rank")
        btc_dominance_pct = enrich.get("btc_dominance_pct")

    return CryptoData(
        id=coin_id,
        symbol=symbol,
        name=name,
        cotacao=cotacao,
        low_52=low_52,
        high_52=high_52,
        margem_52=margem_52,
        ath=ath,
        ath_change_pct=ath_change_pct,
        mcap=mcap,
        rank=rank,
        circ_supply=circ_supply,
        max_supply=max_supply,
        volume_24h=volume_24h,
        change_30d=_pct_change(price_hist, 30),
        change_1y=_pct_change(price_hist, 365),
        price_hist=price_hist,
        btc_hist=btc_hist,
        btc_dominance_pct=btc_dominance_pct,
        source=source,
        dxy=dxy,
        dxy_hist=dxy_hist,
        gold=gold,
        gold_hist=gold_hist,
    )


def _is_bitcoin(data: CryptoData) -> bool:
    return data.id == "bitcoin" or (data.symbol or "").upper() == "BTC"


def montar_tetos_crypto(data: CryptoData) -> tuple[dict, dict]:
    """Monta tetos crypto. Peer de cli._render_usd:111-129."""
    tetos = {
        "teto_margem": teto_margem(data.cotacao, data.low_52, data.high_52),
        "teto_vs_btc": None,
        "teto_vs_ouro": None,
        "teto_vs_dxy": None,
    }
    r2s = {"r2_btc": None, "r2_ouro": None, "r2_dxy": None}
    if not _is_bitcoin(data) and not data.btc_hist.empty and not data.price_hist.empty:
        tetos["teto_vs_btc"], r2s["r2_btc"] = teto_por_regressao(
            data.btc_hist, data.price_hist, float(data.btc_hist.iloc[-1])
        )
    if data.gold is not None and not data.gold_hist.empty and not data.price_hist.empty:
        tetos["teto_vs_ouro"], r2s["r2_ouro"] = teto_por_regressao(
            data.gold_hist, data.price_hist, data.gold
        )
    if data.dxy is not None and not data.dxy_hist.empty and not data.price_hist.empty:
        tetos["teto_vs_dxy"], r2s["r2_dxy"] = teto_por_regressao(
            data.dxy_hist, data.price_hist, data.dxy
        )
    return tetos, r2s
