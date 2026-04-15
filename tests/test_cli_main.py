from types import SimpleNamespace
from typer.testing import CliRunner

from preco_teto.cli import app


runner = CliRunner()


def test_cli_render_acao_envia_nome_para_renderer(mocker):
    data = SimpleNamespace(
        ticker="VALE3",
        nome="Vale S.A.",
        is_br=True,
        cotacao=58.20,
        dividend_rate=3.60,
        dividendo_medio=3.60,
        lpa=5.50,
        vpa=32.00,
        free_cashflow=15_000_000_000,
        shares_outstanding=1_300_000_000,
        beta=0.95,
        earnings_growth=0.12,
        revenue_growth=0.08,
        income_net=None,
        year_prices={},
        previous_close=57.80,
        low_52=20.0,
        high_52=60.0,
    )
    idx = SimpleNamespace(cdi=14.65, ipca=5.85, melhor_indice=12.45)
    renderer = mocker.Mock()

    mocker.patch("preco_teto.cli.fetch_acao", return_value=data)
    mocker.patch("preco_teto.cli.fetch_indices_br", return_value=idx)
    mocker.patch("preco_teto.cli._get_renderer", return_value=renderer)

    result = runner.invoke(app, ["VALE3"])

    assert result.exit_code == 0
    assert renderer.render_acao.call_args.kwargs["nome"] == "Vale S.A."


def test_cli_render_fii_inclui_teto_bazin(mocker):
    data = SimpleNamespace(
        ticker="HGLG11",
        nome="CGHG Logística",
        cotacao=142.50,
        vpa=151.30,
        pvp=0.94,
        dividend_yield=17.01,
        dividendo_estimado=14.52,
        ultimo_dividendo=1.10,
        mes_ano_dividendo="Mar/2026",
        dy_mensal=0.78,
        low_52=140.0,
        high_52=160.0,
    )
    idx = SimpleNamespace(cdi=14.65, ipca=5.85, melhor_indice=12.45)
    renderer = mocker.Mock()

    mocker.patch("preco_teto.cli.fetch_fii", return_value=data)
    mocker.patch("preco_teto.cli.fetch_indices_br", return_value=idx)
    mocker.patch("preco_teto.cli._get_renderer", return_value=renderer)

    result = runner.invoke(app, ["HGLG11"])

    assert result.exit_code == 0
    tetos = renderer.render_fii.call_args.args[2]
    assert "teto_bazin" in tetos
    assert tetos["teto_bazin"] is not None
    assert renderer.render_fii.call_args.kwargs["nome"] == "CGHG Logística"


def test_cli_render_etf_inclui_teto_pl(mocker):
    data = SimpleNamespace(
        ticker="DIVO11",
        nome="IT NOW IDIV",
        cnpj="13.416.245/0001-46",
        cotacao=132.06,
        pl_cota=140.50,
        pl_total=1761051855.0,
        cotistas=12346,
        low_52=91.30,
        high_52=136.43,
    )
    idx = SimpleNamespace(cdi=14.65, ipca=5.85, melhor_indice=12.45)
    renderer = mocker.Mock()

    mocker.patch("preco_teto.cli.fetch_etf", return_value=data)
    mocker.patch("preco_teto.cli.fetch_indices_br", return_value=idx)
    mocker.patch("preco_teto.cli._get_renderer", return_value=renderer)

    result = runner.invoke(app, ["DIVO11", "--etf"])

    assert result.exit_code == 0
    tetos = renderer.render_etf.call_args.args[2]
    assert tetos["teto_pl"] == 132.07
    assert "teto_margem" in tetos
    assert renderer.render_etf.call_args.kwargs["nome"] == "IT NOW IDIV"


def test_cli_etf_sem_pl_mostra_somente_teto_margem(mocker):
    data = SimpleNamespace(
        ticker="DIVO11",
        nome="IT NOW IDIV",
        cnpj="13.416.245/0001-46",
        cotacao=132.06,
        pl_cota=None,
        pl_total=None,
        cotistas=None,
        low_52=91.30,
        high_52=136.43,
    )
    idx = SimpleNamespace(cdi=14.65, ipca=5.85, melhor_indice=12.45)
    renderer = mocker.Mock()

    mocker.patch("preco_teto.cli.fetch_etf", return_value=data)
    mocker.patch("preco_teto.cli.fetch_indices_br", return_value=idx)
    mocker.patch("preco_teto.cli._get_renderer", return_value=renderer)

    result = runner.invoke(app, ["DIVO11", "--etf"])

    assert result.exit_code == 0
    tetos = renderer.render_etf.call_args.args[2]
    assert tetos["teto_pl"] is None
    assert tetos["teto_margem"] is not None


def test_cli_flag_etf_forca_fluxo_etf(mocker):
    etf_data = SimpleNamespace(
        ticker="HGLG11",
        nome="ETF TESTE",
        cnpj="00.000.000/0001-00",
        cotacao=100.0,
        pl_cota=None,
        pl_total=None,
        cotistas=None,
        low_52=90.0,
        high_52=110.0,
    )
    idx = SimpleNamespace(cdi=14.65, ipca=5.85, melhor_indice=12.45)
    renderer = mocker.Mock()

    mocker.patch("preco_teto.cli.fetch_etf", return_value=etf_data)
    fii_mock = mocker.patch("preco_teto.cli.fetch_fii")
    acao_mock = mocker.patch("preco_teto.cli.fetch_acao")
    mocker.patch("preco_teto.cli.fetch_indices_br", return_value=idx)
    mocker.patch("preco_teto.cli._get_renderer", return_value=renderer)

    result = runner.invoke(app, ["HGLG11", "--etf"])

    assert result.exit_code == 0
    fii_mock.assert_not_called()
    acao_mock.assert_not_called()
    assert renderer.render_etf.called


def test_cli_flag_fii_forca_fluxo_fii(mocker):
    fii_data = SimpleNamespace(
        ticker="DIVO11",
        nome="FII TESTE",
        cotacao=100.0,
        vpa=105.0,
        pvp=0.95,
        dividend_yield=12.0,
        dividendo_estimado=12.5,
        ultimo_dividendo=None,
        mes_ano_dividendo=None,
        dy_mensal=None,
        low_52=90.0,
        high_52=110.0,
    )
    idx = SimpleNamespace(cdi=14.65, ipca=5.85, melhor_indice=12.45)
    renderer = mocker.Mock()

    etf_mock = mocker.patch("preco_teto.cli.fetch_etf")
    mocker.patch("preco_teto.cli.fetch_fii", return_value=fii_data)
    acao_mock = mocker.patch("preco_teto.cli.fetch_acao")
    mocker.patch("preco_teto.cli.fetch_indices_br", return_value=idx)
    mocker.patch("preco_teto.cli._get_renderer", return_value=renderer)

    result = runner.invoke(app, ["DIVO11", "--fii"])

    assert result.exit_code == 0
    etf_mock.assert_not_called()
    acao_mock.assert_not_called()
    assert renderer.render_fii.called
