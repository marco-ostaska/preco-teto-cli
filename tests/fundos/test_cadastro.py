import pytest
import pandas as pd
from unittest.mock import patch, MagicMock
from pathlib import Path
from preco_teto.fundos.services.cadastro import buscar_fundo, FundInfo
import io
import zipfile

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


def test_buscar_fundo_fallback_para_registro_classe_quando_cad_fi_nao_tem_cnpj(tmp_path, monkeypatch):
    cad_file = tmp_path / "cad_fi.csv"
    cad_file.write_bytes(
        (
            "CNPJ_FUNDO;DENOM_SOCIAL;SIT;CLASSE_ANBIMA;TAXA_ADM;TAXA_PERFM;VL_PATRIM_LIQ;GESTOR;NR_COTST\n"
            "00.000.000/0001-00;OUTRO FUNDO;EM FUNCIONAMENTO NORMAL;Renda Fixa;0,20;;10;Gestor X;1\n"
        ).encode("latin-1")
    )
    monkeypatch.setattr("preco_teto.fundos.services.cadastro._cache_path", lambda: cad_file)
    monkeypatch.setattr("preco_teto.fundos.services.cadastro.Path.home", lambda: tmp_path)

    classe_csv = (
        "ID_Registro_Fundo;ID_Registro_Classe;CNPJ_Classe;Codigo_CVM;Data_Registro;Data_Constituicao;Data_Inicio;"
        "Tipo_Classe;Denominacao_Social;Situacao;Data_Inicio_Situacao;Classificacao;Indicador_Desempenho;"
        "Classe_Cotas;Classificacao_Anbima;Tributacao_Longo_Prazo;Entidade_Investimento;"
        "Permitido_Aplicacao_CemPorCento_Exterior;Classe_ESG;Forma_Condominio;Exclusivo;Publico_Alvo;"
        "Patrimonio_Liquido;Data_Patrimonio_Liquido;CNPJ_Auditor;Auditor;CNPJ_Custodiante;Custodiante;"
        "CNPJ_Controlador;Controlador\n"
        "6941;53283;26199519000134;48771;2024-07-08;2016-11-22;2024-07-08;Classes de Cotas de Fundos FIF;"
        "ITAU PRIVILEGE RENDA FIXA REFERENCIADO DI;Em Funcionamento Normal;2024-07-08;Renda Fixa;"
        "DI de um dia;S;Renda Fixa Referenciado DI;N/A;;N;N;Aberto;N;Publico Geral;87377682640.97;"
        "2026-03-20;61366936000125;ERNST;60701190000104;ITAU UNIBANCO S.A.;60701190000104;ITAU UNIBANCO S.A.\n"
    )
    fundo_csv = (
        "ID_Registro_Fundo;CNPJ_Fundo;Codigo_CVM;Data_Registro;Data_Constituicao;Tipo_Fundo;Denominacao_Social;"
        "Data_Cancelamento;Situacao;Data_Inicio_Situacao;Data_Adaptacao_RCVM175;Data_Inicio_Exercicio_Social;"
        "Data_Fim_Exercicio_Social;Patrimonio_Liquido;Data_Patrimonio_Liquido;Diretor;CNPJ_Administrador;"
        "Administrador;Tipo_Pessoa_Gestor;CPF_CNPJ_Gestor;Gestor\n"
        "6941;26199519000134;48771;2024-07-08;2016-11-22;FIF;ITAU PRIVILEGE; ;Em Funcionamento Normal;"
        "2024-07-08;;;;87377682640.97;2026-03-20;;60701190000104;ITAU UNIBANCO S.A.;PJ;60701190000104;ITAU ASSET\n"
    )

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("registro_classe.csv", classe_csv.encode("latin-1"))
        zf.writestr("registro_fundo.csv", fundo_csv.encode("latin-1"))
    zip_bytes = buf.getvalue()

    def fake_get(url, timeout=30):
        response = MagicMock()
        if url.endswith("cad_fi.csv"):
            response.content = cad_file.read_bytes()
        elif url.endswith("registro_fundo_classe.zip"):
            response.content = zip_bytes
        else:
            raise AssertionError(url)
        response.raise_for_status = MagicMock()
        return response

    with patch("preco_teto.fundos.services.cadastro.requests.get", side_effect=fake_get):
        info = buscar_fundo("26.199.519/0001-34")

    assert info.nome == "ITAU PRIVILEGE RENDA FIXA REFERENCIADO DI"
    assert info.classe_anbima == "Renda Fixa Referenciado DI"
    assert info.gestor == "ITAU ASSET"
    assert info.pl == pytest.approx(87377682640.97)
