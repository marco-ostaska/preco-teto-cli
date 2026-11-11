from datetime import datetime, timezone
from unittest.mock import MagicMock

import pandas as pd
import pytest


def _resposta(payload, status=200):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = payload
    r.text = "ok"
    r.raise_for_status = MagicMock()
    return r


def test_normalize_strips_usd_suffix():
    from preco_teto.services.crypto import _normalize_query, _yf_symbol

    assert _normalize_query("BTC-USD") == "BTC"
    assert _normalize_query("eth/usd") == "ETH"
    assert _normalize_query("BTC") == "BTC"
    assert _yf_symbol("BTC") == "BTC-USD"
    assert _yf_symbol("ETH-USD") == "ETH-USD"


def test_chart_to_series_dedupa_mesmo_dia():
    from preco_teto.services.crypto import _chart_to_series

    day = 1_700_000_000_000
    serie = _chart_to_series([[day, 100.0], [day + 3_600_000, 110.0], [day + 86_400_000, 120.0]])
    assert not serie.index.has_duplicates
    assert len(serie) == 2
    assert float(serie.iloc[0]) == 110.0


def test_resolve_coin_id_match_exato_por_symbol(monkeypatch):
    from preco_teto.services import crypto

    payload = {
        "coins": [
            {"id": "bitcoin-pro", "symbol": "BTCP", "name": "Bitcoin Pro", "market_cap_rank": 1400},
            {"id": "bitcoin", "symbol": "BTC", "name": "Bitcoin", "market_cap_rank": 1},
            {"id": "wrapped-btc", "symbol": "BTC", "name": "Wrapped", "market_cap_rank": 50},
        ]
    }
    monkeypatch.setattr(
        crypto.requests,
        "get",
        lambda url, params=None, headers=None, timeout=30: _resposta(payload),
    )

    coin_id, symbol, name = crypto.resolve_coin_id("BTC")
    assert coin_id == "bitcoin"
    assert symbol.upper() == "BTC"
    assert name == "Bitcoin"


def test_resolve_coin_id_sem_match_levanta(monkeypatch):
    from preco_teto.services import crypto

    monkeypatch.setattr(
        crypto.requests,
        "get",
        lambda url, params=None, headers=None, timeout=30: _resposta({"coins": []}),
    )
    with pytest.raises(crypto.CryptoFetchError, match="não disponível"):
        crypto.resolve_coin_id("XYZZZ")


def _hist(n=40, start=80.0):
    idx = pd.bdate_range("2025-01-01", periods=n)
    return pd.Series([start + i for i in range(n)], index=idx, dtype=float)


def _patch_yf(monkeypatch, crypto_mod, symbols=None, empty_drivers=False):
    symbols = symbols or {}

    def fake_hist(ticker, periodo="1y"):
        if empty_drivers and ticker in ("DX-Y.NYB", "GC=F"):
            return pd.Series(dtype=float)
        if ticker in symbols:
            return symbols[ticker]
        if ticker.endswith("-USD"):
            return _hist()
        if ticker == "DX-Y.NYB":
            return _hist(start=100.0)
        if ticker == "GC=F":
            return _hist(start=2000.0)
        return pd.Series(dtype=float)

    def fake_meta(yf_ticker):
        if not yf_ticker.endswith("-USD"):
            return {}
        hist = symbols.get(yf_ticker, _hist())
        spot = float(hist.iloc[-1])
        return {
            "cotacao": spot,
            "nome": yf_ticker.replace("-USD", ""),
            "quoteType": "CRYPTOCURRENCY",
            "ath": spot * 1.5,
            "ath_change_pct": -33.33,
            "mcap": 1e12,
            "volume_24h": 1e9,
            "circ_supply": 19e6,
            "max_supply": 21e6,
        }

    monkeypatch.setattr(crypto_mod, "_fetch_history", fake_hist)
    monkeypatch.setattr(crypto_mod, "_fetch_yf_meta", fake_meta)
    monkeypatch.setattr(
        crypto_mod,
        "fetch_onchain",
        lambda gecko_id, symbol: {
            "onchain_kind": None,
            "tvl": None,
            "fees_30d": None,
            "fees_annualized": None,
            "rwa_tvl": None,
            "dex_vol_24h": None,
            "tvl_hist": pd.Series(dtype=float),
            "fees_hist": pd.Series(dtype=float),
        },
    )
    monkeypatch.delenv("COINGECKO_API_KEY", raising=False)


def test_fetch_crypto_yf_monta_spot_e_52w(monkeypatch):
    from preco_teto.services import crypto

    _patch_yf(monkeypatch, crypto)
    data = crypto.fetch_crypto("BTC")

    assert data.symbol == "BTC"
    assert data.id == "bitcoin"
    assert data.cotacao == pytest.approx(119.0)
    assert data.low_52 == pytest.approx(80.0)
    assert data.high_52 == pytest.approx(119.0)
    assert data.margem_52 is not None
    assert data.btc_hist.empty
    assert data.source == "Yahoo Finance"
    assert data.ath == pytest.approx(119.0 * 1.5)
    assert data.mcap == pytest.approx(1e12)
    assert data.volume_24h == pytest.approx(1e9)
    assert data.circ_supply == pytest.approx(19e6)
    assert data.max_supply == pytest.approx(21e6)


def test_fetch_crypto_alt_preenche_btc_hist_yf(monkeypatch):
    from preco_teto.services import crypto

    eth = _hist(start=2000.0)
    btc = _hist(start=90.0)
    _patch_yf(monkeypatch, crypto, symbols={"ETH-USD": eth, "BTC-USD": btc})
    data = crypto.fetch_crypto("ETH")

    assert data.id == "eth"
    assert not data.btc_hist.empty
    assert data.btc_hist.iloc[0] == pytest.approx(90.0)


def test_fetch_crypto_ticker_ausente_levanta(monkeypatch):
    from preco_teto.services import crypto

    monkeypatch.setattr(crypto, "_fetch_history", lambda *a, **k: pd.Series(dtype=float))
    monkeypatch.setattr(crypto, "_fetch_yf_meta", lambda *a, **k: {})
    monkeypatch.delenv("COINGECKO_API_KEY", raising=False)

    with pytest.raises(crypto.CryptoFetchError, match="não disponível"):
        crypto.fetch_crypto("XYZZZ")


def test_fetch_crypto_rejeita_etf_yahoo(monkeypatch):
    from preco_teto.services import crypto

    monkeypatch.setattr(crypto, "_fetch_history", lambda *a, **k: _hist())
    monkeypatch.setattr(
        crypto,
        "_fetch_yf_meta",
        lambda *a, **k: {"cotacao": 33.0, "nome": "Grayscale", "quoteType": "ETF"},
    )
    monkeypatch.delenv("COINGECKO_API_KEY", raising=False)

    with pytest.raises(crypto.CryptoFetchError, match="ETF"):
        crypto.fetch_crypto("BTC")


def test_fetch_crypto_429_nao_explode(monkeypatch):
    from preco_teto.services import crypto

    monkeypatch.setattr(crypto, "_CG_RETRY_SLEEP_S", 0)
    monkeypatch.setattr(
        crypto.requests,
        "get",
        lambda url, params=None, headers=None, timeout=30: _resposta({}, status=429),
    )
    with pytest.raises(crypto.CryptoFetchError, match="429"):
        crypto.resolve_coin_id("BTC")


def test_cg_headers_demo_e_pro(monkeypatch):
    from preco_teto.services import crypto

    monkeypatch.delenv("COINGECKO_API_KEY", raising=False)
    assert crypto._cg_headers() == {}
    assert crypto._cg_base() == crypto._CG_BASE_DEMO
    assert crypto._cg_enabled() is False

    monkeypatch.setenv("COINGECKO_API_KEY", "k1")
    monkeypatch.setenv("COINGECKO_API_PLAN", "demo")
    assert crypto._cg_headers() == {"x-cg-demo-api-key": "k1"}
    assert crypto._cg_enabled() is True

    monkeypatch.setenv("COINGECKO_API_PLAN", "pro")
    assert crypto._cg_headers() == {"x-cg-pro-api-key": "k1"}
    assert crypto._cg_base() == crypto._CG_BASE_PRO


def test_get_json_retry_em_429_depois_sucesso(monkeypatch):
    from preco_teto.services import crypto

    monkeypatch.setattr(crypto, "_CG_RETRY_SLEEP_S", 0)
    calls = {"n": 0}

    def fake_get(url, params=None, headers=None, timeout=30):
        calls["n"] += 1
        if calls["n"] < 2:
            return _resposta({}, status=429)
        return _resposta({"coins": []})

    monkeypatch.setattr(crypto.requests, "get", fake_get)
    assert crypto._get_json("/search", params={"query": "BTC"}) == {"coins": []}
    assert calls["n"] == 2


def test_fetch_crypto_sem_key_nao_chama_coingecko(monkeypatch):
    from preco_teto.services import crypto

    _patch_yf(monkeypatch, crypto)
    called = {"cg": False}

    def boom(*a, **k):
        called["cg"] = True
        raise AssertionError("CG não deveria ser chamado sem key")

    monkeypatch.setattr(crypto, "_get_json", boom)
    data = crypto.fetch_crypto("BTC")
    assert data.source == "Yahoo Finance"
    assert called["cg"] is False


def test_fetch_crypto_com_key_enriquece_ath(monkeypatch):
    from preco_teto.services import crypto

    _patch_yf(monkeypatch, crypto)
    monkeypatch.setenv("COINGECKO_API_KEY", "k1")
    monkeypatch.setenv("COINGECKO_API_PLAN", "demo")

    def fake_get(url, params=None, headers=None, timeout=30):
        if "/search" in url:
            return _resposta({
                "coins": [{"id": "bitcoin", "symbol": "BTC", "name": "Bitcoin", "market_cap_rank": 1}]
            })
        if "/coins/bitcoin" in url:
            return _resposta({
                "id": "bitcoin",
                "market_cap_rank": 1,
                "market_data": {
                    "ath": {"usd": 126000.0},
                    "ath_change_percentage": {"usd": -40.0},
                    "market_cap": {"usd": 1e12},
                    "total_volume": {"usd": 1e9},
                    "circulating_supply": 19e6,
                    "max_supply": 21e6,
                },
            })
        if url.endswith("/global"):
            return _resposta({"data": {"market_cap_percentage": {"btc": 55.0}}})
        return _resposta({})

    monkeypatch.setattr(crypto.requests, "get", fake_get)
    data = crypto.fetch_crypto("BTC")
    assert data.ath == pytest.approx(126000.0)
    assert data.mcap == pytest.approx(1e12)
    assert data.btc_dominance_pct == pytest.approx(55.0)
    assert data.source == "Yahoo Finance + CoinGecko"


def test_fetch_crypto_cg_falha_nao_derruba_yf(monkeypatch):
    from preco_teto.services import crypto

    _patch_yf(monkeypatch, crypto)
    monkeypatch.setenv("COINGECKO_API_KEY", "k1")
    monkeypatch.setattr(crypto, "_CG_RETRY_SLEEP_S", 0)
    monkeypatch.setattr(
        crypto.requests,
        "get",
        lambda *a, **k: _resposta({}, status=429),
    )
    data = crypto.fetch_crypto("BTC")
    assert data.cotacao is not None
    assert data.ath is not None  # YF cobre ATH mesmo se CG falhar
    assert data.source == "Yahoo Finance"


def test_fetch_crypto_anexa_dxy_e_ouro(monkeypatch):
    from preco_teto.services import crypto

    _patch_yf(monkeypatch, crypto)
    data = crypto.fetch_crypto("BTC")
    assert data.dxy == pytest.approx(139.0)
    assert data.gold == pytest.approx(2039.0)


def test_fetch_crypto_driver_vazio_nao_quebra(monkeypatch):
    from preco_teto.services import crypto

    _patch_yf(monkeypatch, crypto, empty_drivers=True)
    data = crypto.fetch_crypto("BTC")
    assert data.cotacao is not None
    assert data.dxy is None
    assert data.gold is None


def test_driver_dxy_reusa_simbolo_peer_usd():
    from preco_teto.services import crypto

    assert crypto._DXY == "DX-Y.NYB"
    assert crypto._GOLD == "GC=F"


def _crypto_data(**overrides):
    idx = pd.bdate_range("2025-01-01", periods=40)
    price = pd.Series([100.0 + i for i in range(40)], index=idx)
    btc = pd.Series([90.0 + i for i in range(40)], index=idx)
    dxy = pd.Series([100.0 + 0.1 * i for i in range(40)], index=idx)
    gold = pd.Series([2000.0 + i for i in range(40)], index=idx)
    base = dict(
        id="ethereum",
        symbol="ETH",
        name="Ethereum",
        cotacao=139.0,
        low_52=100.0,
        high_52=139.0,
        margem_52=1.0,
        ath=200.0,
        ath_change_pct=-30.0,
        mcap=1e9,
        rank=2,
        circ_supply=1e8,
        max_supply=None,
        volume_24h=1e8,
        change_30d=-5.0,
        change_1y=10.0,
        price_hist=price,
        btc_hist=btc,
        btc_dominance_pct=50.0,
        source="Yahoo Finance",
        dxy=float(dxy.iloc[-1]),
        dxy_hist=dxy,
        gold=float(gold.iloc[-1]),
        gold_hist=gold,
    )
    base.update(overrides)
    from preco_teto.services.crypto import CryptoData
    return CryptoData(**base)


def test_montar_tetos_bitcoin_omite_vs_btc():
    from preco_teto.services.crypto import montar_tetos_crypto

    data = _crypto_data(id="bitcoin", symbol="BTC", name="Bitcoin", btc_hist=pd.Series(dtype=float))
    tetos, r2s = montar_tetos_crypto(data)
    assert tetos["teto_vs_btc"] is None
    assert r2s["r2_btc"] is None
    assert tetos["teto_margem"] is not None


def test_montar_tetos_alt_inclui_vs_btc():
    from preco_teto.services.crypto import montar_tetos_crypto

    idx = pd.bdate_range("2025-01-01", periods=40)
    btc = pd.Series([100.0 + i for i in range(40)], index=idx)
    price = btc * 0.05
    data = _crypto_data(price_hist=price, btc_hist=btc, cotacao=float(price.iloc[-1]))
    tetos, r2s = montar_tetos_crypto(data)
    assert tetos["teto_vs_btc"] is not None
    assert r2s["r2_btc"] == pytest.approx(1.0, abs=1e-6)


def test_montar_tetos_driver_vazio_none():
    from preco_teto.services.crypto import montar_tetos_crypto

    data = _crypto_data(
        dxy=None,
        dxy_hist=pd.Series(dtype=float),
        gold=None,
        gold_hist=pd.Series(dtype=float),
        btc_hist=pd.Series(dtype=float),
    )
    tetos, r2s = montar_tetos_crypto(data)
    assert tetos["teto_vs_btc"] is None
    assert tetos["teto_vs_ouro"] is None
    assert tetos["teto_vs_dxy"] is None


def test_fetch_crypto_anexa_onchain(monkeypatch):
    from preco_teto.services import crypto

    _patch_yf(monkeypatch, crypto)
    idx = pd.bdate_range("2025-01-01", periods=20)
    monkeypatch.setattr(
        crypto,
        "fetch_onchain",
        lambda gecko_id, symbol: {
            "onchain_kind": "chain",
            "tvl": 50e9,
            "fees_30d": 1e8,
            "fees_annualized": 1.2e9,
            "rwa_tvl": 2e9,
            "dex_vol_24h": 3e9,
            "tvl_hist": pd.Series([40e9 + i * 1e8 for i in range(20)], index=idx),
            "fees_hist": pd.Series([1e9 + i * 1e6 for i in range(20)], index=idx),
        },
    )
    data = crypto.fetch_crypto("ETH")
    assert data.onchain_kind == "chain"
    assert data.tvl == pytest.approx(50e9)
    assert data.fees_30d == pytest.approx(1e8)
    assert data.rwa_tvl == pytest.approx(2e9)
    assert data.dex_vol_24h == pytest.approx(3e9)
    assert "DefiLlama" in data.source


def test_fetch_crypto_defillama_falha_nao_derruba_yf(monkeypatch):
    from preco_teto.services import crypto

    _patch_yf(monkeypatch, crypto)
    monkeypatch.setattr(
        crypto,
        "fetch_onchain",
        lambda gecko_id, symbol: (_ for _ in ()).throw(RuntimeError("llama down")),
    )
    data = crypto.fetch_crypto("BTC")
    assert data.cotacao is not None
    assert data.tvl is None
    assert "DefiLlama" not in data.source


def test_montar_tetos_inclui_fees_e_tvl():
    from preco_teto.services.crypto import montar_tetos_crypto

    idx = pd.bdate_range("2025-01-01", periods=20)
    circ = 1_000_000.0
    fees = pd.Series([1e6 + i * 1e3 for i in range(20)], index=idx)
    tvl = pd.Series([10e6 + i * 1e4 for i in range(20)], index=idx)
    # múltiplo mcap/fees = 5 → price = 5 * fees / circ
    price = (5.0 * fees) / circ
    data = _crypto_data(
        price_hist=price,
        cotacao=float(price.iloc[-1]),
        circ_supply=circ,
        fees_hist=fees,
        fees_annualized=float(fees.iloc[-1]),
        tvl_hist=tvl,
        tvl=float(tvl.iloc[-1]),
        btc_hist=pd.Series(dtype=float),
        dxy=None,
        dxy_hist=pd.Series(dtype=float),
        gold=None,
        gold_hist=pd.Series(dtype=float),
    )
    tetos, _ = montar_tetos_crypto(data)
    assert tetos["teto_por_fees"] == pytest.approx(float(price.iloc[-1]), abs=0.05)
    assert tetos["teto_por_tvl"] is not None
