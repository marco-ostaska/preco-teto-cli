import pytest
from unittest.mock import patch, MagicMock
import requests
from datetime import date

BCB_CDI_RESPONSE = [
    {"data": "01/01/2024", "valor": "0.0452"},
    {"data": "02/01/2024", "valor": "0.0452"},
]

BCB_IPCA_RESPONSE = [
    {"data": "01/01/2024", "valor": "0.38"},
    {"data": "01/02/2024", "valor": "0.41"},
]


def mock_get(url, *args, **kwargs):
    m = MagicMock()
    if "bcb.gov.br" in url and "sgs.11/" in url:
        m.json.return_value = BCB_CDI_RESPONSE
        m.raise_for_status = MagicMock()
    elif "bcb.gov.br" in url and "sgs.433/" in url:
        m.json.return_value = BCB_IPCA_RESPONSE
        m.raise_for_status = MagicMock()
    return m


@patch("requests.get", side_effect=mock_get)
def test_fetch_cdi_returns_float(mock):
    from preco_teto.services.banco_central import fetch_cdi
    result = fetch_cdi()
    assert isinstance(result, float)
    assert result > 0


@patch("requests.get", side_effect=mock_get)
def test_fetch_ipca_returns_float(mock):
    from preco_teto.services.banco_central import fetch_ipca
    result = fetch_ipca()
    assert isinstance(result, float)
    assert result > 0


@patch("requests.get", side_effect=lambda *a, **k: (_ for _ in ()).throw(requests.ConnectionError()))
def test_fetch_cdi_returns_none_on_error(mock):
    from preco_teto.services.banco_central import fetch_cdi
    result = fetch_cdi()
    assert result is None


@patch("preco_teto.services.banco_central.fetch_cdi", return_value=13.75)
@patch("preco_teto.services.banco_central.fetch_ipca", return_value=4.80)
def test_indices_br(mock_ipca, mock_cdi, tmp_path, monkeypatch):
    import preco_teto.services.referencia as referencia

    monkeypatch.setattr(referencia, "_INDICES_BR_CACHE_PATH", tmp_path / "indices.json")
    referencia._indices_br_cache = None
    referencia._indices_br_cache_date = None
    IndicesBR, fetch_indices_br = referencia.IndicesBR, referencia.fetch_indices_br
    idx = fetch_indices_br()
    assert isinstance(idx, IndicesBR)
    assert idx.cdi == 13.75
    assert idx.ipca == 4.80
    assert not hasattr(idx, "juro_futuro")
    assert idx.melhor_indice == pytest.approx(max(13.75 * 0.85, 4.80 + 2.0), rel=1e-3)


def test_indices_br_reuses_values_during_same_day(tmp_path, monkeypatch):
    import preco_teto.services.referencia as referencia

    monkeypatch.setattr(referencia, "_INDICES_BR_CACHE_PATH", tmp_path / "indices.json")
    referencia._indices_br_cache = None
    referencia._indices_br_cache_date = None
    cdi = MagicMock(side_effect=[13.75, 14.00])
    ipca = MagicMock(side_effect=[4.80, 5.00])
    today = MagicMock()
    today.today.return_value = date(2026, 8, 28)
    monkeypatch.setattr(referencia.banco_central, "fetch_cdi", cdi)
    monkeypatch.setattr(referencia.banco_central, "fetch_ipca", ipca)
    monkeypatch.setattr(referencia, "date", today, raising=False)

    first = referencia.fetch_indices_br()
    second = referencia.fetch_indices_br()

    assert first is second
    cdi.assert_called_once_with()
    ipca.assert_called_once_with()


def test_indices_br_refreshes_values_on_next_day(tmp_path, monkeypatch):
    import preco_teto.services.referencia as referencia

    monkeypatch.setattr(referencia, "_INDICES_BR_CACHE_PATH", tmp_path / "indices.json")
    referencia._indices_br_cache = None
    referencia._indices_br_cache_date = None
    cdi = MagicMock(side_effect=[13.75, 14.00])
    ipca = MagicMock(side_effect=[4.80, 5.00])
    today = MagicMock()
    today.today.side_effect = [date(2026, 8, 28), date(2026, 8, 29)]
    monkeypatch.setattr(referencia.banco_central, "fetch_cdi", cdi)
    monkeypatch.setattr(referencia.banco_central, "fetch_ipca", ipca)
    monkeypatch.setattr(referencia, "date", today, raising=False)

    first = referencia.fetch_indices_br()
    second = referencia.fetch_indices_br()

    assert first.cdi == 13.75
    assert second.cdi == 14.00
    assert first is not second
    assert cdi.call_count == 2
    assert ipca.call_count == 2


def test_indices_br_reuses_persisted_values_after_process_restart(tmp_path, monkeypatch):
    import preco_teto.services.referencia as referencia

    monkeypatch.setattr(referencia, "_INDICES_BR_CACHE_PATH", tmp_path / "indices.json")
    referencia._indices_br_cache = None
    referencia._indices_br_cache_date = None
    cdi = MagicMock(return_value=13.75)
    ipca = MagicMock(return_value=4.80)
    today = MagicMock()
    today.today.return_value = date(2026, 8, 28)
    monkeypatch.setattr(referencia.banco_central, "fetch_cdi", cdi)
    monkeypatch.setattr(referencia.banco_central, "fetch_ipca", ipca)
    monkeypatch.setattr(referencia, "date", today, raising=False)

    referencia.fetch_indices_br()
    referencia._indices_br_cache = None
    referencia._indices_br_cache_date = None
    referencia.fetch_indices_br()

    cdi.assert_called_once_with()
    ipca.assert_called_once_with()


def test_fetch_fed_funds_usa_tbill_de_13_semanas(monkeypatch):
    import pandas as pd

    import preco_teto.services.referencia as referencia

    ticker = MagicMock()
    ticker.history.return_value = pd.DataFrame({"Close": [3.90, 3.95, 3.98]})
    monkeypatch.setattr(referencia.yf, "Ticker", MagicMock(return_value=ticker))

    assert referencia.fetch_fed_funds() == pytest.approx(3.98)


def test_fetch_fed_funds_cai_para_constante_quando_yfinance_falha(monkeypatch):
    import preco_teto.services.referencia as referencia

    monkeypatch.setattr(
        referencia.yf, "Ticker", MagicMock(side_effect=RuntimeError("yahoo fora"))
    )

    assert referencia.fetch_fed_funds() == referencia.FED_FUNDS_US


def test_fetch_fed_funds_cai_para_constante_com_historico_vazio(monkeypatch):
    import pandas as pd

    import preco_teto.services.referencia as referencia

    ticker = MagicMock()
    ticker.history.return_value = pd.DataFrame(columns=["Close"])
    monkeypatch.setattr(referencia.yf, "Ticker", MagicMock(return_value=ticker))

    assert referencia.fetch_fed_funds() == referencia.FED_FUNDS_US


def test_indices_us_usa_fed_funds_dinamico(monkeypatch):
    import preco_teto.services.referencia as referencia

    monkeypatch.setattr(referencia.yf, "Ticker", MagicMock(side_effect=RuntimeError("offline")))

    idx = referencia.fetch_indices_us()

    assert isinstance(idx, referencia.IndicesUS)
    assert idx.fed_funds > 0
    assert idx.cpi > 0
    assert idx.fed_funds == referencia.FED_FUNDS_US


def test_indices_us_propaga_taxa_do_tbill(monkeypatch):
    import pandas as pd

    import preco_teto.services.referencia as referencia

    ticker = MagicMock()
    ticker.history.return_value = pd.DataFrame({"Close": [3.98]})
    monkeypatch.setattr(referencia.yf, "Ticker", MagicMock(return_value=ticker))

    assert referencia.fetch_indices_us().fed_funds == pytest.approx(3.98)


def test_fetch_cdi_usa_endpoint_ultimos_e_tenta_de_novo_apos_timeout(monkeypatch):
    from preco_teto.services.banco_central import fetch_cdi
    import preco_teto.services.banco_central as bc

    monkeypatch.setattr(bc.time, "sleep", lambda *_: None)
    ok = MagicMock()
    ok.json.return_value = [{"data": "28/10/2026", "valor": "0.050788"}]
    ok.raise_for_status = MagicMock()
    get = MagicMock(side_effect=[requests.ReadTimeout("timeout"), ok])
    monkeypatch.setattr(bc.requests, "get", get)

    assert fetch_cdi() == pytest.approx(13.65, abs=0.02)
    assert get.call_count == 2
    assert "sgs.11/dados/ultimos/1" in get.call_args.args[0]


def test_fetch_cdi_retorna_none_apos_esgotar_tentativas(monkeypatch):
    from preco_teto.services.banco_central import fetch_cdi
    import preco_teto.services.banco_central as bc

    monkeypatch.setattr(bc.time, "sleep", lambda *_: None)
    get = MagicMock(side_effect=requests.ReadTimeout("timeout"))
    monkeypatch.setattr(bc.requests, "get", get)

    assert fetch_cdi() is None
    assert get.call_count == 3


def test_fetch_ipca_usa_serie_433_ultimos_12(monkeypatch):
    from preco_teto.services.banco_central import fetch_ipca
    import preco_teto.services.banco_central as bc

    ok = MagicMock()
    ok.json.return_value = [{"data": f"01/{m:02d}/2025", "valor": "0.50"} for m in range(1, 13)]
    ok.raise_for_status = MagicMock()
    get = MagicMock(return_value=ok)
    monkeypatch.setattr(bc.requests, "get", get)

    assert fetch_ipca() == pytest.approx(6.00)
    assert "sgs.433/dados/ultimos/12" in get.call_args.args[0]


def test_indices_br_nao_cacheia_ipca_none(tmp_path, monkeypatch):
    import preco_teto.services.referencia as referencia

    monkeypatch.setattr(referencia, "_INDICES_BR_CACHE_PATH", tmp_path / "indices.json")
    referencia._indices_br_cache = None
    referencia._indices_br_cache_date = None
    cdi = MagicMock(return_value=13.75)
    ipca = MagicMock(side_effect=[None, 4.80])
    today = MagicMock()
    today.today.return_value = date(2026, 8, 28)
    monkeypatch.setattr(referencia.banco_central, "fetch_cdi", cdi)
    monkeypatch.setattr(referencia.banco_central, "fetch_ipca", ipca)
    monkeypatch.setattr(referencia, "date", today, raising=False)

    first = referencia.fetch_indices_br()
    second = referencia.fetch_indices_br()

    assert first.ipca is None
    assert second.ipca == 4.80
    assert ipca.call_count == 2


def test_indices_br_ignora_cache_persistido_com_ipca_none(tmp_path, monkeypatch):
    import json as _json

    import preco_teto.services.referencia as referencia

    cache = tmp_path / "indices.json"
    cache.write_text(_json.dumps({
        "date": "2026-08-28", "cdi": 13.65, "ipca": None, "melhor_indice": 11.60,
    }))
    monkeypatch.setattr(referencia, "_INDICES_BR_CACHE_PATH", cache)
    referencia._indices_br_cache = None
    referencia._indices_br_cache_date = None
    ipca = MagicMock(return_value=4.80)
    today = MagicMock()
    today.today.return_value = date(2026, 8, 28)
    monkeypatch.setattr(referencia.banco_central, "fetch_cdi", MagicMock(return_value=13.75))
    monkeypatch.setattr(referencia.banco_central, "fetch_ipca", ipca)
    monkeypatch.setattr(referencia, "date", today, raising=False)

    idx = referencia.fetch_indices_br()

    assert idx.ipca == 4.80
    assert ipca.call_count == 1
