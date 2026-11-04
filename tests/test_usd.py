from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest


def _resposta(payload):
    r = MagicMock()
    r.status_code = 200
    r.json.return_value = payload
    r.text = "[{}]"
    r.raise_for_status = MagicMock()
    return r


@pytest.fixture
def ptax_serie():
    idx = pd.bdate_range("2025-08-01", periods=300)
    rng = np.random.default_rng(7)
    return pd.Series(5.0 + np.cumsum(rng.normal(0, 0.01, len(idx))), index=idx)


@pytest.fixture
def dxy_serie(ptax_serie):
    rng = np.random.default_rng(11)
    return pd.Series(100 + np.cumsum(rng.normal(0, 0.2, len(ptax_serie))), index=ptax_serie.index)


@pytest.fixture
def ewz_serie(ptax_serie):
    rng = np.random.default_rng(13)
    return pd.Series(32 + np.cumsum(rng.normal(0, 0.15, len(ptax_serie))), index=ptax_serie.index)


@pytest.fixture
def ibov_serie(ptax_serie):
    rng = np.random.default_rng(17)
    return pd.Series(165000 + np.cumsum(rng.normal(0, 400, len(ptax_serie))), index=ptax_serie.index)


def test_fetch_ptax_concatena_anos_e_ordena(monkeypatch):
    from preco_teto.services import usd

    monkeypatch.setattr(usd, "_anos_ptax", lambda anos: [2025, 2026])

    def fake_get(url, timeout=30):
        if "2025" in url:
            return _resposta([{"data": "31/12/2025", "valor": "5,1000"}])
        return _resposta([{"data": "02/01/2026", "valor": "5,2000"}])

    monkeypatch.setattr(usd.requests, "get", fake_get)

    serie = usd.fetch_ptax()

    assert list(serie.round(4)) == [5.1, 5.2]
    assert serie.index.is_monotonic_increasing


def test_fetch_ptax_ignora_ano_sem_dados(monkeypatch):
    from preco_teto.services import usd

    monkeypatch.setattr(usd, "_anos_ptax", lambda anos: [2025, 2026])

    def fake_get(url, timeout=30):
        if "2025" in url:
            r = MagicMock()
            r.status_code = 500
            r.text = "<html>erro</html>"
            return r
        return _resposta([{"data": "02/01/2026", "valor": "5,2000"}])

    monkeypatch.setattr(usd.requests, "get", fake_get)

    serie = usd.fetch_ptax()

    assert list(serie.round(4)) == [5.2]


def test_fetch_ptax_sem_rede_retorna_serie_vazia(monkeypatch):
    from preco_teto.services import usd

    monkeypatch.setattr(usd, "_anos_ptax", lambda anos: [2026])

    def fake_get(url, timeout=30):
        raise ConnectionError("sem rede")

    monkeypatch.setattr(usd.requests, "get", fake_get)

    serie = usd.fetch_ptax()

    assert serie.empty


def test_fetch_cot_real_calcula_net_e_percentil(monkeypatch):
    from preco_teto.services import usd

    payload = [
        {
            "report_date_as_yyyy_mm_dd": "2026-10-20T00:00:00.000",
            "open_interest_all": "100000",
            "lev_money_positions_long": "60000",
            "lev_money_positions_short": "20000",
            "asset_mgr_positions_long": "30000",
            "asset_mgr_positions_short": "10000",
        },
        {
            "report_date_as_yyyy_mm_dd": "2026-10-13T00:00:00.000",
            "open_interest_all": "100000",
            "lev_money_positions_long": "40000",
            "lev_money_positions_short": "20000",
            "asset_mgr_positions_long": "20000",
            "asset_mgr_positions_short": "10000",
        },
    ]
    monkeypatch.setattr(usd.requests, "get", lambda url, params=None, timeout=30: _resposta(payload))

    cot = usd.fetch_cot_real()

    assert cot.data == date(2026, 10, 20)
    assert cot.lev_net_pct == pytest.approx(40.0)
    assert cot.am_net_pct == pytest.approx(20.0)
    assert cot.lev_pctl == pytest.approx(50.0)
    assert cot.serie_am_net.iloc[-1] == pytest.approx(20.0)


def test_fetch_cot_real_sem_dados_retorna_none(monkeypatch):
    from preco_teto.services import usd

    monkeypatch.setattr(usd.requests, "get", lambda url, params=None, timeout=30: _resposta([]))

    assert usd.fetch_cot_real() is None


def test_fetch_cot_real_com_erro_http_retorna_none(monkeypatch):
    from preco_teto.services import usd

    def fake_get(url, params=None, timeout=30):
        raise ConnectionError("cftc fora")

    monkeypatch.setattr(usd.requests, "get", fake_get)

    assert usd.fetch_cot_real() is None


def _fake_quote(ticker):
    return {
        "BRL=X": (5.4645, None),
        "UUP": (29.04, 29.04),
        "UDN": (17.82, 17.81),
    }.get(ticker, (None, None))


def test_fetch_usd_monta_spot_faixa_e_desvio(monkeypatch, ptax_serie, dxy_serie, ewz_serie, ibov_serie):
    from preco_teto.services import usd

    monkeypatch.setattr(usd, "fetch_ptax", lambda anos=3: ptax_serie)
    monkeypatch.setattr(usd, "fetch_cot_real", lambda: SimpleNamespace(
        data=date(2026, 10, 20),
        lev_net_pct=13.8,
        am_net_pct=37.8,
        lev_pctl=81.0,
        am_pctl=48.0,
        serie_lev_net=pd.Series([1.0, 2.0]),
        serie_am_net=pd.Series([1.0, 2.0]),
    ))
    historicos = {"DX-Y.NYB": dxy_serie, "EWZ": ewz_serie, "^BVSP": ibov_serie}
    monkeypatch.setattr(usd, "_fetch_history", lambda ticker, periodo="5y": historicos[ticker])
    monkeypatch.setattr(usd, "_quote", _fake_quote)

    data = usd.fetch_usd()

    assert data.spot == pytest.approx(float(ptax_serie.iloc[-1]))
    assert data.data_spot == ptax_serie.index[-1].date()
    assert data.spot_comercial == pytest.approx(5.4645)
    assert data.spot_ref == pytest.approx(5.4645)
    assert data.low_52 == pytest.approx(float(ptax_serie.tail(252).min()))
    assert data.high_52 == pytest.approx(float(ptax_serie.tail(252).max()))
    assert 0.0 <= data.margem_52 <= 1.0
    assert data.dxy == pytest.approx(float(dxy_serie.iloc[-1]))
    assert 0.0 <= data.dxy_pctl <= 100.0
    assert data.cot.lev_net_pct == pytest.approx(13.8)
    assert data.k_hat is not None
    assert data.desvio_z is not None
    assert data.uup == (29.04, 29.04)
    assert data.udn == (17.82, 17.81)


def test_fetch_usd_sem_comercial_usa_ptax_como_ref(monkeypatch, ptax_serie, dxy_serie, ewz_serie, ibov_serie):
    from preco_teto.services import usd

    monkeypatch.setattr(usd, "fetch_ptax", lambda anos=3: ptax_serie)
    monkeypatch.setattr(usd, "fetch_cot_real", lambda: None)
    historicos = {"DX-Y.NYB": dxy_serie, "EWZ": ewz_serie, "^BVSP": ibov_serie}
    monkeypatch.setattr(usd, "_fetch_history", lambda ticker, periodo="5y": historicos[ticker])
    monkeypatch.setattr(usd, "_quote", lambda ticker: (None, None))

    data = usd.fetch_usd()

    assert data.spot_comercial is None
    assert data.spot_ref == pytest.approx(float(ptax_serie.iloc[-1]))


def test_fetch_usd_sem_ptax_retorna_spot_none(monkeypatch, dxy_serie, ewz_serie, ibov_serie):
    from preco_teto.services import usd

    monkeypatch.setattr(usd, "fetch_ptax", lambda anos=3: pd.Series(dtype=float))
    monkeypatch.setattr(usd, "fetch_cot_real", lambda: None)
    historicos = {"DX-Y.NYB": dxy_serie, "EWZ": ewz_serie, "^BVSP": ibov_serie}
    monkeypatch.setattr(usd, "_fetch_history", lambda ticker, periodo="5y": historicos[ticker])
    monkeypatch.setattr(usd, "_quote", lambda ticker: (None, None))

    data = usd.fetch_usd()

    assert data.spot is None
    assert data.spot_comercial is None
    assert data.spot_ref is None
    assert data.cot is None
    assert data.k_hat is None


def test_fetch_usd_sem_cot_nao_quebra(monkeypatch, ptax_serie, dxy_serie, ewz_serie, ibov_serie):
    from preco_teto.services import usd

    monkeypatch.setattr(usd, "fetch_ptax", lambda anos=3: ptax_serie)
    monkeypatch.setattr(usd, "fetch_cot_real", lambda: None)
    historicos = {"DX-Y.NYB": dxy_serie, "EWZ": ewz_serie, "^BVSP": ibov_serie}
    monkeypatch.setattr(usd, "_fetch_history", lambda ticker, periodo="5y": historicos[ticker])
    monkeypatch.setattr(usd, "_quote", _fake_quote)

    data = usd.fetch_usd()

    assert data.spot is not None
    assert data.spot_comercial == pytest.approx(5.4645)
    assert data.cot is None
    assert data.dxy is not None


def test_fetch_usd_historico_vazio_nao_quebra(monkeypatch, ptax_serie):
    from preco_teto.services import usd

    monkeypatch.setattr(usd, "fetch_ptax", lambda anos=3: ptax_serie)
    monkeypatch.setattr(usd, "fetch_cot_real", lambda: None)
    monkeypatch.setattr(usd, "_fetch_history", lambda ticker, periodo="5y": pd.Series(dtype=float))
    monkeypatch.setattr(usd, "_quote", _fake_quote)

    data = usd.fetch_usd()

    assert data.spot is not None
    assert data.spot_comercial == pytest.approx(5.4645)
    assert data.dxy is None
    assert data.k_hat is None
    assert data.desvio_z is None
