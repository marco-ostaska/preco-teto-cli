from datetime import date, datetime, timezone

from preco_teto.output import fundamentos as fund_out
from preco_teto.services.acao import _fundamentos


def _ts(ano, mes, dia, hora=0):
    return datetime(ano, mes, dia, hora, tzinfo=timezone.utc).timestamp()


def test_fundamentos_marca_defasado_quando_balanco_posterior_nao_entrou():
    info = {
        "mostRecentQuarter": _ts(2026, 6, 30),
        "earningsTimestamp": _ts(2026, 11, 11, 20),
    }

    resultado = _fundamentos(info, hoje=date(2026, 11, 12))

    assert resultado["ref"] == date(2026, 6, 30)
    assert resultado["balanco"] == date(2026, 11, 11)
    assert resultado["defasado"] is True


def test_fundamentos_atualizado_apos_balanco_do_trimestre_nao_marca_defasado():
    info = {
        "mostRecentQuarter": _ts(2026, 9, 30),
        "earningsTimestamp": _ts(2026, 11, 11, 20),
    }

    resultado = _fundamentos(info, hoje=date(2026, 11, 12))

    assert resultado["balanco"] == date(2026, 11, 11)
    assert resultado["defasado"] is False


def test_fundamentos_sem_balanco_passado_nao_marca_defasado():
    info = {
        "mostRecentQuarter": _ts(2026, 6, 30),
        "earningsTimestamp": _ts(2027, 2, 10, 20),
    }

    resultado = _fundamentos(info, hoje=date(2026, 11, 12))

    assert resultado["balanco"] is None
    assert resultado["defasado"] is False


def test_fundamentos_sem_referencia_retorna_none():
    assert _fundamentos({}, hoje=date(2026, 11, 12)) is None
    assert _fundamentos({"mostRecentQuarter": "x"}, hoje=date(2026, 11, 12)) is None


def test_linha_dados_formatada_quando_em_dia():
    linha = fund_out.linha(
        {"ref": date(2026, 9, 30), "balanco": date(2026, 11, 11), "defasado": False}
    )

    assert linha == "Dados: 3T2026 (30/09/2026)"


def test_linha_dados_com_aviso_quando_defasado():
    linha = fund_out.linha(
        {"ref": date(2026, 6, 30), "balanco": date(2026, 11, 11), "defasado": True}
    )

    assert linha.startswith("Dados: 2T2026 (30/06/2026)")
    assert "balanço de 11/11/2026" in linha
    assert "⚠" in linha


def test_linha_dados_none_sem_fundamentos():
    assert fund_out.linha(None) is None
