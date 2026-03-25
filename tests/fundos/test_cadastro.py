import pytest
import pandas as pd
from unittest.mock import patch, MagicMock
from pathlib import Path
from preco_teto.fundos.services.cadastro import buscar_fundo, FundInfo

SAMPLE_CSV = (
    "CNPJ_FUNDO;DENOM_SOCIAL;SIT;CLASSE_ANBIMA;TAXA_ADM;TAXA_PERFM;VL_PATRIM_LIQ;GESTOR;NR_COTST\n"
    "26.199.519/0001-34;ITAÚ PRIVILÈGE RF DI;EM FUNCIONAMENTO NORMAL;"
    "Renda Fixa Referenciado DI;0,20;;87000000000;Itaú;480549\n"
    "03.618.256/0001-55;FUNDO CANCELADO;CANCELADA;"
    "Multimercado Macro;1,00;;0;Gestor X;0\n"
)


@pytest.fixture
def mock_csv(tmp_path, monkeypatch):
    csv_file = tmp_path / "cad_fi.csv"
    csv_file.write_bytes(SAMPLE_CSV.encode("latin-1"))
    monkeypatch.setattr(
        "preco_teto.fundos.services.cadastro._cache_path",
        lambda: csv_file,
    )
    return csv_file


def test_buscar_fundo_ativo(mock_csv):
    info = buscar_fundo("26.199.519/0001-34")
    assert info.nome == "ITAÚ PRIVILÈGE RF DI"
    assert info.classe_anbima == "Renda Fixa Referenciado DI"
    assert info.taxa_adm == pytest.approx(0.20)
    assert info.taxa_perf is None
    assert info.gestor == "Itaú"
    assert info.cotistas == 480549


def test_buscar_fundo_cancelado_raises(mock_csv):
    with pytest.raises(ValueError, match="EM FUNCIONAMENTO NORMAL"):
        buscar_fundo("03.618.256/0001-55")


def test_buscar_fundo_inexistente_raises(mock_csv):
    with pytest.raises(ValueError, match="não encontrado"):
        buscar_fundo("00.000.000/0001-00")
