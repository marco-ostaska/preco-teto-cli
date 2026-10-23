import pytest
from unittest.mock import patch, MagicMock
import pandas as pd


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


def test_dy_medio_3y(mock_dividends_3y, mock_yf_info_br, mock_adj_close, mocker):
    """dy_medio deve usar média dos 3 anos completos mais recentes."""
    mock_ticker = mocker.MagicMock()
    mock_ticker.info = mock_yf_info_br
    mock_ticker.history.return_value = mock_adj_close
    mock_ticker.income_stmt = None
    mock_ticker.dividends = mock_dividends_3y
    mocker.patch("yfinance.Ticker", return_value=mock_ticker)

    from preco_teto.services.acao import fetch_acao
    data = fetch_acao("VALE3")
    # média de 12.00, 14.40, 16.80 = 14.40
    assert data.dividendo_medio == pytest.approx(14.40, rel=1e-2)


def test_dy_medio_fallback_sem_historico(mock_dividends_empty, mock_yf_info_br, mock_adj_close, mocker):
    """Sem histórico, dy_medio usa dividendRate do info."""
    mock_ticker = mocker.MagicMock()
    mock_ticker.info = mock_yf_info_br  # dividendRate = 3.60
    mock_ticker.history.return_value = mock_adj_close
    mock_ticker.income_stmt = None
    mock_ticker.dividends = mock_dividends_empty
    mocker.patch("yfinance.Ticker", return_value=mock_ticker)

    from preco_teto.services.acao import fetch_acao
    data = fetch_acao("VALE3")
    assert data.dividendo_medio == pytest.approx(3.60, rel=1e-2)


def test_todos_tetos_none_sem_dados(mocker):
    """Ativo sem dados suficientes retorna dividendo_medio None."""
    mock_ticker = mocker.MagicMock()
    mock_ticker.info = {}
    mock_ticker.history.return_value = __import__("pandas").DataFrame()
    mock_ticker.income_stmt = None
    mock_ticker.dividends = __import__("pandas").Series([], dtype=float)
    mocker.patch("yfinance.Ticker", return_value=mock_ticker)

    from preco_teto.services.acao import fetch_acao
    data = fetch_acao("IAU")
    assert data.dividendo_medio is None
    assert data.cotacao is None


@patch("yfinance.Ticker")
def test_fetch_acao_expoe_nome_do_ativo(mock_cls, mock_yf_info_br, mock_income_stmt, mock_adj_close):
    info = dict(mock_yf_info_br, shortName="Vale S.A.")
    mock_cls.return_value = make_ticker_mock(info, mock_income_stmt, mock_adj_close)

    from preco_teto.services.acao import fetch_acao

    data = fetch_acao("VALE3")
    assert data.nome == "Vale S.A."


@patch("yfinance.Ticker")
def test_fetch_acao_usa_history_como_fallback_para_52_semanas(mock_cls, mock_yf_info_br, mock_income_stmt, mock_adj_close):
    info = dict(mock_yf_info_br)
    info.pop("fiftyTwoWeekLow")
    info.pop("fiftyTwoWeekHigh")
    mock_cls.return_value = make_ticker_mock(info, mock_income_stmt, mock_adj_close)

    from preco_teto.services.acao import fetch_acao

    data = fetch_acao("VALE3")
    assert data.low_52 == pytest.approx(float(mock_adj_close["Close"].min()))
    assert data.high_52 == pytest.approx(float(mock_adj_close["Close"].max()))


def test_dividend_yield_atual_calculado(mock_dividends_3y, mock_yf_info_br, mock_adj_close, mocker):
    """DY atual deve ser dividend_rate / cotacao * 100."""
    mock_ticker = mocker.MagicMock()
    mock_ticker.info = mock_yf_info_br  # dividendRate=3.60, currentPrice=58.20
    mock_ticker.history.return_value = mock_adj_close
    mock_ticker.income_stmt = None
    mock_ticker.dividends = mock_dividends_3y
    mocker.patch("yfinance.Ticker", return_value=mock_ticker)

    from preco_teto.services.acao import fetch_acao
    data = fetch_acao("VALE3")
    # 3.60 / 58.20 * 100 = 6.1856...
    assert data.dividend_yield == pytest.approx(6.19, rel=1e-2)


def test_roe_calculado_como_percentual(mock_yf_info_br, mock_adj_close, mocker):
    mock_ticker = mocker.MagicMock()
    mock_ticker.info = mock_yf_info_br
    mock_ticker.history.return_value = mock_adj_close
    mock_ticker.income_stmt = None
    mock_ticker.dividends = None
    mocker.patch("yfinance.Ticker", return_value=mock_ticker)

    from preco_teto.services.acao import fetch_acao
    data = fetch_acao("VALE3")

    assert data.roe == pytest.approx(17.12)


def test_roe_historico_calcula_media_e_tendencia(mock_yf_info_br, mock_adj_close, mocker):
    mock_ticker = mocker.MagicMock()
    mock_ticker.info = mock_yf_info_br
    mock_ticker.history.return_value = mock_adj_close
    mock_ticker.income_stmt = pd.DataFrame(
        {"Net Income": [100.0, 110.0, 120.0, 130.0, 140.0]},
        index=pd.to_datetime(["2019-12-31", "2020-12-31", "2021-12-31", "2022-12-31", "2023-12-31"]),
    ).T
    mock_ticker.balance_sheet = pd.DataFrame(
        {"Stockholders Equity": [1000.0, 1000.0, 1000.0, 1000.0, 1000.0]},
        index=pd.to_datetime(["2019-12-31", "2020-12-31", "2021-12-31", "2022-12-31", "2023-12-31"]),
    ).T
    mock_ticker.dividends = None
    mocker.patch("yfinance.Ticker", return_value=mock_ticker)

    from preco_teto.services.acao import fetch_acao
    data = fetch_acao("VALE3")

    assert data.roe_medio_5a == pytest.approx(12.0)
    assert data.roe_tendencia == pytest.approx(1.0)
    assert data.roe_ajustado == pytest.approx(13.0)


def test_dy_medio_calculado(mock_dividends_3y, mock_yf_info_br, mock_adj_close, mocker):
    """DY medio deve ser dividendo_medio / cotacao * 100."""
    mock_ticker = mocker.MagicMock()
    mock_ticker.info = mock_yf_info_br
    mock_ticker.history.return_value = mock_adj_close
    mock_ticker.income_stmt = None
    mock_ticker.dividends = mock_dividends_3y
    mocker.patch("yfinance.Ticker", return_value=mock_ticker)

    from preco_teto.services.acao import fetch_acao
    data = fetch_acao("VALE3")
    # 14.40 / 58.20 * 100 = 24.742...
    assert data.dy_medio == pytest.approx(24.74, rel=1e-2)


def test_ultimo_dividendo_exposto(mock_dividends_3y, mock_yf_info_br, mock_adj_close, mocker):
    """Deve expor ultimo dividendo e mes/ano da serie historica."""
    mock_ticker = mocker.MagicMock()
    mock_ticker.info = mock_yf_info_br
    mock_ticker.history.return_value = mock_adj_close
    mock_ticker.income_stmt = None
    mock_ticker.dividends = mock_dividends_3y
    mocker.patch("yfinance.Ticker", return_value=mock_ticker)

    from preco_teto.services.acao import fetch_acao
    data = fetch_acao("VALE3")
    assert data.ultimo_dividendo == 1.40
    assert data.mes_ano_dividendo == "Dez/2023"
