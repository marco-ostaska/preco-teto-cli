from unittest.mock import MagicMock, patch

import pytest

from preco_teto.services.etf_br import (
    EtfBrFetchError,
    _PUSH_RE,
    _concat_t_chunk,
    _find_performance_series_chunk_id,
    _find_series_chunk_id,
    _parse_etfsbrasil_html,
    _parse_latest_spread,
    _parse_quotation_52w,
    fetch_etf_br,
    pl_cota_from_spread,
)


@patch("preco_teto.services.etf_br.requests.get")
def test_fetch_etf_br_extrai_cotacao_vp_e_52w(mock_get, mock_etfsbrasil_divo11_html):
    mock_get.return_value = MagicMock(
        status_code=200,
        text=mock_etfsbrasil_divo11_html,
        raise_for_status=MagicMock(),
    )

    data = fetch_etf_br("divo11")

    assert data.ticker == "DIVO11"
    assert data.nome == "IT NOW IDIV FUNDO DE ÍNDICE"
    assert data.cotacao == pytest.approx(128.24)
    assert data.pl_cota == pytest.approx(128.16, rel=1e-3)
    assert data.premio_desconto_pct == pytest.approx(0.06, abs=0.01)
    assert data.low_52 == pytest.approx(98.88, rel=1e-3)
    assert data.high_52 == pytest.approx(142.00, rel=1e-3)
    assert data.pl_total_mm == pytest.approx(2250.16)
    assert data.taxa_adm_pct == pytest.approx(0.50)
    assert data.cotistas == 48778
    assert data.cnpj == "13.416.245/0001-46"
    assert data.indice == "IDIV"


@patch("preco_teto.services.etf_br.requests.get")
def test_fetch_etf_br_http_erro_levanta(mock_get):
    import requests

    mock_get.side_effect = requests.RequestException("timeout")

    with pytest.raises(EtfBrFetchError):
        fetch_etf_br("DIVO11")


def test_fetch_etf_br_html_sem_spread_levanta(mock_etfsbrasil_divo11_html):
    html = "<html><body><div class=\"quoteValue\">R$ 10,00</div></body></html>"

    with pytest.raises(EtfBrFetchError):
        _parse_etfsbrasil_html("DIVO11", html)


def test_parse_spread_deriva_pl_cota():
    vp = pl_cota_from_spread(128.24, 0.05943717435002327)
    assert vp == pytest.approx(128.16, rel=1e-3)


def test_parse_historico_52w(mock_etfsbrasil_divo11_html):
    pushes = _PUSH_RE.findall(mock_etfsbrasil_divo11_html)
    quot_id = _find_performance_series_chunk_id(pushes)
    blob = _concat_t_chunk(pushes, quot_id)
    low, high = _parse_quotation_52w(blob, 128.24)

    assert low == pytest.approx(98.88, rel=1e-3)
    assert high == pytest.approx(142.00, rel=1e-3)


def test_parse_latest_spread_fixture(mock_etfsbrasil_divo11_html):
    pushes = _PUSH_RE.findall(mock_etfsbrasil_divo11_html)
    spread_id = _find_series_chunk_id(pushes, "Spread entre o Pre")
    blob = _concat_t_chunk(pushes, spread_id)
    spread = _parse_latest_spread(blob)

    assert spread == pytest.approx(0.0594, abs=0.001)
