import pytest
from unittest.mock import patch, MagicMock


def make_ticker_mock(info, income_stmt, adj_close):
    m = MagicMock()
    m.info = info
    m.income_stmt = income_stmt
    m.history.return_value = adj_close
    return m


@patch("yfinance.Ticker")
def test_br_ticker_adds_sa(mock_cls, mock_yf_info_br, mock_income_stmt, mock_adj_close):
    mock_cls.return_value = make_ticker_mock(mock_yf_info_br, mock_income_stmt, mock_adj_close)
    from preco_teto.services.acao import fetch_acao
    data = fetch_acao("VALE3")
    mock_cls.assert_called_with("VALE3.SA")


@patch("yfinance.Ticker")
def test_us_ticker_no_sa(mock_cls, mock_yf_info_us, mock_income_stmt, mock_adj_close):
    mock_cls.return_value = make_ticker_mock(mock_yf_info_us, mock_income_stmt, mock_adj_close)
    from preco_teto.services.acao import fetch_acao
    data = fetch_acao("AAPL")
    mock_cls.assert_called_with("AAPL")


@patch("yfinance.Ticker")
def test_cotacao_fallback_chain(mock_cls, mock_income_stmt, mock_adj_close):
    info_no_current = {"previousClose": 57.80}
    mock_cls.return_value = make_ticker_mock(info_no_current, mock_income_stmt, mock_adj_close)
    from preco_teto.services.acao import fetch_acao
    data = fetch_acao("VALE3")
    assert data.cotacao == 57.80


@patch("yfinance.Ticker")
def test_cotacao_none_when_all_missing(mock_cls, mock_income_stmt, mock_adj_close):
    import pandas as pd
    empty = pd.DataFrame()
    mock_cls.return_value = make_ticker_mock({}, mock_income_stmt, empty)
    mock_cls.return_value.history.return_value = empty
    from preco_teto.services.acao import fetch_acao
    data = fetch_acao("VALE3")
    assert data.cotacao is None


@patch("yfinance.Ticker")
def test_is_br_detection_br(mock_cls, mock_yf_info_br, mock_income_stmt, mock_adj_close):
    mock_cls.return_value = make_ticker_mock(mock_yf_info_br, mock_income_stmt, mock_adj_close)
    from preco_teto.services.acao import fetch_acao
    data = fetch_acao("VALE3")
    assert data.is_br is True


@patch("yfinance.Ticker")
def test_is_br_detection_us(mock_cls, mock_yf_info_us, mock_income_stmt, mock_adj_close):
    mock_cls.return_value = make_ticker_mock(mock_yf_info_us, mock_income_stmt, mock_adj_close)
    from preco_teto.services.acao import fetch_acao
    data = fetch_acao("AAPL")
    assert data.is_br is False
