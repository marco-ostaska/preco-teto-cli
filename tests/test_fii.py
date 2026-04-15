import pytest
from unittest.mock import patch, MagicMock
import pandas as pd


@patch("requests.get")
def test_fii_cotacao_from_fiiscom(mock_get, mock_fiiscom_html):
    mock_get.return_value.text = mock_fiiscom_html
    mock_get.return_value.encoding = "utf-8"
    from preco_teto.services.fii import FiisComService
    svc = FiisComService("HGLG11")
    assert svc.cotacao == 142.50


@patch("requests.get")
def test_fii_vpa_from_fiiscom(mock_get, mock_fiiscom_html):
    mock_get.return_value.text = mock_fiiscom_html
    mock_get.return_value.encoding = "utf-8"
    from preco_teto.services.fii import FiisComService
    svc = FiisComService("HGLG11")
    assert svc.vpa == 151.30


@patch("requests.get")
def test_dividendo_estimado_uses_3m_when_declining(mock_get, mock_fiiscom_html, mock_dividends_series):
    """Quando média 3m < média 6m (queda), usa 3m × 12 (conservador)."""
    mock_get.return_value.text = mock_fiiscom_html
    mock_get.return_value.encoding = "utf-8"
    from preco_teto.services.fii import FiisComService
    svc = FiisComService("HGLG11")
    svc._dividends = mock_dividends_series
    result = svc.dividendo_estimado
    tres = mock_dividends_series.iloc[:3].mean()
    seis = mock_dividends_series.iloc[:6].mean()
    assert tres < seis  # confirm declining
    assert result == pytest.approx(tres * 12, rel=1e-3)


@patch("requests.get")
def test_dividendo_estimado_uses_6m_when_stable(mock_get, mock_fiiscom_html):
    mock_get.return_value.text = mock_fiiscom_html
    mock_get.return_value.encoding = "utf-8"
    from preco_teto.services.fii import FiisComService
    svc = FiisComService("HGLG11")
    stable = pd.Series([1.20, 1.21, 1.22, 1.19, 1.20, 1.21], index=range(6))
    svc._dividends = stable
    tres = stable.iloc[:3].mean()
    seis = stable.iloc[:6].mean()
    assert tres >= seis  # stable/growing
    assert svc.dividendo_estimado == pytest.approx(seis * 12, rel=1e-3)


@patch("requests.get")
def test_fetch_fii_expoe_nome_do_ativo(mock_get, mock_fiiscom_html, mocker):
    mock_get.return_value.text = mock_fiiscom_html
    mock_get.return_value.encoding = "utf-8"

    mock_ticker = mocker.MagicMock()
    mock_ticker.info = {"fiftyTwoWeekLow": 140.0, "fiftyTwoWeekHigh": 160.0}
    mock_ticker.history.return_value = pd.DataFrame({"Close": [140.0, 160.0]})
    mocker.patch("yfinance.Ticker", return_value=mock_ticker)

    from preco_teto.services.fii import fetch_fii

    data = fetch_fii("HGLG11")
    assert data.nome == "CGHG Logística"


@patch("requests.get")
def test_fetch_fii_usa_history_como_fallback_para_52_semanas(mock_get, mock_fiiscom_html, mocker):
    mock_get.return_value.text = mock_fiiscom_html
    mock_get.return_value.encoding = "utf-8"

    hist = pd.DataFrame({"Close": [138.5, 145.0, 159.2]})
    mock_ticker = mocker.MagicMock()
    mock_ticker.info = {}
    mock_ticker.history.return_value = hist
    mocker.patch("yfinance.Ticker", return_value=mock_ticker)

    from preco_teto.services.fii import fetch_fii

    data = fetch_fii("HGLG11")
    assert data.low_52 == pytest.approx(138.5)
    assert data.high_52 == pytest.approx(159.2)


@patch("requests.get")
def test_fetch_fii_descarta_outlier_no_historico_de_52_semanas(mock_get, mock_fiiscom_html, mocker):
    mock_get.return_value.text = mock_fiiscom_html
    mock_get.return_value.encoding = "utf-8"

    hist = pd.DataFrame({"Close": [100.0, 104.0, 112.0, 1.06]})
    mock_ticker = mocker.MagicMock()
    mock_ticker.info = {"fiftyTwoWeekLow": 1.06, "fiftyTwoWeekHigh": 112.0}
    mock_ticker.history.return_value = hist
    mocker.patch("yfinance.Ticker", return_value=mock_ticker)

    from preco_teto.services.fii import fetch_fii
    from preco_teto.formulas import teto_margem

    data = fetch_fii("XPML11")
    assert data.low_52 == pytest.approx(100.0)
    assert data.high_52 == pytest.approx(112.0)
    mock_ticker.history.assert_called_once_with(period="1y", auto_adjust=False)
    assert teto_margem(107.64, data.low_52, data.high_52) == pytest.approx(103.0)


# --- Último dividendo ---


@patch("requests.get")
def test_ultimo_dividendo_from_fiiscom(mock_get, mock_fiiscom_html):
    """Scraper extrai valor, data base (mês/ano) e DY mensal do primeiro bloco."""
    mock_get.return_value.text = mock_fiiscom_html
    mock_get.return_value.encoding = "utf-8"
    from preco_teto.services.fii import FiisComService
    svc = FiisComService("HGLG11")
    assert svc.ultimo_dividendo == 1.10
    assert svc.mes_ano_dividendo == "Mar/2026"
    assert svc.dy_mensal == pytest.approx(0.78)


@patch("requests.get")
def test_fetch_fii_inclui_ultimo_dividendo(mock_get, mock_fiiscom_html, mocker):
    """FiiData inclui campos do último dividendo."""
    mock_get.return_value.text = mock_fiiscom_html
    mock_get.return_value.encoding = "utf-8"

    mock_ticker = mocker.MagicMock()
    mock_ticker.info = {"fiftyTwoWeekLow": 140.0, "fiftyTwoWeekHigh": 160.0}
    mock_ticker.history.return_value = pd.DataFrame({"Close": [140.0, 160.0]})
    mocker.patch("yfinance.Ticker", return_value=mock_ticker)

    from preco_teto.services.fii import fetch_fii
    data = fetch_fii("HGLG11")
    assert data.ultimo_dividendo == 1.10
    assert data.mes_ano_dividendo == "Mar/2026"
    assert data.dy_mensal == pytest.approx(0.78)


@patch("requests.get")
def test_ultimo_dividendo_fallback_yfinance(mock_get, mocker):
    """Quando scraper não tem dados de dividendo, yfinance fornece fallback."""
    html_sem_dividendo = """
    <html><body>
      <h1>XYZF11</h1>
      <div class="item quotation"><span class="value">100,00</span></div>
      <div class="indicators">
        <div class="indicators__box">
          <p><b>8,00%</b></p><p>Dividend Yield</p>
        </div>
      </div>
      <div class="wrapper indicators">
        <div class="indicators__box">
          <p><b>95,00</b></p><p>Val. Patrimonial p/Cota</p>
        </div>
      </div>
    </body></html>
    """
    mock_get.return_value.text = html_sem_dividendo
    mock_get.return_value.encoding = "utf-8"

    mock_ticker = mocker.MagicMock()
    mock_ticker.info = {
        "fiftyTwoWeekLow": 90.0,
        "fiftyTwoWeekHigh": 110.0,
        "lastDividendValue": 0.95,
        "lastDividendDate": 1713150000,  # 2024-04-15
    }
    mock_ticker.history.return_value = pd.DataFrame({"Close": [100.0]})
    mocker.patch("yfinance.Ticker", return_value=mock_ticker)

    from preco_teto.services.fii import fetch_fii
    data = fetch_fii("XYZF11")
    assert data.ultimo_dividendo == 0.95
    assert data.mes_ano_dividendo == "Abr/2024"
    assert data.dy_mensal == pytest.approx(0.95)  # 0.95/100*100


@patch("requests.get")
def test_ultimo_dividendo_none_quando_sem_dados(mock_get, mocker):
    """Campos ficam None quando nem scraper nem yfinance têm dados."""
    html_minimo = """
    <html><body>
      <h1>SEM11</h1>
      <div class="item quotation"><span class="value">50,00</span></div>
      <div class="indicators">
        <div class="indicators__box">
          <p><b>5,00%</b></p><p>Dividend Yield</p>
        </div>
      </div>
    </body></html>
    """
    mock_get.return_value.text = html_minimo
    mock_get.return_value.encoding = "utf-8"

    mock_ticker = mocker.MagicMock()
    mock_ticker.info = {
        "fiftyTwoWeekLow": 40.0,
        "fiftyTwoWeekHigh": 60.0,
    }
    mock_ticker.history.return_value = pd.DataFrame({"Close": [50.0]})
    mocker.patch("yfinance.Ticker", return_value=mock_ticker)

    from preco_teto.services.fii import fetch_fii
    data = fetch_fii("SEM11")
    assert data.ultimo_dividendo is None
    assert data.mes_ano_dividendo is None
    assert data.dy_mensal is None
