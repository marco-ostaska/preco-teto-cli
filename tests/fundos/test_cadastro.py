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


@pytest.fixture
def mock_extrato_vazio(monkeypatch):
    monkeypatch.setattr(
        "preco_teto.fundos.services.cadastro._load_extrato",
        lambda: pd.DataFrame(columns=["CNPJ_FUNDO_CLASSE", "DT_COMPTC"]),
    )


def test_buscar_fundo_ativo(mock_csv, mock_extrato_vazio):
    empty_df = pd.DataFrame(columns=["CNPJ_Classe", "Situacao", "ID_Registro_Fundo"])
    empty_fundo_df = pd.DataFrame(columns=["ID_Registro_Fundo"])
    with patch(
        "preco_teto.fundos.services.cadastro._load_registro_frames",
        return_value=(empty_df, empty_fundo_df),
    ):
        info = buscar_fundo("26.199.519/0001-34")

    assert info.nome == "ITAÚ PRIVILÈGE RF DI"
    assert info.classe_anbima == "Renda Fixa Referenciado DI"
    assert info.taxa_adm == pytest.approx(0.20)
    assert info.taxa_perf is None
    assert info.gestor == "Itaú"
    assert info.cotistas == 480549


def test_buscar_fundo_cancelado_raises(mock_csv, mock_extrato_vazio):
    empty_df = pd.DataFrame(columns=["CNPJ_Classe", "Situacao", "ID_Registro_Fundo"])
    empty_fundo_df = pd.DataFrame(columns=["ID_Registro_Fundo"])
    with patch(
        "preco_teto.fundos.services.cadastro._load_registro_frames",
        return_value=(empty_df, empty_fundo_df),
    ):
        with pytest.raises(ValueError, match="EM FUNCIONAMENTO NORMAL"):
            buscar_fundo("03.618.256/0001-55")


def test_buscar_fundo_prefere_registro_ativo_no_cadastro_legado(tmp_path, monkeypatch, mock_extrato_vazio):
    csv_file = tmp_path / "cad_fi.csv"
    csv_file.write_bytes(
        (
            "CNPJ_FUNDO;DENOM_SOCIAL;SIT;CLASSE_ANBIMA;TAXA_ADM;TAXA_PERFM;VL_PATRIM_LIQ;GESTOR;NR_COTST\n"
            "03.618.256/0001-55;FUNDO ANTIGO;CANCELADA;Multimercado Macro;1,00;;0;Gestor X;0\n"
            "03.618.256/0001-55;FUNDO NOVO;EM FUNCIONAMENTO NORMAL;Multimercado Livre;0,50;;123;Gestor Y;42\n"
        ).encode("latin-1")
    )
    monkeypatch.setattr(
        "preco_teto.fundos.services.cadastro._cache_path",
        lambda: csv_file,
    )

    info = buscar_fundo("03.618.256/0001-55")

    assert info.nome == "FUNDO NOVO"
    assert info.classe_anbima == "Multimercado Livre"
    assert info.taxa_adm == pytest.approx(0.50)
    assert info.gestor == "Gestor Y"
    assert info.cotistas == 42


def test_buscar_fundo_inexistente_raises(mock_csv, mock_extrato_vazio):
    with pytest.raises(ValueError, match="não encontrado"):
        buscar_fundo("00.000.000/0001-00")


def test_buscar_fundo_fallback_para_registro_classe_quando_cad_fi_nao_tem_cnpj(tmp_path, monkeypatch, mock_extrato_vazio):
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


def test_buscar_fundo_prefere_registro_ativo_no_registro_classe(tmp_path, monkeypatch, mock_extrato_vazio):
    cad_file = tmp_path / "cad_fi.csv"
    cad_file.write_bytes(
        (
            "CNPJ_FUNDO;DENOM_SOCIAL;SIT;CLASSE_ANBIMA;TAXA_ADM;TAXA_PERFM;VL_PATRIM_LIQ;GESTOR;NR_COTST\n"
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
        "1;10;03618256000155;111;2024-01-01;2024-01-01;2024-01-01;Classe;FUNDO ANTIGO;Cancelada;2024-01-01;"
        "Multimercado;CDI;S;Classe Antiga;N/A;;N;N;Aberto;N;Publico Geral;0;2024-01-01;;;;;;\n"
        "2;20;03618256000155;222;2025-01-01;2025-01-01;2025-01-01;Classe;FUNDO NOVO;Em Funcionamento Normal;2025-01-01;"
        "Multimercado;CDI;S;Classe Nova;N/A;;N;N;Aberto;N;Publico Geral;456.78;2025-01-01;;;;;;\n"
    )
    fundo_csv = (
        "ID_Registro_Fundo;CNPJ_Fundo;Codigo_CVM;Data_Registro;Data_Constituicao;Tipo_Fundo;Denominacao_Social;"
        "Data_Cancelamento;Situacao;Data_Inicio_Situacao;Data_Adaptacao_RCVM175;Data_Inicio_Exercicio_Social;"
        "Data_Fim_Exercicio_Social;Patrimonio_Liquido;Data_Patrimonio_Liquido;Diretor;CNPJ_Administrador;"
        "Administrador;Tipo_Pessoa_Gestor;CPF_CNPJ_Gestor;Gestor\n"
        "1;00000000000000;111;2024-01-01;2024-01-01;FIF;FUNDO ANTIGO;2024-01-01;Cancelada;2024-01-01;;;;0;2024-01-01;;1;ADM X;PJ;1;GESTOR X\n"
        "2;99999999999999;222;2025-01-01;2025-01-01;FIF;FUNDO NOVO;;Em Funcionamento Normal;2025-01-01;;;;456.78;2025-01-01;;2;ADM Y;PJ;2;GESTOR Y\n"
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
        info = buscar_fundo("03.618.256/0001-55")

    assert info.nome == "FUNDO NOVO"
    assert info.classe_anbima == "Classe Nova"
    assert info.gestor == "GESTOR Y"
    assert info.pl == pytest.approx(456.78)


def test_buscar_fundo_faz_fallback_para_registro_ativo_quando_legado_esta_cancelado(tmp_path, monkeypatch, mock_extrato_vazio):
    cad_file = tmp_path / "cad_fi.csv"
    cad_file.write_bytes(
        (
            "CNPJ_FUNDO;DENOM_SOCIAL;SIT;CLASSE_ANBIMA;TAXA_ADM;TAXA_PERFM;VL_PATRIM_LIQ;GESTOR;NR_COTST\n"
            "03.618.256/0001-55;FUNDO ANTIGO;CANCELADA;Multimercado Macro;1,00;;0;Gestor X;0\n"
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
        "2;20;03618256000155;222;2025-01-01;2025-01-01;2025-01-01;Classe;FUNDO NOVO;Em Funcionamento Normal;2025-01-01;"
        "Multimercado;CDI;S;Classe Nova;N/A;;N;N;Aberto;N;Publico Geral;456.78;2025-01-01;;;;;;\n"
    )
    fundo_csv = (
        "ID_Registro_Fundo;CNPJ_Fundo;Codigo_CVM;Data_Registro;Data_Constituicao;Tipo_Fundo;Denominacao_Social;"
        "Data_Cancelamento;Situacao;Data_Inicio_Situacao;Data_Adaptacao_RCVM175;Data_Inicio_Exercicio_Social;"
        "Data_Fim_Exercicio_Social;Patrimonio_Liquido;Data_Patrimonio_Liquido;Diretor;CNPJ_Administrador;"
        "Administrador;Tipo_Pessoa_Gestor;CPF_CNPJ_Gestor;Gestor\n"
        "2;99999999999999;222;2025-01-01;2025-01-01;FIF;FUNDO NOVO;;Em Funcionamento Normal;2025-01-01;;;;456.78;2025-01-01;;2;ADM Y;PJ;2;GESTOR Y\n"
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
        info = buscar_fundo("03.618.256/0001-55")

    assert info.nome == "FUNDO NOVO"
    assert info.classe_anbima == "Classe Nova"
    assert info.gestor == "GESTOR Y"


def test_buscar_fundo_prefere_extrato_antes_do_registro_e_legado():
    extrato_info = FundInfo(
        cnpj="03.618.256/0001-55",
        nome="FUNDO VIA EXTRATO",
        classe_anbima="Multimercado Livre",
        taxa_adm=0.04,
        taxa_perf=20.0,
        gestor="Gestor Extrato",
        pl=2000.0,
        cotistas=None,
    )
    registro_info = FundInfo(
        cnpj="03.618.256/0001-55",
        nome="FUNDO VIA REGISTRO",
        classe_anbima="Classe Registro",
        taxa_adm=None,
        taxa_perf=None,
        gestor="Gestor Registro",
        pl=1000.0,
        cotistas=None,
    )
    legado_info = FundInfo(
        cnpj="03.618.256/0001-55",
        nome="FUNDO VIA LEGADO",
        classe_anbima="Classe Legado",
        taxa_adm=0.5,
        taxa_perf=None,
        gestor="Gestor Legado",
        pl=500.0,
        cotistas=10,
    )

    with patch(
        "preco_teto.fundos.services.cadastro._buscar_no_extrato",
        return_value=extrato_info,
    ) as extrato_mock, patch(
        "preco_teto.fundos.services.cadastro._buscar_no_registro_classe",
        return_value=registro_info,
    ) as registro_mock, patch(
        "preco_teto.fundos.services.cadastro._buscar_no_cadastro_legado",
        return_value=legado_info,
    ) as legado_mock:
        info = buscar_fundo("03.618.256/0001-55")

    assert info == extrato_info
    extrato_mock.assert_called_once_with("03.618.256/0001-55")
    registro_mock.assert_not_called()
    legado_mock.assert_not_called()


def test_buscar_fundo_faz_fallback_para_registro_quando_extrato_nao_tem_cnpj():
    registro_info = FundInfo(
        cnpj="03.618.256/0001-55",
        nome="FUNDO VIA REGISTRO",
        classe_anbima="Classe Registro",
        taxa_adm=None,
        taxa_perf=None,
        gestor="Gestor Registro",
        pl=1000.0,
        cotistas=None,
    )

    with patch(
        "preco_teto.fundos.services.cadastro._buscar_no_extrato",
        return_value=None,
    ) as extrato_mock, patch(
        "preco_teto.fundos.services.cadastro._buscar_no_registro_classe",
        return_value=registro_info,
    ) as registro_mock, patch(
        "preco_teto.fundos.services.cadastro._buscar_no_cadastro_legado",
        side_effect=AssertionError("cadastro legado nao deveria ser consultado"),
    ):
        info = buscar_fundo("03.618.256/0001-55")

    assert info == registro_info
    extrato_mock.assert_called_once_with("03.618.256/0001-55")
    registro_mock.assert_called_once_with("03.618.256/0001-55")


def test_buscar_fundo_faz_fallback_para_legado_quando_extrato_e_registro_nao_tem_cnpj():
    legado_info = FundInfo(
        cnpj="03.618.256/0001-55",
        nome="FUNDO VIA LEGADO",
        classe_anbima="Classe Legado",
        taxa_adm=0.5,
        taxa_perf=None,
        gestor="Gestor Legado",
        pl=500.0,
        cotistas=10,
    )

    with patch(
        "preco_teto.fundos.services.cadastro._buscar_no_extrato",
        return_value=None,
    ) as extrato_mock, patch(
        "preco_teto.fundos.services.cadastro._buscar_no_registro_classe",
        return_value=None,
    ) as registro_mock, patch(
        "preco_teto.fundos.services.cadastro._buscar_no_cadastro_legado",
        return_value=legado_info,
    ) as legado_mock:
        info = buscar_fundo("03.618.256/0001-55")

    assert info == legado_info
    extrato_mock.assert_called_once_with("03.618.256/0001-55")
    registro_mock.assert_called_once_with("03.618.256/0001-55")
    legado_mock.assert_called_once_with("03.618.256/0001-55")


def test_buscar_no_extrato_prefere_linha_mais_recente(tmp_path, monkeypatch):
    extrato_file = tmp_path / "extrato_fi.csv"
    extrato_file.write_bytes(
        (
            "CNPJ_FUNDO_CLASSE;DENOM_SOCIAL;DT_COMPTC;CLASSE_ANBIMA;TAXA_ADM;TAXA_PERFM;VL_PATRIM_LIQ\n"
            "03.618.256/0001-55;FUNDO ANTIGO;2025-01-01;Multimercado Macro;0.90;20.00;100\n"
            "03.618.256/0001-55;FUNDO NOVO;2025-05-07;Multimercado Livre;0.04;20.00;200\n"
        ).encode("latin-1")
    )
    monkeypatch.setattr(
        "preco_teto.fundos.services.cadastro._extrato_cache_path",
        lambda: extrato_file,
    )

    info = buscar_fundo("03.618.256/0001-55")

    assert info.nome == "FUNDO NOVO"
    assert info.classe_anbima == "Multimercado Livre"
    assert info.taxa_adm == pytest.approx(0.04)
    assert info.taxa_perf == pytest.approx(20.0)
    assert info.pl == pytest.approx(200.0)
