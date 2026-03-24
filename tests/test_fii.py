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
