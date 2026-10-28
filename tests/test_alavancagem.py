from types import SimpleNamespace

import pandas as pd


def _ticker_mock(mocker, info, balance_sheet=None, income_stmt=None):
    ticker = mocker.MagicMock()
    ticker.info = info
    ticker.balance_sheet = balance_sheet
    ticker.income_stmt = income_stmt
    ticker.dividends = None
    ticker.history.return_value = pd.DataFrame()
    return ticker


def test_classifica_alavancagem_por_dois_indices():
    from preco_teto.formulas import classificar_alavancagem

    assert classificar_alavancagem(0.50, 1.50) == "Saudável"
    assert classificar_alavancagem(0.51, 1.50) == "Atenção"
    assert classificar_alavancagem(1.00, 3.01) == "Elevada"
    assert classificar_alavancagem(None, None) == "Indisponível"


def test_fetch_acao_calcula_alavancagem_com_info(mock_yf_info_br, mocker):
    ticker = _ticker_mock(
        mocker,
        {
            **mock_yf_info_br,
            "totalDebt": 30_000_000_000,
            "totalCash": 10_000_000_000,
            "totalStockholderEquity": 100_000_000_000,
            "ebitda": 20_000_000_000,
        },
    )
    mocker.patch("yfinance.Ticker", return_value=ticker)

    from preco_teto.services.acao import fetch_acao

    data = fetch_acao("VALE3")

    assert data.divida_total == 30_000_000_000
    assert data.caixa == 10_000_000_000
    assert data.divida_liquida == 20_000_000_000
    assert data.divida_sobre_patrimonio == 0.30
    assert data.divida_liquida_sobre_ebitda == 1.00
    assert data.alavancagem_status == "Saudável"


def test_fetch_acao_usa_balance_sheet_e_income_stmt_como_fallback(mock_yf_info_br, mocker):
    datas = pd.to_datetime(["2023-12-31"])
    balance_sheet = pd.DataFrame(
        {
            "Total Debt": [60.0],
            "Cash Cash Equivalents And Short Term Investments": [10.0],
            "Stockholders Equity": [100.0],
        },
        index=datas,
    ).T
    income_stmt = pd.DataFrame({"EBITDA": [20.0]}, index=datas).T
    ticker = _ticker_mock(mocker, mock_yf_info_br, balance_sheet, income_stmt)
    mocker.patch("yfinance.Ticker", return_value=ticker)

    from preco_teto.services.acao import fetch_acao

    data = fetch_acao("VALE3")

    assert data.divida_total == 60.0
    assert data.divida_liquida == 50.0
    assert data.divida_sobre_patrimonio == 0.60
    assert data.divida_liquida_sobre_ebitda == 2.50
    assert data.alavancagem_status == "Atenção"


def test_json_render_expoe_alavancagem(capsys):
    from preco_teto.output import json_out

    indices = SimpleNamespace(cdi=10.0, ipca=4.0)
    json_out.render_acao(
        "VALE3",
        58.20,
        True,
        {},
        indices,
        alavancagem={"status": "Saudável", "divida_total": 30.0},
    )

    assert '"alavancagem"' in capsys.readouterr().out
