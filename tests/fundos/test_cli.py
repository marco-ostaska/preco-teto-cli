import pytest
from typer.testing import CliRunner
from preco_teto.fundos.cli import app

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


from unittest.mock import patch, MagicMock
import pandas as pd
from datetime import date


def _make_cotas_df(n=400):
    dates = pd.date_range("2023-01-01", periods=n, freq="B")
    values = [10.0 * (1.0008 ** i) for i in range(n)]  # steady growth
    return pd.DataFrame({"DT_COMPTC": dates, "VL_QUOTA": values})


def _make_cdi_df(n=400):
    dates = pd.date_range("2023-01-01", periods=n, freq="B")
    return pd.DataFrame({"data": dates, "taxa": [0.052] * n})


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
        patch("preco_teto.fundos.cli.fetch_cdi_historico", return_value=_make_cdi_df()),
    ):
        result = runner.invoke(app, ["26.199.519/0001-34"])
    assert result.exit_code == 0
    assert "ITAÚ PRIVILÈGE RF DI" in result.output


def test_cli_fundo_cancelado_mostra_erro():
    with patch(
        "preco_teto.fundos.cli.buscar_fundo",
        side_effect=ValueError("não está EM FUNCIONAMENTO NORMAL"),
    ):
        result = runner.invoke(app, ["03.618.256/0001-55"])
    assert result.exit_code != 0
    assert "EM FUNCIONAMENTO NORMAL" in result.output
