import pytest
from unittest.mock import patch, MagicMock
import requests

BCB_SELIC_RESPONSE = [
    {"data": "01/01/2024", "valor": "0.0452"},
    {"data": "02/01/2024", "valor": "0.0452"},
]

BCB_IPCA_RESPONSE = [
    {"data": "01/01/2024", "valor": "0.38"},
    {"data": "01/02/2024", "valor": "0.41"},
]

TESOURO_RESPONSE = {
    "response": {
        "TrsrBdTradgList": [
            {
                "TrsrBd": {
                    "nm": "Tesouro Prefixado 2026",
                    "anulInvstmtRate": 13.10,
                    "mtrtyDt": "2026-01-01T00:00:00",
                }
            },
            {
                "TrsrBd": {
                    "nm": "Tesouro Prefixado 2030",
                    "anulInvstmtRate": 13.50,
                    "mtrtyDt": "2030-01-01T00:00:00",
                }
            },
        ]
    }
}


def mock_get(url, *args, **kwargs):
    m = MagicMock()
    if "bcb.gov.br" in url and "11" in url:
        m.json.return_value = BCB_SELIC_RESPONSE
        m.raise_for_status = MagicMock()
    elif "bcb.gov.br" in url and "10844" in url:
        m.json.return_value = BCB_IPCA_RESPONSE
        m.raise_for_status = MagicMock()
    elif "tesourodireto" in url:
        m.json.return_value = TESOURO_RESPONSE
        m.raise_for_status = MagicMock()
    return m


@patch("requests.get", side_effect=mock_get)
def test_fetch_selic_returns_float(mock):
    from radar.services.banco_central import fetch_selic
    result = fetch_selic()
    assert isinstance(result, float)
    assert result > 0


@patch("requests.get", side_effect=mock_get)
def test_fetch_ipca_returns_float(mock):
    from radar.services.banco_central import fetch_ipca
    result = fetch_ipca()
    assert isinstance(result, float)
    assert result > 0


@patch("requests.get", side_effect=mock_get)
def test_fetch_juro_futuro_returns_float(mock):
    from radar.services.tesouro import fetch_juro_futuro
    result = fetch_juro_futuro()
    assert isinstance(result, float)
    assert result > 0


@patch("requests.get", side_effect=lambda *a, **k: (_ for _ in ()).throw(requests.ConnectionError()))
def test_fetch_selic_returns_none_on_error(mock):
    from radar.services.banco_central import fetch_selic
    result = fetch_selic()
    assert result is None


@patch("requests.get", side_effect=lambda *a, **k: (_ for _ in ()).throw(requests.ConnectionError()))
def test_fetch_juro_futuro_returns_none_on_error(mock):
    from radar.services.tesouro import fetch_juro_futuro
    result = fetch_juro_futuro()
    assert result is None


# --- IndicesBR and IndicesUS ---

@patch("radar.services.banco_central.fetch_selic", return_value=13.75)
@patch("radar.services.banco_central.fetch_ipca", return_value=4.80)
@patch("radar.services.tesouro.fetch_juro_futuro", return_value=13.10)
def test_indices_br(mock_jf, mock_ipca, mock_selic):
    from radar.services.referencia import IndicesBR, fetch_indices_br
    idx = fetch_indices_br()
    assert isinstance(idx, IndicesBR)
    assert idx.selic == 13.75
    assert idx.ipca == 4.80
    assert idx.juro_futuro == 13.10
    assert idx.melhor_indice == pytest.approx(max(13.75 * 0.85, 4.80 + 2.0), rel=1e-3)


@patch("yfinance.Ticker")
def test_indices_us_tflo(mock_ticker_cls):
    mock_tflo = MagicMock()
    mock_tflo.info = {"dividendYield": 0.0528}
    mock_tlt = MagicMock()
    mock_tlt.info = {"dividendYield": 0.046}
    mock_ticker_cls.side_effect = [mock_tflo, mock_tlt]

    from radar.services.referencia import IndicesUS, fetch_indices_us
    idx = fetch_indices_us()
    assert isinstance(idx, IndicesUS)
    assert idx.taxa_curto == pytest.approx(5.28, rel=1e-2)
    assert idx.taxa_longo == pytest.approx(4.6, rel=1e-2)
    assert idx.cpi == 3.1


@patch("yfinance.Ticker")
def test_indices_us_fallback_bil(mock_ticker_cls):
    """Quando TFLO não tem dividendYield, usa BIL."""
    mock_tflo = MagicMock()
    mock_tflo.info = {}
    mock_bil = MagicMock()
    mock_bil.info = {"dividendYield": 0.051}
    mock_tlt = MagicMock()
    mock_tlt.info = {"dividendYield": 0.046}
    mock_ticker_cls.side_effect = [mock_tflo, mock_bil, mock_tlt]

    from radar.services.referencia import fetch_indices_us
    idx = fetch_indices_us()
    assert idx.taxa_curto == pytest.approx(5.1, rel=1e-2)
