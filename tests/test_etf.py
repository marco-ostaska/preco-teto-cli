import io
import zipfile
from unittest.mock import patch, MagicMock

import pandas as pd
import pytest


@patch("requests.get")
def test_fetch_etf_combina_statusinvest_com_cvm(mock_get, mock_statusinvest_etf_html, monkeypatch):
    from preco_teto.services.etf import fetch_etf

    csv = (
        "TP_FUNDO_CLASSE;CNPJ_FUNDO_CLASSE;ID_SUBCLASSE;DT_COMPTC;VL_TOTAL;VL_QUOTA;VL_PATRIM_LIQ;CAPTC_DIA;RESG_DIA;NR_COTST\n"
        "FUNDO DE INDICE;13.416.245/0001-46;;2026-03-26;1761000000;140.490000000000;1760051855;0;0;12345\n"
        "FUNDO DE INDICE;13.416.245/0001-46;;2026-03-27;1762000000;140.500000000000;1761051855;0;0;12346\n"
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("inf_diario_fi_202603.csv", csv.encode("latin-1"))
    zip_bytes = buf.getvalue()

    def fake_get(url, headers=None, timeout=30):
        response = MagicMock()
        if "statusinvest.com.br/etfs/divo11" in url:
            response.text = mock_statusinvest_etf_html
            response.raise_for_status = MagicMock()
            return response
        if url.endswith(".zip"):
            response.content = zip_bytes
            response.raise_for_status = MagicMock()
            return response
        raise AssertionError(url)

    mock_get.side_effect = fake_get
    monkeypatch.setattr(
        "preco_teto.services.etf._iter_inf_diario_urls",
        lambda: ["https://dados.cvm.gov.br/dados/FI/DOC/INF_DIARIO/DADOS/inf_diario_fi_202603.zip"],
    )

    data = fetch_etf("DIVO11")

    assert data.ticker == "DIVO11"
    assert data.nome == "DIVO11"
    assert data.cnpj == "13.416.245/0001-46"
    assert data.cotacao == pytest.approx(132.06)
    assert data.low_52 == pytest.approx(91.30)
    assert data.high_52 == pytest.approx(136.43)
    assert data.pl_total == pytest.approx(1761051855.0)
    assert data.pl_cota == pytest.approx(140.50)
    assert data.cotistas == 12346


@patch("requests.get")
def test_fetch_etf_us_usa_yfinance_quando_statusinvest_nao_tem_cnpj(mock_get, mocker):
    mock_get.return_value.text = "<html><body><h1>TFLO</h1></body></html>"
    mock_get.return_value.raise_for_status = MagicMock()

    hist = pd.DataFrame({"Close": [50.0, 51.0, 52.0]})
    mock_ticker = mocker.MagicMock()
    mock_ticker.info = {
        "shortName": "iShares Treasury Floating Rate Bond ETF",
        "currentPrice": 50.75,
        "fiftyTwoWeekLow": 49.10,
        "fiftyTwoWeekHigh": 52.30,
        "navPrice": 50.90,
    }
    mock_ticker.history.return_value = hist
    mocker.patch("yfinance.Ticker", return_value=mock_ticker)

    from preco_teto.services.etf import fetch_etf

    data = fetch_etf("TFLO")

    assert data.ticker == "TFLO"
    assert data.nome == "iShares Treasury Floating Rate Bond ETF"
    assert data.cnpj == ""
    assert data.cotacao == pytest.approx(50.75)
    assert data.pl_cota == pytest.approx(50.90)
    assert data.low_52 == pytest.approx(49.10)
    assert data.high_52 == pytest.approx(52.30)
