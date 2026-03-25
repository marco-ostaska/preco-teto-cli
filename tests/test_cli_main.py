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
