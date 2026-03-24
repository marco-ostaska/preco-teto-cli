import pytest
from unittest.mock import patch, MagicMock
import requests

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
def test_indices_br(mock_ipca, mock_cdi):
    from preco_teto.services.referencia import IndicesBR, fetch_indices_br
    idx = fetch_indices_br()
    assert isinstance(idx, IndicesBR)
    assert idx.cdi == 13.75
    assert idx.ipca == 4.80
    assert not hasattr(idx, "juro_futuro")
    assert idx.melhor_indice == pytest.approx(max(13.75 * 0.85, 4.80 + 2.0), rel=1e-3)


def test_indices_us_hardcoded():
    from preco_teto.services.referencia import IndicesUS, fetch_indices_us
    idx = fetch_indices_us()
    assert isinstance(idx, IndicesUS)
    assert idx.fed_funds > 0
    assert idx.cpi > 0
