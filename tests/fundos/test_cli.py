import pytest
from typer.testing import CliRunner
from preco_teto.fundos.cli import app, _resolve_benchmark

runner = CliRunner()


def test_cnpj_invalido_letras():
    result = runner.invoke(app, ["VALE3"])
    assert result.exit_code != 0
    assert "CNPJ inválido" in result.output


def test_cnpj_invalido_formato_errado():
    result = runner.invoke(app, ["12.345.678/0001"])
    assert result.exit_code != 0
    assert "CNPJ inválido" in result.output


def test_cnpj_valido_formato():
    # Should NOT fail with CNPJ format error (will fail later for other reasons)
    result = runner.invoke(app, ["26.199.519/0001-34"])
    assert "CNPJ inválido" not in result.output


from unittest.mock import patch
import pandas as pd


def _make_cotas_df(n=400):
    dates = pd.date_range("2023-01-01", periods=n, freq="B")
    values = [10.0 * (1.0008 ** i) for i in range(n)]  # steady growth
    return pd.DataFrame({"DT_COMPTC": dates, "VL_QUOTA": values})


def _make_cdi_df(n=400):
    dates = pd.date_range("2023-01-01", periods=n, freq="B")
    return pd.DataFrame({"data": dates, "taxa": [0.052] * n})


def _make_benchmark_df(n=400):
    dates = pd.date_range("2023-01-01", periods=n, freq="B")
    values = [100.0 * (1.001 ** i) for i in range(n)]
    return pd.DataFrame({"data": dates, "valor": values})


def test_cli_full_flow_mocked():
    from preco_teto.fundos.services.cadastro import FundInfo
    info = FundInfo(
        cnpj="26.199.519/0001-34",
        nome="ITAÚ PRIVILÈGE RF DI",
        classe_anbima="Renda Fixa Referenciado DI",
        taxa_adm=0.20,
        taxa_perf=None,
        gestor="Itaú",
        pl=87_000_000_000.0,
        cotistas=480549,
    )
    with (
        patch("preco_teto.fundos.cli.buscar_fundo", return_value=info),
        patch("preco_teto.fundos.cli.extrair_cotas", return_value=_make_cotas_df()),
        patch("preco_teto.fundos.cli.fetch_benchmark_historico", return_value=_make_cdi_df()),
    ):
        result = runner.invoke(app, ["26.199.519/0001-34"])
    assert result.exit_code == 0
    assert "ITAÚ PRIVILÈGE RF DI" in result.output
    assert "Análise do Fundo:" in result.output
    assert "Se tivesse investido R$ 100 há 12 meses:" in result.output
    assert "Diferença vs CDB líquido:" in result.output
    assert "CDI Líq." in result.output
    assert "% CDI Líq." in result.output


def test_cli_usa_benchmark_da_flag_sem_prompt():
    from preco_teto.fundos.services.cadastro import FundInfo
    info = FundInfo(
        cnpj="37.306.536/0001-40",
        nome="ITAÚ S&P500",
        classe_anbima="Ações Livre",
        taxa_adm=None,
        taxa_perf=None,
        gestor="Itaú",
        pl=621_000_000.0,
        cotistas=None,
    )
    with (
        patch("preco_teto.fundos.cli.buscar_fundo", return_value=info),
        patch("preco_teto.fundos.cli.extrair_cotas", return_value=_make_cotas_df()),
        patch("preco_teto.fundos.cli.fetch_benchmark_historico", return_value=_make_benchmark_df()),
        patch("preco_teto.fundos.cli.sys.stdin.isatty", return_value=True),
    ):
        result = runner.invoke(app, ["37.306.536/0001-40", "--benchmark", "IVV"])
    assert result.exit_code == 0
    assert "Benchmark?" not in result.output
    assert "Rentabilidade vs IVV" in result.output
    assert "CDI Líq." not in result.output
    assert "Diferença vs IVV:" in result.output


def test_cli_mostra_performance_relativa_quando_benchmark_do_periodo_e_negativo():
    from preco_teto.fundos.services.cadastro import FundInfo
    info = FundInfo(
        cnpj="37.306.536/0001-40",
        nome="ITAÚ S&P500",
        classe_anbima="Ações Livre",
        taxa_adm=None,
        taxa_perf=None,
        gestor="Itaú",
        pl=621_000_000.0,
        cotistas=None,
    )
    cotas = _make_cotas_df()
    cotas.loc[cotas.index[-1], "VL_QUOTA"] = cotas.iloc[-22]["VL_QUOTA"] * 0.9705
    benchmark = _make_benchmark_df()
    benchmark.loc[benchmark.index[-1], "valor"] = benchmark.iloc[-22]["valor"] * 0.9730
    with (
        patch("preco_teto.fundos.cli.buscar_fundo", return_value=info),
        patch("preco_teto.fundos.cli.extrair_cotas", return_value=cotas),
        patch("preco_teto.fundos.cli.fetch_benchmark_historico", return_value=benchmark),
        patch("preco_teto.fundos.cli.sys.stdin.isatty", return_value=True),
    ):
        result = runner.invoke(app, ["37.306.536/0001-40", "--benchmark", "DIVO11"])
    assert result.exit_code == 0
    assert "│ 1m" in result.output
    assert "N/A" in result.output
    assert "Pior" in result.output


def test_resolve_benchmark_pergunta_quando_flag_nao_vem():
    with (
        patch("preco_teto.fundos.cli.sys.stdin.isatty", return_value=True),
        patch("preco_teto.fundos.cli.typer.prompt", return_value="IVV") as mock_prompt,
    ):
        benchmark, fallback = _resolve_benchmark(None)
    mock_prompt.assert_called_once()
    assert benchmark == "IVV"
    assert fallback is False


def test_cli_fundo_cancelado_mostra_erro():
    with patch(
        "preco_teto.fundos.cli.buscar_fundo",
        side_effect=ValueError("não está EM FUNCIONAMENTO NORMAL"),
    ):
        result = runner.invoke(app, ["03.618.256/0001-55"])
    assert result.exit_code != 0
    assert "EM FUNCIONAMENTO NORMAL" in result.output
