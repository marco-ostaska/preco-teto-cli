from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import requests

_BASE = "https://api.llama.fi"
_TIMEOUT = 30


class DefiLlamaError(Exception):
    pass


@dataclass(frozen=True)
class LlamaEntity:
    kind: str  # "chain" | "protocol"
    slug: str
    gecko_id: str | None = None
    symbol: str | None = None


def _get_json(path: str, params: dict | None = None) -> dict | list:
    url = f"{_BASE}{path}"
    try:
        resp = requests.get(url, params=params, timeout=_TIMEOUT)
    except Exception as exc:
        raise DefiLlamaError(f"DefiLlama indisponível: {exc}") from exc
    if resp.status_code != 200:
        raise DefiLlamaError(f"DefiLlama HTTP {resp.status_code}")
    try:
        return resp.json()
    except Exception as exc:
        raise DefiLlamaError("DefiLlama payload inválido") from exc


def _empty_enrichment() -> dict:
    return {
        "onchain_kind": None,
        "tvl": None,
        "fees_30d": None,
        "fees_annualized": None,
        "rwa_tvl": None,
        "dex_vol_24h": None,
        "tvl_hist": pd.Series(dtype=float),
        "fees_hist": pd.Series(dtype=float),
    }


def _chart_to_series(rows: list | None, value_key: str | None = None) -> pd.Series:
    """Aceita [[ts, val], ...] ou [{date, tvl|totalLiquidityUSD}, ...]."""
    if not rows:
        return pd.Series(dtype=float)
    try:
        dates: list = []
        vals: list[float] = []
        for row in rows:
            if isinstance(row, (list, tuple)) and len(row) >= 2:
                dates.append(row[0])
                vals.append(float(row[1]))
            elif isinstance(row, dict):
                ts = row.get("date")
                if value_key and value_key in row:
                    raw = row[value_key]
                else:
                    raw = row.get("tvl", row.get("totalLiquidityUSD"))
                if ts is None or raw is None:
                    continue
                dates.append(ts)
                vals.append(float(raw))
        if not dates:
            return pd.Series(dtype=float)
        idx = pd.to_datetime(dates, unit="s").tz_localize(None).normalize()
        serie = pd.Series(vals, index=pd.DatetimeIndex(idx)).sort_index()
        if serie.index.has_duplicates:
            serie = serie.groupby(serie.index).last()
        return serie
    except Exception:
        return pd.Series(dtype=float)


def annualize_fees_series(daily: pd.Series) -> pd.Series:
    """Rolling 30d sum × 12 a partir de fees diárias."""
    if daily is None or daily.empty:
        return pd.Series(dtype=float)
    s = daily.astype(float).sort_index()
    rolling = s.rolling(window=30, min_periods=min(7, len(s))).sum() * 12.0
    return rolling.dropna()


def sum_rwa_tvl(protocols: list, chain_name: str) -> float | None:
    total = 0.0
    found = False
    chain_l = chain_name.lower()
    for p in protocols or []:
        if not isinstance(p, dict):
            continue
        cat = str(p.get("category") or "").lower()
        if "rwa" not in cat and "real world asset" not in cat:
            continue
        chains = p.get("chains") or []
        if not any(str(c).lower() == chain_l for c in chains):
            continue
        try:
            tvl = float(p.get("tvl") or 0.0)
        except (TypeError, ValueError):
            continue
        total += tvl
        found = True
    return total if found else None


def _chain_entity(chain: dict, sym: str | None) -> LlamaEntity | None:
    name = str(chain.get("name") or "").strip()
    if not name:
        return None
    return LlamaEntity(
        kind="chain",
        slug=name,
        gecko_id=str(chain.get("gecko_id") or "") or None,
        symbol=sym or (str(chain.get("tokenSymbol") or "").upper() or None),
    )


def resolve_entity(gecko_id: str | None, symbol: str | None) -> LlamaEntity | None:
    gid = (gecko_id or "").strip().lower() or None
    sym = (symbol or "").strip().upper() or None
    if not gid and not sym:
        return None

    try:
        chains = _get_json("/v2/chains")
    except DefiLlamaError:
        chains = []
    if not isinstance(chains, list):
        chains = []

    # 1) chain por gecko_id canônico (ex.: ethereum)
    if gid:
        for c in chains:
            if not isinstance(c, dict):
                continue
            if str(c.get("gecko_id") or "").lower() == gid:
                ent = _chain_entity(c, sym)
                if ent:
                    return ent
            if str(c.get("gasTokenGeckoId") or "").lower() == gid:
                # gas token da chain (ETH em Base/Arbitrum) — preferir a chain
                # cujo gecko_id == gid; se só gasToken bate, continua e tenta tokenSymbol
                pass

    # 2) chain por tokenSymbol nativo (ex.: ETH → Ethereum) — antes de protocol
    if sym:
        for c in chains:
            if not isinstance(c, dict):
                continue
            if str(c.get("tokenSymbol") or "").upper() == sym:
                ent = _chain_entity(c, sym)
                if ent:
                    return ent

    try:
        protocols = _get_json("/protocols")
    except DefiLlamaError:
        protocols = []
    if not isinstance(protocols, list):
        return None

    if gid:
        for p in protocols:
            if not isinstance(p, dict):
                continue
            if str(p.get("gecko_id") or "").lower() == gid:
                slug = str(p.get("slug") or p.get("name") or "").strip()
                if slug:
                    return LlamaEntity(
                        kind="protocol",
                        slug=slug,
                        gecko_id=gid,
                        symbol=str(p.get("symbol") or sym or "").upper() or None,
                    )

    if sym:
        hits = [
            p for p in protocols
            if isinstance(p, dict) and str(p.get("symbol") or "").upper() == sym
        ]
        if hits:
            # prefer higher TVL when multiple symbols collide
            def tvl_key(p: dict) -> float:
                try:
                    return float(p.get("tvl") or 0.0)
                except (TypeError, ValueError):
                    return 0.0

            best = max(hits, key=tvl_key)
            slug = str(best.get("slug") or best.get("name") or "").strip()
            if slug:
                return LlamaEntity(
                    kind="protocol",
                    slug=slug,
                    gecko_id=str(best.get("gecko_id") or "") or None,
                    symbol=sym,
                )
    return None


def _fees_from_payload(payload: dict) -> tuple[float | None, float | None, pd.Series]:
    """Devolve (fees_30d, fees_annualized_atual, fees_hist anualizado)."""
    daily = _chart_to_series(payload.get("totalDataChart"))
    fees_hist = annualize_fees_series(daily)
    fees_30d = None
    raw_30 = payload.get("total30d")
    try:
        if raw_30 is not None:
            fees_30d = float(raw_30)
    except (TypeError, ValueError):
        fees_30d = None
    if fees_30d is None and not daily.empty and len(daily) >= 7:
        fees_30d = float(daily.tail(30).sum())
    fees_ann = None
    # Chart curto: preferir total30d×12 (peer do plano).
    if fees_30d is not None and fees_30d > 0 and (daily.empty or len(daily) < 30):
        fees_ann = fees_30d * 12.0
    elif not fees_hist.empty:
        fees_ann = float(fees_hist.iloc[-1])
    elif fees_30d is not None and fees_30d > 0:
        fees_ann = fees_30d * 12.0
    return fees_30d, fees_ann, fees_hist


def _fetch_chain(entity: LlamaEntity) -> dict:
    out = _empty_enrichment()
    out["onchain_kind"] = "chain"
    chain = entity.slug

    try:
        tvl_rows = _get_json(f"/v2/historicalChainTvl/{chain}")
        tvl_hist = _chart_to_series(tvl_rows if isinstance(tvl_rows, list) else None)
        out["tvl_hist"] = tvl_hist
        if not tvl_hist.empty:
            out["tvl"] = float(tvl_hist.iloc[-1])
    except DefiLlamaError:
        pass

    try:
        fees_payload = _get_json(
            f"/overview/fees/{chain}",
            params={"dataType": "dailyFees"},
        )
        if isinstance(fees_payload, dict):
            fees_30d, fees_ann, fees_hist = _fees_from_payload(fees_payload)
            out["fees_30d"] = fees_30d
            out["fees_annualized"] = fees_ann
            out["fees_hist"] = fees_hist
    except DefiLlamaError:
        pass

    try:
        dexs = _get_json(f"/overview/dexs/{chain}")
        if isinstance(dexs, dict):
            vol = dexs.get("total24h")
            out["dex_vol_24h"] = float(vol) if vol is not None else None
    except (DefiLlamaError, TypeError, ValueError):
        pass

    try:
        protocols = _get_json("/protocols")
        if isinstance(protocols, list):
            out["rwa_tvl"] = sum_rwa_tvl(protocols, chain)
    except DefiLlamaError:
        pass

    return out


def _fetch_protocol(entity: LlamaEntity) -> dict:
    out = _empty_enrichment()
    out["onchain_kind"] = "protocol"
    slug = entity.slug

    try:
        proto = _get_json(f"/protocol/{slug}")
        if isinstance(proto, dict):
            tvl_hist = _chart_to_series(proto.get("tvl"))
            out["tvl_hist"] = tvl_hist
            if not tvl_hist.empty:
                out["tvl"] = float(tvl_hist.iloc[-1])
            elif proto.get("currentChainTvls"):
                try:
                    out["tvl"] = float(sum(float(v) for v in proto["currentChainTvls"].values()))
                except (TypeError, ValueError):
                    pass
    except DefiLlamaError:
        pass

    try:
        fees_payload = _get_json(
            f"/summary/fees/{slug}",
            params={"dataType": "dailyFees"},
        )
        if isinstance(fees_payload, dict):
            fees_30d, fees_ann, fees_hist = _fees_from_payload(fees_payload)
            out["fees_30d"] = fees_30d
            out["fees_annualized"] = fees_ann
            out["fees_hist"] = fees_hist
    except DefiLlamaError:
        pass

    return out


def fetch_onchain(gecko_id: str | None, symbol: str | None) -> dict:
    """Enrichment soft-fail: nunca propaga erro para o caller."""
    try:
        entity = resolve_entity(gecko_id, symbol)
    except Exception:
        return _empty_enrichment()
    if entity is None:
        return _empty_enrichment()
    try:
        if entity.kind == "chain":
            return _fetch_chain(entity)
        return _fetch_protocol(entity)
    except Exception:
        return _empty_enrichment()
