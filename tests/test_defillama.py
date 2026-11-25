from __future__ import annotations

import pandas as pd
import pytest


def test_resolve_prefers_chain_by_gecko_id(monkeypatch):
    from preco_teto.services import defillama as dl

    monkeypatch.setattr(
        dl,
        "_get_json",
        lambda path, params=None: (
            [{"name": "Ethereum", "gecko_id": "ethereum", "tokenSymbol": "ETH", "tvl": 50e9}]
            if path == "/v2/chains"
            else []
        ),
    )
    ent = dl.resolve_entity("ethereum", "ETH")
    assert ent is not None
    assert ent.kind == "chain"
    assert ent.slug == "Ethereum"


def test_resolve_chain_by_token_symbol_before_protocol(monkeypatch):
    """Sem CG id canônico (eth), ETH deve ir pra chain Ethereum — não ethereum-foundation."""
    from preco_teto.services import defillama as dl

    def fake_get(path, params=None):
        if path == "/v2/chains":
            return [
                {
                    "name": "Ethereum",
                    "gecko_id": "ethereum",
                    "tokenSymbol": "ETH",
                    "tvl": 50e9,
                }
            ]
        if path == "/protocols":
            return [
                {
                    "name": "Ethereum Foundation",
                    "slug": "ethereum-foundation",
                    "symbol": "ETH",
                    "gecko_id": "ethereum",
                    "category": "Services",
                    "tvl": None,
                    "chains": ["Ethereum"],
                }
            ]
        return None

    monkeypatch.setattr(dl, "_get_json", fake_get)
    ent = dl.resolve_entity("eth", "ETH")
    assert ent is not None
    assert ent.kind == "chain"
    assert ent.slug == "Ethereum"


def test_resolve_falls_back_to_protocol(monkeypatch):
    from preco_teto.services import defillama as dl

    def fake_get(path, params=None):
        if path == "/v2/chains":
            return []
        if path == "/protocols":
            return [
                {
                    "name": "Aave",
                    "slug": "aave",
                    "symbol": "AAVE",
                    "gecko_id": "aave",
                    "category": "Lending",
                    "tvl": 10e9,
                    "chains": ["Ethereum"],
                }
            ]
        return None

    monkeypatch.setattr(dl, "_get_json", fake_get)
    ent = dl.resolve_entity("aave", "AAVE")
    assert ent is not None
    assert ent.kind == "protocol"
    assert ent.slug == "aave"


def test_resolve_sem_match_retorna_none(monkeypatch):
    from preco_teto.services import defillama as dl

    monkeypatch.setattr(dl, "_get_json", lambda path, params=None: [])
    assert dl.resolve_entity("unknown-coin", "XYZ") is None


def test_fetch_enrichment_soft_fail_http(monkeypatch):
    from preco_teto.services import defillama as dl

    def boom(path, params=None):
        raise dl.DefiLlamaError("down")

    monkeypatch.setattr(dl, "_get_json", boom)
    out = dl.fetch_onchain("ethereum", "ETH")
    assert out["tvl"] is None
    assert out["fees_30d"] is None
    assert out["rwa_tvl"] is None
    assert out["dex_vol_24h"] is None
    assert out["tvl_hist"].empty
    assert out["fees_hist"].empty
    assert out["onchain_kind"] is None


def test_rwa_sum_filter_by_chain(monkeypatch):
    from preco_teto.services import defillama as dl

    protocols = [
        {
            "name": "RWA A",
            "slug": "rwa-a",
            "category": "RWA",
            "tvl": 100.0,
            "chains": ["Ethereum"],
        },
        {
            "name": "RWA B",
            "slug": "rwa-b",
            "category": "Real World Assets",
            "tvl": 50.0,
            "chains": ["Ethereum", "Polygon"],
        },
        {
            "name": "Other",
            "slug": "other",
            "category": "Lending",
            "tvl": 999.0,
            "chains": ["Ethereum"],
        },
        {
            "name": "RWA Sol",
            "slug": "rwa-sol",
            "category": "RWA",
            "tvl": 70.0,
            "chains": ["Solana"],
        },
    ]
    assert dl.sum_rwa_tvl(protocols, "Ethereum") == pytest.approx(150.0)


def test_annualize_fees_rolling_30d():
    from preco_teto.services.defillama import annualize_fees_series

    idx = pd.date_range("2025-01-01", periods=40, freq="D")
    daily = pd.Series([10.0] * 40, index=idx)
    ann = annualize_fees_series(daily)
    assert not ann.empty
    # 30d * 10 * 12 = 3600
    assert float(ann.iloc[-1]) == pytest.approx(3600.0)


def test_fetch_chain_enrichment(monkeypatch):
    from preco_teto.services import defillama as dl

    def fake_get(path, params=None):
        if path == "/v2/chains":
            return [{"name": "Ethereum", "gecko_id": "ethereum", "tvl": 50e9}]
        if path == "/protocols":
            return [
                {
                    "name": "RWA Eth",
                    "slug": "rwa-eth",
                    "category": "RWA",
                    "tvl": 1e9,
                    "chains": ["Ethereum"],
                }
            ]
        if path == "/v2/historicalChainTvl/Ethereum":
            return [
                {"date": 1704067200, "tvl": 40e9},
                {"date": 1704153600, "tvl": 41e9},
            ]
        if path == "/overview/fees/Ethereum":
            return {
                "total30d": 300.0,
                "totalDataChart": [
                    [1704067200, 10.0],
                    [1704153600, 11.0],
                ],
            }
        if path == "/overview/dexs/Ethereum":
            return {"total24h": 1.5e9}
        raise AssertionError(path)

    monkeypatch.setattr(dl, "_get_json", fake_get)
    out = dl.fetch_onchain("ethereum", "ETH")
    assert out["onchain_kind"] == "chain"
    assert out["tvl"] == pytest.approx(41e9)
    assert out["fees_30d"] == pytest.approx(300.0)
    assert out["fees_annualized"] == pytest.approx(3600.0)
    assert out["rwa_tvl"] == pytest.approx(1e9)
    assert out["dex_vol_24h"] == pytest.approx(1.5e9)
    assert len(out["tvl_hist"]) == 2
