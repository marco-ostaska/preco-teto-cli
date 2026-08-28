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
    if "bcb.gov.br" in url and "11" in url:
        m.json.return_value = BCB_CDI_RESPONSE
        m.raise_for_status = MagicMock()
    elif "bcb.gov.br" in url and "10844" in url:
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


def test_indices_us_hardcoded():
    from preco_teto.services.referencia import IndicesUS, fetch_indices_us
    idx = fetch_indices_us()
    assert isinstance(idx, IndicesUS)
    assert idx.fed_funds > 0
    assert idx.cpi > 0
