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
