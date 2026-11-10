from types import SimpleNamespace
from typer.testing import CliRunner

import numpy as np
import pandas as pd
import pytest

from preco_teto.cli import app


runner = CliRunner()


def test_cli_render_acao_envia_nome_para_renderer(mocker):
    data = SimpleNamespace(
        ticker="VALE3",
        nome="Vale S.A.",
        is_br=True,
        cotacao=58.20,
        dividend_rate=3.60,
        dividend_yield=6.19,
        dy_medio=24.74,
        dividendo_medio=3.60,
        lpa=5.50,
        vpa=32.00,
        free_cashflow=15_000_000_000,
        shares_outstanding=1_300_000_000,
        beta=0.95,
        earnings_growth=0.12,
        revenue_growth=0.08,
        roe=17.12,
        roe_medio_5a=16.0,
        roe_tendencia=-1.0,
        roe_r2=0.9,
        roe_ajustado=15.0,
        income_net=None,
        year_prices={},
        previous_close=57.80,
        low_52=20.0,
        high_52=60.0,
        ultimo_dividendo=0.30,
        mes_ano_dividendo="Dez/2024",
    )
    idx = SimpleNamespace(cdi=14.65, ipca=5.85, melhor_indice=12.45)
    renderer = mocker.Mock()

    mocker.patch("preco_teto.cli.fetch_acao", return_value=data)
    mocker.patch("preco_teto.cli.fetch_indices_br", return_value=idx)
    mocker.patch("preco_teto.cli._get_renderer", return_value=renderer)

    result = runner.invoke(app, ["VALE3"])

    assert result.exit_code == 0
    assert renderer.render_acao.call_args.kwargs["nome"] == "Vale S.A."
    assert renderer.render_acao.call_args.kwargs["dividend_yield"] == 6.19
    assert renderer.render_acao.call_args.kwargs["dy_medio"] == 24.74
    assert renderer.render_acao.call_args.kwargs["roe"] == 17.12
    tetos = renderer.render_acao.call_args.args[3]
    assert "teto_vpa_roe_taxa" in tetos
    assert "teto_vpa_roe_inflacao" in tetos
    assert renderer.render_acao.call_args.kwargs["ultimo_dividendo"] == 0.30
    assert renderer.render_acao.call_args.kwargs["mes_ano_dividendo"] == "Dez/2024"


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
        dividend_yield_12m=10.0,
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
    assert tetos["teto_por_dy_cdi_12m"] == pytest.approx(14.25 / 0.1465, rel=1e-2)
    assert renderer.render_fii.call_args.kwargs["nome"] == "CGHG Logística"
    assert renderer.render_fii.call_args.kwargs["dividend_yield_12m"] == 10.0


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
        holdings=[],
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
    assert renderer.render_etf.call_args.kwargs["p_fcf_agregado"] is None
    assert renderer.render_etf.call_args.kwargs["peg_agregado"] is None


def test_cli_etf_us_envia_p_fcf_e_peg_agregados(mocker):
    holding = SimpleNamespace(
        symbol="AAPL",
        weight=0.10,
        price=100.0,
        free_cashflow=1_000_000_000,
        shares_outstanding=100_000_000,
        peg_ratio=2.0,
    )
    data = SimpleNamespace(
        ticker="SPY",
        nome="SPDR S&P 500 ETF",
        cnpj="",
        cotacao=500.0,
        pl_cota=500.5,
        pl_total=1e12,
        cotistas=None,
        low_52=400.0,
        high_52=520.0,
        holdings=[holding],
    )
    idx = SimpleNamespace(cdi=14.65, ipca=5.85, melhor_indice=12.45)
    renderer = mocker.Mock()

    mocker.patch("preco_teto.cli.fetch_etf", return_value=data)
    mocker.patch("preco_teto.cli.fetch_indices_br", return_value=idx)
    mocker.patch("preco_teto.cli._get_renderer", return_value=renderer)

    result = runner.invoke(app, ["SPY", "--etf"])

    assert result.exit_code == 0
    kwargs = renderer.render_etf.call_args.kwargs
    # P/FCF = 100 / (1e9/1e8) = 10; PEG = 2.0; cobertura = 0.10
    assert kwargs["p_fcf_agregado"] == pytest.approx(10.0)
    assert kwargs["peg_agregado"] == pytest.approx(2.0)
    assert kwargs["cobertura_p_fcf"] == pytest.approx(0.10)
    assert kwargs["cobertura_peg"] == pytest.approx(0.10)


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


@pytest.mark.parametrize("output_flags", [[], ["--plain"], ["--json"]])
@pytest.mark.parametrize("type_flags", [[], ["--fii"]])
@pytest.mark.parametrize("cotacao", [None, 0.0])
def test_cli_fii_missing_quote_is_reported(mocker, output_flags, type_flags, cotacao):
    from preco_teto.services.fii import FiiData

    data = FiiData(
        ticker="HGLG11",
        nome="CGHG Logística",
        cotacao=cotacao,
        vpa=166.43,
        pvp=None,
        dividend_yield=8.56,
        dividendo_estimado=13.62,
    )
    mocker.patch("preco_teto.cli.fetch_fii", return_value=data)
    mocker.patch(
        "preco_teto.cli.fetch_indices_br",
        return_value=SimpleNamespace(cdi=14.65, ipca=5.85, melhor_indice=12.45),
    )
    acao_mock = mocker.patch("preco_teto.cli.fetch_acao")

    result = runner.invoke(app, ["HGLG11", *type_flags, *output_flags])

    assert result.exit_code == 0, result.exception
    assert "HGLG11 — cotação indisponível para este FII." in result.output
    acao_mock.assert_not_called()


@pytest.mark.parametrize("output_flags", [[], ["--plain"], ["--json"]])
def test_cli_fii_renders_with_real_renderer(mocker, output_flags):
    from preco_teto.services.fii import FiiData

    data = FiiData(
        ticker="HGLG11",
        nome="CGHG Logística",
        cotacao=156.60,
        vpa=166.43,
        pvp=0.94,
        dividend_yield=8.56,
        dividendo_estimado=13.62,
        ultimo_dividendo=1.17,
        mes_ano_dividendo="Set/2026",
        dy_mensal=0.79,
        dividend_yield_12m=8.56,
        low_52=145.11,
        high_52=157.58,
    )
    mocker.patch("preco_teto.cli.fetch_fii", return_value=data)
    mocker.patch(
        "preco_teto.cli.fetch_indices_br",
        return_value=SimpleNamespace(cdi=14.65, ipca=5.85, melhor_indice=12.45),
    )

    result = runner.invoke(app, ["HGLG11", "--fii", *output_flags])

    assert result.exit_code == 0, result.exception
    assert "HGLG11" in result.output
    if "--json" in output_flags:
        import json

        payload = json.loads(result.output)
        assert payload["cotacao"] == 156.60
        assert payload["tetos"]["vpa"] == 166.43
    else:
        assert "156.60" in result.output
        assert "166.43" in result.output


def test_cli_etfbr_chama_fetch_e_render(mocker):
    from preco_teto.services.etf_br import EtfBrData

    data = EtfBrData(
        ticker="DIVO11",
        nome="IT NOW IDIV FUNDO DE ÍNDICE",
        cotacao=128.24,
        pl_cota=128.16,
        premio_desconto_pct=0.06,
        low_52=98.88,
        high_52=142.00,
        pl_total_mm=2250.16,
        taxa_adm_pct=0.50,
        cotistas=48778,
        cnpj="13.416.245/0001-46",
        indice="IDIV",
    )
    idx = SimpleNamespace(cdi=14.65, ipca=5.85, melhor_indice=12.45)
    renderer = mocker.Mock()

    mocker.patch("preco_teto.cli.fetch_etf_br", return_value=data)
    mocker.patch("preco_teto.cli.fetch_indices_br", return_value=idx)
    mocker.patch("preco_teto.cli._get_renderer", return_value=renderer)

    result = runner.invoke(app, ["DIVO11", "--etfbr"])

    assert result.exit_code == 0
    assert renderer.render_etfbr.called
    tetos = renderer.render_etfbr.call_args.args[1]
    assert tetos["teto_nav"] == 128.16
    assert tetos["premio_desconto_pct"] == 0.06


def test_cli_etfbr_erro_mensagem_unica(mocker):
    from preco_teto.services.etf_br import EtfBrFetchError

    renderer = mocker.Mock()
    mocker.patch("preco_teto.cli.fetch_etf_br", side_effect=EtfBrFetchError("falha"))
    mocker.patch("preco_teto.cli._get_renderer", return_value=renderer)

    result = runner.invoke(app, ["DIVO11", "--etfbr"])

    assert result.exit_code == 0
    assert "DIVO11 — não foi possível obter dados do ETF (etfsbrasil.com.br)." in result.output
    renderer.render_etfbr.assert_not_called()


def test_cli_etfbr_exclusivo_com_etf():
    result = runner.invoke(app, ["DIVO11", "--etf", "--etfbr"])

    assert result.exit_code != 0
    # Rich pode quebrar a frase em duas linhas do box de erro
    assert "Use apenas uma flag" in result.output
    assert "--etf" in result.output and "--crypto" in result.output


def test_cli_usd_chama_render_usd(mocker):
    idx_datas = pd.bdate_range("2023-11-01", periods=700)
    dxy = pd.Series(np.linspace(95.0, 105.0, len(idx_datas)), index=idx_datas)
    ptax = pd.Series(np.exp(0.759 + 0.2 * np.log(dxy)), index=idx_datas)
    data = SimpleNamespace(
        spot=5.3744,
        data_spot=None,
        spot_comercial=5.3500,
        spot_ref=5.3500,
        ptax=ptax,
        dxy_hist=dxy,
        low_52=4.8973,
        high_52=5.5739,
        margem_52=0.71,
        dxy=102.04,
        dxy_pctl=55.0,
        cot=None,
        k_hat=0.00106,
        ibov=169186.0,
        ewz=33.14,
        desvio_z=1.02,
        uup=(29.04, 29.04),
        udn=(17.82, 17.81),
    )
    idx = SimpleNamespace(cdi=13.65, ipca=5.85, melhor_indice=11.6)
    fed = SimpleNamespace(fed_funds=3.98, cpi=3.1)
    renderer = mocker.Mock()

    mocker.patch("preco_teto.cli.fetch_usd", return_value=data)
    mocker.patch("preco_teto.cli.fetch_indices_br", return_value=idx)
    mocker.patch("preco_teto.cli.fetch_indices_us", return_value=fed)
    mocker.patch("preco_teto.cli._get_renderer", return_value=renderer)

    result = runner.invoke(app, ["USD", "--usd"])

    assert result.exit_code == 0
    tetos = renderer.render_usd.call_args.args[1]
    # carrego ancora no spot comercial (mais fresco), não na PTAX
    assert tetos["teto_carrego"] == pytest.approx(5.35 * 1.1365 / 1.0398, abs=0.02)
    assert tetos["teto_margem"] is not None
    assert tetos["teto_ewz"] is not None
    # DXY entra pela regressão log ancorada no DXY de hoje, com o R² junto
    assert tetos["teto_dxy"] == pytest.approx(5.39, abs=0.02)
    assert renderer.render_usd.call_args.kwargs["r2_dxy"] == pytest.approx(1.0, abs=1e-6)
    assert renderer.render_usd.call_args.kwargs["fed"] == 3.98
    assert tetos["teto_cot"] is None


def test_cli_usd_sem_spot_avisa_e_nao_renderiza(mocker):
    data = SimpleNamespace(spot=None, ptax=pd.Series(dtype=float), cot=None)
    renderer = mocker.Mock()

    mocker.patch("preco_teto.cli.fetch_usd", return_value=data)
    mocker.patch("preco_teto.cli._get_renderer", return_value=renderer)

    result = runner.invoke(app, ["USD", "--usd"])

    assert result.exit_code == 0
    assert "PTAX" in result.output
    renderer.render_usd.assert_not_called()


def test_cli_usd_exclusivo_com_etf():
    result = runner.invoke(app, ["USD", "--usd", "--etf"])

    assert result.exit_code != 0
    assert "--usd" in result.output


def test_cli_usd_funciona_sem_ticker(mocker):
    data = SimpleNamespace(
        spot=5.3744,
        data_spot=None,
        spot_comercial=5.3500,
        spot_ref=5.3500,
        ptax=pd.Series(dtype=float),
        dxy_hist=pd.Series(dtype=float),
        low_52=4.8973,
        high_52=5.5739,
        margem_52=0.71,
        dxy=102.04,
        dxy_pctl=55.0,
        cot=None,
        k_hat=0.00106,
        ibov=169186.0,
        ewz=33.14,
        desvio_z=1.02,
        uup=(29.04, 29.04),
        udn=(17.82, 17.81),
    )
    idx = SimpleNamespace(cdi=13.65, ipca=5.85, melhor_indice=11.6)
    fed = SimpleNamespace(fed_funds=3.98, cpi=3.1)
    renderer = mocker.Mock()

    mocker.patch("preco_teto.cli.fetch_usd", return_value=data)
    mocker.patch("preco_teto.cli.fetch_indices_br", return_value=idx)
    mocker.patch("preco_teto.cli.fetch_indices_us", return_value=fed)
    mocker.patch("preco_teto.cli._get_renderer", return_value=renderer)

    result = runner.invoke(app, ["--usd"])

    assert result.exit_code == 0
    renderer.render_usd.assert_called_once()


def test_cli_sem_ticker_e_sem_flag_pede_ticker():
    result = runner.invoke(app, [])

    assert result.exit_code != 0
    assert "TICKER" in result.output


def test_cli_sem_ticker_com_etf_pede_ticker():
    result = runner.invoke(app, ["--etf"])

    assert result.exit_code != 0
    assert "TICKER" in result.output


def test_cli_usd_cot_alimenta_teto_pelo_posicionamento_em_26_semanas(mocker):
    datas = pd.bdate_range("2023-11-01", periods=400)
    cot_datas = datas[::5]
    posicao = pd.Series(np.linspace(-20.0, 20.0, len(cot_datas)), index=cot_datas)
    ptax = pd.Series(np.linspace(6.2, 5.2, len(cot_datas)), index=cot_datas)
    spot = float(ptax.iloc[-1])
    data = SimpleNamespace(
        spot=spot,
        data_spot=None,
        spot_comercial=spot - 0.05,
        spot_ref=spot - 0.05,
        ptax=ptax,
        dxy_hist=pd.Series(dtype=float),
        low_52=float(ptax.tail(52).min()),
        high_52=float(ptax.tail(52).max()),
        margem_52=0.0,
        dxy=None,
        dxy_pctl=None,
        cot=SimpleNamespace(serie_am_net=posicao),
        k_hat=None,
        ibov=None,
        ewz=None,
        desvio_z=None,
        uup=(None, None),
        udn=(None, None),
    )
    idx = SimpleNamespace(cdi=13.65, ipca=5.85, melhor_indice=11.6)
    fed = SimpleNamespace(fed_funds=3.98, cpi=3.1)
    renderer = mocker.Mock()

    mocker.patch("preco_teto.cli.fetch_usd", return_value=data)
    mocker.patch("preco_teto.cli.fetch_indices_br", return_value=idx)
    mocker.patch("preco_teto.cli.fetch_indices_us", return_value=fed)
    mocker.patch("preco_teto.cli._get_renderer", return_value=renderer)

    result = runner.invoke(app, ["--usd"])

    assert result.exit_code == 0
    tetos = renderer.render_usd.call_args.args[1]
    # posição subindo com câmbio caindo => expectativa abaixo do spot comercial
    assert tetos["teto_cot"] is not None
    assert tetos["teto_cot"] < data.spot_ref
    assert renderer.render_usd.call_args.kwargs["r2_cot"] is not None


def _crypto_data(**overrides):
    idx = pd.bdate_range("2025-01-01", periods=40)
    price = pd.Series([100.0 + i for i in range(40)], index=idx)
    btc = pd.Series([90.0 + i for i in range(40)], index=idx)
    dxy = pd.Series([100.0 + 0.1 * i for i in range(40)], index=idx)
    gold = pd.Series([2000.0 + i for i in range(40)], index=idx)
    base = dict(
        id="ethereum",
        symbol="ETH",
        name="Ethereum",
        cotacao=float(price.iloc[-1]),
        low_52=float(price.min()),
        high_52=float(price.max()),
        margem_52=1.0,
        ath=200.0,
        ath_change_pct=-30.0,
        mcap=1e9,
        rank=2,
        circ_supply=1e8,
        max_supply=None,
        volume_24h=1e8,
        change_30d=-5.0,
        change_1y=10.0,
        price_hist=price,
        btc_hist=btc,
        btc_dominance_pct=50.0,
        source="Yahoo Finance",
        dxy=float(dxy.iloc[-1]),
        dxy_hist=dxy,
        gold=float(gold.iloc[-1]),
        gold_hist=gold,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def test_cli_crypto_chama_render_crypto(mocker):
    data = _crypto_data()
    renderer = mocker.Mock()
    mocker.patch("preco_teto.cli.fetch_crypto", return_value=data)
    mocker.patch("preco_teto.cli._get_renderer", return_value=renderer)

    result = runner.invoke(app, ["ETH", "--crypto"])

    assert result.exit_code == 0
    renderer.render_crypto.assert_called_once()
    tetos = renderer.render_crypto.call_args.args[1]
    assert "teto_margem" in tetos
    assert "teto_graham" not in tetos
    assert "teto_bazin" not in tetos
    assert tetos["teto_vs_btc"] is not None


def test_cli_crypto_btc_omite_teto_vs_btc(mocker):
    data = _crypto_data(
        id="bitcoin",
        symbol="BTC",
        name="Bitcoin",
        btc_hist=pd.Series(dtype=float),
    )
    renderer = mocker.Mock()
    mocker.patch("preco_teto.cli.fetch_crypto", return_value=data)
    mocker.patch("preco_teto.cli._get_renderer", return_value=renderer)

    result = runner.invoke(app, ["BTC", "--crypto"])

    assert result.exit_code == 0
    tetos = renderer.render_crypto.call_args.args[1]
    assert tetos["teto_vs_btc"] is None


def test_cli_crypto_alt_inclui_teto_vs_btc(mocker):
    idx = pd.bdate_range("2025-01-01", periods=40)
    btc = pd.Series([100.0 + i for i in range(40)], index=idx)
    price = btc * 0.05
    data = _crypto_data(price_hist=price, btc_hist=btc, cotacao=float(price.iloc[-1]))
    renderer = mocker.Mock()
    mocker.patch("preco_teto.cli.fetch_crypto", return_value=data)
    mocker.patch("preco_teto.cli._get_renderer", return_value=renderer)

    result = runner.invoke(app, ["ETH", "--crypto"])

    assert result.exit_code == 0
    tetos = renderer.render_crypto.call_args.args[1]
    assert tetos["teto_vs_btc"] is not None


def test_cli_crypto_exclusivo_com_etf():
    result = runner.invoke(app, ["BTC", "--crypto", "--etf"])
    assert result.exit_code != 0
    assert "--crypto" in result.output


def test_cli_crypto_exclusivo_com_usd():
    result = runner.invoke(app, ["BTC", "--crypto", "--usd"])
    assert result.exit_code != 0
    assert "--crypto" in result.output


def test_cli_crypto_sem_ticker_pede_ticker():
    result = runner.invoke(app, ["--crypto"])
    assert result.exit_code != 0
    assert "ticker" in result.output.lower()


def test_cli_crypto_fetch_error_echo(mocker):
    from preco_teto.services.crypto import CryptoFetchError

    renderer = mocker.Mock()
    mocker.patch(
        "preco_teto.cli.fetch_crypto",
        side_effect=CryptoFetchError("XYZ — ticker não disponível na API."),
    )
    mocker.patch("preco_teto.cli._get_renderer", return_value=renderer)

    result = runner.invoke(app, ["XYZ", "--crypto"])

    assert result.exit_code == 0
    assert "não disponível" in result.output
    renderer.render_crypto.assert_not_called()


def test_cli_crypto_nao_chama_fetch_acao(mocker):
    data = _crypto_data(id="bitcoin", symbol="BTC", name="Bitcoin", btc_hist=pd.Series(dtype=float))
    renderer = mocker.Mock()
    fetch_acao = mocker.patch("preco_teto.cli.fetch_acao")
    mocker.patch("preco_teto.cli.fetch_crypto", return_value=data)
    mocker.patch("preco_teto.cli._get_renderer", return_value=renderer)

    result = runner.invoke(app, ["BTC", "--crypto"])

    assert result.exit_code == 0
    fetch_acao.assert_not_called()


def test_cli_crypto_tetos_sem_graham_bazin_dy(mocker):
    data = _crypto_data(id="bitcoin", symbol="BTC", btc_hist=pd.Series(dtype=float))
    renderer = mocker.Mock()
    mocker.patch("preco_teto.cli.fetch_crypto", return_value=data)
    mocker.patch("preco_teto.cli._get_renderer", return_value=renderer)

    runner.invoke(app, ["BTC", "--crypto"])
    tetos = renderer.render_crypto.call_args.args[1]
    for key in ("teto_graham", "teto_bazin", "teto_por_dy", "teto_por_lucro", "teto_dcf"):
        assert key not in tetos
